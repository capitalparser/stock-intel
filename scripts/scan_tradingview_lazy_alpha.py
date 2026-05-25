#!/usr/bin/env python
"""Scan TradingView chart directly for Lazy Alpha buy labels."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signals.tradingview_direct import format_tradingview_direct_report, map_lazy_alpha_labels_to_outcomes


DEFAULT_MCP_DIR = Path("/Users/kjun/code/tradingview-mcp")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="TradingView symbols, e.g. NASDAQ:AAPL NYSE:PLTR")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--bars", type=int, default=500)
    parser.add_argument("--max-labels", type=int, default=200)
    parser.add_argument("--timeframe", default="D")
    parser.add_argument("--duplicate-window-bars", type=int, default=5)
    parser.add_argument("--entry-policy", choices=["first", "last"], default="first")
    parser.add_argument("--mcp-dir", default=str(DEFAULT_MCP_DIR))
    parser.add_argument("--sleep", type=float, default=2.5)
    parser.add_argument("--universe", default="state/universe_snapshot.json")
    args = parser.parse_args(argv)

    symbols = args.symbols or _symbols_from_universe(Path(args.universe), limit=args.limit)
    runner = TradingViewCli(Path(args.mcp_dir))
    all_outcomes = []
    errors = []
    for symbol in symbols[: args.limit]:
        try:
            runner.run(["symbol", symbol])
            time.sleep(args.sleep)
            runner.run(["timeframe", args.timeframe])
            time.sleep(args.sleep)
            ohlcv = runner.run(["ohlcv", "-n", str(args.bars)])
            labels = runner.run(["data", "labels", "--filter", "Lazy", "--max", str(args.max_labels), "--verbose"])
            study_labels = []
            for study in labels.get("studies", []):
                study_labels.extend(study.get("labels", []))
            outcomes = map_lazy_alpha_labels_to_outcomes(
                symbol=symbol,
                market=_market(symbol),
                bars=ohlcv.get("bars", []),
                labels=study_labels,
                total_available=ohlcv.get("total_available"),
                duplicate_window_bars=args.duplicate_window_bars,
                entry_policy=args.entry_policy,
            )
            all_outcomes.extend(outcomes)
            print(f"{symbol}: labels={len(study_labels)} buy_signals={len(outcomes)}", flush=True)
        except Exception as exc:
            errors.append((symbol, str(exc)))
            print(f"{symbol}: ERROR {exc}", flush=True)

    print()
    print(format_tradingview_direct_report(all_outcomes, title="TradingView Lazy Alpha 직접 사후검증"))
    if errors:
        print()
        print("errors:")
        for symbol, error in errors:
            print(f"- {symbol}: {error}")
    return 0


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


def _symbols_from_universe(path: Path, *, limit: int) -> list[str]:
    data = json.loads(path.read_text())
    preferred = []
    fallback = []
    for symbol, meta in data.get("symbols", {}).items():
        if not symbol.startswith(("NASDAQ:", "NYSE:", "AMEX:", "KRX:")):
            continue
        watchlists = " ".join(meta.get("watchlists", []))
        if any(keyword in watchlists for keyword in ("관심", "예비", "jesse", "국장")):
            preferred.append(symbol)
        else:
            fallback.append(symbol)
    return [*preferred, *fallback][:limit]


def _market(symbol: str) -> str:
    if symbol.startswith("KRX:"):
        return "KR"
    if symbol.startswith(("NASDAQ:", "NYSE:", "AMEX:")):
        return "US"
    return "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
