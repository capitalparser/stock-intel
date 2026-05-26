#!/usr/bin/env python
"""Audit stored BUY signals against later close-price outcomes."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signals.backtest import audit_signal_outcomes, format_calibration_report
from signals.price_history import CachedPriceHistoryProvider, MarketPriceHistoryProvider
from signals.storage import SignalStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("STATE_DB_PATH", "state.db"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--action", default="BUY")
    parser.add_argument("--market", choices=["KR", "US", "JP"], default="KR")
    args = parser.parse_args(argv)

    store = SignalStore(args.db)
    rows = [
        row
        for row in store.events_for_audit(limit=args.limit, action=args.action.upper())
        if row.market == args.market
    ]
    provider = CachedPriceHistoryProvider(
        MarketPriceHistoryProvider(),
        db_path=os.getenv("PRICE_HISTORY_CACHE_DB", args.db),
        ttl_seconds=int(os.getenv("PRICE_HISTORY_CACHE_TTL_SECONDS", str(6 * 3600))),
    )
    outcomes = audit_signal_outcomes(rows, price_provider=provider)
    print(format_calibration_report(outcomes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
