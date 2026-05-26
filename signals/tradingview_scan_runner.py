"""Run TradingView CLI scans for Lazy Alpha labels."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from signals.independence import format_independence_alert, decide_independence
from signals.leading_discovery import SupplyScore, score_supply_accumulation
from signals.market import Market, ticker_for_lookup
from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelFlowItem,
    TradingViewLabelOutcome,
    TradingViewTableSnapshot,
    classify_priority_risks,
    evaluate_lazy_alpha_state,
    interpret_lazy_alpha_flow,
    map_lazy_alpha_labels_to_flow,
    map_lazy_alpha_labels_to_exclusions,
    map_lazy_alpha_labels_to_outcomes,
    parse_lazy_alpha_tables,
)
from utils.ticker import load_ticker_cache

SUPPORTED_PREFIXES = ("NASDAQ:", "NYSE:", "AMEX:", "KRX:", "TSE:", "TYO:", "JPX:")
US_PREFIXES = ("NASDAQ:", "NYSE:", "AMEX:")
JP_PREFIXES = ("TSE:", "TYO:", "JPX:")
PREFERRED_WATCHLIST_KEYWORDS = ("관심", "예비", "jesse", "국장", "미장", "일본", "us", "jp")


@dataclass(frozen=True)
class TradingViewScanResult:
    outcomes: list[TradingViewLabelOutcome]
    exclusions: list[TradingViewExcludedSignal]
    errors: list[tuple[str, str]]
    scanned: list[str]
    label_flows: dict[str, list[TradingViewLabelFlowItem]]
    table_snapshots: dict[str, TradingViewTableSnapshot | None]


@dataclass(frozen=True)
class KrSignalEnrichment:
    supply: str
    supply_score: SupplyScore
    fundamental: str
    auditor: str
    independence_alert: str


class TradingViewCli:
    def __init__(self, mcp_dir: Path, *, timeout_seconds: float | None = None) -> None:
        self.mcp_dir = mcp_dir
        self.cli = ["node", "src/cli/index.js"]
        self.timeout_seconds = timeout_seconds or float(os.getenv("TRADINGVIEW_CLI_TIMEOUT", "30"))

    def run(self, args: list[str]) -> dict:
        result = subprocess.run(
            [*self.cli, *args],
            cwd=self.mcp_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        return json.loads(result.stdout)


def scan_tradingview_symbols(
    symbols: list[str],
    *,
    mcp_dir: Path,
    bars: int = 500,
    max_labels: int = 250,
    timeframe: str = "D",
    duplicate_window_bars: int = 5,
    entry_policy: str = "first",
    sleep_seconds: float = 2.0,
    runner: TradingViewCli | None = None,
) -> TradingViewScanResult:
    cli = runner or TradingViewCli(mcp_dir)
    outcomes: list[TradingViewLabelOutcome] = []
    exclusions: list[TradingViewExcludedSignal] = []
    errors: list[tuple[str, str]] = []
    scanned: list[str] = []
    label_flows: dict[str, list[TradingViewLabelFlowItem]] = {}
    table_snapshots: dict[str, TradingViewTableSnapshot | None] = {}
    for symbol in symbols:
        try:
            cli.run(["symbol", symbol])
            time.sleep(sleep_seconds)
            cli.run(["timeframe", timeframe])
            time.sleep(sleep_seconds)
            ohlcv = cli.run(["ohlcv", "-n", str(bars)])
            labels = cli.run(["data", "labels", "--filter", "Lazy", "--max", str(max_labels), "--verbose"])
            try:
                tables = cli.run(["data", "tables", "--filter", "Lazy"])
                table_snapshots[symbol] = parse_lazy_alpha_tables(tables)
            except Exception:  # pragma: no cover - optional TradingView table boundary
                table_snapshots[symbol] = None
            study_labels = [
                label
                for study in labels.get("studies", [])
                for label in study.get("labels", [])
            ]
            market = market_for_symbol(symbol)
            bars_payload = ohlcv.get("bars", [])
            total_available = ohlcv.get("total_available")
            outcomes.extend(
                map_lazy_alpha_labels_to_outcomes(
                    symbol=symbol,
                    market=market,
                    bars=bars_payload,
                    labels=study_labels,
                    total_available=total_available,
                    duplicate_window_bars=duplicate_window_bars,
                    entry_policy=entry_policy,
                    active_only=True,
                )
            )
            exclusions.extend(
                map_lazy_alpha_labels_to_exclusions(
                    symbol=symbol,
                    market=market,
                    bars=bars_payload,
                    labels=study_labels,
                    total_available=total_available,
                    duplicate_window_bars=duplicate_window_bars,
                    entry_policy=entry_policy,
                )
            )
            label_flows[symbol] = map_lazy_alpha_labels_to_flow(
                bars=bars_payload,
                labels=study_labels,
                lookback_bars=22,
                limit=8,
            )
            scanned.append(symbol)
        except Exception as exc:  # pragma: no cover - external CLI boundary
            errors.append((symbol, str(exc)))
    return TradingViewScanResult(
        outcomes=outcomes,
        exclusions=exclusions,
        errors=errors,
        scanned=scanned,
        label_flows=label_flows,
        table_snapshots=table_snapshots,
    )


def symbols_from_universe(path: Path, *, limit: int, market: str | None = None) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    preferred: list[str] = []
    fallback: list[str] = []
    for symbol, meta in data.get("symbols", {}).items():
        if not symbol.startswith(SUPPORTED_PREFIXES):
            continue
        if market and market_for_symbol(symbol) != market.upper():
            continue
        watchlists = " ".join(meta.get("watchlists", [])).lower()
        target = preferred if any(keyword in watchlists for keyword in PREFERRED_WATCHLIST_KEYWORDS) else fallback
        target.append(symbol)
    return [*preferred, *fallback][:limit]


def normalize_scan_symbol(token: str) -> str:
    value = token.strip().upper()
    if not value:
        return value
    if ":" in value:
        return value
    if value.isdigit() and len(value) == 6:
        return f"KRX:{value}"
    return f"NASDAQ:{value}"


def market_for_symbol(symbol: str) -> str:
    if symbol.startswith("KRX:"):
        return "KR"
    if symbol.startswith(US_PREFIXES):
        return "US"
    if symbol.startswith(JP_PREFIXES):
        return "JP"
    return "UNKNOWN"


def format_scan_report(
    *,
    outcomes: list[TradingViewLabelOutcome],
    errors: list[tuple[str, str]],
    scanned: list[str],
    title: str = "📡 TradingView 직접 스캔",
    enrichments: dict[str, KrSignalEnrichment] | None = None,
    exclusions: list[TradingViewExcludedSignal] | None = None,
    table_snapshots: dict[str, TradingViewTableSnapshot | None] | None = None,
    label_flows: dict[str, list[TradingViewLabelFlowItem]] | None = None,
    include_exclusions: bool = True,
    requested_count: int | None = None,
    batch_count: int | None = None,
) -> str:
    current_exclusions = current_exclusions_for_report(
        outcomes=outcomes,
        exclusions=exclusions or [],
    )
    exclusion_count = len(current_exclusions)
    scan_summary = f"스캔: {len(scanned)}종목 · 활성 후보: {len(outcomes)}건"
    if include_exclusions:
        scan_summary += f" · 제외: {exclusion_count}건"
    header = title if title.startswith("📡") else f"📡 TradingView 직접 스캔 — {title}"
    lines = [
        header,
        "기준: 웹훅 저장소가 아니라 현재 열린 TradingView 차트의 Lazy Alpha 라벨을 직접 읽음",
        scan_summary,
    ]
    if scanned:
        lines.append("대상: " + ", ".join(scanned[:12]))
    if requested_count is not None and batch_count is not None:
        lines.append(f"요청: {requested_count}종목 · 배치: {batch_count}회")
    if errors:
        lines.append("오류: " + " · ".join(f"{symbol}" for symbol, _error in errors[:5]))
    lines.append("")
    lines.extend(
        format_telegram_outcome_cards(
            sorted(outcomes, key=priority_sort_key),
            enrichments=enrichments,
            table_snapshots=table_snapshots,
            label_flows=label_flows,
        )
    )
    if include_exclusions and current_exclusions:
        lines.append("")
        lines.extend(format_telegram_exclusion_cards(current_exclusions, enrichments=enrichments))
    return "\n".join(lines)


def current_exclusions_for_report(
    *,
    outcomes: list[TradingViewLabelOutcome],
    exclusions: list[TradingViewExcludedSignal],
) -> list[TradingViewExcludedSignal]:
    active_symbols = {item.symbol for item in outcomes}
    latest_by_symbol: dict[str, TradingViewExcludedSignal] = {}
    for item in exclusions:
        if item.symbol in active_symbols:
            continue
        previous = latest_by_symbol.get(item.symbol)
        if previous is None or (item.exit_bar_index, item.entry_bar_index) > (previous.exit_bar_index, previous.entry_bar_index):
            latest_by_symbol[item.symbol] = item
    return sorted(latest_by_symbol.values(), key=lambda row: (row.exit_bar_index, row.symbol), reverse=True)


def priority_sort_key(item: TradingViewLabelOutcome) -> tuple[int, str]:
    return (adjusted_priority_penalty(item), item.signal_date)


def adjusted_priority_penalty(item: TradingViewLabelOutcome) -> int:
    return item.score_penalty_hint + priority_penalty(item)


def priority_penalty(item: TradingViewLabelOutcome) -> int:
    penalties = {
        "PRICE_ALREADY_MOVED_5D": 10,
        "PRICE_ALREADY_MOVED_10D": 10,
        "PRICE_ALREADY_MOVED_20D": 8,
        "CURRENT_SMA20_EXTENSION": 6,
        "CURRENT_SMA50_EXTENSION": 6,
    }
    flags = classify_priority_risks(returns=item.returns, context=item.context)
    return min(30, sum(penalties.get(flag, 0) for flag in set(flags)))


def format_telegram_outcome_cards(
    outcomes: list[TradingViewLabelOutcome],
    *,
    ticker_cache: list[dict] | None = None,
    enrichments: dict[str, KrSignalEnrichment] | None = None,
    table_snapshots: dict[str, TradingViewTableSnapshot | None] | None = None,
    label_flows: dict[str, list[TradingViewLabelFlowItem]] | None = None,
) -> list[str]:
    if not outcomes:
        return [
            "활성 매수 후보: 0건",
            "",
            "판정: 현재 매수 후보 없음",
            "진입 이후 손절/청산/이탈/SELL 라벨이 나온 종목은 활성 후보에서 제외했습니다.",
        ]

    cache = ticker_cache if ticker_cache is not None else _load_ticker_cache_safely()
    ordered_outcomes = sorted(
        outcomes,
        key=lambda row: _card_sort_key(row, enrichments or {}, label_flows or {}),
    )
    lines = [f"활성 매수 후보: {len(ordered_outcomes)}건"]
    for index, item in enumerate(ordered_outcomes, start=1):
        priority_risks = classify_priority_risks(returns=item.returns, context=item.context)
        combined_risks = [*item.risk_flags, *priority_risks]
        risk = "없음" if not combined_risks else ", ".join(combined_risks)
        adjusted_penalty = adjusted_priority_penalty(item)
        interpretation = interpret_lazy_alpha_flow((label_flows or {}).get(item.symbol, []))
        flow_adjustment = interpretation.score_adjustment if interpretation else 0
        score = max(0, min(100, 100 - adjusted_penalty + flow_adjustment))
        status = "매수 후보 유지" if adjusted_penalty == 0 else f"주의 필요 · 감점 {adjusted_penalty}"
        price_unit = "원" if item.market == "KR" else ""
        table = (table_snapshots or {}).get(item.symbol)
        decision = evaluate_lazy_alpha_state(
            outcome_label=item.label,
            table_signal=table.signal if table else None,
            table_conviction=table.conviction if table else None,
            table_buy_eligibility=table.buy_eligibility if table else None,
            table_score=table.aux_score if table else None,
            penalty=adjusted_penalty,
        )
        enrichment = (enrichments or {}).get(item.symbol)
        score_label = f"기술점수 {score}점"
        if enrichment:
            composite_score = _composite_signal_score(score, enrichment.supply_score.score)
            score_label = f"종합점수 {composite_score}점 · 기술점수 {score}점"
        lines.extend(
            [
                "",
                f"{index}. {symbol_display_name(item.symbol, ticker_cache=cache)} · {score_label}",
                f"최종판정: {decision.verdict} · {decision.reason}",
                f"행동: {decision.action}",
                f"판정: {status}",
                f"시그널: {item.signal_date} · {item.label} · 중복 {item.duplicate_count}회",
                f"신호 기준가: {_fmt_price(item.entry_price)}{price_unit}",
                f"감점 사유: {risk}",
            ]
        )
        if enrichment:
            lines.extend(
                [
                    f"독립성알림: {enrichment.independence_alert}",
                    f"감사인: {enrichment.auditor}",
                    f"수급: {enrichment.supply}",
                    f"수급점수: {enrichment.supply_score.score}/35 · {enrichment.supply_score.state}",
                    f"실적/밸류: {enrichment.fundamental}",
                ]
            )
            if enrichment.supply_score.evidence:
                lines.append("수급근거: " + " · ".join(enrichment.supply_score.evidence[:3]))
            if enrichment.supply_score.risks:
                lines.append("수급리스크: " + " · ".join(enrichment.supply_score.risks[:2]))
        if table:
            lines.extend(format_lazy_alpha_table_card_lines(table))
        if interpretation:
            lines.extend(
                [
                    (
                        "흐름평가: "
                        f"{interpretation.pattern} · {interpretation.confidence} · "
                        f"점수영향 {interpretation.score_adjustment:+d}"
                    ),
                    f"흐름행동: {interpretation.action}",
                ]
            )
        if item.failure_class:
            lines.append(f"실패분류: {item.failure_class}")
    return lines


def _card_sort_key(
    item: TradingViewLabelOutcome,
    enrichments: dict[str, KrSignalEnrichment],
    label_flows: dict[str, list[TradingViewLabelFlowItem]],
) -> tuple[int, int, str]:
    interpretation = interpret_lazy_alpha_flow(label_flows.get(item.symbol, []))
    flow_adjustment = interpretation.score_adjustment if interpretation else 0
    technical_score = max(0, min(100, 100 - adjusted_priority_penalty(item) + flow_adjustment))
    enrichment = enrichments.get(item.symbol)
    if enrichment:
        return (-_composite_signal_score(technical_score, enrichment.supply_score.score), adjusted_priority_penalty(item), item.symbol)
    return (-technical_score, adjusted_priority_penalty(item), item.symbol)


def _composite_signal_score(technical_score: int, supply_score: int) -> int:
    return max(0, min(100, round(technical_score * 0.75 + (supply_score / 35) * 25)))


def format_lazy_alpha_table_card_lines(table: TradingViewTableSnapshot) -> list[str]:
    lines: list[str] = []
    if table.aux_score is not None or table.conviction:
        score = f"{table.aux_score}점" if table.aux_score is not None else "-"
        lines.append(f"Lazy 원점수: {score} · 확신 {table.conviction or '-'}")
    status_parts = [part for part in [table.signal, table.buy_eligibility] if part]
    if status_parts:
        lines.append("Lazy 상태: " + " · ".join(status_parts))
    trend_parts = []
    if table.ema_alignment:
        trend_parts.append(table.ema_alignment)
    if table.rs_score is not None:
        trend_parts.append(f"RS {table.rs_score}점")
    if table.volume_strength is not None:
        trend_parts.append(f"거래량 {table.volume_strength:g}배")
    if table.high_52w_pct is not None:
        trend_parts.append(f"52주고점 {table.high_52w_pct:+g}%")
    if trend_parts:
        lines.append("Lazy 추세: " + " · ".join(trend_parts))
    evidence_parts = []
    if table.aux_signal:
        evidence_parts.append(table.aux_signal)
    if table.smart_eval:
        evidence_parts.append(table.smart_eval)
    if evidence_parts:
        lines.append("Lazy 근거: " + " · ".join(evidence_parts))
    market_parts = [part for part in [table.market_sector, table.trend_energy, table.market_control] if part]
    if market_parts:
        lines.append("Lazy 시장: " + " · ".join(market_parts))
    risk_parts = []
    if table.stop_loss is not None:
        risk_parts.append(f"SL {_fmt_price(table.stop_loss)} ({_fmt_signed_pct(table.stop_loss_pct)})")
    if table.target_price is not None:
        risk_parts.append(f"TP1 {_fmt_price(table.target_price)} ({_fmt_signed_pct(table.target_return_pct)})")
    if table.risk_reward:
        risk_parts.append(f"R/R {table.risk_reward}")
    if risk_parts:
        lines.append("Lazy 리스크: " + " · ".join(risk_parts))
    if table.fundamental:
        lines.append(f"Lazy 펀더멘털: {table.fundamental}")
    if table.eps_growth or table.sales_growth:
        growth_parts = []
        if table.eps_growth:
            growth_parts.append("EPS " + " / ".join(table.eps_growth))
        if table.sales_growth:
            growth_parts.append("Sales " + " / ".join(table.sales_growth))
        lines.append("Lazy 성장: " + " · ".join(growth_parts))
    return lines


def format_telegram_exclusion_cards(
    exclusions: list[TradingViewExcludedSignal],
    *,
    ticker_cache: list[dict] | None = None,
    enrichments: dict[str, KrSignalEnrichment] | None = None,
    limit: int = 12,
) -> list[str]:
    cache = ticker_cache if ticker_cache is not None else _load_ticker_cache_safely()
    reason_counts = Counter(_compact_label(item.exit_label) for item in exclusions)
    lines = [
        f"제외 후보: {len(exclusions)}건",
        "기준: 진입 이후 손절/청산/이탈/SELL 라벨 확인",
    ]
    if reason_counts:
        summary = " · ".join(f"{reason} {count}건" for reason, count in reason_counts.most_common(5))
        lines.append(f"주요 제외 사유: {summary}")
    for index, item in enumerate(
        sorted(exclusions, key=lambda row: (row.exit_bar_index, row.symbol), reverse=True)[:limit],
        start=1,
    ):
        exit_date = item.exit_date or "차트 우측 최신 라벨"
        decision = evaluate_lazy_alpha_state(exclusion_label=item.exit_label)
        enrichment = (enrichments or {}).get(item.symbol)
        lines.extend(
            [
                "",
                f"{index}. {symbol_display_name(item.symbol, ticker_cache=cache)}",
                f"제외: {exit_date} · {_compact_label(item.exit_label)}",
                f"분류: {decision.verdict} · {decision.reason}",
                f"행동: {decision.action}",
                f"직전 진입: {item.signal_date} · {_compact_label(item.label)}",
            ]
        )
        if enrichment:
            lines.extend(
                [
                    f"독립성알림: {enrichment.independence_alert}",
                    f"감사인: {enrichment.auditor}",
                ]
            )
    return lines


def build_kr_signal_enrichments(
    outcomes: list[TradingViewLabelOutcome],
    *,
    supply_lookup: Callable[[str], dict],
    fundamental_lookup: Callable[[str], dict],
    audit_lookup: Callable[[str], dict],
) -> dict[str, KrSignalEnrichment]:
    enrichments: dict[str, KrSignalEnrichment] = {}
    for item in outcomes:
        if item.market != "KR":
            continue
        ticker = ticker_for_lookup(item.symbol, "KR")
        if not ticker.isdigit() or len(ticker) != 6:
            continue
        supply = _safe_lookup(supply_lookup, ticker)
        fundamental = _safe_lookup(fundamental_lookup, ticker)
        audit = _safe_lookup(audit_lookup, ticker)
        decision = decide_independence(Market("KR", "한국"), audit)
        enrichments[item.symbol] = KrSignalEnrichment(
            supply=_format_supply_summary(supply),
            supply_score=score_supply_accumulation(supply),
            fundamental=_format_fundamental_summary(fundamental),
            auditor=_format_auditor_summary(decision.status, decision.auditor, decision.reason),
            independence_alert=format_independence_alert(decision),
        )
    return enrichments


def _safe_lookup(lookup: Callable[[str], dict], ticker: str) -> dict:
    try:
        return lookup(ticker)
    except Exception as exc:
        return {"error": str(exc)}


def _format_supply_summary(supply: dict) -> str:
    if supply.get("error"):
        return "데이터 없음"
    inst = supply.get("institution") or {}
    fore = supply.get("foreigner") or {}
    return (
        f"기관 오늘 {_fmt_amount_krw(inst.get('today'))} / 5일 {_fmt_amount_krw(inst.get('5d'))} · "
        f"외국인 오늘 {_fmt_amount_krw(fore.get('today'))} / 5일 {_fmt_amount_krw(fore.get('5d'))}"
    )


def _format_fundamental_summary(fundamental: dict) -> str:
    if fundamental.get("error"):
        return "데이터 없음"
    financials = fundamental.get("financials") or []
    ratios = fundamental.get("ratios") or {}
    parts: list[str] = []
    if financials:
        latest = sorted(financials, key=lambda row: row.get("year") or 0)[-1]
        parts.append(f"매출 {latest.get('year')} {_fmt_amount_krw(latest.get('revenue'), signed=False)}")
        parts.append(f"영업익 {_fmt_amount_krw(latest.get('operating_income'))}")
    if ratios:
        if ratios.get("per") is not None:
            parts.append(f"PER {ratios.get('per'):.2f}x")
        if ratios.get("pbr") is not None:
            parts.append(f"PBR {ratios.get('pbr'):.2f}x")
    return " · ".join(parts) if parts else "데이터 없음"


def _format_auditor_summary(status: str, auditor: str | None, reason: str) -> str:
    labels = {
        "BLOCKED_CONFIRMED": "독립성 차단",
        "BLOCKED_POSSIBLE": "독립성 차단 가능",
        "CLEAR_CONFIRMED": "차단 없음",
        "ROLLOVER_INFERRED": "감사인 추정 확인 필요",
        "MANUAL_VERIFY_CURRENT_YEAR": "현재연도 감사인 확인 필요",
        "DATA_MISSING": "감사인 데이터 없음",
    }
    return f"{labels.get(status, status)} · {auditor or '-'} · {reason}"


def _compact_label(text: str) -> str:
    return " / ".join(part.strip() for part in text.splitlines() if part.strip()) or "-"


def _fmt_amount_krw(value: int | float | None, *, signed: bool = True) -> str:
    if value is None:
        return "-"
    eok = round(value / 1e8)
    sign = "+" if signed and eok > 0 else ""
    return f"{sign}{eok:,}억"


def symbol_display_name(symbol: str, *, ticker_cache: list[dict] | None = None) -> str:
    if not symbol.startswith("KRX:"):
        return symbol
    code = symbol.split(":", 1)[1]
    cache = ticker_cache if ticker_cache is not None else _load_ticker_cache_safely()
    for item in cache:
        if str(item.get("code")) == code:
            return f"{symbol} · {item.get('name')}"
    return symbol


def _load_ticker_cache_safely() -> list[dict]:
    try:
        return load_ticker_cache()
    except Exception:
        return []


def _fmt_price(value: float) -> str:
    return f"{value:,.0f}" if value >= 100 else f"{value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _fmt_signed_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+g}%"
