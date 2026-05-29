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
    blocked: bool = False


@dataclass(frozen=True)
class DashboardInput:
    as_of: str
    regime: MarketRegime
    lenses: list[Lens]
    stocks: list[StockInput]


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


@dataclass(frozen=True)
class Dashboard:
    as_of: str
    regime: MarketRegime
    lenses: list[Lens]
    candidates: list[Candidate]


def parse_dashboard_input(payload: dict[str, Any]) -> DashboardInput:
    regime_payload = payload["regime"]
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
            blocked=bool(item.get("blocked", False)),
        )
        for item in payload.get("stocks", [])
    ]
    return DashboardInput(
        as_of=str(payload["as_of"]),
        regime=MarketRegime(
            verdict=str(regime_payload["verdict"]),
            risk_appetite=str(regime_payload["risk_appetite"]),
            rates=str(regime_payload["rates"]),
            dollar=str(regime_payload["dollar"]),
            volatility=str(regime_payload["volatility"]),
            notes=[str(value) for value in regime_payload.get("notes", [])],
        ),
        lenses=lenses,
        stocks=stocks,
    )


def _parse_metrics(payload: dict[str, Any]) -> StockMetrics:
    return StockMetrics(
        valuation=float(payload.get("valuation", 0)),
        quality=float(payload.get("quality", 0)),
        growth=float(payload.get("growth", 0)),
        revision=float(payload.get("revision", 0)),
        momentum=float(payload.get("momentum", 0)),
    )
