"""Live dashboard input: curated narrative + real-data snapshot overlay.

Qualitative content (thesis, bull/bear, lens mapping, the universe itself)
stays curated in ``SAMPLE_DASHBOARD``/vault. The quantitative fields
(metrics, price, day change, PER, peer PER, macro indicators, dual regime) are
overlaid from the cached real-data snapshot. Fields the snapshot could not
source are flagged as explicit data gaps so the UI never shows a fabricated
number as if it were real.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from dashboard.market_insights import (
    DEFAULT_MARKET_INSIGHTS_DIR,
    build_market_insights_payload,
)
from dashboard.models import DashboardInput, parse_dashboard_input
from dashboard.policy_lens import LOW_PBR_THRESHOLD, VALUE_UP_LENS
from dashboard.providers.independence_overlay import independence_flag
from dashboard.snapshot import (
    DEFAULT_CACHE_DIR,
    UniverseEntry,
    load_latest_snapshot,
)

# Korean labels for missing-field gap messages.
_FIELD_LABELS = {
    "price": "현재가",
    "pe": "PER",
    "valuation": "가치평가 점수",
    "quality": "퀄리티 점수",
    "growth": "성장 점수",
    "revision": "이익상향 점수",
    "momentum": "모멘텀 점수",
}


def universe_from_payload(payload: dict) -> list[UniverseEntry]:
    """The set of tickers + peer groups to fetch, derived from the payload."""
    entries: list[UniverseEntry] = []
    for stock in payload.get("stocks", []):
        entries.append(
            UniverseEntry(
                ticker=str(stock["ticker"]),
                peer_group=str(stock.get("peer_group") or stock.get("sector") or ""),
            )
        )
    return entries


def load_live_dashboard_input(
    insights_dir: str | Path = DEFAULT_MARKET_INSIGHTS_DIR,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    snapshot: dict | None = None,
) -> tuple[DashboardInput, bool]:
    """Return ``(input, used_snapshot)``.

    When no snapshot is available it transparently falls back to the curated
    sample input, with ``used_snapshot=False`` so the caller can label the
    dashboard as seed/mock data.
    """
    payload = build_market_insights_payload(insights_dir)
    snap = snapshot if snapshot is not None else load_latest_snapshot(cache_dir)
    if not snap or not snap.get("stocks"):
        return parse_dashboard_input(payload), False
    overlay_snapshot(payload, snap)
    return parse_dashboard_input(payload), True


def overlay_snapshot(payload: dict, snapshot: dict) -> dict:
    """Mutate ``payload`` in place, overlaying real-data fields from snapshot."""
    macro = snapshot.get("macro") or {}
    indicators = macro.get("market_indicators")
    if indicators:
        payload["market_indicators"] = deepcopy(indicators)
    dual_regime = macro.get("dual_regime")
    if dual_regime and dual_regime.get("us") and dual_regime.get("kr"):
        payload["dual_regime"] = deepcopy(dual_regime)

    payload["as_of"] = snapshot.get("as_of", payload.get("as_of"))
    if snapshot.get("generated_at"):
        payload["price_time"] = snapshot["generated_at"]
    if snapshot.get("valuation_expectations") is not None:
        payload["valuation_expectations"] = deepcopy(snapshot.get("valuation_expectations") or [])

    snap_stocks = snapshot.get("stocks") or {}
    for stock in payload.get("stocks", []):
        snap = snap_stocks.get(str(stock["ticker"]))
        if not snap:
            _append_gap(stock, "실데이터 미연결: 스냅샷에 종목 없음")
            continue
        _overlay_stock(stock, snap)
    return payload


def _overlay_stock(stock: dict, snap: dict) -> None:
    for field_name in ("price", "day_change_pct", "pe", "peer_pe"):
        if snap.get(field_name) is not None:
            stock[field_name] = snap[field_name]
    if snap.get("peer_group"):
        stock["peer_group"] = snap["peer_group"]
    if snap.get("metrics"):
        stock["metrics"] = dict(snap["metrics"])
    _overlay_expectation_verdict(stock, snap)
    _overlay_policy_lenses(stock, snap)
    _overlay_signature_fields(stock, snap)
    _overlay_catalysts(stock, snap)

    dq = snap.get("data_quality") or {}
    source = snap.get("source", "?")
    as_of = dq.get("as_of") or ""
    _append_evidence(stock, f"실데이터 연결: 가격·PER·지표 ({source}{', ' + as_of if as_of else ''})")

    missing = dq.get("missing") or []
    for field_name in missing:
        label = _FIELD_LABELS.get(field_name, field_name)
        _append_gap(stock, f"실데이터 미연결: {label}")
    proxy = dq.get("proxy") or []
    if "revision" in proxy:
        _append_evidence(stock, "이익상향(revision)은 수급·추세 기반 프록시 — 컨센서스 실데이터 아님")


def _overlay_policy_lenses(stock: dict, snap: dict) -> None:
    pbr = _optional_number(snap.get("pbr"))
    if pbr is None or pbr >= LOW_PBR_THRESHOLD:
        return

    lens_ids = list(stock.get("lens_ids") or [])
    if VALUE_UP_LENS.id not in lens_ids:
        lens_ids.append(VALUE_UP_LENS.id)
        stock["lens_ids"] = lens_ids
    _append_evidence(
        stock,
        f"저PBR 밸류업 자동 편입 (PBR {pbr:.2f} < {LOW_PBR_THRESHOLD:.2f})",
    )


def _overlay_expectation_verdict(stock: dict, snap: dict) -> None:
    verdict = str(snap.get("expectation_verdict") or "")
    if not verdict:
        return
    stock["expectation_verdict"] = verdict
    _append_evidence(stock, f"밸류에이션 기대치: {verdict}")


def _overlay_signature_fields(stock: dict, snap: dict) -> None:
    status = str(snap.get("independence_status") or "")
    auditor = str(snap.get("auditor") or "")
    reason = str(snap.get("independence_reason") or "")
    if status:
        stock["independence_status"] = status
        stock["auditor"] = auditor
        flag, blocked = independence_flag(status)
        if blocked:
            stock["blocked"] = True
        if flag:
            parts = [flag]
            if auditor:
                parts.append(auditor)
            if reason:
                parts.append(reason)
            _append_evidence(stock, " · ".join(parts))
        elif status == "CLEAR_CONFIRMED":
            parts = ["🟢 독립성 확인"]
            if auditor:
                parts.append(auditor)
            if reason:
                parts.append(reason)
            _append_evidence(stock, " · ".join(parts))

    net_flow = _optional_number(snap.get("net_flow_signal"))
    if net_flow is not None and net_flow < 0:
        _append_evidence(stock, "수급: 기관·외국인 순매도")

    short_ratio = _optional_number(snap.get("short_ratio"))
    if short_ratio is not None and short_ratio >= 5.0:
        _append_evidence(stock, f"공매도 비중 높음 (약 {short_ratio:.1f}%)")


def _overlay_catalysts(stock: dict, snap: dict) -> None:
    catalysts = [dict(item) for item in (snap.get("catalysts") or [])]
    if not catalysts:
        return
    stock["catalysts"] = catalysts
    label = str(catalysts[0].get("label") or "")
    if label:
        _append_evidence(stock, f"catalyst: {label}")


def _append_gap(stock: dict, message: str) -> None:
    gaps = list(stock.get("gaps") or [])
    if message not in gaps:
        gaps.append(message)
    stock["gaps"] = gaps


def _append_evidence(stock: dict, message: str) -> None:
    evidence = list(stock.get("evidence") or [])
    if message not in evidence:
        evidence.append(message)
    stock["evidence"] = evidence


def _optional_number(value) -> float | None:
    if value is None:
        return None
    try:  # 외부 snapshot dict의 비숫자(빈문자열/"N/A")에도 degrade — code review should-fix
        return float(value)
    except (TypeError, ValueError):
        return None
