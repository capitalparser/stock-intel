"""Normalize raw fundamental/technical/flow data into 0~100 lens metrics.

This is the layer that was previously missing: the dashboard scored hardcoded
0~100 metrics, but nothing mapped *real* data onto that scale. Every function
here is pure and deterministic so it can be unit-tested without network access.

Design rules
------------
* Inputs are optional. When the inputs a score needs are entirely missing the
  function returns ``None`` so callers can render an explicit data gap instead
  of a misleading number.
* Outputs are always clamped to ``[0, 100]``.
* The scale convention is "higher = more attractive for a long candidate":
  cheaper valuation, higher quality, faster growth, more positive revision
  proxy, stronger momentum all push the score up.
* Mappings are intentionally simple, monotonic and documented. They are meant
  to be auditable and tunable, not a black box. Thresholds live in module-level
  constants so they can be adjusted in one place.
"""

from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _lerp(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
    """Linear interpolation of ``value`` from [lo, hi] onto [out_lo, out_hi]."""
    if hi == lo:
        return (out_lo + out_hi) / 2
    t = (value - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    return out_lo + t * (out_hi - out_lo)


# --------------------------------------------------------------------------- #
# Valuation
# --------------------------------------------------------------------------- #
# Cheaper than peers -> higher score. Driven primarily by PE relative to the
# peer-group median, with a light PBR sanity overlay. A stock at half its peer
# PE scores ~85; at 2x peer PE scores ~25.
VALUATION_REL_LOW = 0.5   # PE / peer_pe at/below this -> top of band
VALUATION_REL_HIGH = 2.0  # PE / peer_pe at/above this -> bottom of band


def valuation_score(
    pe: float | None,
    peer_pe: float | None,
    pbr: float | None = None,
) -> float | None:
    if pe is None or pe <= 0:
        # No usable earnings multiple. PBR alone can still anchor a rough read.
        if pbr is not None and pbr > 0:
            # PBR 1.0 -> 60 (cheap-ish), 5.0 -> 25 (rich).
            return clamp(_lerp(pbr, 1.0, 5.0, 75.0, 25.0))
        return None

    if peer_pe is not None and peer_pe > 0:
        rel = pe / peer_pe
        score = _lerp(rel, VALUATION_REL_LOW, VALUATION_REL_HIGH, 90.0, 20.0)
    else:
        # Absolute fallback when no peer anchor: PER 10 -> 80, PER 50 -> 25.
        score = _lerp(pe, 10.0, 50.0, 80.0, 25.0)

    if pbr is not None and pbr > 0:
        # Nudge ±5 for extreme book multiples without overriding the PE signal.
        if pbr <= 1.0:
            score += 5
        elif pbr >= 6.0:
            score -= 5
    return clamp(score)


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #
# Operating margin is the spine; positive operating cash flow is a quality
# confirmation. Margin 0% -> 35, 25% -> 80, 40%+ -> 92.
def quality_score(
    op_margin_pct: float | None,
    ocf_positive: bool | None = None,
    roe_pct: float | None = None,
) -> float | None:
    components: list[float] = []

    if op_margin_pct is not None:
        components.append(clamp(_lerp(op_margin_pct, 0.0, 40.0, 35.0, 92.0)))
    if roe_pct is not None:
        # ROE 5% -> 45, 25% -> 85.
        components.append(clamp(_lerp(roe_pct, 5.0, 25.0, 45.0, 85.0)))

    if not components:
        return None

    score = sum(components) / len(components)
    if ocf_positive is True:
        score += 4
    elif ocf_positive is False:
        score -= 8
    return clamp(score)


# --------------------------------------------------------------------------- #
# Growth
# --------------------------------------------------------------------------- #
# Blend of revenue and operating-income growth (%). Operating income is
# weighted slightly higher because it reflects operating leverage. 0% -> 40,
# 30% -> 80, 60%+ -> 92.
def growth_score(
    revenue_growth_pct: float | None,
    op_growth_pct: float | None = None,
) -> float | None:
    parts: list[tuple[float, float]] = []  # (score, weight)
    if revenue_growth_pct is not None:
        parts.append((clamp(_lerp(revenue_growth_pct, 0.0, 60.0, 40.0, 92.0)), 1.0))
    if op_growth_pct is not None:
        parts.append((clamp(_lerp(op_growth_pct, 0.0, 60.0, 40.0, 92.0)), 1.3))
    if not parts:
        return None
    total_w = sum(w for _, w in parts)
    return clamp(sum(s * w for s, w in parts) / total_w)


# --------------------------------------------------------------------------- #
# Revision (proxy)
# --------------------------------------------------------------------------- #
# True estimate-revision data is not wired in (no consensus feed). We expose an
# explicit *proxy* built from flow + trend signals, and callers should mark the
# metric as a proxy. Inputs:
#   net_flow_signal: +1 institutions/foreigners net buying, -1 net selling, 0 mixed
#   trend_signal:    "정배열"/"역배열"/"혼조" or US-style up/down/flat
def revision_proxy_score(
    net_flow_signal: float | None,
    trend_signal: str | None = None,
) -> float | None:
    if net_flow_signal is None and trend_signal is None:
        return None
    score = 50.0
    if net_flow_signal is not None:
        score += 18 * max(-1.0, min(1.0, net_flow_signal))
    if trend_signal:
        up = {"정배열", "up", "improving", "진입"}
        down = {"역배열", "down", "deteriorating", "매도", "손절"}
        if trend_signal in up:
            score += 12
        elif trend_signal in down:
            score -= 12
    return clamp(score)


# --------------------------------------------------------------------------- #
# Momentum
# --------------------------------------------------------------------------- #
# Combines Bollinger %B (position in band), MA alignment, a trailing return and
# volume confirmation. Each available component contributes; missing ones are
# skipped and the rest re-weighted.
def momentum_score(
    bb_pct: float | None = None,
    ma_trend: str | None = None,
    return_pct: float | None = None,
    volume_ratio: float | None = None,
) -> float | None:
    parts: list[tuple[float, float]] = []  # (score, weight)

    if bb_pct is not None:
        # %B 0 -> 30 (bottom of band), 50 -> 60, 100 -> 88.
        parts.append((clamp(_lerp(bb_pct, 0.0, 100.0, 30.0, 88.0)), 1.0))

    if ma_trend is not None:
        mapping = {
            "정배열": 80.0, "up": 80.0,
            "혼조": 50.0, "flat": 50.0, "mixed": 50.0,
            "역배열": 25.0, "down": 25.0,
        }
        if ma_trend in mapping:
            parts.append((mapping[ma_trend], 1.0))

    if return_pct is not None:
        # Trailing return (e.g. ~1 month %): -15% -> 30, 0 -> 55, +20% -> 85.
        parts.append((clamp(_lerp(return_pct, -15.0, 20.0, 30.0, 85.0)), 1.0))

    if volume_ratio is not None:
        # Light confirmation: 0.5x -> 45, 1.0x -> 55, 2.0x+ -> 70.
        parts.append((clamp(_lerp(volume_ratio, 0.5, 2.0, 45.0, 70.0)), 0.5))

    if not parts:
        return None
    total_w = sum(w for _, w in parts)
    return clamp(sum(s * w for s, w in parts) / total_w)


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
METRIC_FIELDS = ("valuation", "quality", "growth", "revision", "momentum")


@dataclass(frozen=True)
class MetricResult:
    """Normalized metrics plus provenance for the data-quality panel.

    ``scores`` always has all five keys; missing inputs fall back to
    ``DEFAULT_NEUTRAL`` so downstream scoring stays well-defined, while
    ``missing`` records which metrics were *not* backed by real data so the UI
    can flag them as gaps. ``proxy`` records metrics derived from a proxy.
    """

    scores: dict[str, float]
    missing: list[str]
    proxy: list[str]


DEFAULT_NEUTRAL = 50.0


def build_metrics(
    *,
    pe: float | None,
    peer_pe: float | None,
    pbr: float | None,
    op_margin_pct: float | None,
    ocf_positive: bool | None,
    roe_pct: float | None,
    revenue_growth_pct: float | None,
    op_growth_pct: float | None,
    net_flow_signal: float | None,
    ma_trend: str | None,
    bb_pct: float | None,
    return_pct: float | None,
    volume_ratio: float | None,
) -> MetricResult:
    raw = {
        "valuation": valuation_score(pe, peer_pe, pbr),
        "quality": quality_score(op_margin_pct, ocf_positive, roe_pct),
        "growth": growth_score(revenue_growth_pct, op_growth_pct),
        "revision": revision_proxy_score(net_flow_signal, ma_trend),
        "momentum": momentum_score(bb_pct, ma_trend, return_pct, volume_ratio),
    }
    scores: dict[str, float] = {}
    missing: list[str] = []
    for name in METRIC_FIELDS:
        value = raw[name]
        if value is None:
            scores[name] = DEFAULT_NEUTRAL
            missing.append(name)
        else:
            scores[name] = round(value, 1)
    # revision is always a proxy in the current build (no consensus feed).
    proxy = ["revision"] if "revision" not in missing else []
    return MetricResult(scores=scores, missing=missing, proxy=proxy)
