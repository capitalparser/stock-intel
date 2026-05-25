"""TradingView direct Lazy Alpha label outcome mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections import Counter


@dataclass(frozen=True)
class TradingViewLabelOutcome:
    symbol: str
    market: str
    signal_date: str
    first_signal_date: str
    last_signal_date: str
    duplicate_count: int
    label: str
    entry_price: float
    returns: dict[str, float | None]
    context: dict[str, float | None]
    risk_flags: list[str]
    score_penalty_hint: int
    failure_class: str | None = None


BUY_LABEL_KEYWORDS = (
    "진입",
    "추매",
    "상방 돌파",
    "돌파 진입",
)

NON_BUY_LABEL_KEYWORDS = (
    "청산",
    "익절",
    "이탈",
    "관망",
    "셋업",
    "TP",
    "종료",
    "Short",
    "PBS",
    "PBB",
    "Vol",
    "NH",
)

EXIT_LABEL_KEYWORDS = (
    "청산",
    "손절",
    "익절",
    "이탈",
    "종료",
    "SL",
)


def is_lazy_alpha_buy_label(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if any(keyword in normalized for keyword in NON_BUY_LABEL_KEYWORDS):
        return False
    return any(keyword in normalized for keyword in BUY_LABEL_KEYWORDS)


def is_lazy_alpha_exit_label(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in EXIT_LABEL_KEYWORDS)


def map_lazy_alpha_labels_to_outcomes(
    *,
    symbol: str,
    market: str,
    bars: list[dict],
    labels: list[dict],
    total_available: int | None = None,
    horizons: tuple[int, ...] = (5, 10, 20),
    duplicate_window_bars: int = 5,
    entry_policy: str = "first",
    active_only: bool = False,
) -> list[TradingViewLabelOutcome]:
    if not bars:
        return []
    offset = max(0, (total_available or len(bars)) - len(bars))
    candidates: list[tuple[int, dict]] = []
    exit_bar_indexes: list[int] = []
    for label in labels:
        text = str(label.get("text") or "")
        x_value = label.get("x")
        if not isinstance(x_value, int):
            continue
        bar_index = x_value - offset
        if bar_index < 0 or bar_index >= len(bars):
            continue
        if is_lazy_alpha_buy_label(text):
            candidates.append((bar_index, label))
        elif is_lazy_alpha_exit_label(text):
            exit_bar_indexes.append(bar_index)

    outcomes: list[TradingViewLabelOutcome] = []
    for cluster in _cluster_candidates(candidates, duplicate_window_bars=duplicate_window_bars):
        selected_bar_index, selected_label = _select_cluster_entry(cluster, entry_policy=entry_policy)
        first_bar_index = cluster[0][0]
        last_bar_index = cluster[-1][0]
        if active_only and _has_later_exit(last_bar_index, exit_bar_indexes):
            continue
        text = str(selected_label.get("text") or "")
        entry = _float_or_none(bars[selected_bar_index].get("close"))
        if entry is None or entry == 0:
            continue
        returns = _forward_returns(bars, selected_bar_index, entry, horizons)
        context = _context_metrics(bars, selected_bar_index, entry)
        risk_flags = classify_pre_signal_risks(
            label=text,
            context=context,
            duplicate_count=len(cluster),
        )
        failure_class = classify_lazy_alpha_failure(returns=returns, context=context)
        outcomes.append(
            TradingViewLabelOutcome(
                symbol=symbol,
                market=market,
                signal_date=_date_from_bar(bars[selected_bar_index]),
                first_signal_date=_date_from_bar(bars[first_bar_index]),
                last_signal_date=_date_from_bar(bars[last_bar_index]),
                duplicate_count=len(cluster),
                label=text,
                entry_price=entry,
                returns=returns,
                context=context,
                risk_flags=risk_flags,
                score_penalty_hint=score_penalty_hint(risk_flags),
                failure_class=failure_class,
            )
        )
    return outcomes


def _has_later_exit(last_entry_bar_index: int, exit_bar_indexes: list[int]) -> bool:
    return any(exit_bar_index > last_entry_bar_index for exit_bar_index in exit_bar_indexes)


def _cluster_candidates(
    candidates: list[tuple[int, dict]],
    *,
    duplicate_window_bars: int,
) -> list[list[tuple[int, dict]]]:
    clusters: list[list[tuple[int, dict]]] = []
    sorted_candidates = sorted(candidates, key=lambda item: (item[0], str(item[1].get("text") or "")))
    for bar_index, label in sorted_candidates:
        if clusters and bar_index - clusters[-1][-1][0] <= duplicate_window_bars:
            clusters[-1].append((bar_index, label))
        else:
            clusters.append([(bar_index, label)])
    return clusters


def _select_cluster_entry(
    cluster: list[tuple[int, dict]],
    *,
    entry_policy: str,
) -> tuple[int, dict]:
    if entry_policy == "last":
        return cluster[-1]
    if entry_policy != "first":
        raise ValueError("entry_policy must be 'first' or 'last'")
    return cluster[0]


def classify_lazy_alpha_failure(
    *,
    returns: dict[str, float | None],
    context: dict[str, float | None],
) -> str | None:
    ret20 = returns.get("20d")
    if ret20 is None or ret20 > -5:
        return None
    ret5 = returns.get("5d")
    ret10 = returns.get("10d")
    if ret5 is not None and ret5 <= -7:
        return "외생/갭하락 의심 또는 즉시 실패"
    if ret5 is not None and ret5 < 0 and ret10 is not None and ret10 < 0:
        return "페이크/휩쏘 돌파"
    if (
        (context.get("prior_20d_return_pct") or 0) >= 30
        or (context.get("dist_sma20_pct") or 0) >= 25
        or (context.get("stop_distance_pct") or 0) >= 30
    ):
        return "과열 추격/확장 리스크"
    return "미분류: 뉴스/섹터/실적 확인 필요"


def classify_pre_signal_risks(
    *,
    label: str,
    context: dict[str, float | None],
    duplicate_count: int,
) -> list[str]:
    flags: list[str] = []
    if "추매" in label:
        flags.append("PYRAMID_ADD")
    if "추매 2" in label or "추매 3" in label:
        flags.append("LATE_PYRAMID_ADD")
    if duplicate_count >= 2:
        flags.append("DUPLICATE_SIGNAL_CLUSTER")
    if (context.get("prior_20d_return_pct") or 0) >= 50:
        flags.append("EXTREME_20D_RUNUP")
    elif (context.get("prior_20d_return_pct") or 0) >= 30:
        flags.append("HOT_20D_RUNUP")
    if (context.get("dist_sma20_pct") or 0) >= 25:
        flags.append("SMA20_EXTENSION")
    if (context.get("dist_sma50_pct") or 0) >= 40:
        flags.append("SMA50_EXTENSION")
    if (context.get("stop_distance_pct") or 0) >= 30:
        flags.append("STOP_TOO_WIDE")
    return flags


def score_penalty_hint(risk_flags: list[str]) -> int:
    penalties = {
        "PYRAMID_ADD": 3,
        "LATE_PYRAMID_ADD": 5,
        "DUPLICATE_SIGNAL_CLUSTER": 3,
        "HOT_20D_RUNUP": 5,
        "EXTREME_20D_RUNUP": 10,
        "SMA20_EXTENSION": 6,
        "SMA50_EXTENSION": 6,
        "STOP_TOO_WIDE": 8,
    }
    return min(25, sum(penalties.get(flag, 0) for flag in set(risk_flags)))


def format_tradingview_direct_report(outcomes: list[TradingViewLabelOutcome], *, title: str) -> str:
    lines = [title, f"샘플: {len(outcomes)}건", ""]
    if not outcomes:
        lines.append("TradingView Lazy Alpha 매수 라벨이 없습니다.")
        return "\n".join(lines)
    classified = Counter(item.failure_class for item in outcomes if item.failure_class)
    if classified:
        lines.append("실패 유형: " + " · ".join(f"{name} {count}건" for name, count in classified.items()))
        lines.append("")
    risk_flagged = Counter(flag for item in outcomes for flag in item.risk_flags)
    if risk_flagged:
        lines.append("사전 리스크: " + " · ".join(f"{name} {count}건" for name, count in risk_flagged.items()))
        lines.append("")
    lines.append("symbol | date | dup | penalty | label | price | 5d | 10d | 20d | class")
    lines.append("-" * 96)
    for item in outcomes:
        lines.append(
            " | ".join(
                [
                    item.symbol,
                    item.signal_date,
                    str(item.duplicate_count),
                    str(item.score_penalty_hint),
                    item.label,
                    _fmt_price(item.entry_price),
                    _fmt_pct(item.returns.get("5d")),
                    _fmt_pct(item.returns.get("10d")),
                    _fmt_pct(item.returns.get("20d")),
                    item.failure_class or "-",
                ]
            )
        )
    return "\n".join(lines)


def _forward_returns(
    bars: list[dict],
    bar_index: int,
    entry: float,
    horizons: tuple[int, ...],
) -> dict[str, float | None]:
    returns: dict[str, float | None] = {}
    for horizon in horizons:
        target = bar_index + horizon
        if target >= len(bars):
            returns[f"{horizon}d"] = None
            continue
        close = _float_or_none(bars[target].get("close"))
        returns[f"{horizon}d"] = None if close is None else round((close / entry - 1) * 100, 2)
    return returns


def _context_metrics(bars: list[dict], bar_index: int, entry: float) -> dict[str, float | None]:
    prior_20 = _close_at(bars, bar_index - 20)
    prior_low_20 = _prior_low(bars, bar_index, 20)
    sma20 = _sma_close(bars, bar_index, 20)
    sma50 = _sma_close(bars, bar_index, 50)
    stop = prior_low_20 * 0.98 if prior_low_20 is not None else None
    return {
        "prior_20d_return_pct": None if prior_20 is None else round((entry / prior_20 - 1) * 100, 2),
        "dist_sma20_pct": None if sma20 is None else round((entry / sma20 - 1) * 100, 2),
        "dist_sma50_pct": None if sma50 is None else round((entry / sma50 - 1) * 100, 2),
        "stop_distance_pct": None if stop is None else round(abs(entry - stop) / entry * 100, 2),
    }


def _close_at(bars: list[dict], index: int) -> float | None:
    if index < 0 or index >= len(bars):
        return None
    return _float_or_none(bars[index].get("close"))


def _prior_low(bars: list[dict], bar_index: int, count: int) -> float | None:
    start = max(0, bar_index - count)
    lows = [_float_or_none(bar.get("low")) for bar in bars[start:bar_index]]
    values = [value for value in lows if value is not None]
    return min(values) if values else None


def _sma_close(bars: list[dict], bar_index: int, count: int) -> float | None:
    start = bar_index - count + 1
    if start < 0:
        return None
    values = [_float_or_none(bar.get("close")) for bar in bars[start : bar_index + 1]]
    closes = [value for value in values if value is not None]
    return sum(closes) / len(closes) if len(closes) == count else None


def _date_from_bar(bar: dict) -> str:
    ts = bar.get("time")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts).date().isoformat()
    return str(ts or "")


def _float_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_price(value: float) -> str:
    return f"{value:,.0f}" if value >= 100 else f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
