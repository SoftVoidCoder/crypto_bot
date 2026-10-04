from __future__ import annotations

from queue import Queue


class KlineStream:
    """Official pybit stream; pybit reconnects and resubscribes automatically."""

    @staticmethod
    def symbol_from(message: dict, candle: dict) -> str:
        symbol = candle.get("symbol") or message.get("topic", "").rsplit(".", 1)[-1]
        if not symbol:
            raise ValueError("Bybit kline message has no symbol")
        return symbol

    def __init__(self, symbols: list[str], interval: int, testnet: bool):
        from pybit.unified_trading import WebSocket

        self.events: Queue[str] = Queue()
        self.ws = WebSocket(
            testnet=testnet,
            channel_type="linear",
            retries=0,
            restart_on_error=True,
        )

        def callback(message: dict) -> None:
            for candle in message.get("data", []):
                if candle.get("confirm"):
                    self.events.put(self.symbol_from(message, candle))

        self.ws.kline_stream(interval=interval, symbol=symbols, callback=callback)

    def next(self, timeout: float = 90.0) -> str | None:
        try:
            return self.events.get(timeout=timeout)
        except Exception:
            return None

    def close(self) -> None:
        self.ws.exit()
