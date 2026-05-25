#!/usr/bin/env python
"""Evaluate Korean watchlist candidates by sector."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.audit_firm import fetch_audit_firm
from data.fundamental import fetch_fundamental
from signals.kr_watch_candidates import (
    KR_CANDIDATE_SEEDS,
    evaluate_candidate,
    format_candidate_report,
    format_tradingview_watchlist_sections,
)
from signals.market import ticker_for_lookup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Limit seeds for a quick smoke run.")
    parser.add_argument("--as-of-year", type=int, default=date.today().year)
    parser.add_argument("--report", default=f"state/kr_watch_candidates_{date.today().isoformat()}.md")
    parser.add_argument("--watchlist", default=f"state/tradingview_kr_watch_candidates_{date.today().isoformat()}.txt")
    args = parser.parse_args(argv)

    seeds = list(KR_CANDIDATE_SEEDS)
    if args.limit:
        seeds = seeds[: args.limit]

    evaluations = []
    for index, seed in enumerate(seeds, start=1):
        ticker = ticker_for_lookup(seed.symbol, "KR")
        print(f"[{index}/{len(seeds)}] {seed.symbol} {seed.name}", flush=True)
        fundamental = fetch_fundamental(ticker)
        audit = fetch_audit_firm(ticker)
        evaluations.append(
            evaluate_candidate(
                seed,
                fundamental=fundamental,
                audit=audit,
                as_of_year=args.as_of_year,
            )
        )

    report = format_candidate_report(evaluations)
    watchlist = format_tradingview_watchlist_sections(evaluations)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report, encoding="utf-8")
    Path(args.watchlist).parent.mkdir(parents=True, exist_ok=True)
    Path(args.watchlist).write_text(watchlist, encoding="utf-8")
    print()
    print(report)
    print(f"report: {args.report}")
    print(f"watchlist: {args.watchlist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
