"""Run TradingView CLI scans for Lazy Alpha labels."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from signals.independence import decide_independence
from signals.market import Market, ticker_for_lookup
from signals.tradingview_direct import (
    TradingViewExcludedSignal,
    TradingViewLabelOutcome,
    classify_priority_risks,
    map_lazy_alpha_labels_to_exclusions,
    map_lazy_alpha_labels_to_outcomes,
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


@dataclass(frozen=True)
class KrSignalEnrichment:
    supply: str
    fundamental: str
    auditor: str


class TradingViewCli:
    def __init__(self, mcp_dir: Path) -> None:
        self.mcp_dir = mcp_dir
        self.cli = ["node", "src/cli/index.js"]

    def run(self, args: list[str]) -> dict:
        result = subprocess.run(
            [*self.cli, *args],
            cwd=self.mcp_dir,
            check=True,
            capture_output=True,
            text=True,
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
    for symbol in symbols:
        try:
            cli.run(["symbol", symbol])
            time.sleep(sleep_seconds)
            cli.run(["timeframe", timeframe])
            time.sleep(sleep_seconds)
            ohlcv = cli.run(["ohlcv", "-n", str(bars)])
            labels = cli.run(["data", "labels", "--filter", "Lazy", "--max", str(max_labels), "--verbose"])
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
            scanned.append(symbol)
        except Exception as exc:  # pragma: no cover - external CLI boundary
            errors.append((symbol, str(exc)))
    return TradingViewScanResult(outcomes=outcomes, exclusions=exclusions, errors=errors, scanned=scanned)


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
) -> str:
    lines = [
        f"📡 TradingView 직접 스캔 — {title}" if "TradingView 직접 스캔" not in title else title,
        "기준: 웹훅 저장소가 아니라 현재 열린 TradingView 차트의 Lazy Alpha 라벨을 직접 읽음",
        f"스캔: {len(scanned)}종목 · 활성 후보: {len(outcomes)}건 · 제외: {len(exclusions or [])}건",
    ]
    if scanned:
        lines.append("대상: " + ", ".join(scanned[:12]))
    if errors:
        lines.append("오류: " + " · ".join(f"{symbol}" for symbol, _error in errors[:5]))
    lines.append("")
    lines.extend(
        format_telegram_outcome_cards(
            sorted(outcomes, key=priority_sort_key),
            enrichments=enrichments,
        )
    )
    if exclusions:
        lines.append("")
        lines.extend(format_telegram_exclusion_cards(exclusions))
    return "\n".join(lines)


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
) -> list[str]:
    if not outcomes:
        return [
            "활성 매수 후보: 0건",
            "",
            "판정: 현재 매수 후보 없음",
            "진입 이후 손절/청산/이탈/SELL 라벨이 나온 종목은 활성 후보에서 제외했습니다.",
        ]

    cache = ticker_cache if ticker_cache is not None else _load_ticker_cache_safely()
    lines = [f"활성 매수 후보: {len(outcomes)}건"]
    for index, item in enumerate(outcomes, start=1):
        priority_risks = classify_priority_risks(returns=item.returns, context=item.context)
        combined_risks = [*item.risk_flags, *priority_risks]
        risk = "없음" if not combined_risks else ", ".join(combined_risks)
        adjusted_penalty = adjusted_priority_penalty(item)
        score = max(0, 100 - adjusted_penalty)
        status = "매수 후보 유지" if adjusted_penalty == 0 else f"주의 필요 · 감점 {adjusted_penalty}"
        price_unit = "원" if item.market == "KR" else ""
        lines.extend(
            [
                "",
                f"{index}. {symbol_display_name(item.symbol, ticker_cache=cache)} · 기술점수 {score}점",
                f"판정: {status}",
                f"시그널: {item.signal_date} · {item.label} · 중복 {item.duplicate_count}회",
                f"신호 기준가: {_fmt_price(item.entry_price)}{price_unit}",
                f"감점 사유: {risk}",
            ]
        )
        enrichment = (enrichments or {}).get(item.symbol)
        if enrichment:
            lines.extend(
                [
                    f"감사인: {enrichment.auditor}",
                    f"수급: {enrichment.supply}",
                    f"실적/밸류: {enrichment.fundamental}",
                ]
            )
        if item.failure_class:
            lines.append(f"실패분류: {item.failure_class}")
    return lines


def format_telegram_exclusion_cards(
    exclusions: list[TradingViewExcludedSignal],
    *,
    ticker_cache: list[dict] | None = None,
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
        lines.extend(
            [
                "",
                f"{index}. {symbol_display_name(item.symbol, ticker_cache=cache)}",
                f"제외: {exit_date} · {_compact_label(item.exit_label)}",
                f"직전 진입: {item.signal_date} · {_compact_label(item.label)}",
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
            fundamental=_format_fundamental_summary(fundamental),
            auditor=_format_auditor_summary(decision.status, decision.auditor, decision.reason),
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
