"""Run TradingView CLI scans for Lazy Alpha labels."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from signals.tradingview_direct import (
    TradingViewLabelOutcome,
    format_tradingview_direct_report,
    map_lazy_alpha_labels_to_outcomes,
)

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
    lines.append(format_tradingview_direct_report(outcomes, title="Lazy Alpha 매수 라벨"))
    return "\n".join(lines)
