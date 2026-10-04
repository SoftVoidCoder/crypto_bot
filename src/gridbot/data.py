from __future__ import annotations

import pandas as pd


KLINE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]


class BybitData:
    def __init__(self, testnet: bool = False):
        from pybit.unified_trading import HTTP

        self.http = HTTP(testnet=testnet)

    def klines(
        self, symbol: str, interval: str, start_ms: int | None = None, end_ms: int | None = None, limit: int = 1000
    ) -> pd.DataFrame:
        rows: list[list[str]] = []
        cursor = end_ms
        while len(rows) < limit:
            size = min(1000, limit - len(rows))
            params = {"category": "linear", "symbol": symbol.upper(), "interval": interval, "limit": size}
            if start_ms is not None:
                params["start"] = start_ms
            if cursor is not None:
                params["end"] = cursor
            response = self.http.get_kline(**params)
            page = response["result"]["list"]
            if not page:
                break
            rows.extend(page)
            oldest = min(int(row[0]) for row in page)
            if len(page) < size or (start_ms is not None and oldest <= start_ms):
                break
            cursor = oldest - 1

        frame = pd.DataFrame(rows, columns=KLINE_COLUMNS).drop_duplicates("timestamp")
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
        frame[KLINE_COLUMNS[1:]] = frame[KLINE_COLUMNS[1:]].astype(float)
        return frame.sort_values("timestamp").set_index("timestamp").tail(limit)

