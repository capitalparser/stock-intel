"""TradingView watchlist universe snapshot utilities."""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from signals.market import classify_market, supports_audit_lookup


INDEX_EXCHANGES = {"TVC", "INDEX", "SP"}
CRYPTO_EXCHANGES = {"UPBIT", "COINBASE", "BINANCE", "BITHUMB"}
FUTURES_EXCHANGES = {"CME", "CME_MINI", "CBOT", "NYMEX", "COMEX"}
ETF_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "KORU",
    "UVIX",
    "SLV",
    "UCO",
    "HYG",
    "LQD",
    "KRE",
    "MAGS",
    "ARKK",
    "XBI",
    "XLE",
    "XLY",
    "XLP",
    "XLF",
    "XLV",
    "XLI",
    "XLB",
    "XLU",
    "IYZ",
    "IBB",
}


@dataclass(frozen=True)
class UniverseSymbol:
    symbol: str
    market: str
    asset_type: str
    watchlists: list[str]
    audit_lookup_supported: bool


@dataclass(frozen=True)
class UniverseWatchlist:
    name: str
    type: str
    id: str
    symbol_count: int


@dataclass(frozen=True)
class UniverseSnapshot:
    fetched_at: str
    total_symbols: int
    symbols: dict[str, UniverseSymbol]
    watchlists: dict[str, UniverseWatchlist]
    counts_by_market: dict[str, int]
    counts_by_asset_type: dict[str, int]

    def contains(self, symbol: str) -> bool:
        return symbol in self.symbols


def build_universe_snapshot(
    watchlists: list[dict[str, Any]],
    *,
    fetched_at: str,
) -> UniverseSnapshot:
    membership: dict[str, set[str]] = defaultdict(set)
    watchlist_map: dict[str, UniverseWatchlist] = {}

    for item in watchlists:
        name = str(item.get("name") or item.get("id") or "unknown")
        symbols = [
            str(symbol).strip()
            for symbol in item.get("symbols", [])
            if str(symbol).strip() and not str(symbol).startswith("###")
        ]
        watchlist_map[name] = UniverseWatchlist(
            name=name,
            type=str(item.get("type") or "custom"),
            id=str(item.get("id") or name),
            symbol_count=len(symbols),
        )
        for symbol in symbols:
            membership[symbol].add(name)

    symbols: dict[str, UniverseSymbol] = {}
    for symbol, lists in sorted(membership.items()):
        market = _classify_universe_market(symbol)
        asset_type = _classify_asset_type(symbol, market)
        symbols[symbol] = UniverseSymbol(
            symbol=symbol,
            market=market,
            asset_type=asset_type,
            watchlists=sorted(lists),
            audit_lookup_supported=supports_audit_lookup(symbol, market),
        )

    return UniverseSnapshot(
        fetched_at=fetched_at,
        total_symbols=len(symbols),
        symbols=symbols,
        watchlists=dict(sorted(watchlist_map.items())),
        counts_by_market=dict(Counter(symbol.market for symbol in symbols.values())),
        counts_by_asset_type=dict(Counter(symbol.asset_type for symbol in symbols.values())),
    )


