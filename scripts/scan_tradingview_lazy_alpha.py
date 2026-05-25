#!/usr/bin/env python
"""Scan TradingView chart directly for Lazy Alpha buy labels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signals.tradingview_direct import format_tradingview_direct_report
from signals.tradingview_scan_runner import TradingViewCli, market_for_symbol, scan_tradingview_symbols, symbols_from_universe


DEFAULT_MCP_DIR = Path("/Users/kjun/code/tradingview-mcp")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="TradingView symbols, e.g. NASDAQ:AAPL NYSE:PLTR")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--bars", type=int, default=500)
    parser.add_argument("--max-labels", type=int, default=250)
    parser.add_argument("--timeframe", default="D")
    parser.add_argument("--duplicate-window-bars", type=int, default=5)
    parser.add_argument("--entry-policy", choices=["first", "last"], default="first")
    parser.add_argument("--mcp-dir", default=str(DEFAULT_MCP_DIR))
    parser.add_argument("--sleep", type=float, default=2.5)
    parser.add_argument("--universe", default="state/universe_snapshot.json")
    args = parser.parse_args(argv)

    symbols = args.symbols or symbols_from_universe(Path(args.universe), limit=args.limit)
    result = scan_tradingview_symbols(
        symbols[: args.limit],
        mcp_dir=Path(args.mcp_dir),
        bars=args.bars,
        max_labels=args.max_labels,
        timeframe=args.timeframe,
        duplicate_window_bars=args.duplicate_window_bars,
        entry_policy=args.entry_policy,
        sleep_seconds=args.sleep,
        runner=TradingViewCli(Path(args.mcp_dir)),
    )

    print()
    print(format_tradingview_direct_report(result.outcomes, title="TradingView Lazy Alpha 직접 사후검증"))
    if result.errors:
        print()
        print("errors:")
        for symbol, error in result.errors:
            print(f"- {symbol}: {error}")
    return 0

_market = market_for_symbol


if __name__ == "__main__":
    raise SystemExit(main())
