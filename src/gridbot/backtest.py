from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import GridConfig, RiskConfig
from .indicators import add_indicators
from .risk import RiskManager


@dataclass
class Lot:
    side: int
    entry: float
    qty: float


@dataclass(frozen=True)
class BacktestResult:
    final_equity: float
    return_pct: float
    max_drawdown_pct: float
    trades: int
    halted_reason: str | None
    equity_curve: pd.Series


def run_backtest(
    frame: pd.DataFrame,
    ranging: pd.Series,
    initial_equity: float = 10_000.0,
    grid: GridConfig = GridConfig(),
    risk_config: RiskConfig = RiskConfig(),
) -> BacktestResult:
    data = add_indicators(frame)
    cash, anchor, trades = initial_equity, None, 0
    lots: list[Lot] = []
    curve: dict[pd.Timestamp, float] = {}
    risk = RiskManager(initial_equity, risk_config)
    ranging = ranging.reindex(data.index, fill_value=False)

    def close_lot(lot: Lot, price: float) -> None:
        nonlocal cash, trades
        exit_price = price * (1 - risk_config.slippage_rate * lot.side)
        cash += lot.side * (exit_price - lot.entry) * lot.qty
        cash -= (lot.entry + exit_price) * lot.qty * risk_config.fee_rate
        trades += 1

    for timestamp, row in data.iterrows():
        price = float(row.close)
        equity = cash + sum(lot.side * (price - lot.entry) * lot.qty for lot in lots)
        curve[timestamp] = equity
        if not risk.update(equity, timestamp.date()):
            for lot in lots:
                close_lot(lot, price)
            lots.clear()
            break

        if not bool(ranging.loc[timestamp]) or pd.isna(row.atr):
            for lot in lots:
                close_lot(lot, price)
            lots.clear()
            anchor = None
            continue

        step = float(row.atr) * grid.spacing_atr
        if anchor is None:
            anchor = price
        if not lots and abs(price - anchor) > step * grid.levels:
            anchor = price

        survivors = []
        for lot in lots:
            target = lot.entry + lot.side * step
            hit = row.high >= target if lot.side == 1 else row.low <= target
            if hit:
                close_lot(lot, target)
            else:
                survivors.append(lot)
        lots = survivors

        max_notional = equity * grid.max_position_fraction
        current_notional = sum(lot.qty * price for lot in lots)
        qty = max_notional / (2 * grid.levels * price)
        occupied = {(lot.side, round(lot.entry, 10)) for lot in lots}
        for level in range(1, grid.levels + 1):
            for side, entry, hit in (
                (1, anchor - level * step, row.low <= anchor - level * step),
                (-1, anchor + level * step, row.high >= anchor + level * step),
            ):
                if hit and (side, round(entry, 10)) not in occupied and current_notional + qty * price <= max_notional:
                    lots.append(Lot(side, entry, qty))
                    current_notional += qty * price

    if lots:
        last_price = float(data.close.iloc[-1])
        for lot in lots:
            close_lot(lot, last_price)
        curve[data.index[-1]] = cash
    curve_series = pd.Series(curve, name="equity")
    final = cash
    max_dd = (1 - curve_series / curve_series.cummax()).max() if not curve_series.empty else 0.0
    return BacktestResult(final, (final / initial_equity - 1) * 100, float(max_dd) * 100, trades, risk.halted_reason, curve_series)
