"""Curated v1 seed data for local dashboard rendering."""

from __future__ import annotations

from dashboard.models import DashboardInput, parse_dashboard_input


SAMPLE_DASHBOARD = {
    "as_of": "2026-05-29",
    "regime": {
        "verdict": "conditional",
        "risk_appetite": "risk-on",
        "rates": "stable",
        "dollar": "stable",
        "volatility": "low",
        "notes": [
            "AI 인프라 수요는 살아 있지만 반도체 주가는 조정을 받을 수 있습니다.",
            "전력·아날로그 반도체는 AI 인프라의 2차 병목이 될 수 있습니다.",
        ],
    },
    "lenses": [
        {
            "id": "ai_agent_compute",
            "kind": "thesis",
            "name": "AI 에이전트 컴퓨팅",
            "conviction": "high",
            "direction": "improving",
            "weights": {
                "growth": 0.35,
                "revision": 0.25,
                "valuation": 0.15,
                "momentum": 0.15,
                "quality": 0.10,
            },
            "risks": ["빅테크 투자 피로"],
        },
        {
            "id": "ai_power_bottleneck",
            "kind": "thesis",
            "name": "AI 전력 병목",
            "conviction": "high",
            "direction": "improving",
            "weights": {
                "growth": 0.25,
                "revision": 0.25,
                "valuation": 0.20,
                "quality": 0.15,
                "momentum": 0.15,
            },
            "risks": ["늦은 사이클의 가격 인상"],
        },
        {
            "id": "low_per_revision",
            "kind": "factor",
            "name": "저PER + 이익상향",
            "conviction": "medium",
            "direction": "improving",
            "weights": {
                "valuation": 0.40,
                "revision": 0.30,
                "quality": 0.15,
                "growth": 0.10,
                "momentum": 0.05,
            },
            "risks": ["싸 보이는 함정"],
        },
        {
            "id": "semiconductors",
            "kind": "sector",
            "name": "반도체",
            "conviction": "medium",
            "direction": "stable",
            "weights": {
                "growth": 0.25,
                "revision": 0.20,
                "valuation": 0.25,
                "momentum": 0.20,
                "quality": 0.10,
            },
            "risks": ["밸류에이션 부담"],
        },
        {
            "id": "power_analog",
            "kind": "sector",
            "name": "전력·아날로그 반도체",
            "conviction": "medium",
            "direction": "improving",
            "weights": {
                "valuation": 0.25,
                "quality": 0.20,
                "growth": 0.20,
                "revision": 0.20,
                "momentum": 0.15,
            },
            "risks": ["자동차·산업재 사이클 부담"],
        },
        {
            "id": "risk_on_liquidity",
            "kind": "macro",
            "name": "위험자산 선호",
            "conviction": "medium",
            "direction": "stable",
            "weights": {
                "momentum": 0.35,
                "growth": 0.25,
                "revision": 0.20,
                "quality": 0.10,
                "valuation": 0.10,
            },
            "risks": ["유동성 반전"],
        },
    ],
    "stocks": [
        {
            "ticker": "ON",
            "company": "ON Semiconductor",
            "sector": "Power Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog", "low_per_revision"],
            "thesis": "AI 서버 전력 공급망이 타이트해질수록 전력반도체 쪽으로 수혜가 번질 수 있는 후보.",
            "metrics": {
                "valuation": 74,
                "quality": 58,
                "growth": 66,
                "revision": 70,
                "momentum": 60,
            },
            "evidence": ["AI 데이터센터 사업이 강하게 성장했다는 회사 측 언급"],
            "bull_case": [
                "GPU/HBM 중심 랠리 이후 전력반도체 병목으로 관심이 이동할 때 민감도가 큼.",
                "저평가·이익상향 관점이 함께 붙으면 단순 경기민감주가 아니라 재평가 후보가 됨.",
            ],
            "bear_case": [
                "자동차·EV·SiC 사이클 둔화가 AI 데이터센터 성장 신호를 희석할 수 있음.",
                "가격 인상 뉴스가 실제 마진 개선이 아니라 원가 전가에 그치면 매력도가 약해짐.",
            ],
            "gaps": ["다음 공시 후 정상화 이익 기준 가치평가 재확인 필요"],
            "next_action": "다음 실적에서 AI 데이터센터 매출, 매출총이익률, 재고 흐름을 먼저 확인.",
        },
        {
            "ticker": "TXN",
            "company": "Texas Instruments",
            "sector": "Analog Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog"],
            "thesis": "가장 넓은 아날로그·전력관리 노출을 가진 품질주. AI 전력 수요가 산업재 회복과 겹치면 방어적인 2차 수혜가 가능.",
            "metrics": {
                "valuation": 48,
                "quality": 78,
                "growth": 58,
                "revision": 62,
                "momentum": 68,
            },
            "evidence": ["산업재와 데이터센터 수요 언급이 전력관리 노출을 뒷받침"],
            "bull_case": [
                "PMIC, 전력관리, 산업재 수요를 넓게 받는 구조라 단일 제품 리스크가 낮음.",
                "데이터센터 전력 체인이 넓어질수록 범용 아날로그 부품 수요가 같이 살아날 수 있음.",
            ],
            "bear_case": [
                "이미 품질 프리미엄을 받는 종목이라 가치평가 재평가 여지가 제한될 수 있음.",
                "산업재 회복이 지연되면 AI 관련 노출만으로 전체 성장률을 끌어올리기 어려움.",
            ],
            "gaps": [],
            "next_action": "동종 기업 대비 예상 PER와 잉여현금흐름 수익률을 비교해 추격 여부보다 조정 대기 가격을 잡기.",
        },
        {
            "ticker": "ADI",
            "company": "Analog Devices",
            "sector": "Analog Semiconductors",
            "lens_ids": ["ai_power_bottleneck", "power_analog"],
            "thesis": "전력밀도와 혼합신호 품질에 베팅하는 후보. AI 인프라가 '더 많은 연산'에서 '더 조밀한 전력 전달'로 이동할 때 유리.",
            "metrics": {
                "valuation": 42,
                "quality": 82,
                "growth": 62,
                "revision": 64,
                "momentum": 70,
            },
            "evidence": ["Empower 인수로 전력밀도 포지션 강화"],
            "bull_case": [
                "고품질 아날로그 사업에 AI 전력밀도 이야기가 붙으면서 장기 투자 이야기가 선명함.",
                "전력 전달, 센싱, 혼합신호 포트폴리오가 데이터센터 외 산업재 회복과도 연결됨.",
            ],
            "bear_case": [
                "품질주 프리미엄이 높아 실적이 좋아도 기대치가 먼저 앞설 수 있음.",
                "인수 효과가 매출·마진으로 확인되기 전에는 이야기만 앞설 위험이 있음.",
            ],
            "gaps": [],
            "next_action": "Empower 인수 이후 데이터센터 전력밀도 관련 수주·제품 언급이 반복되는지 추적.",
        },
        {
            "ticker": "NVDA",
            "company": "NVIDIA",
            "sector": "Accelerated Compute",
            "lens_ids": ["ai_agent_compute", "semiconductors", "risk_on_liquidity"],
            "thesis": "AI 에이전트 확산이 추론 사용량을 구조적으로 키운다는 핵심 기준점. 다만 투자 가설이 맞는 것과 주가가 싼 것은 분리해야 함.",
            "metrics": {
                "valuation": 30,
                "quality": 92,
                "growth": 95,
                "revision": 88,
                "momentum": 90,
            },
            "evidence": ["데이터센터 매출이 AI 인프라 수요의 기준 신호 역할"],
            "bull_case": [
                "에이전트는 계획·검색·검증·재시도를 반복하므로 일반 챗봇보다 추론 사용량이 커질 수 있음.",
                "AI 인프라 투자가 이어지는 한 데이터센터 매출이 전체 공급망의 기준 신호 역할을 함.",
            ],
            "bear_case": [
                "시장 기대치가 이미 2027년 수요와 옵션 가치를 크게 반영했을 수 있음.",
                "빅테크 설비투자 피로가 나오면 실수요가 있어도 가치평가부터 흔들릴 수 있음.",
            ],
            "gaps": ["주가가 이미 큰 옵션 가치를 반영했을 가능성"],
            "next_action": "추격 후보가 아니라 설비투자 가이던스와 추론 매출화를 확인하는 기준 종목으로 둠.",
        },
    ],
}


def load_sample_dashboard_input() -> DashboardInput:
    return parse_dashboard_input(SAMPLE_DASHBOARD)
