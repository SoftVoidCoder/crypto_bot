from dataclasses import dataclass

from .config import GridConfig


@dataclass(frozen=True)
class GridOrder:
    side: str
    price: float
    qty: float
    reduce_only: bool = False


def build_grid(mid: float, atr: float, equity: float, config: GridConfig = GridConfig()) -> list[GridOrder]:
    if min(mid, atr, equity) <= 0:
        raise ValueError("mid, atr and equity must be positive")
    step = atr * config.spacing_atr
    qty = equity * config.max_position_fraction / (2 * config.levels * mid)
    return [
        GridOrder(side, mid + direction * step * level, qty)
        for level in range(1, config.levels + 1)
        for side, direction in (("Buy", -1), ("Sell", 1))
    ]
