"""Audit-independence overlay for dashboard candidates (Plan 5).

기존 자산 재사용: data.audit_firm.fetch_audit_firm + signals.independence.
KR 6자리만 실제 판정. 비-KR(classify_market이 KR/US만 구분)·kreports 미가용은
graceful degrade(MANUAL_VERIFY / DATA_MISSING → 🟡).
"""

from __future__ import annotations

from data.audit_firm import fetch_audit_firm
from dashboard.providers.base import classify_market
from signals.independence import decide_independence
from signals.market import Market

_BLOCKED = {"BLOCKED_CONFIRMED", "BLOCKED_POSSIBLE"}
_MANUAL = {
    "MANUAL_VERIFY",
    "MANUAL_VERIFY_CURRENT_YEAR",
    "ROLLOVER_INFERRED",
    "DATA_MISSING",
    "UNKNOWN_MARKET",
}
_BLOCKED_LABELS = {
    "BLOCKED_CONFIRMED": "🚫 독립성 차단 — 매입 검토 금지",
    "BLOCKED_POSSIBLE": "🚫 독립성 차단 가능 — 원천 확인 전 보류",
}


def independence_flag(status: str | None) -> tuple[str | None, bool]:
    """status -> (risk_flag or None, blocked). CLEAR_CONFIRMED → (None, False)."""
    if status in _BLOCKED:
        return _BLOCKED_LABELS[str(status)], True
    if status in _MANUAL:
        return "🟡 독립성 확인 필요", False
    return None, False


def fetch_independence(ticker: str, *, as_of_year: int | None = None) -> dict:
    """KR 6자리만 실제 판정. 비-KR은 MANUAL_VERIFY, kreports 실패는 DATA_MISSING."""
    market = classify_market(ticker)
    if market != "KR":
        return {
            "status": "MANUAL_VERIFY",
            "auditor": None,
            "reason": f"{market} 종목 감사인 자동 확인 미지원 → 원천 확인 필요",
        }
    try:
        audit = fetch_audit_firm(ticker)
    except Exception as exc:  # pragma: no cover - defensive degrade
        return {"status": "DATA_MISSING", "auditor": None, "reason": f"감사인 조회 실패: {type(exc).__name__}"}
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=as_of_year)
    return {"status": decision.status, "auditor": decision.auditor, "reason": decision.reason}
