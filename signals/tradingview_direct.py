"""TradingView direct Lazy Alpha label outcome mapping."""

from __future__ import annotations

import re
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


@dataclass(frozen=True)
class TradingViewExcludedSignal:
    symbol: str
    market: str
    signal_date: str
    label: str
    exit_date: str | None
    exit_label: str
    entry_bar_index: int
    exit_bar_index: int
    risk_flags: list[str]
    score_penalty_hint: int


@dataclass(frozen=True)
class TradingViewLabelFlowItem:
    date: str
    label: str
    bar_index: int


@dataclass(frozen=True)
class TradingViewFlowInterpretation:
    stage: str
    summary: str
    risk: str
    action: str


@dataclass(frozen=True)
class TradingViewTableSnapshot:
    signal: str | None
    conviction: str | None
    smart_eval: str | None
    ema_alignment: str | None
    aux_score: int | None
    aux_signal: str | None
    market_sector: str | None
    trend_energy: str | None
    market_control: str | None
    rs_score: int | None
    volume_strength: float | None
    high_52w_pct: float | None
    stop_loss: float | None
    stop_loss_pct: float | None
    target_price: float | None
    target_return_pct: float | None
    risk_reward: str | None
    buy_eligibility: str | None
    fundamental: str | None
    eps_growth: list[str]
    sales_growth: list[str]
    raw_rows: list[str]


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
    "SELL",
    "매도",
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
    "SELL",
    "매도",
)

FLOW_LABEL_KEYWORDS = (
    "셋업",
    "진입",
    "추매",
    "돌파",
    "청산",
    "손절",
    "익절",
    "이탈",
    "SELL",
    "매도",
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
    shift = _label_bar_shift(bars, labels)
    candidates: list[tuple[int, dict]] = []
    exit_bar_indexes: list[int] = []
    for label in labels:
        text = str(label.get("text") or "")
        x_value = label.get("x")
        if not isinstance(x_value, int):
            continue
        bar_index = x_value + shift
        if bar_index < 0:
            continue
        if is_lazy_alpha_exit_label(text):
            exit_bar_indexes.append(bar_index)
            continue
        if bar_index >= len(bars):
            continue
        if is_lazy_alpha_buy_label(text):
            candidates.append((bar_index, label))

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


def map_lazy_alpha_labels_to_exclusions(
    *,
    symbol: str,
    market: str,
    bars: list[dict],
    labels: list[dict],
    total_available: int | None = None,
    duplicate_window_bars: int = 5,
    entry_policy: str = "first",
) -> list[TradingViewExcludedSignal]:
    if not bars:
        return []
    shift = _label_bar_shift(bars, labels)
    candidates: list[tuple[int, dict]] = []
    exits: list[tuple[int, dict]] = []
    for label in labels:
        text = str(label.get("text") or "")
        x_value = label.get("x")
        if not isinstance(x_value, int):
            continue
        bar_index = x_value + shift
        if bar_index < 0:
            continue
        if is_lazy_alpha_exit_label(text):
            exits.append((bar_index, label))
            continue
        if bar_index >= len(bars):
            continue
        if is_lazy_alpha_buy_label(text):
            candidates.append((bar_index, label))

    excluded: list[TradingViewExcludedSignal] = []
    for cluster in _cluster_candidates(candidates, duplicate_window_bars=duplicate_window_bars):
        selected_bar_index, selected_label = _select_cluster_entry(cluster, entry_policy=entry_policy)
        last_bar_index = cluster[-1][0]
        later_exits = [(bar_index, label) for bar_index, label in exits if bar_index > last_bar_index]
        if not later_exits:
            continue
        exit_bar_index, exit_label = min(later_exits, key=lambda item: item[0])
        text = str(selected_label.get("text") or "")
        entry = _float_or_none(bars[selected_bar_index].get("close"))
        context = _context_metrics(bars, selected_bar_index, entry or 0)
        risk_flags = classify_pre_signal_risks(
            label=text,
            context=context,
            duplicate_count=len(cluster),
        )
        excluded.append(
            TradingViewExcludedSignal(
                symbol=symbol,
                market=market,
                signal_date=_date_from_bar(bars[selected_bar_index]),
                label=text,
                exit_date=_date_from_bar(bars[exit_bar_index]) if exit_bar_index < len(bars) else None,
                exit_label=str(exit_label.get("text") or ""),
                entry_bar_index=selected_bar_index,
                exit_bar_index=exit_bar_index,
                risk_flags=risk_flags,
                score_penalty_hint=score_penalty_hint(risk_flags),
            )
        )
    return excluded


def map_lazy_alpha_labels_to_flow(
    *,
    bars: list[dict],
    labels: list[dict],
    lookback_bars: int = 22,
    limit: int = 8,
) -> list[TradingViewLabelFlowItem]:
    if not bars:
        return []
    shift = _label_bar_shift(bars, labels)
    min_bar_index = max(0, len(bars) - lookback_bars)
    items: list[TradingViewLabelFlowItem] = []
    seen: set[tuple[int, str]] = set()
    for label in labels:
        text = str(label.get("text") or "").strip()
        x_value = label.get("x")
        if not text or not isinstance(x_value, int):
            continue
        if not _is_flow_label(text):
            continue
        bar_index = x_value + shift
        if bar_index < min_bar_index or bar_index >= len(bars):
            continue
        compact = _compact_flow_label(text)
        key = (bar_index, compact)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            TradingViewLabelFlowItem(
                date=_date_from_bar(bars[bar_index]),
                label=compact,
                bar_index=bar_index,
            )
        )
    return sorted(items, key=lambda item: (item.bar_index, item.label))[-limit:]


