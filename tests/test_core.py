import numpy as np
import pandas as pd
import pytest

from gridbot.backtest import run_backtest
from gridbot.broker import BybitBroker
from gridbot.indicators import RuleRegimeFilter
from gridbot.strategy import build_grid
from gridbot.runtime import LiveBot
from gridbot.stream import KlineStream


def candles(count: int = 300) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=count, freq="15min", tz="UTC")
    close = 100 + np.sin(np.arange(count) / 5) * 2
    return pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 10.0, "turnover": 1000.0},
        index=index,
    )


def test_grid_is_symmetric_and_sized() -> None:
    orders = build_grid(mid=100, atr=2, equity=1000)
    assert len(orders) == 10
    assert orders[0].price == 99 and orders[1].price == 101
    assert sum(order.qty * 100 for order in orders) == 500


def test_backtest_runs_without_lookahead_crash() -> None:
    frame = candles()
    ranging = RuleRegimeFilter().predict(frame)
    result = run_backtest(frame, ranging)
    assert result.final_equity > 0
    assert 0 <= result.max_drawdown_pct <= 100


def test_mainnet_writes_need_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = object.__new__(BybitBroker)
    broker.environment = "mainnet"
    monkeypatch.delenv("GRIDBOT_LIVE_CONFIRM", raising=False)
    with pytest.raises(RuntimeError, match="Real-money writes are locked"):
        broker._assert_writes_allowed()


def test_live_grid_uses_reduce_only_to_unwind_position() -> None:
    bot = object.__new__(LiveBot)
    bot.grid = type("Grid", (), {"levels": 5})()
    orders = bot._orders(anchor=100, step=1, qty=0.2, position=1.0)
    buys = [order for order in orders if order.side == "Buy"]
    sells = [order for order in orders if order.side == "Sell"]
    assert all(not order.reduce_only for order in buys)
    assert all(order.reduce_only for order in sells)


def test_bybit_kline_symbol_is_read_from_topic() -> None:
    message = {"topic": "kline.15.BTCUSDT", "data": [{"confirm": True}]}
    assert KlineStream.symbol_from(message, message["data"][0]) == "BTCUSDT"
