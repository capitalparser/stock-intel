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
    return [VALUE_UP_LENS]


def low_pbr_seed_stocks() -> list[dict]:
    return [_seed_to_stock(code) for code in LOW_PBR_SEEDS]


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
