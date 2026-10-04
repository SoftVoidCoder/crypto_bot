from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RegimeConfig


def add_indicators(frame: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = frame.copy()
    high, low, close = out["high"], out["low"], out["close"]
    previous = close.shift()
    true_range = pd.concat(
        [(high - low), (high - previous).abs(), (low - previous).abs()], axis=1
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    up, down = high.diff(), -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)

    out["atr"] = atr
    out["atr_fraction"] = atr / close
    out["adx"] = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    out["return_abs"] = close.pct_change().abs().rolling(period).mean()
    out["efficiency"] = close.diff(period).abs() / close.diff().abs().rolling(period).sum()
    return out


class RuleRegimeFilter:
    def __init__(self, config: RegimeConfig = RegimeConfig()):
        self.config = config

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        data = add_indicators(frame, self.config.adx_period)
        return (
            (data["adx"] <= self.config.max_adx)
            & (data["atr_fraction"] <= self.config.max_atr_fraction)
        ).fillna(False)


class MLRegimeFilter:
    """Small, interpretable classifier; fit only on data before the test window."""

    columns = ["adx", "atr_fraction", "return_abs", "efficiency"]

    def __init__(self, config: RegimeConfig = RegimeConfig()):
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        self.config = config
        self.model = make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=500)
        )

    def _xy(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        data = add_indicators(frame, self.config.adx_period)
        future_move = data["close"].shift(-self.config.ml_horizon).div(data["close"]).sub(1).abs()
        target = future_move.le(data["atr_fraction"])
        valid = data[self.columns].notna().all(axis=1) & future_move.notna()
        return data.loc[valid, self.columns], target.loc[valid]

    def fit(self, frame: pd.DataFrame) -> "MLRegimeFilter":
        features, target = self._xy(frame)
        if len(features) < 100 or target.nunique() < 2:
            raise ValueError("ML filter needs at least 100 valid rows and both regime classes")
        self.model.fit(features, target)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        data = add_indicators(frame, self.config.adx_period)
        valid = data[self.columns].notna().all(axis=1)
        result = pd.Series(False, index=frame.index)
        result.loc[valid] = self.model.predict_proba(data.loc[valid, self.columns])[:, 1] >= 0.55
        return result

