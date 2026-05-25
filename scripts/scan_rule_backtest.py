#!/usr/bin/env python
"""Scan historical OHLCV for rule-based entry signals and audit outcomes."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pykrx import stock

from signals.historical_scan import format_historical_scan_report, scan_rule_signal_outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="KRX ticker, e.g. 005930")
    parser.add_argument("--market", default="KR")
    parser.add_argument("--start", default=(datetime.today() - timedelta(days=900)).strftime("%Y-%m-%d"))
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--min-volume-ratio", type=float, default=1.5)
    parser.add_argument("--min-signal-gap-bars", type=int, default=10)
    args = parser.parse_args(argv)

    df = stock.get_market_ohlcv_by_date(args.start.replace("-", ""), args.end.replace("-", ""), args.ticker)
    outcomes = scan_rule_signal_outcomes(
        ticker=args.ticker,
        market=args.market,
        ohlcv=df,
        min_volume_ratio=args.min_volume_ratio,
        min_signal_gap_bars=args.min_signal_gap_bars,
    )
    print(format_historical_scan_report(outcomes, title=f"{args.ticker} Rule Signal 사후검증"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
