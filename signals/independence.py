"""Audit independence decision rules."""

from __future__ import annotations

from dataclasses import dataclass

from signals.market import Market

BLOCKED_ALIASES = {
    "삼정회계법인": "삼정회계법인",
    "삼정KPMG": "삼정회계법인",
    "삼정 KPMG": "삼정회계법인",
    "KPMG삼정": "삼정회계법인",
}


@dataclass(frozen=True)
class IndependenceDecision:
    status: str
    reason: str
    auditor: str | None = None


def decide_independence(market: Market, audit_firm: dict) -> IndependenceDecision:
    if market.code == "US":
        return IndependenceDecision(
            "MANUAL_VERIFY",
            "미국 종목 감사인 자동 확인 미지원. EDGAR/10-K 등 원천 확인 필요.",
        )
    if market.code == "JP":
        return IndependenceDecision(
            "MANUAL_VERIFY",
            "일본 종목 감사인 자동 확인 미지원. EDINET/유가증권보고서 등 원천 확인 필요.",
        )
    if market.code != "KR":
        return IndependenceDecision("UNKNOWN_MARKET", "시장 분류 실패. 원천 확인 필요.")

    if audit_firm.get("error"):
        return IndependenceDecision("MANUAL_VERIFY", f"감사인 확인 필요: {audit_firm['error']}")

    auditor = _current_auditor(audit_firm)
    if not auditor:
        return IndependenceDecision("MANUAL_VERIFY", "감사인 데이터 없음. DART 원천 확인 필요.")

    normalized = _normalize_auditor(auditor)
    if normalized in set(BLOCKED_ALIASES.values()):
        return IndependenceDecision("BLOCKED", f"차단 감사인: {normalized}", normalized)
    return IndependenceDecision("CLEAR", "차단 감사인 없음", auditor)


def _current_auditor(audit_firm: dict) -> str | None:
    firm = audit_firm.get("current_firm")
    if firm:
        return str(firm)
    recent = audit_firm.get("recent") or []
    if recent and recent[0].get("firm"):
        return str(recent[0]["firm"])
    return None


def _normalize_auditor(value: str) -> str:
    compact = value.replace(" ", "")
    for alias, canonical in BLOCKED_ALIASES.items():
        if compact == alias.replace(" ", ""):
            return canonical
    return value

