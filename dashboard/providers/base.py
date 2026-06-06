"""RawStock model, market classification, and shared price-series helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Sequence


@dataclass
class RawStock:
    """Normalized raw inputs for one ticker, pre-scoring.

    Every numeric field is optional so partial fetches are representable.
    ``source`` is ``"KR"`` or ``"US"``; ``errors`` collects fetch problems.
    """

    ticker: str
    source: str
    price: float | None = None
    day_change_pct: float | None = None
    return_pct: float | None = None  # trailing ~1 month return

    # valuation
    pe: float | None = None
    pbr: float | None = None

    # quality
    op_margin_pct: float | None = None
    roe_pct: float | None = None
    ocf_positive: bool | None = None

    # growth
    revenue_growth_pct: float | None = None
    op_growth_pct: float | None = None

    # flow / revision proxy
    net_flow_signal: float | None = None  # +1 net buy, -1 net sell, 0 mixed
    short_ratio: float | None = None

    # momentum / technical
    bb_pct: float | None = None
    ma_trend: str | None = None
    volume_ratio: float | None = None

    # recent close series (sparkline) — most-recent last, best-effort
    closes: list[float] = field(default_factory=list)

    # 외국인/기관 순매수 누적(원) — KR only, Naver 수급. 표면화 + graded net_flow.
    foreign_net_5d: float | None = None
    foreign_net_20d: float | None = None
    inst_net_5d: float | None = None
    inst_net_20d: float | None = None

    as_of: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_KR_TICKER = re.compile(r"^\d{6}$")


def classify_market(ticker: str) -> str:
    """``"KR"`` for 6-digit codes (e.g. 005930), else ``"US"``."""
    return "KR" if _KR_TICKER.match(ticker.strip()) else "US"


def fetch_raw_stock(ticker: str) -> RawStock:
    """Dispatch to the KR or US provider based on ticker shape."""
    market = classify_market(ticker)
    if market == "KR":
        from dashboard.providers.kr import fetch_kr_stock

        return fetch_kr_stock(ticker)
    from dashboard.providers.us import fetch_us_stock

    return fetch_us_stock(ticker)


# --------------------------------------------------------------------------- #
# Shared price-series math (used by US + macro; KR reuses data/technical).
# --------------------------------------------------------------------------- #
def day_change_pct(closes: Sequence[float]) -> float | None:
    if len(closes) < 2 or not closes[-2]:
        return None
    return (closes[-1] / closes[-2] - 1) * 100


def trailing_return_pct(closes: Sequence[float], lookback: int = 21) -> float | None:
    if len(closes) <= lookback or not closes[-lookback - 1]:
        return None
    return (closes[-1] / closes[-lookback - 1] - 1) * 100


def bollinger_pct_b(closes: Sequence[float], window: int = 20, n_std: float = 2.0) -> float | None:
    """Bollinger %B in percent (0 = lower band, 100 = upper band)."""
    if len(closes) < window:
        return None
    window_vals = list(closes[-window:])
    mean = sum(window_vals) / window
    var = sum((c - mean) ** 2 for c in window_vals) / window
    std = var ** 0.5
    if std == 0:
        return 50.0
    lower = mean - n_std * std
    upper = mean + n_std * std
    pct = (closes[-1] - lower) / (upper - lower) * 100
    return max(0.0, min(100.0, pct))


def ma_alignment(closes: Sequence[float]) -> str | None:
    """정배열 (price>MA50>MA150) / 역배열 / 혼조 from close history."""
    if len(closes) < 50:
        return None

    def sma(n: int) -> float | None:
        if len(closes) < n:
            return None
        return sum(closes[-n:]) / n

    price = closes[-1]
    ma50 = sma(50)
    ma150 = sma(150) if len(closes) >= 150 else sma(min(len(closes), 100))
    if ma50 is None or ma150 is None:
        return None
    if price > ma50 > ma150:
        return "정배열"
    if price < ma50 < ma150:
        return "역배열"
    return "혼조"


def volume_ratio(volumes: Sequence[float], window: int = 50) -> float | None:
    if len(volumes) < 2:
        return None
    use = volumes[-window:] if len(volumes) >= window else volumes
    avg = sum(use) / len(use)
    if not avg:
        return None
    return volumes[-1] / avg
