from dataclasses import dataclass


@dataclass(frozen=True)
class GridConfig:
    levels: int = 5
    spacing_atr: float = 0.5
    max_position_fraction: float = 0.50


@dataclass(frozen=True)
class RiskConfig:
    max_drawdown: float = 0.10
    max_daily_loss: float = 0.03
    fee_rate: float = 0.00055
    slippage_rate: float = 0.0002


@dataclass(frozen=True)
class RegimeConfig:
    adx_period: int = 14
    max_adx: float = 25.0
    max_atr_fraction: float = 0.025
    ml_horizon: int = 12

