"""Run TradingView CLI scans for Lazy Alpha labels."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from signals.tradingview_direct import (
    TradingViewLabelOutcome,
    classify_priority_risks,
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
    errors: list[tuple[str, str]]
    scanned: list[str]


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
    max_labels: int = 200,
    timeframe: str = "D",
    duplicate_window_bars: int = 5,
    entry_policy: str = "first",
    sleep_seconds: float = 2.0,
    runner: TradingViewCli | None = None,
) -> TradingViewScanResult:
    cli = runner or TradingViewCli(mcp_dir)
    outcomes: list[TradingViewLabelOutcome] = []
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
            outcomes.extend(
                map_lazy_alpha_labels_to_outcomes(
                    symbol=symbol,
                    market=market_for_symbol(symbol),
                    bars=ohlcv.get("bars", []),
                    labels=study_labels,
                    total_available=ohlcv.get("total_available"),
                    duplicate_window_bars=duplicate_window_bars,
                    entry_policy=entry_policy,
                    active_only=True,
                )
            )
            scanned.append(symbol)
        except Exception as exc:  # pragma: no cover - external CLI boundary
            errors.append((symbol, str(exc)))
    return TradingViewScanResult(outcomes=outcomes, errors=errors, scanned=scanned)


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
) -> str:
    lines = [
        f"📡 TradingView 직접 스캔 — {title}" if "TradingView 직접 스캔" not in title else title,
        "기준: 웹훅 저장소가 아니라 현재 열린 TradingView 차트의 Lazy Alpha 라벨을 직접 읽음",
        f"스캔: {len(scanned)}종목 · 라벨 매핑: {len(outcomes)}건",
    ]
    if scanned:
        lines.append("대상: " + ", ".join(scanned[:12]))
    if errors:
        lines.append("오류: " + " · ".join(f"{symbol}" for symbol, _error in errors[:5]))
    lines.append("")
    lines.extend(format_telegram_outcome_cards(sorted(outcomes, key=priority_sort_key)))
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
) -> list[str]:
    if not outcomes:
        return [
            "현재 활성 매수 라벨 없음",
            "진입 이후 손절/청산/이탈 라벨이 나온 경우에는 활성 후보에서 제외했습니다.",
        ]

    cache = ticker_cache if ticker_cache is not None else _load_ticker_cache_safely()
    lines = [f"활성 매수 후보: {len(outcomes)}건"]
    for index, item in enumerate(outcomes, start=1):
        priority_risks = classify_priority_risks(returns=item.returns, context=item.context)
        combined_risks = [*item.risk_flags, *priority_risks]
        risk = "없음" if not combined_risks else ", ".join(combined_risks)
        adjusted_penalty = adjusted_priority_penalty(item)
        status = "정상" if adjusted_penalty == 0 else f"주의 penalty {adjusted_penalty}"
        lines.extend(
            [
                "",
                f"{index}. {symbol_display_name(item.symbol, ticker_cache=cache)}",
                f"   일자: {item.signal_date} · 상태: {status}",
                f"   라벨: {item.label}",
                f"   가격: {_fmt_price(item.entry_price)} · 중복: {item.duplicate_count}",
                "   수익률: "
                f"5일 {_fmt_pct(item.returns.get('5d'))} · "
                f"10일 {_fmt_pct(item.returns.get('10d'))} · "
                f"20일 {_fmt_pct(item.returns.get('20d'))}",
                f"   리스크: {risk}",
            ]
        )
        if item.failure_class:
            lines.append(f"   실패분류: {item.failure_class}")
    return lines


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
