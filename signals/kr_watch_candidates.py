"""Korean equity watchlist candidate scoring and sector sectioning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from signals.independence import decide_independence
from signals.market import Market


@dataclass(frozen=True)
class CandidateSeed:
    symbol: str
    name: str
    sector: str
    thesis_fit: int
    contract_visibility: int
    notes: str


@dataclass(frozen=True)
class CandidateEvaluation:
    symbol: str
    name: str
    sector: str
    thesis_fit: int
    profit_improvement: int
    contract_visibility: int
    cashflow: int
    financial_stability: int
    risk: int
    total_score: int
    status: str
    audit_status: str
    auditor: str | None
    notes: str


SECTOR_ORDER = (
    "반도체/HBM/소부장",
    "전력기기/전선/ESS/원전",
    "조선/방산",
    "금융/증권/지주사",
    "AI 소프트웨어/플랫폼",
)


KR_CANDIDATE_SEEDS: tuple[CandidateSeed, ...] = (
    CandidateSeed("KRX:000660", "SK하이닉스", "반도체/HBM/소부장", 20, 16, "HBM/AI 메모리 대표주"),
    CandidateSeed("KRX:042700", "한미반도체", "반도체/HBM/소부장", 19, 17, "HBM TC bonder/패키징 장비"),
    CandidateSeed("KRX:039030", "이오테크닉스", "반도체/HBM/소부장", 17, 13, "레이저 장비/패키징 공정"),
    CandidateSeed("KRX:089030", "테크윙", "반도체/HBM/소부장", 17, 13, "검사장비/AI 반도체 테스트"),
    CandidateSeed("KRX:095340", "ISC", "반도체/HBM/소부장", 16, 12, "테스트 소켓/고부가 반도체"),
    CandidateSeed("KRX:058470", "리노공업", "반도체/HBM/소부장", 16, 11, "테스트 핀/소켓 고마진"),
    CandidateSeed("KRX:036930", "주성엔지니어링", "반도체/HBM/소부장", 15, 11, "ALD/증착 장비"),
    CandidateSeed("KRX:403870", "HPSP", "반도체/HBM/소부장", 16, 12, "고압수소 어닐링 장비"),
    CandidateSeed("KRX:010120", "LS ELECTRIC", "전력기기/전선/ESS/원전", 18, 17, "전력기기/북미 전력망"),
    CandidateSeed("KRX:103590", "일진전기", "전력기기/전선/ESS/원전", 18, 18, "전선/변압기 수주잔고 후보"),
    CandidateSeed("KRX:267260", "HD현대일렉트릭", "전력기기/전선/ESS/원전", 20, 19, "변압기/북미 전력기기 대표주"),
    CandidateSeed("KRX:298040", "효성중공업", "전력기기/전선/ESS/원전", 18, 17, "초고압 변압기/중공업"),
    CandidateSeed("KRX:033100", "제룡전기", "전력기기/전선/ESS/원전", 16, 15, "배전 변압기"),
    CandidateSeed("KRX:001440", "대한전선", "전력기기/전선/ESS/원전", 15, 15, "전선/해저케이블 후보"),
    CandidateSeed("KRX:034020", "두산에너빌리티", "전력기기/전선/ESS/원전", 17, 16, "원전/SMR/가스터빈"),
    CandidateSeed("KRX:083650", "비에이치아이", "전력기기/전선/ESS/원전", 15, 15, "원전/발전 보조기기"),
    CandidateSeed("KRX:009540", "HD한국조선해양", "조선/방산", 18, 18, "조선 지주/수주잔고"),
    CandidateSeed("KRX:329180", "HD현대중공업", "조선/방산", 18, 18, "LNG/고부가 선종"),
    CandidateSeed("KRX:010620", "HD현대미포", "조선/방산", 16, 15, "중형선/인도 정상화"),
    CandidateSeed("KRX:010140", "삼성중공업", "조선/방산", 16, 16, "LNG/해양플랜트"),
    CandidateSeed("KRX:042660", "한화오션", "조선/방산", 17, 17, "특수선/방산/조선"),
    CandidateSeed("KRX:012450", "한화에어로스페이스", "조선/방산", 20, 19, "방산 수출/엔진"),
    CandidateSeed("KRX:064350", "현대로템", "조선/방산", 18, 18, "방산 수출/철도"),
    CandidateSeed("KRX:079550", "LIG넥스원", "조선/방산", 18, 17, "미사일/방산 수출"),
    CandidateSeed("KRX:047810", "한국항공우주", "조선/방산", 16, 16, "항공/방산 수출"),
    CandidateSeed("KRX:105560", "KB금융", "금융/증권/지주사", 18, 10, "밸류업/주주환원"),
    CandidateSeed("KRX:055550", "신한지주", "금융/증권/지주사", 17, 10, "은행 지주/주주환원"),
    CandidateSeed("KRX:086790", "하나금융지주", "금융/증권/지주사", 17, 10, "은행 지주/ROE"),
    CandidateSeed("KRX:316140", "우리금융지주", "금융/증권/지주사", 16, 9, "은행 지주/배당"),
    CandidateSeed("KRX:138040", "메리츠금융지주", "금융/증권/지주사", 18, 11, "자사주/주주환원"),
    CandidateSeed("KRX:039490", "키움증권", "금융/증권/지주사", 15, 8, "거래대금 민감도"),
    CandidateSeed("KRX:071050", "한국금융지주", "금융/증권/지주사", 15, 8, "증권/IB/브로커리지"),
    CandidateSeed("KRX:035420", "NAVER", "AI 소프트웨어/플랫폼", 18, 12, "AI/광고/커머스/클라우드"),
    CandidateSeed("KRX:035720", "카카오", "AI 소프트웨어/플랫폼", 14, 9, "플랫폼/AI 턴어라운드 후보"),
    CandidateSeed("KRX:012510", "더존비즈온", "AI 소프트웨어/플랫폼", 18, 15, "ERP/AI SaaS/공공"),
    CandidateSeed("KRX:018260", "삼성에스디에스", "AI 소프트웨어/플랫폼", 16, 11, "클라우드/물류/생성AI"),
    CandidateSeed("KRX:300080", "플리토", "AI 소프트웨어/플랫폼", 15, 11, "언어 데이터/AI"),
    CandidateSeed("KRX:041020", "폴라리스오피스", "AI 소프트웨어/플랫폼", 14, 9, "AI 오피스/구독 전환"),
    CandidateSeed("KRX:304100", "솔트룩스", "AI 소프트웨어/플랫폼", 14, 9, "LLM/AI 솔루션"),
    CandidateSeed("KRX:377480", "마음AI", "AI 소프트웨어/플랫폼", 13, 8, "AI 에이전트/솔루션"),
)


def evaluate_candidate(
    seed: CandidateSeed,
    *,
    fundamental: dict,
    audit: dict,
    as_of_year: int | None = None,
) -> CandidateEvaluation:
    profit = _score_profit_improvement(fundamental)
    cashflow = _score_cashflow(fundamental)
    stability = _score_financial_stability(fundamental)
    risk = _score_risk(fundamental)
    total = max(0, seed.thesis_fit + profit + seed.contract_visibility + cashflow + stability + risk)
    decision = decide_independence(Market("KR", "한국"), audit, as_of_year=as_of_year or date.today().year)
    blocked = decision.status in {"BLOCKED_CONFIRMED", "BLOCKED_POSSIBLE"}
    return CandidateEvaluation(
        symbol=seed.symbol,
        name=seed.name,
        sector=seed.sector,
        thesis_fit=seed.thesis_fit,
        profit_improvement=profit,
        contract_visibility=seed.contract_visibility,
        cashflow=cashflow,
        financial_stability=stability,
        risk=risk,
        total_score=total,
        status=watch_status(total, blocked=blocked),
        audit_status=decision.status,
        auditor=decision.auditor,
        notes=seed.notes,
    )


def watch_status(total_score: int, *, blocked: bool) -> str:
    if blocked:
        if total_score >= 80:
            return "Blocked Core Watch"
        if total_score >= 65:
            return "Blocked Watch"
        if total_score >= 50:
            return "Blocked Hold for Proof"
        return "Exclude (Blocked)"
    if total_score >= 80:
        return "Core Watch"
    if total_score >= 65:
        return "Watch"
    if total_score >= 50:
        return "Hold for Proof"
    return "Exclude"


def group_by_sector(evaluations: list[CandidateEvaluation]) -> dict[str, list[CandidateEvaluation]]:
    grouped: dict[str, list[CandidateEvaluation]] = {sector: [] for sector in SECTOR_ORDER}
    for item in sorted(evaluations, key=lambda row: (-row.total_score, row.symbol)):
        grouped.setdefault(item.sector, []).append(item)
    return {sector: rows for sector, rows in grouped.items() if rows}


def format_candidate_report(evaluations: list[CandidateEvaluation]) -> str:
    lines = ["# KR Watchlist Candidates", ""]
    for sector, rows in group_by_sector(evaluations).items():
        lines.extend([f"## {sector}", ""])
        for row in rows:
            lines.append(
                f"- {row.name} ({row.symbol}) | {row.total_score} | {row.status} | "
                f"감사인 {row.audit_status} {row.auditor or '-'} | {row.notes}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_tradingview_watchlist_sections(
    evaluations: list[CandidateEvaluation],
    *,
    min_score: int = 50,
) -> str:
    lines: list[str] = []
    for sector, rows in group_by_sector(evaluations).items():
        selected = [row for row in rows if row.total_score >= min_score]
        if not selected:
            continue
        lines.append(f"###{sector}")
        lines.extend(row.symbol for row in selected)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_candidate_outputs(
    evaluations: list[CandidateEvaluation],
    *,
    report_path: str | Path,
    watchlist_path: str | Path,
) -> None:
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(format_candidate_report(evaluations), encoding="utf-8")
    Path(watchlist_path).parent.mkdir(parents=True, exist_ok=True)
    Path(watchlist_path).write_text(format_tradingview_watchlist_sections(evaluations), encoding="utf-8")


def _score_profit_improvement(fundamental: dict) -> int:
    financials = _financials(fundamental)
    if len(financials) < 2:
        return 8
    first = financials[0]
    latest = financials[-1]
    revenue_up = _num(latest.get("revenue")) > _num(first.get("revenue"))
    op_up = _num(latest.get("operating_income")) > _num(first.get("operating_income"))
    if revenue_up and op_up:
        return 20
    if revenue_up or op_up:
        return 14
    return 6


def _score_cashflow(fundamental: dict) -> int:
    financials = _financials(fundamental)
    if not financials:
        return 7
    ocfs = [_num(row.get("operating_cash_flow")) for row in financials if row.get("operating_cash_flow") is not None]
    if not ocfs:
        return 7
    if all(value > 0 for value in ocfs[-2:]):
        return 15
    if ocfs[-1] > 0:
        return 11
    if all(value < 0 for value in ocfs[-2:]):
        return 0
    return 6


def _score_financial_stability(fundamental: dict) -> int:
    return 11 if _financials(fundamental) else 7


def _score_risk(fundamental: dict) -> int:
    financials = _financials(fundamental)
    if len(financials) < 2:
        return -6
    first = financials[0]
    latest = financials[-1]
    first_margin = _margin(first)
    latest_margin = _margin(latest)
    if first_margin is not None and latest_margin is not None and latest_margin < first_margin * 0.65:
        return -12
    latest_ocf = latest.get("operating_cash_flow")
    latest_op = latest.get("operating_income")
    if latest_ocf is not None and latest_op is not None and _num(latest_ocf) < 0 < _num(latest_op):
        return -10
    return 0


def _financials(fundamental: dict) -> list[dict]:
    rows = fundamental.get("financials") or []
    return sorted(rows, key=lambda row: row.get("year") or 0)


def _margin(row: dict) -> float | None:
    revenue = _num(row.get("revenue"))
    if revenue == 0:
        return None
    return _num(row.get("operating_income")) / revenue


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
