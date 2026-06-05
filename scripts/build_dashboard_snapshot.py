"""Fetch the real-data snapshot for the dashboard universe and cache it.

Run on a machine with network access (the user's box or the fly app), e.g.::

    uv run python scripts/build_dashboard_snapshot.py

KR tickers (6-digit) are sourced from the existing ``data/`` layer
(pykrx/Naver/DART); US tickers from yfinance. The result is written to
``state/dashboard/cache/`` and consumed by the renderer / web route.
"""

from __future__ import annotations

import argparse

from dashboard.live import universe_from_payload
from dashboard.market_insights import build_market_insights_payload
from dashboard.snapshot import DEFAULT_CACHE_DIR, build_snapshot, save_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and cache the dashboard real-data snapshot.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    args = parser.parse_args()

    payload = build_market_insights_payload()
    universe = universe_from_payload(payload)
    print(f"Universe: {len(universe)} tickers")

    snapshot = build_snapshot(universe, persist_regime_history=True)
    path = save_snapshot(snapshot, args.cache_dir)

    stocks = snapshot["stocks"]
    priced = sum(1 for s in stocks.values() if s.get("price") is not None)
    with_errors = sum(1 for s in stocks.values() if s["data_quality"]["errors"])
    macro_n = len(snapshot["macro"].get("market_indicators", []))
    print(f"Fetched {len(stocks)} stocks — {priced} priced, {with_errors} with fetch errors.")
    print(f"Macro indicators: {macro_n} · regime: {snapshot['macro'].get('regime', {}).get('verdict', '—')}")
    print(f"Saved snapshot: {path}")
    for ticker, s in sorted(stocks.items()):
        if s["data_quality"]["errors"]:
            print(f"  ! {ticker}: {s['data_quality']['errors']}")


if __name__ == "__main__":
    main()
