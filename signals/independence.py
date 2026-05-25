"""Audit independence decision rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


def decide_independence(
    market: Market,
    audit_firm: dict,
    *,
    as_of_year: int | None = None,
) -> IndependenceDecision:
    target_year = as_of_year or date.today().year
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
        return IndependenceDecision("DATA_MISSING", f"감사인 확인 필요: {audit_firm['error']}")

    latest_year = _latest_audit_year(audit_firm)
    auditor = _current_auditor(audit_firm)
    if not auditor:
        return IndependenceDecision("DATA_MISSING", "감사인 데이터 없음. DART 원천 확인 필요.")

    normalized = _normalize_auditor(auditor)
    blocked = normalized in set(BLOCKED_ALIASES.values())
    display_auditor = normalized if blocked else auditor

    if latest_year is not None and latest_year >= target_year:
        if blocked:
            return IndependenceDecision("BLOCKED_CONFIRMED", f"{target_year} 감사인 직접 확인 · 차단 감사인: {normalized}", display_auditor)
        return IndependenceDecision("CLEAR_CONFIRMED", f"{target_year} 감사인 직접 확인 · 차단 감사인 없음", display_auditor)

    if latest_year == target_year - 1 and _same_auditor_streak(audit_firm, auditor) >= 2:
        if blocked:
            return IndependenceDecision(
                "BLOCKED_POSSIBLE",
                f"{target_year} 감사인 직접 확인 없음 · 직전 2개년 {normalized} · 매입 전 독립성 원천 확인 필요",
                display_auditor,
            )
        return IndependenceDecision(
            "ROLLOVER_INFERRED",
            f"{target_year} 감사인 직접 확인 없음 · 직전 2개년 동일 감사인 · 원천 확인 필요",
            display_auditor,
        )

    return IndependenceDecision(
        "MANUAL_VERIFY_CURRENT_YEAR",
        f"{target_year} 감사인 직접 확인 없음 · 직전 감사인 연속성 부족 또는 교체 가능성 확인 필요",
        display_auditor,
    )


def _current_auditor(audit_firm: dict) -> str | None:
    firm = audit_firm.get("current_firm")
    if firm:
        return str(firm)
    recent = audit_firm.get("recent") or []
    if recent and recent[0].get("firm"):
        return str(recent[0]["firm"])
    return None


def _latest_audit_year(audit_firm: dict) -> int | None:
    year = audit_firm.get("current_year")
    if isinstance(year, int):
        return year
    recent = audit_firm.get("recent") or []
    years = [row.get("year") for row in recent if isinstance(row.get("year"), int)]
    return max(years) if years else None


def _same_auditor_streak(audit_firm: dict, auditor: str) -> int:
    recent = sorted(
        audit_firm.get("recent") or [],
        key=lambda row: row.get("year") or 0,
        reverse=True,
    )
    normalized = _normalize_auditor(auditor)
    count = 0
    for row in recent:
        firm = row.get("firm")
        if firm and _normalize_auditor(str(firm)) == normalized:
            count += 1
            continue
        break
    return count


def _normalize_auditor(value: str) -> str:
    compact = value.replace(" ", "")
    for alias, canonical in BLOCKED_ALIASES.items():
        if compact == alias.replace(" ", ""):
            return canonical
    return value
