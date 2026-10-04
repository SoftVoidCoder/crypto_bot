from __future__ import annotations

import os
import time
from decimal import Decimal, ROUND_DOWN

from .strategy import GridOrder


def _floor(value: float, step: str) -> str:
    unit = Decimal(step)
    return str((Decimal(str(value)) / unit).to_integral_value(rounding=ROUND_DOWN) * unit)


class BybitBroker:
    """Private Bybit adapter for testnet, demo, or guarded mainnet."""

    prefix = "gridbot-"
    environments = {"testnet", "demo", "mainnet"}

    def __init__(self, environment: str | None = None):
        from dotenv import load_dotenv
        from pybit.unified_trading import HTTP

        load_dotenv()
        self.environment = (environment or os.getenv("BYBIT_ENV", "paper")).lower()
        if self.environment not in self.environments:
            raise RuntimeError("BYBIT_ENV must be testnet, demo, or mainnet for private API access")
        key, secret = os.getenv("BYBIT_API_KEY"), os.getenv("BYBIT_API_SECRET")
        if not key or not secret:
            raise RuntimeError("BYBIT_API_KEY and BYBIT_API_SECRET are required")
        self.http = HTTP(
            testnet=self.environment == "testnet",
            demo=self.environment == "demo",
            api_key=key,
            api_secret=secret,
        )

    def account_equity(self) -> float:
        account = self.http.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        return float(account["result"]["list"][0]["totalEquity"])

    def position_qty(self, symbol: str) -> float:
        positions = self.http.get_positions(category="linear", symbol=symbol)["result"]["list"]
        if any(int(item.get("positionIdx", 0)) in (1, 2) for item in positions):
            raise RuntimeError(f"{symbol}: switch the Bybit account to one-way position mode")
        return sum(
            float(item["size"]) * (1 if item["side"] == "Buy" else -1)
            for item in positions
            if float(item["size"]) > 0
        )

    def _assert_writes_allowed(self) -> None:
        if self.environment == "mainnet" and os.getenv("GRIDBOT_LIVE_CONFIRM") != "true":
            raise RuntimeError("Real-money writes are locked; set GRIDBOT_LIVE_CONFIRM=true intentionally")

    def cancel_grid(self, symbol: str) -> int:
        self._assert_writes_allowed()
        orders = self.http.get_open_orders(category="linear", symbol=symbol)["result"]["list"]
        owned = [order for order in orders if order.get("orderLinkId", "").startswith(self.prefix)]
        for order in owned:
            self.http.cancel_order(category="linear", symbol=symbol, orderId=order["orderId"])
        return len(owned)

    def grid_order_count(self, symbol: str) -> int:
        orders = self.http.get_open_orders(category="linear", symbol=symbol)["result"]["list"]
        return sum(order.get("orderLinkId", "").startswith(self.prefix) for order in orders)

    def flatten(self, symbol: str) -> str | None:
        self._assert_writes_allowed()
        qty = self.position_qty(symbol)
        if qty == 0:
            return None
        result = self.http.place_order(
            category="linear", symbol=symbol, side="Sell" if qty > 0 else "Buy",
            orderType="Market", qty=str(abs(qty)), reduceOnly=True, positionIdx=0,
            orderLinkId=f"{self.prefix}stop-{int(time.time() * 1000)}",
        )
        return result["result"]["orderId"]

    def replace_grid(self, symbol: str, orders: list[GridOrder]) -> list[str]:
        self._assert_writes_allowed()
        info = self.http.get_instruments_info(category="linear", symbol=symbol)["result"]["list"][0]
        tick = info["priceFilter"]["tickSize"]
        qty_step = info["lotSizeFilter"]["qtyStep"]
        min_qty = Decimal(info["lotSizeFilter"]["minOrderQty"])
        self.cancel_grid(symbol)

        ids = []
        stamp = int(time.time() * 1000)
        for index, order in enumerate(orders):
            link_id = f"{self.prefix}{stamp}-{index}"
            qty = _floor(order.qty, qty_step)
            if Decimal(qty) < min_qty:
                continue
            result = self.http.place_order(
                category="linear", symbol=symbol, side=order.side, orderType="Limit",
                qty=qty, price=_floor(order.price, tick), reduceOnly=order.reduce_only,
                timeInForce="PostOnly", positionIdx=0, orderLinkId=link_id,
            )
            ids.append(result["result"]["orderId"])
        return ids
