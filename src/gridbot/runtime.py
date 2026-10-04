from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .broker import BybitBroker
from .config import GridConfig, RegimeConfig, RiskConfig
from .data import BybitData
from .indicators import RuleRegimeFilter, add_indicators
from .strategy import GridOrder

log = logging.getLogger("gridbot")


@dataclass
class BotState:
    peak_equity: float = 0.0
    day: str = ""
    day_start_equity: float = 0.0
    halted_reason: str = ""
    anchors: dict[str, float] = field(default_factory=dict)
    last_candles: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "BotState":
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))
        os.replace(temporary, path)


class LiveBot:
    def __init__(self, execute: bool = False, confirm_real: bool = False):
        self.environment = os.getenv("BYBIT_ENV", "paper").lower()
        self.symbols = [s.strip().replace("/", "").upper() for s in os.getenv(
            "GRIDBOT_SYMBOLS", "BTCUSDT,ADAUSDT,DOGEUSDT"
        ).split(",") if s.strip()]
        self.interval = int(os.getenv("GRIDBOT_INTERVAL", "15"))
        self.execute = execute and self.environment != "paper"
        if self.environment == "mainnet" and self.execute and not confirm_real:
            raise RuntimeError("Mainnet execution also requires --confirm-real")
        self.data = BybitData(testnet=self.environment == "testnet")
        self.broker = None if self.environment == "paper" else BybitBroker(self.environment)
        self.paper_equity = float(os.getenv("PAPER_EQUITY", "10000"))
        self.grid = GridConfig(
            levels=int(os.getenv("GRIDBOT_LEVELS", "5")),
            spacing_atr=float(os.getenv("GRIDBOT_SPACING_ATR", "0.5")),
            max_position_fraction=float(os.getenv("GRIDBOT_MAX_POSITION_FRACTION", "0.45")),
        )
        self.risk = RiskConfig(
            max_drawdown=float(os.getenv("GRIDBOT_MAX_DRAWDOWN", "0.10")),
            max_daily_loss=float(os.getenv("GRIDBOT_MAX_DAILY_LOSS", "0.03")),
        )
        self.regime = RuleRegimeFilter(RegimeConfig(
            max_adx=float(os.getenv("GRIDBOT_MAX_ADX", "25")),
            max_atr_fraction=float(os.getenv("GRIDBOT_MAX_ATR_FRACTION", "0.025")),
        ))
        self.flatten_on_stop = os.getenv("GRIDBOT_FLATTEN_ON_STOP", "false").lower() == "true"
        self.state_path = Path(os.getenv("GRIDBOT_STATE_FILE", f"state/{self.environment}.json"))
        self.state = BotState.load(self.state_path)

    def equity(self) -> float:
        return self.paper_equity if self.broker is None else self.broker.account_equity()

    def _risk_ok(self, equity: float) -> bool:
        today = datetime.now(UTC).date().isoformat()
        if not self.state.day:
            self.state.day, self.state.day_start_equity = today, equity
        elif self.state.day != today:
            self.state.day, self.state.day_start_equity = today, equity
        self.state.peak_equity = max(self.state.peak_equity, equity)
        drawdown = 1 - equity / self.state.peak_equity if self.state.peak_equity else 0
        daily = 1 - equity / self.state.day_start_equity if self.state.day_start_equity else 0
        if drawdown >= self.risk.max_drawdown:
            self.state.halted_reason = f"max drawdown {drawdown:.2%}"
        elif daily >= self.risk.max_daily_loss:
            self.state.halted_reason = f"daily loss {daily:.2%}"
        return not self.state.halted_reason

    def _orders(self, anchor: float, step: float, qty: float, position: float) -> list[GridOrder]:
        if qty <= 0 and position == 0:
            return []
        exit_qty = abs(position) / self.grid.levels if position else 0.0
        orders = []
        for level in range(1, self.grid.levels + 1):
            buy_reduce, sell_reduce = position < 0, position > 0
            buy_qty = exit_qty if buy_reduce else qty
            sell_qty = exit_qty if sell_reduce else qty
            if buy_qty > 0:
                orders.append(GridOrder("Buy", anchor - step * level, buy_qty, buy_reduce))
            if sell_qty > 0:
                orders.append(GridOrder("Sell", anchor + step * level, sell_qty, sell_reduce))
        return orders

    def stop(self, flatten: bool = False) -> None:
        if not self.broker:
            self.state.save(self.state_path)
            return
        for symbol in self.symbols:
            cancelled = self.broker.cancel_grid(symbol) if self.execute else 0
            if flatten and self.execute:
                self.broker.flatten(symbol)
            log.info("%s stopped: cancelled=%s flatten=%s", symbol, cancelled, flatten and self.execute)
        self.state.save(self.state_path)

    def cycle(self) -> None:
        equity = self.equity()
        if not self._risk_ok(equity):
            log.error("risk halt: %s", self.state.halted_reason)
            if self.execute:
                for symbol in self.symbols:
                    self.broker.cancel_grid(symbol)
                    if self.flatten_on_stop:
                        self.broker.flatten(symbol)
            self.state.save(self.state_path)
            return

        per_symbol_budget = equity * self.grid.max_position_fraction / len(self.symbols)
        for symbol in self.symbols:
            frame = self.data.klines(symbol, str(self.interval), limit=250)
            now = datetime.now(UTC)
            if len(frame) and frame.index[-1].to_pydatetime() + timedelta(minutes=self.interval) > now:
                frame = frame.iloc[:-1]
            if len(frame) < 50:
                log.warning("%s: not enough candles", symbol)
                continue
            candle_id = frame.index[-1].isoformat()
            if self.state.last_candles.get(symbol) == candle_id:
                continue
            indicators = add_indicators(frame)
            row = indicators.iloc[-1]
            ranging = bool(self.regime.predict(frame).iloc[-1])
            price, atr = float(row.close), float(row.atr)
            position = 0.0 if not self.broker else self.broker.position_qty(symbol)
            self.state.last_candles[symbol] = candle_id

            if not ranging or atr <= 0:
                if self.execute:
                    self.broker.cancel_grid(symbol)
                log.info("%s trend/off adx=%.2f atr=%.4f position=%g", symbol, row.adx, atr, position)
                continue

            step = atr * self.grid.spacing_atr
            anchor = self.state.anchors.get(symbol, price)
            if abs(price - anchor) > step * self.grid.levels:
                anchor = price
            self.state.anchors[symbol] = anchor
            remaining = max(0.0, per_symbol_budget - abs(position) * price)
            qty = remaining / (self.grid.levels * price)
            orders = self._orders(anchor, step, qty, position)
            placed = len(self.broker.replace_grid(symbol, orders)) if self.execute else 0
            log.info(
                "%s range price=%.6g adx=%.2f position=%g plan=%s placed=%s",
                symbol, price, row.adx, position, len(orders), placed,
            )
        self.state.save(self.state_path)

    def status(self) -> list[dict]:
        equity = self.equity()
        return [{
            "environment": self.environment,
            "equity": equity,
            "symbol": symbol,
            "position": 0.0 if not self.broker else self.broker.position_qty(symbol),
            "grid_orders": 0 if not self.broker else self.broker.grid_order_count(symbol),
            "halted": self.state.halted_reason or None,
        } for symbol in self.symbols]

    def dashboard_snapshot(self) -> dict:
        equity = self.equity()
        pairs = []
        for symbol in self.symbols:
            frame = self.data.klines(symbol, str(self.interval), limit=100)
            now = datetime.now(UTC)
            if len(frame) and frame.index[-1].to_pydatetime() + timedelta(minutes=self.interval) > now:
                frame = frame.iloc[:-1]
            indicators = add_indicators(frame)
            row = indicators.iloc[-1]
            pairs.append({
                "symbol": symbol,
                "price": float(row.close),
                "adx": float(row.adx),
                "atr": float(row.atr),
                "ranging": bool(self.regime.predict(frame).iloc[-1]),
                "position": 0.0 if not self.broker else self.broker.position_qty(symbol),
                "orders": 0 if not self.broker else self.broker.grid_order_count(symbol),
                "closes": frame.close.tail(50).astype(float).tolist(),
            })
        return {
            "environment": self.environment,
            "equity": equity,
            "halted": self.state.halted_reason or None,
            "pairs": pairs,
            "updated": datetime.now(UTC).strftime("%H:%M:%S UTC"),
        }

    def reset(self) -> None:
        self.state = BotState()
        self.state.save(self.state_path)

    def run_forever(self, stop_event=None) -> None:
        from .stream import KlineStream

        self.cycle()
        stream = KlineStream(self.symbols, self.interval, self.environment == "testnet")
        reconciled = time.monotonic()
        try:
            while stop_event is None or not stop_event.is_set():
                symbol = stream.next(timeout=5)
                if symbol is not None or time.monotonic() - reconciled >= 60:
                    self.cycle()
                    reconciled = time.monotonic()
        finally:
            stream.close()
