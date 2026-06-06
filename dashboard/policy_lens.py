"""Policy lenses for dashboard candidate discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pprint import pprint

from dashboard.models import LensKind


@dataclass(frozen=True)
class PolicyLens:
    id: str
    name: str
    kind: LensKind
    description: str
    conviction: str
    direction: str
    weights: dict[str, float]
    risks: list[str]


LOW_PBR_THRESHOLD: float = 0.5

VALUE_UP_LENS = PolicyLens(
    id="value_up_low_pbr",
    name="저PBR 밸류업",
    kind=LensKind.POLICY,
    description="정부 밸류업 프로그램이 저PBR 자산주 재평가를 유도하는지 추적하는 정책 렌즈.",
    conviction="medium",
    direction="long",
    weights={
        "valuation": 0.6,
        "quality": 0.2,
        "growth": 0.0,
        "revision": 0.1,
        "momentum": 0.1,
    },
    risks=[
        "밸류업 정책 동력 약화 시 저PBR 재평가 지연",
        "업황 회복 지연 시 자산가치 할인 지속",
    ],
)

CHIPS_LENS = PolicyLens(
    id="policy_chips_act",
    name="美 반도체 (CHIPS)",
    kind=LensKind.POLICY,
    description="美 CHIPS법 보조금·자국 생산 인센티브의 반도체 capex 수혜를 추적하는 정책 렌즈.",
    conviction="medium",
    direction="long",
    weights={"valuation": 0.1, "quality": 0.3, "growth": 0.4, "revision": 0.1, "momentum": 0.1},
    risks=[
        "보조금 집행 지연·정권 교체 시 capex 모멘텀 둔화",
        "반도체 다운사이클이 정책 수혜를 상쇄",
    ],
)

IRA_LENS = PolicyLens(
    id="policy_ira_clean_energy",
    name="美 IRA 청정에너지·배터리",
    kind=LensKind.POLICY,
    description="美 IRA 세액공제·현지 생산 요건의 배터리·청정에너지 수혜를 추적하는 정책 렌즈.",
    conviction="medium",
    direction="long",
    weights={"valuation": 0.1, "quality": 0.2, "growth": 0.4, "revision": 0.1, "momentum": 0.2},
    risks=[
        "IRA 축소·해외우려기관(FEOC) 규정 강화 시 한국 배터리 수혜 약화",
        "전기차 수요 둔화가 가동률·마진 압박",
    ],
)

KDEF_LENS = PolicyLens(
    id="policy_k_defense",
    name="K-방산 수출",
    kind=LensKind.POLICY,
    description="지정학 긴장·유럽 재무장 사이클의 한국 방산 수출 수주 모멘텀을 추적하는 정책 렌즈.",
    conviction="medium",
    direction="long",
    weights={"valuation": 0.1, "quality": 0.2, "growth": 0.3, "revision": 0.2, "momentum": 0.2},
    risks=[
        "휴전·지정학 완화 시 수주 모멘텀 둔화",
        "납기 지연·환율 변동이 수익 인식에 영향",
    ],
)

LOW_PBR_SEEDS = [
    "004020",
    "011170",
    "011780",
    "010060",
    "460860",
    "001430",
    "078930",
    "034730",
    "000880",
    "003240",
]

_SEED_DETAILS = {
    "004020": ("현대제철", "0.2배대", "철강 업황 회복 + 미국 투자 옵션"),
    "011170": ("롯데케미칼", "0.2배대", "석유화학 최악 업황 반영"),
    "011780": ("금호석유화학", "0.3배 전후", "고배당 + 화학 업황 회복 수혜"),
    "010060": ("OCI홀딩스", "0.3배 전후", "태양광 사이클 회복 기대"),
    "460860": ("동국제강", "0.2~0.3배", "철강 업황 레버리지"),
    "001430": ("세아베스틸지주", "0.2배대", "특수강 사이클"),
    "078930": ("GS", "0.3배대", "정유·발전 자산 보유"),
    "034730": ("SK", "0.3배대", "NAV 할인 극심"),
    "000880": ("한화", "0.3배대", "방산·태양광 가치 대비 할인"),
    "003240": ("태광산업", "0.2배대", "현금성 자산 많음"),
}

_NEUTRAL_METRICS = {
    "valuation": 50,
    "quality": 50,
    "growth": 50,
    "revision": 50,
    "momentum": 50,
}


def policy_lenses() -> list[PolicyLens]:
    return [VALUE_UP_LENS, CHIPS_LENS, IRA_LENS, KDEF_LENS]


# 시드 종목: code -> (company, sector_label, feature). lens별 큐레이션 수혜주.
_POLICY_SEED_GROUPS: list[tuple[PolicyLens, dict[str, tuple[str, str, str]]]] = [
    (
        CHIPS_LENS,
        {
            "INTC": ("인텔", "美 반도체 (CHIPS)", "美 파운드리 보조금 최대 수혜·자국 생산"),
            "MU": ("마이크론", "美 반도체 (CHIPS)", "메모리 美 증설·보조금 대상"),
            "TSM": ("TSMC", "美 반도체 (CHIPS)", "애리조나 팹 보조금·선단공정"),
            "GFS": ("글로벌파운드리", "美 반도체 (CHIPS)", "성숙공정 자국 생산 수혜"),
            "TXN": ("텍사스인스트루먼트", "美 반도체 (CHIPS)", "아날로그 美 증설·보조금"),
        },
    ),
    (
        IRA_LENS,
        {
            "373220": ("LG에너지솔루션", "美 IRA 청정에너지·배터리", "美 현지생산 세액공제(AMPC) 최대 수혜"),
            "006400": ("삼성SDI", "美 IRA 청정에너지·배터리", "美 합작 증설·AMPC 수혜"),
            "005490": ("POSCO홀딩스", "美 IRA 청정에너지·배터리", "양극재·리튬 밸류체인 현지화"),
            "FSLR": ("퍼스트솔라", "美 IRA 청정에너지·배터리", "美 태양광 모듈 생산 세액공제"),
            "ENPH": ("엔페이즈", "美 IRA 청정에너지·배터리", "주거용 태양광 인버터 IRA 수요"),
        },
    ),
    (
        KDEF_LENS,
        {
            "012450": ("한화에어로스페이스", "K-방산 수출", "유럽·중동 수출 + 우주/엔진"),
            "079550": ("LIG디펜스앤에어로스페이스", "K-방산 수출", "유도무기 수출 수주 모멘텀"),
            "064350": ("현대로템", "K-방산 수출", "K2 전차 폴란드 등 수출"),
            "047810": ("한국항공우주", "K-방산 수출", "FA-50 경공격기 수출"),
            "042660": ("한화오션", "K-방산 수출", "함정 수출 + 방산 조선"),
        },
    ),
]


def low_pbr_seed_stocks() -> list[dict]:
    return [_seed_to_stock(code) for code in LOW_PBR_SEEDS]


def policy_seed_stocks() -> list[dict]:
    """모든 정책 렌즈의 시드 종목(저PBR + CHIPS/IRA/K-방산)."""
    stocks = low_pbr_seed_stocks()
    for lens, seeds in _POLICY_SEED_GROUPS:
        for code, (name, sector, feature) in seeds.items():
            stocks.append(_policy_seed_to_stock(code, lens, name, sector, feature))
    return stocks


def _policy_seed_to_stock(code: str, lens: PolicyLens, name: str, sector: str, feature: str) -> dict:
    return {
        "ticker": code,
        "company": name,
        "sector": sector,
        "lens_ids": [lens.id],
        "thesis": f"{name}: {lens.name} 정책 수혜 후보 - {feature}.",
        "metrics": dict(_NEUTRAL_METRICS),
        "evidence": [f"{lens.name} 정책 시드", feature],
        "bull_case": [f"{lens.name} 정책 동력 강화 시 {name} 수혜 - {feature}"],
        "bear_case": [f"{lens.name} 정책 후퇴·집행/수주 지연 시 모멘텀 약화."],
        "gaps": [f"{lens.name} 시드 - 실데이터(가격·수주/실적·가이던스) 스냅샷 overlay 필요"],
        "next_action": f"{name} 관련 정책 집행·수주/가이던스 업데이트 확인.",
        "source_refs": [f"{lens.name} 정책 렌즈"],
        "peer_group": sector,
    }


def _seed_to_stock(code: str) -> dict:
    name, pbr_band, feature = _SEED_DETAILS[code]
    return {
        "ticker": code,
        "company": name,
        "sector": "저PBR 밸류업",
        "lens_ids": [VALUE_UP_LENS.id],
        "thesis": (
            f"{name}: 정부 밸류업 프로그램이 저PBR 자산주({pbr_band}) "
            f"재평가를 유도하는지 보는 정책 카드 - {feature}."
        ),
        "metrics": dict(_NEUTRAL_METRICS),
        "evidence": [f"저PBR 밸류업 시드: 대략 PBR {pbr_band}", feature],
        "bull_case": [
            f"밸류업(자사주·배당) 강화 시 {pbr_band} 저PBR 재평가 여지 - {feature}"
        ],
        "bear_case": [
            "정책 동력이나 업황 회복이 늦으면 자산가치 할인이 지속될 수 있음."
        ],
        "gaps": [
            "저PBR 밸류업 시드 - 실데이터(PBR·가격·자사주/배당 공시) 스냅샷 overlay 필요",
            "PBR 임계 자동 스크린은 live overlay에서 보강",
        ],
        "next_action": "최근 PBR, 자사주 소각/배당 정책 공시, 업황 회복 신호를 확인.",
        "source_refs": ["저PBR 밸류업 정책 렌즈"],
        "peer_group": "저PBR 밸류업",
    }


def main() -> None:
    pprint(policy_lenses())
    pprint(low_pbr_seed_stocks()[:3])


if __name__ == "__main__":
    main()
