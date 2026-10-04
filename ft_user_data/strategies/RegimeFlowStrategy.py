from datetime import datetime

from pandas import DataFrame
import talib.abstract as ta
from technical import qtpylib

from freqtrade.strategy import IStrategy


class RegimeFlowStrategy(IStrategy):
    """Conservative 15m long/short regime strategy for liquid USDT perpetuals."""

    INTERFACE_VERSION = 3
    can_short = True
    timeframe = "15m"
    startup_candle_count = 220
    process_only_new_candles = True

    minimal_roi = {"0": 0.012}
    stoploss = -0.015
    trailing_stop = True
    trailing_stop_positive = 0.006
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True
    use_exit_signal = False
    exit_profit_only = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    @property
    def protections(self) -> list[dict]:
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 3,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 96,
                "trade_limit": 4,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.08,
                "calculation_mode": "equity",
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 24,
                "required_profit": 0.005,
            },
        ]

    plot_config = {
        "main_plot": {
            "ema50": {"color": "#46a0ff"},
            "ema200": {"color": "#ff9f43"},
            "bb_upper": {"color": "#555b66"},
            "bb_lower": {"color": "#555b66"},
        },
        "subplots": {
            "Режим рынка": {"adx": {"color": "#9b59b6"}},
            "RSI": {"rsi": {"color": "#00d2a0"}},
            "MACD": {
                "macd": {"color": "#46a0ff"},
                "macdsignal": {"color": "#ff9f43"},
            },
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["atr_median"] = dataframe["atr_pct"].rolling(96).median()
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        bands = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bands["lower"]
        dataframe["bb_mid"] = bands["mid"]
        dataframe["bb_upper"] = bands["upper"]
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()
        dataframe["range_high"] = dataframe["high"].rolling(48).max().shift(1)
        dataframe["range_low"] = dataframe["low"].rolling(48).min().shift(1)
        dataframe["anomaly"] = dataframe["atr_pct"] > dataframe["atr_median"] * 3.0
        dataframe["trend"] = dataframe["adx"] > 25
        dataframe["range"] = dataframe["adx"] < 22
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        liquid = (dataframe["volume"] > dataframe["volume_mean"] * 1.1) & ~dataframe["anomaly"]
        trend_long = (
            dataframe["trend"]
            & (dataframe["ema50"] > dataframe["ema200"])
            & qtpylib.crossed_above(dataframe["close"], dataframe["range_high"])
            & (dataframe["macd"] > dataframe["macdsignal"])
            & dataframe["rsi"].between(52, 75)
        )
        trend_short = (
            dataframe["trend"]
            & (dataframe["ema50"] < dataframe["ema200"])
            & qtpylib.crossed_below(dataframe["close"], dataframe["range_low"])
            & (dataframe["macd"] < dataframe["macdsignal"])
            & dataframe["rsi"].between(25, 48)
        )
        dataframe.loc[liquid & trend_long, ["enter_long", "enter_tag"]] = (1, "trend_long")
        dataframe.loc[liquid & trend_short, ["enter_short", "enter_tag"]] = (1, "trend_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return 1.0

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """Reject live entries when top-20 orderbook imbalance is strongly adverse."""
        if not self.dp or self.dp.runmode.value not in {"live", "dry_run"}:
            return True
        try:
            book = self.dp.orderbook(pair, 20)
            bid_value = sum(price * size for price, size in book["bids"])
            ask_value = sum(price * size for price, size in book["asks"])
            if not bid_value or not ask_value:
                return False
            ratio = bid_value / ask_value
            return ratio >= 0.55 if side == "long" else ratio <= 1.82
        except Exception:
            return False
