"""Domain models for the lens investment dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LensKind(str, Enum):
    THESIS = "thesis"
    SECTOR = "sector"
    MACRO = "macro"
    FACTOR = "factor"


class CandidateStatus(str, Enum):
    WATCH = "Watch"
    RESEARCH = "Research"
    SETUP = "Setup"
    AVOID = "Avoid"
    BLOCKED = "Blocked"
    DROPPED = "Dropped"


@dataclass(frozen=True)
class MarketRegime:
    verdict: str
    risk_appetite: str
    rates: str
    dollar: str
    volatility: str
    notes: list[str]


@dataclass(frozen=True)
class Lens:
    id: str
    kind: LensKind
    name: str
    conviction: str
    direction: str
    weights: dict[str, float]
    risks: list[str]


@dataclass(frozen=True)
class StockMetrics:
    valuation: float
    quality: float
    growth: float
    revision: float
    momentum: float


@dataclass(frozen=True)
class StockInput:
    ticker: str
    company: str
    sector: str
    lens_ids: list[str]
    metrics: StockMetrics
    evidence: list[str]
    gaps: list[str]
    thesis: str = ""
    bull_case: list[str] | None = None
    bear_case: list[str] | None = None
    next_action: str = ""
    price: float | None = None
    day_change_pct: float | None = None
    pe: float | None = None
    peer_pe: float | None = None
    peer_group: str = ""
    source_refs: list[str] | None = None
    blocked: bool = False
    independence_status: str = ""
    auditor: str = ""


@dataclass(frozen=True)
class MarketIndicator:
    symbol: str
    name: str
    group: str
    price: float
    day_change_pct: float
    read: str


@dataclass(frozen=True)
class DashboardInput:
    as_of: str
    regime: MarketRegime | None
    price_time: str
    market_indicators: list[MarketIndicator]
    lenses: list[Lens]
    stocks: list[StockInput]
    dual_regime: DualRegime | None = None


@dataclass(frozen=True)
class Candidate:
    ticker: str
    company: str
    sector: str
    linked_lenses: list[Lens]
    score: float
    status: CandidateStatus
    strongest_lens: str
    evidence: list[str]
    gaps: list[str]
    risk_flags: list[str]
    thesis: str
    bull_case: list[str]
    bear_case: list[str]
    next_action: str
    price: float | None
    day_change_pct: float | None
    pe: float | None
    peer_pe: float | None
    peer_group: str
    source_refs: list[str]
    independence_status: str = ""
    auditor: str = ""


@dataclass(frozen=True)
class Dashboard:
    as_of: str
    regime: MarketRegime | None
    price_time: str
    market_indicators: list[MarketIndicator]
    lenses: list[Lens]
    candidates: list[Candidate]
    dual_regime: DualRegime | None = None


def parse_dashboard_input(payload: dict[str, Any]) -> DashboardInput:
    regime_payload = payload.get("regime")
    lenses = [
        Lens(
            id=str(item["id"]),
            kind=LensKind(str(item["kind"])),
            name=str(item["name"]),
            conviction=str(item["conviction"]),
            direction=str(item["direction"]),
            weights={str(key): float(value) for key, value in item.get("weights", {}).items()},
            risks=[str(value) for value in item.get("risks", [])],
        )
        for item in payload.get("lenses", [])
    ]
    stocks = [
        StockInput(
            ticker=str(item["ticker"]),
            company=str(item["company"]),
            sector=str(item["sector"]),
            lens_ids=[str(value) for value in item.get("lens_ids", [])],
            metrics=_parse_metrics(item.get("metrics", {})),
            evidence=[str(value) for value in item.get("evidence", [])],
            gaps=[str(value) for value in item.get("gaps", [])],
            thesis=str(item.get("thesis", "")),
            bull_case=[str(value) for value in item.get("bull_case", [])],
            bear_case=[str(value) for value in item.get("bear_case", [])],
            next_action=str(item.get("next_action", "")),
            price=_optional_float(item.get("price")),
            day_change_pct=_optional_float(item.get("day_change_pct")),
            pe=_optional_float(item.get("pe")),
            peer_pe=_optional_float(item.get("peer_pe")),
            peer_group=str(item.get("peer_group", "")),
            source_refs=[str(value) for value in item.get("source_refs", [])],
            blocked=bool(item.get("blocked", False)),
            independence_status=str(item.get("independence_status", "")),
            auditor=str(item.get("auditor", "")),
        )
        for item in payload.get("stocks", [])
    ]
    return DashboardInput(
        as_of=str(payload["as_of"]),
        regime=_parse_legacy_regime(regime_payload),
        price_time=str(payload.get("price_time", "")),
        market_indicators=[
            MarketIndicator(
                symbol=str(item["symbol"]),
                name=str(item["name"]),
                group=str(item["group"]),
                price=float(item["price"]),
                day_change_pct=float(item["day_change_pct"]),
                read=str(item["read"]),
            )
            for item in payload.get("market_indicators", [])
        ],
        lenses=lenses,
        stocks=stocks,
        dual_regime=parse_dual_regime(payload.get("dual_regime")),
    )


def _parse_legacy_regime(payload: dict[str, Any] | None) -> MarketRegime | None:
    if not payload:
        return None
    return MarketRegime(
        verdict=str(payload["verdict"]),
        risk_appetite=str(payload["risk_appetite"]),
        rates=str(payload["rates"]),
        dollar=str(payload["dollar"]),
        volatility=str(payload["volatility"]),
        notes=[str(value) for value in payload.get("notes", [])],
    )


def _parse_metrics(payload: dict[str, Any]) -> StockMetrics:
    return StockMetrics(
        valuation=float(payload.get("valuation", 0)),
        quality=float(payload.get("quality", 0)),
        growth=float(payload.get("growth", 0)),
        revision=float(payload.get("revision", 0)),
        momentum=float(payload.get("momentum", 0)),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True)
class AxisRead:
    dimension: str
    label: str
    state: str
    pctile: float | None
    read: str
    symbols: list[str]
    source_kind: str | None = None


@dataclass(frozen=True)
class MarketRegimeRead:
    market: str
    regime: str
    why_it_matters: str
    next_action: str
    axis_reads: list[AxisRead]
    data_gaps: list[str]


@dataclass(frozen=True)
class RegimeTransition:
    changed: bool
    to: str
    streak: int
    whipsaw: bool
    from_regime: str | None
    axis_changes: list[dict]


@dataclass(frozen=True)
class DualRegime:
    as_of: str | None
    us: MarketRegimeRead
    kr: MarketRegimeRead
    transitions: dict[str, RegimeTransition]


def _parse_market_regime(payload: dict[str, Any]) -> MarketRegimeRead:
    return MarketRegimeRead(
        market=str(payload["market"]),
        regime=str(payload["regime"]),
        why_it_matters=str(payload.get("why_it_matters", "")),
        next_action=str(payload.get("next_action", "")),
        axis_reads=[
            AxisRead(
                dimension=str(a["dimension"]), label=str(a["label"]), state=str(a["state"]),
                pctile=(None if a.get("pctile") is None else float(a["pctile"])),
                read=str(a.get("read", "")), symbols=[str(s) for s in a.get("symbols", [])],
                source_kind=(None if a.get("source_kind") is None else str(a["source_kind"])),
            )
            for a in payload.get("axis_reads", [])
        ],
        data_gaps=[str(g) for g in payload.get("data_gaps", [])],
    )


def _parse_transition(payload: dict[str, Any]) -> RegimeTransition:
    return RegimeTransition(
        changed=bool(payload["changed"]), to=str(payload["to"]),
        streak=int(payload["streak"]), whipsaw=bool(payload["whipsaw"]),
        from_regime=(None if payload.get("from") is None else str(payload["from"])),
        axis_changes=[dict(c) for c in payload.get("axis_changes", [])],
    )


def parse_dual_regime(payload: dict[str, Any] | None) -> DualRegime | None:
    if not payload:
        return None
    return DualRegime(
        as_of=(None if payload.get("as_of") is None else str(payload["as_of"])),
        us=_parse_market_regime(payload["us"]),
        kr=_parse_market_regime(payload["kr"]),
        transitions={k: _parse_transition(v) for k, v in (payload.get("transitions") or {}).items()},
    )
