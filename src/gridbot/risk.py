from dataclasses import dataclass
from datetime import date

from .config import RiskConfig


@dataclass
class RiskManager:
    starting_equity: float
    config: RiskConfig = RiskConfig()

    def __post_init__(self) -> None:
        self.peak_equity = self.starting_equity
        self.day_start_equity = self.starting_equity
        self.current_day: date | None = None
        self.halted_reason: str | None = None

    def update(self, equity: float, day: date) -> bool:
        if self.current_day != day:
            self.current_day, self.day_start_equity = day, equity
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = 1 - equity / self.peak_equity
        daily_loss = 1 - equity / self.day_start_equity
        if drawdown >= self.config.max_drawdown:
            self.halted_reason = f"max drawdown reached: {drawdown:.2%}"
        elif daily_loss >= self.config.max_daily_loss:
            self.halted_reason = f"daily loss reached: {daily_loss:.2%}"
        return self.halted_reason is None

    def reset_daily_halt(self) -> None:
        if self.halted_reason and self.halted_reason.startswith("daily loss"):
            self.halted_reason = None

