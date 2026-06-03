"""Real-data providers for the lens dashboard.

A *provider* turns a ticker into a :class:`RawStock` of normalized raw fields.
``fetch_raw_stock`` dispatches by ticker shape (6-digit numeric -> KR via the
existing ``data/`` layer, alphabetic -> US via yfinance). ``fetch_macro``
returns market indicators + a derived regime read.

All providers degrade gracefully: on any fetch failure they return a
``RawStock``/payload with ``errors`` populated and whatever fields succeeded,
so the snapshot builder can record partial data instead of crashing.
"""

from __future__ import annotations

from dashboard.providers.base import RawStock, classify_market, fetch_raw_stock
from dashboard.providers.macro import fetch_macro

__all__ = ["RawStock", "classify_market", "fetch_raw_stock", "fetch_macro"]
