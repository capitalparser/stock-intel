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

from signals.backtest import audit_signal_outcomes, format_outcome_report
from signals.price_history import PykrxPriceHistoryProvider
from signals.storage import SignalStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("STATE_DB_PATH", "state.db"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--action", default="BUY")
    args = parser.parse_args(argv)

    store = SignalStore(args.db)
    rows = store.events_for_audit(limit=args.limit, action=args.action.upper())
    outcomes = audit_signal_outcomes(rows, price_provider=PykrxPriceHistoryProvider())
    print(format_outcome_report(outcomes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