def interpret_lazy_alpha_flow(flow: list[TradingViewLabelFlowItem]) -> TradingViewFlowInterpretation | None:
    if not flow:
        return None
    events = [_flow_event_type(item.label) for item in flow]
    latest = events[-1]
    exit_count = sum(1 for event in events if event in {"EXIT", "WHIPSAW"})
    has_setup = "SETUP" in events
    has_breakout = "BREAKOUT" in events
    has_add = latest == "ADD"
    has_entry_after_exit = _has_entry_after_exit(events)

    if latest == "ADD":
        stage = "재진입 후 추매 단계" if has_entry_after_exit else "추매 단계"
        action = "신규 추격보다 눌림/손절선 기준 확인"
    elif latest == "BREAKOUT":
        stage = "돌파 확인"
        action = "돌파 유지와 거래량 지속 확인"
    elif latest == "ENTRY":
        stage = "초기 진입"
        action = "초기 진입 후보, 무효화 라벨 발생 여부 확인"
    elif latest == "SETUP":
        stage = "셋업 형성"
        action = "진입 라벨 대기"
    elif latest in {"EXIT", "WHIPSAW"}:
        stage = "청산/이탈 후 대기"
        action = "재셋업 전까지 관망"
    else:
        stage = "관찰"
        action = "라벨 전환 확인"

    summary_parts: list[str] = []
    if has_setup and has_breakout:
        summary_parts.append("셋업 후 돌파 진입")
    elif has_breakout:
        summary_parts.append("돌파 진입 확인")
    elif "ENTRY" in events:
        summary_parts.append("진입 라벨 확인")
    if has_add:
        summary_parts.append("현재 추매 라벨")
    if has_entry_after_exit:
        summary_parts.append("청산 후 재진입")
    summary = " · ".join(summary_parts) if summary_parts else "주요 전환 라벨 확인"

    if exit_count >= 2:
        risk = f"청산/이탈 {exit_count}회로 휩쏘 이력 주의"
    elif exit_count == 1:
        risk = "최근 청산/이탈 이력 1회"
    else:
        risk = "최근 청산/이탈 라벨 없음"

    return TradingViewFlowInterpretation(
        stage=stage,
        summary=summary,
        risk=risk,
        action=action,
    )


def parse_lazy_alpha_tables(payload: dict) -> TradingViewTableSnapshot | None:
    rows = [
        str(row)
        for study in payload.get("studies", [])
        if "Lazy" in str(study.get("name", ""))
        for table in study.get("tables", [])
        for row in table.get("rows", [])
    ]
    if not rows:
        return None

    values: dict[str, str] = {}
    eps_growth: list[str] = []
    sales_growth: list[str] = []
    for row in rows:
        parts = [part.strip() for part in row.split("|")]
        if len(parts) < 2:
            continue
        key = parts[0]
        value = " | ".join(part for part in parts[1:] if part)
        value = _normalize_table_value(value)
        if key == "EPS":
            eps_growth = [_normalize_table_value(part) for part in parts[1:] if part.strip()]
            continue
        if key == "Sales":
            sales_growth = [_normalize_table_value(part) for part in parts[1:] if part.strip()]
            continue
        values[key] = value

    aux_score, aux_signal = _parse_aux_signal(values.get("보조 신호"))
    stop_loss, stop_loss_pct = _parse_price_pct(values.get("손절 관리(SL)"))
    target_price, target_return_pct = _parse_price_pct(values.get("목표 수익(TP1)"))
    return TradingViewTableSnapshot(
        signal=values.get("시그널"),
        conviction=values.get("확신 등급"),
        smart_eval=values.get("SMART 평가"),
        ema_alignment=values.get("EMA 정렬"),
        aux_score=aux_score,
        aux_signal=aux_signal,
        market_sector=values.get("시장/섹터"),
        trend_energy=values.get("추세 에너지"),
        market_control=values.get("시장 주도권"),
        rs_score=_parse_int(values.get("상대 강도(RS)")),
        volume_strength=_parse_float(values.get("거래량 강도")),
        high_52w_pct=_parse_float(values.get("52주 고점%")),
        stop_loss=stop_loss,
        stop_loss_pct=stop_loss_pct,
        target_price=target_price,
        target_return_pct=target_return_pct,
        risk_reward=values.get("실시간 손익비"),
        buy_eligibility=values.get("매수 자격"),
        fundamental=values.get("펀더멘털"),
        eps_growth=eps_growth,
        sales_growth=sales_growth,
        raw_rows=rows,
    )


