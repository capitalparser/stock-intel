"""Scoring and candidate status logic for the lens dashboard."""

from __future__ import annotations

from dashboard.models import (
    Candidate,
    CandidateStatus,
    Dashboard,
    DashboardInput,
    Lens,
    StockInput,
    StockMetrics,
)


METRIC_NAMES = ("valuation", "quality", "growth", "revision", "momentum")


def build_dashboard(source: DashboardInput) -> Dashboard:
    lens_by_id = {lens.id: lens for lens in source.lenses}
    candidates = [_build_candidate(stock, lens_by_id) for stock in source.stocks]
    candidates.sort(
        key=lambda item: (
            item.status != CandidateStatus.SETUP,
            item.price is None,
            -len(item.linked_lenses),
            -item.score,
            item.ticker,
        )
    )
    return Dashboard(
        as_of=source.as_of,
        regime=source.regime,
        price_time=source.price_time,
        market_indicators=source.market_indicators,
        macro_state=source.macro_state,
        lenses=source.lenses,
        candidates=candidates,
    )


def _build_candidate(stock: StockInput, lens_by_id: dict[str, Lens]) -> Candidate:
    linked = [lens_by_id[lens_id] for lens_id in stock.lens_ids if lens_id in lens_by_id]
    lens_scores = [(lens, _score_for_lens(stock.metrics, lens)) for lens in linked]
    score = round(sum(score for _, score in lens_scores) / len(lens_scores), 1) if lens_scores else 0.0
    strongest = max(lens_scores, key=_lens_priority)[0].name if lens_scores else "-"
    return Candidate(
        ticker=stock.ticker,
        company=stock.company,
        sector=stock.sector,
        linked_lenses=linked,
        score=score,
        status=_status_for(stock, linked, score),
        strongest_lens=strongest,
        evidence=stock.evidence,
        gaps=stock.gaps,
        risk_flags=_risk_flags(stock, score),
        thesis=stock.thesis,
        bull_case=stock.bull_case or [],
        bear_case=stock.bear_case or [],
        next_action=stock.next_action,
        price=stock.price,
        day_change_pct=stock.day_change_pct,
        pe=stock.pe,
        peer_pe=stock.peer_pe,
        peer_group=stock.peer_group,
        source_refs=stock.source_refs or [],
    )


def _score_for_lens(metrics: StockMetrics, lens: Lens) -> float:
    weighted_sum = 0.0
    total_weight = 0.0
    for metric in METRIC_NAMES:
        weight = float(lens.weights.get(metric, 0.0))
        weighted_sum += getattr(metrics, metric) * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return weighted_sum / total_weight


def _lens_priority(item: tuple[Lens, float]) -> tuple[int, float]:
    lens, score = item
    conviction_rank = {"high": 3, "medium": 2, "low": 1}.get(lens.conviction.lower(), 0)
    return conviction_rank, score


def _status_for(stock: StockInput, linked: list[Lens], score: float) -> CandidateStatus:
    if stock.blocked:
        return CandidateStatus.BLOCKED
    if not stock.evidence or stock.gaps:
        return CandidateStatus.RESEARCH
    if len(linked) >= 2 and score >= 65:
        return CandidateStatus.SETUP
    if score < 35:
        return CandidateStatus.AVOID
    return CandidateStatus.WATCH


def _risk_flags(stock: StockInput, score: float) -> list[str]:
    flags: list[str] = []
    if stock.metrics.valuation < 35:
        flags.append("valuation stretch")
    if stock.metrics.revision < 40:
        flags.append("weak revision")
    if score < 35:
        flags.append("low composite score")
    if stock.gaps:
        flags.append("evidence gap")
    return flags
