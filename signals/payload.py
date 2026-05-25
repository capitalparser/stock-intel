"""TradingView private-indicator webhook payload model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["BUY", "SELL", "CHECK"]
Conviction = Literal["S", "A", "B", "C", "D"]
Momentum = Literal["BUY", "SELL", ""]


class TradingViewSignal(BaseModel):
    """TradingView webhook payload v6.2."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=False)

    schema_version: str = "v6.2"
    ticker: str
    name: str
    exchange: str = ""
    timeframe: str
    action: ActionType
    type: str
    price: float
    sl: float | None = None
    rr: float | None = None
    desc: str = ""
    market: str = ""
    ai_summary: str = ""
    score: int = 0
    status: str = ""
    signal: str = ""
    conviction: Conviction = "B"
    momentum: Momentum = ""
    momentum_sl: float | None = None
    momentum_tp: float | None = None
    momentum_bars: int | None = None
    energy: float = 0.0
    ema1_dist: float = 0.0
    candle_type: str = ""
    candle_strength: float = 0.0
    ema_touch: str = "none"
    ema_align: str = ""
    daily_trend: str = ""
    daily_ema_aligned: bool = False
    daily_rs: int = 0
    daily_above_200ma: bool = False
    daily_setup_stage: str = ""
    daily_volume_trend: str = ""
    daily_dist_from_high: float = 0.0
    rsi2: float = Field(default=50.0, ge=0.0, le=100.0)
    upper_wick_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    atr_multiple: float | None = None
    atr_dot: bool = False
    atr_dot_threshold: float = 7.0
    sb_z_score: float = 0.0

    def base_type(self) -> str:
        return self.type.removesuffix(" @SR↩").strip()

    def has_sr_flip(self) -> bool:
        return self.type.endswith(" @SR↩")

