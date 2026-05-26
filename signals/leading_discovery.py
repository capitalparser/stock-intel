"""Pre-signal discovery scoring for Korean equities.

The goal is to surface names where supply and setup improve before price has
fully reflected the move. Lazy Alpha remains the later confirmation layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadingCandidate:
    symbol: str
    name: str
    total_score: int
    leading_score: int
    supply_score: int
    setup_score: int
    fundamental_score: int
    risk_penalty: int
    state: str
    evidence: list[str]
    risks: list[str]
    next_trigger: str
    auditor: str


def score_leading_candidate(
    *,
    symbol: str,
    name: str,
    supply: dict,
    technical: dict,
    fundamental: dict,
    auditor: str,
) -> LeadingCandidate:
    supply_score, supply_evidence, supply_risks = _score_supply(supply)
    setup_score, setup_evidence, setup_risks = _score_setup(technical)
    fundamental_score, fundamental_evidence, fundamental_risks = _score_fundamental(fundamental)
    risk_penalty, risk_notes = _risk_penalty(technical, supply)
    leading_score = min(50, round(supply_score * 0.9 + setup_score * 0.45 + fundamental_score * 0.2))
    total = max(0, min(100, leading_score + setup_score + fundamental_score - risk_penalty))
    risks = [*risk_notes, *supply_risks, *setup_risks, *fundamental_risks]
    evidence = [*supply_evidence, *setup_evidence, *fundamental_evidence]
    if total >= 80 and risk_penalty <= 15:
        state = "선행 후보"
    elif total >= 65:
        state = "관찰"
    else:
        state = "대기"
    return LeadingCandidate(
        symbol=symbol,
        name=name,
        total_score=total,
        leading_score=leading_score,
        supply_score=supply_score,
        setup_score=setup_score,
        fundamental_score=fundamental_score,
        risk_penalty=risk_penalty,
        state=state,
        evidence=evidence[:5] or ["선행 근거 부족"],
        risks=risks[:4],
        next_trigger=_next_trigger(technical, risks),
        auditor=auditor,
    )


def format_leading_report(
    candidates: list[LeadingCandidate],
    *,
    scanned: int,
    errors: list[tuple[str, str]],
    limit: int = 12,
) -> str:
    ordered = sorted(candidates, key=lambda row: (-row.total_score, -row.leading_score, row.symbol))
    lines = [
        "🔎 국장 선행 후보",
        "목적: 이미 오른 뒤 반응보다, 수급+차트 전조로 시세 반영 전 후보를 먼저 압축",
        f"스캔: {scanned}종목 · 후보: {len(ordered)}건 · 오류: {len(errors)}건",
        "정렬: 종합점수 높은 순",
        "",
    ]
    if not ordered:
        lines.extend(
            [
                "표시할 선행 후보가 없습니다.",
                "조건: 기관/외국인 누적 매집 + 과열 전 차트 셋업 + 펀더멘탈 훼손 없음",
            ]
        )
    for index, item in enumerate(ordered[:limit], start=1):
        risks = "없음" if not item.risks else " · ".join(item.risks)
        lines.extend(
            [
                f"{index}. {item.symbol} · {item.name} · 종합 {item.total_score}점",
                f"상태: {item.state}",
                (
                    f"점수: 선행 {item.leading_score}/50 · 수급 {item.supply_score}/35 · "
                    f"진입준비 {item.setup_score}/30 · 펀더멘탈 {item.fundamental_score}/20 · "
                    f"리스크 -{item.risk_penalty}"
                ),
                "근거: " + " · ".join(item.evidence),
                f"리스크: {risks}",
                f"다음 조건: {item.next_trigger}",
                f"감사인: {item.auditor}",
                "",
            ]
        )
    if errors:
        lines.append("오류: " + " · ".join(symbol for symbol, _error in errors[:5]))
    return "\n".join(lines).rstrip()


def _score_supply(supply: dict) -> tuple[int, list[str], list[str]]:
    if supply.get("error"):
        return 0, [], ["수급 데이터 없음"]
    inst = supply.get("institution") or {}
    fore = supply.get("foreigner") or {}
    score = 0
    evidence: list[str] = []
    risks: list[str] = []

    inst_20d = _num(inst.get("20d"))
    inst_5d = _num(inst.get("5d"))
    inst_today = _num(inst.get("today"))
    fore_20d = _num(fore.get("20d"))
    fore_5d = _num(fore.get("5d"))
    fore_today = _num(fore.get("today"))

    if inst_20d > 0:
        score += 8
        evidence.append(f"기관 20일 순매수 {_fmt_amount(inst_20d)}")
    if inst_5d > 0:
        score += 5
        evidence.append(f"기관 5일 순매수 {_fmt_amount(inst_5d)}")
    if inst_today > 0:
        score += 2
    if fore_20d > 0:
        score += 8
        evidence.append(f"외국인 20일 순매수 {_fmt_amount(fore_20d)}")
    if fore_5d > 0:
        score += 5
        evidence.append(f"외국인 5일 순매수 {_fmt_amount(fore_5d)}")
    if fore_today > 0:
        score += 2
    if inst_20d > 0 and fore_20d > 0:
        score += 5
        evidence.append("기관+외국인 20일 동반 매집")

    daily = supply.get("daily") or []
    recent_positive = sum(
        1
        for row in daily[:5]
        if _num(row.get("institution")) + _num(row.get("foreigner")) > 0
    )
    if recent_positive >= 4:
        score += 5
        evidence.append(f"최근 5거래일 중 {recent_positive}일 순매수 우위")

    if inst_20d < 0 and fore_20d < 0:
        risks.append("기관+외국인 20일 동반 순매도")
    elif inst_20d * fore_20d < 0:
        risks.append("기관/외국인 수급 엇갈림")
    return min(score, 35), evidence, risks


def _score_setup(technical: dict) -> tuple[int, list[str], list[str]]:
    if technical.get("error"):
        return 0, [], ["기술 데이터 없음"]
    score = 0
    evidence: list[str] = []
    risks: list[str] = []
    price = _num(technical.get("price"))
    ma20 = _num(technical.get("ma20"))
    ma50 = _num(technical.get("ma50"))
    ma150 = _num(technical.get("ma150"))
    ma200 = _num(technical.get("ma200"))
    volume_ratio = _optional_num(technical.get("volume_ratio"))
    rsi = _optional_num(technical.get("rsi14"))
    bb_pct = _optional_num(technical.get("bb_pct"))
    from_high = _optional_num(technical.get("from_52w_high_pct"))

    if technical.get("trend_template") == "통과":
        score += 8
        evidence.append("성장주 추세 템플릿 통과")
    elif technical.get("ma_trend") == "정배열":
        score += 5
        evidence.append("단기 이평 정배열")

    if price and ma20 and price >= ma20:
        score += 5
        evidence.append("20일선 위")
    if price and ma50 and price >= ma50:
        score += 5
        evidence.append("50일선 위")
    if price and ma50 and ma150 and ma200 and ma50 >= ma150 >= ma200:
        score += 5
        evidence.append("중장기 이평 배열 개선")
    if volume_ratio is not None:
        if 1.0 <= volume_ratio <= 2.2:
            score += 5
            evidence.append(f"거래량 조용한 증가 {volume_ratio:.2f}x")
        elif volume_ratio > 3.0:
            risks.append("거래량 급증 후 추격 위험")
    if from_high is not None and -25 <= from_high <= -5:
        score += 2
        evidence.append(f"52주 고점 대비 {from_high:.1f}%")
    if rsi is not None and 45 <= rsi <= 68:
        score += 3
        evidence.append(f"RSI {rsi:.0f} 중립 우상향")
    if bb_pct is not None and 35 <= bb_pct <= 85:
        score += 2

    if technical.get("signal") in {"매도", "손절"}:
        risks.append(f"기술 시그널 {technical.get('signal')}")
    if price and ma50 and price < ma50:
        risks.append("50일선 아래")
    return min(score, 30), evidence, risks


def _score_fundamental(fundamental: dict) -> tuple[int, list[str], list[str]]:
    if fundamental.get("error"):
        return 0, [], ["펀더멘탈 데이터 없음"]
    rows = sorted(fundamental.get("financials") or [], key=lambda row: row.get("year") or 0)
    if len(rows) < 2:
        return 8, ["펀더멘탈 확인 제한"], []
    first = rows[0]
    latest = rows[-1]
    score = 0
    evidence: list[str] = []
    risks: list[str] = []
    if _num(latest.get("revenue")) > _num(first.get("revenue")):
        score += 6
        evidence.append("매출 개선")
    if _num(latest.get("operating_income")) > _num(first.get("operating_income")):
        score += 8
        evidence.append("영업이익 개선")
    ocf = latest.get("operating_cash_flow")
    if ocf is not None and _num(ocf) > 0:
        score += 6
        evidence.append("영업CF 양호")
    elif ocf is not None and _num(latest.get("operating_income")) > 0:
        risks.append("이익 대비 현금흐름 약함")
    return min(score, 20), evidence, risks


def _risk_penalty(technical: dict, supply: dict) -> tuple[int, list[str]]:
    penalty = 0
    risks: list[str] = []
    rsi = _optional_num(technical.get("rsi14"))
    bb_pct = _optional_num(technical.get("bb_pct"))
    volume_ratio = _optional_num(technical.get("volume_ratio"))
    from_low = _optional_num(technical.get("from_52w_low_pct"))
    if rsi is not None and rsi >= 75:
        penalty += 10
        risks.append("RSI 과열")
    if bb_pct is not None and bb_pct >= 110:
        penalty += 8
        risks.append("볼린저 상단 과확장")
    if volume_ratio is not None and volume_ratio >= 3.0:
        penalty += 7
        risks.append("거래량 급증")
    if from_low is not None and from_low >= 150:
        penalty += 12
        risks.append("이미 시세 반영 가능성 높음")
    if technical.get("signal") in {"매도", "손절"}:
        penalty += 10
    inst_20d = _num((supply.get("institution") or {}).get("20d"))
    fore_20d = _num((supply.get("foreigner") or {}).get("20d"))
    if inst_20d < 0 and fore_20d < 0:
        penalty += 8
    return min(penalty, 40), risks


def _next_trigger(technical: dict, risks: list[str]) -> str:
    if technical.get("signal") in {"매도", "손절"}:
        return "SELL/손절 상태 해소 후 20일선 회복 확인"
    if any("50일선 아래" in risk for risk in risks):
        return "50일선 회복 후 Lazy Alpha 진입 라벨 확인"
    if technical.get("signal") == "진입":
        return "Lazy Alpha 활성 진입 여부와 감사인 독립성 확인"
    return "20일선 지지 후 Lazy Alpha 진입 라벨 확인"


def _fmt_amount(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value / 100_000_000:,.0f}억"


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