def _has_later_exit(last_entry_bar_index: int, exit_bar_indexes: list[int]) -> bool:
    return any(exit_bar_index > last_entry_bar_index for exit_bar_index in exit_bar_indexes)


def _label_bar_shift(bars: list[dict], labels: list[dict]) -> int:
    x_values = [label.get("x") for label in labels if isinstance(label.get("x"), int)]
    if not x_values:
        return 0
    max_x = max(x_values)
    right_edge_gap = (len(bars) - 1) - max_x
    if right_edge_gap > 50:
        return right_edge_gap
    return 0


def _is_flow_label(text: str) -> bool:
    if text in {"PBB", "PBS", "Vol", "NH", "T", "W", "●", "🔥", "❄️"}:
        return False
    return any(keyword in text for keyword in FLOW_LABEL_KEYWORDS)


def _compact_flow_label(text: str) -> str:
    return " / ".join(part.strip() for part in text.splitlines() if part.strip()) or text.strip()


def _flow_event_type(label: str) -> str:
    if "셋업" in label:
        return "SETUP"
    if "추매" in label:
        return "ADD"
    if "돌파" in label and "진입" in label:
        return "BREAKOUT"
    if "진입" in label:
        return "ENTRY"
    if "휩소" in label or "휩쏘" in label or "이탈" in label:
        return "WHIPSAW"
    if is_lazy_alpha_exit_label(label):
        return "EXIT"
    return "OTHER"


def _has_entry_after_exit(events: list[str]) -> bool:
    seen_exit = False
    for event in events:
        if event in {"EXIT", "WHIPSAW"}:
            seen_exit = True
        elif seen_exit and event in {"ENTRY", "BREAKOUT", "ADD"}:
            return True
    return False


def _normalize_table_value(value: str) -> str:
    return " / ".join(part.strip() for part in value.splitlines() if part.strip())


def _parse_aux_signal(value: str | None) -> tuple[int | None, str | None]:
    if not value:
        return None, None
    score = _parse_int(value)
    parts = [part.strip() for part in value.split("|") if part.strip()]
    signal = parts[-1] if len(parts) >= 2 else None
    return score, signal


def _parse_price_pct(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    numbers = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", value)
    price = _parse_float(numbers[0]) if numbers else None
    pct = _parse_float(numbers[1]) if len(numbers) > 1 else None
    return price, pct


def _parse_int(value: str | None) -> int | None:
    parsed = _parse_float(value)
    return None if parsed is None else int(parsed)


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


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


def classify_priority_risks(
    *,
    returns: dict[str, float | None],
    context: dict[str, float | None],
) -> list[str]:
    flags: list[str] = []
    ret5 = returns.get("5d")
    ret10 = returns.get("10d")
    ret20 = returns.get("20d")
    if ret5 is not None and ret5 >= 15:
        flags.append("PRICE_ALREADY_MOVED_5D")
    if ret10 is not None and ret10 >= 25:
        flags.append("PRICE_ALREADY_MOVED_10D")
    if ret20 is not None and ret20 >= 35:
        flags.append("PRICE_ALREADY_MOVED_20D")
    if (context.get("dist_sma20_pct") or 0) >= 20:
        flags.append("CURRENT_SMA20_EXTENSION")
    if (context.get("dist_sma50_pct") or 0) >= 35:
        flags.append("CURRENT_SMA50_EXTENSION")
    if flags:
        flags.append("PRIORITY_DOWN_ALREADY_REFLECTED")
    return flags


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
