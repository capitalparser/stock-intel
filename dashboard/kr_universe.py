"""Convert KR sector screen seeds into dashboard candidate stocks.

This module only translates seed data into the dashboard universe shape. Live
price, valuation, and metric data are overlaid later by the existing snapshot
path.
"""

from __future__ import annotations

from signals.kr_watch_candidates import KR_CANDIDATE_SEEDS, CandidateSeed

_NEUTRAL_METRICS = {
    "valuation": 50,
    "quality": 50,
    "growth": 50,
    "revision": 50,
    "momentum": 50,
}

# Sector lens mapping reuses 5 of the existing 7 dashboard lenses. The
# power_analog and stablecoin_rails lenses are excluded because the KR seed
# sectors do not directly map to them.
KR_SECTOR_LENS: dict[str, list[str]] = {
    # HBM, memory, equipment, and materials belong to the semiconductor cycle.
    "반도체/HBM/소부장": ["semiconductors"],
    # Grid, transformer, ESS, and nuclear exposure track the AI power bottleneck.
    "전력기기/전선/ESS/원전": ["ai_power_bottleneck"],
    # Shipbuilding and defense are cyclical exporters with risk-on sensitivity.
    "조선/방산": ["risk_on_liquidity"],
    # Financial holding companies and brokers map to valuation/revision rerating.
    "금융/증권/지주사": ["low_per_revision"],
    # KR platform and SaaS names fit the AI agent compute thesis lens.
    "AI 소프트웨어/플랫폼": ["ai_agent_compute"],
}


def normalize_kr_ticker(ticker: str) -> str:
    """Return a plain 6-digit KR ticker from ``KRX:000660`` or ``000660``."""
    parts = ticker.split(":", 1)
    raw = parts[1] if len(parts) == 2 else parts[0]
    return raw.strip()


def seed_to_stock(seed: CandidateSeed) -> dict:
    """Convert one KR candidate seed into a dashboard stock payload."""
    ticker = normalize_kr_ticker(seed.symbol)
    return {
        "ticker": ticker,
        "company": seed.name,
        "sector": seed.sector,
        "lens_ids": list(KR_SECTOR_LENS.get(seed.sector, ["risk_on_liquidity"])),
        "thesis": f"{seed.name}: {seed.notes} (국장 스크린 섹터 {seed.sector}).",
        "metrics": dict(_NEUTRAL_METRICS),
        "evidence": [
            f"국장 스크린: thesis_fit {seed.thesis_fit}, 수주 가시성 {seed.contract_visibility}",
            seed.notes,
        ],
        "bull_case": [f"{seed.sector} 테마 시드 - {seed.notes}"],
        "bear_case": [
            "국장 스크린 시드 - 가격, 실적, 감사인 독립성 자동 검증 전이므로 테마 강도와 투자 판단 분리."
        ],
        "gaps": [
            "국장 스크린 시드 - 실데이터(가격, 수급, 공매도) 스냅샷 overlay 필요",
            "감사인 독립성 차단 여부는 Plan 5(봇 시그니처)에서 주입 예정",
        ],
        "next_action": "국장 후보: 최근 가격, 수급, 감사인 독립성을 확인한 뒤 관찰/제외 판단.",
        "source_refs": ["국장 스크린 (kr_watch_candidates)"],
        "peer_group": seed.sector,
    }


def kr_screen_stocks() -> list[dict]:
    """Return all KR dynamic screen seeds as dashboard stock payloads."""
    return [seed_to_stock(seed) for seed in KR_CANDIDATE_SEEDS]