def save_universe_snapshot(snapshot: UniverseSnapshot, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_snapshot_to_dict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")


def load_universe_snapshot(path: str | Path) -> UniverseSnapshot | None:
    target = Path(path)
    if not target.exists():
        return None
    return _snapshot_from_dict(json.loads(target.read_text(encoding="utf-8")))


def format_universe_summary(snapshot: UniverseSnapshot | None) -> str:
    if snapshot is None:
        return "🌐 TradingView Universe\n아직 동기화된 universe snapshot이 없습니다.\n/sync-universe 를 먼저 실행하세요."

    market_counts = " · ".join(
        f"{key} {snapshot.counts_by_market[key]}"
        for key in sorted(snapshot.counts_by_market)
    )
    asset_counts = " · ".join(
        f"{key} {snapshot.counts_by_asset_type[key]}"
        for key in sorted(snapshot.counts_by_asset_type)
    )
    lines = [
        "🌐 TradingView Universe",
        f"동기화: {snapshot.fetched_at}",
        f"전체 심볼: {snapshot.total_symbols}",
        f"시장: {market_counts or '-'}",
        f"유형: {asset_counts or '-'}",
        "",
        "Watchlists",
    ]
    for item in snapshot.watchlists.values():
        lines.append(f"- {item.name}: {item.symbol_count}")
    return "\n".join(lines)


def symbol_in_universe(symbol: str, snapshot: UniverseSnapshot | None) -> bool:
    if snapshot is None:
        return True
    if symbol in snapshot.symbols:
        return True
    if symbol.isdigit() and len(symbol) == 6 and f"KRX:{symbol}" in snapshot.symbols:
        return True
    if symbol.startswith("KRX:") and symbol.removeprefix("KRX:") in snapshot.symbols:
        return True
    return False


def sync_universe_from_tradingview(
    *,
    mcp_dir: str | Path,
    output_path: str | Path,
    fetched_at: str | None = None,
) -> UniverseSnapshot:
    result = subprocess.run(
        ["node", "--input-type=module", "-"],
        input=_TRADINGVIEW_WATCHLISTS_SCRIPT,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
        cwd=str(mcp_dir),
    )
    payload = json.loads(result.stdout)
    if not payload.get("success"):
        raise RuntimeError(str(payload.get("error") or "TradingView watchlist sync failed"))
    snapshot = build_universe_snapshot(
        payload.get("lists", []),
        fetched_at=fetched_at or datetime.now(UTC).isoformat(),
    )
    save_universe_snapshot(snapshot, output_path)
    return snapshot


def _classify_universe_market(symbol: str) -> str:
    exchange, _ticker = _split_symbol(symbol)
    if exchange in CRYPTO_EXCHANGES:
        return "CRYPTO"
    if exchange in INDEX_EXCHANGES:
        return "INDEX"
    if exchange in FUTURES_EXCHANGES or symbol.endswith("!"):
        return "FUTURES"
    return classify_market(_ticker or symbol, exchange).code


def _classify_asset_type(symbol: str, market: str) -> str:
    exchange, ticker = _split_symbol(symbol)
    if market == "CRYPTO":
        return "CRYPTO"
    if market == "INDEX":
        return "INDEX"
    if market == "FUTURES":
        return "FUTURES"
    if ticker in ETF_TICKERS:
        return "ETF"
    if market in {"KR", "US", "JP"}:
        return "EQUITY"
    if exchange:
        return "OTHER"
    return "UNKNOWN"


def _split_symbol(symbol: str) -> tuple[str, str]:
    if ":" not in symbol:
        return "", symbol.upper()
    exchange, ticker = symbol.split(":", 1)
    return exchange.upper(), ticker.upper()


_TRADINGVIEW_WATCHLISTS_SCRIPT = r"""
import { evaluateAsync } from './src/connection.js';
const result = await evaluateAsync(`
(async function() {
  window.webpackChunktradingview.push([[Date.now()], {}, function(req) { window.__tv_req = req; }]);
  var service = await window.__tv_req('918061').initSymbolListService();
  var state = service.store.getState();
  var custom = Object.values(state.customLists?.lists?.byId || {}).map(function(list) {
    return {
      type: 'custom',
      id: String(list.id),
      name: list.name,
      symbols: list.symbols || []
    };
  });
  var color = Object.entries(state.markedLists?.lists?.byColor || {}).map(function(entry) {
    var id = entry[0], list = entry[1];
    return {
      type: 'color',
      id: String(id),
      name: String(id),
      symbols: list.symbols || []
    };
  });
  return { success: true, active: state.activeSymbolList, lists: custom.concat(color) };
})()
`);
console.log(JSON.stringify(result));
process.exit(0);
"""


def _snapshot_to_dict(snapshot: UniverseSnapshot) -> dict[str, Any]:
    return {
        "fetched_at": snapshot.fetched_at,
        "total_symbols": snapshot.total_symbols,
        "symbols": {
            key: {
                "symbol": value.symbol,
                "market": value.market,
                "asset_type": value.asset_type,
                "watchlists": value.watchlists,
                "audit_lookup_supported": value.audit_lookup_supported,
            }
            for key, value in snapshot.symbols.items()
        },
        "watchlists": {
            key: {
                "name": value.name,
                "type": value.type,
                "id": value.id,
                "symbol_count": value.symbol_count,
            }
            for key, value in snapshot.watchlists.items()
        },
        "counts_by_market": snapshot.counts_by_market,
        "counts_by_asset_type": snapshot.counts_by_asset_type,
    }


def _snapshot_from_dict(data: dict[str, Any]) -> UniverseSnapshot:
    return UniverseSnapshot(
        fetched_at=str(data["fetched_at"]),
        total_symbols=int(data["total_symbols"]),
        symbols={
            key: UniverseSymbol(
                symbol=str(value["symbol"]),
                market=str(value["market"]),
                asset_type=str(value["asset_type"]),
                watchlists=list(value["watchlists"]),
                audit_lookup_supported=bool(value["audit_lookup_supported"]),
            )
            for key, value in data["symbols"].items()
        },
        watchlists={
            key: UniverseWatchlist(
                name=str(value["name"]),
                type=str(value["type"]),
                id=str(value["id"]),
                symbol_count=int(value["symbol_count"]),
            )
            for key, value in data["watchlists"].items()
        },
        counts_by_market={str(k): int(v) for k, v in data["counts_by_market"].items()},
        counts_by_asset_type={str(k): int(v) for k, v in data["counts_by_asset_type"].items()},
    )
