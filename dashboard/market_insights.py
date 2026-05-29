"""Build dashboard input from the local Market Insights vault."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from dashboard.models import DashboardInput, parse_dashboard_input
from dashboard.sample_data import SAMPLE_DASHBOARD


DEFAULT_MARKET_INSIGHTS_DIR = Path(__file__).resolve().parents[3] / "02_Areas" / "Market_Insights"


def load_market_insights_dashboard_input(
    insights_dir: str | Path = DEFAULT_MARKET_INSIGHTS_DIR,
) -> DashboardInput:
    payload = deepcopy(SAMPLE_DASHBOARD)
    insights = _collect_related_tickers(Path(insights_dir))
    payload["stocks"] = _merge_stocks(payload["stocks"], insights)
    return parse_dashboard_input(payload)


def _collect_related_tickers(root: Path) -> dict[str, list[str]]:
    if not root.exists():
        return {}

    ticker_sources: dict[str, list[str]] = {}
    for path in sorted(root.glob("**/*.md")):
        if "_templates" in path.parts or path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^related_tickers:\s*\[(.*?)\]\s*$", text, re.MULTILINE)
        if not match:
            continue
        label = _display_label(path, text)
        for ticker in _parse_tickers(match.group(1)):
            ticker_sources.setdefault(ticker, []).append(label)
    return ticker_sources


def _merge_stocks(curated: list[dict], insights: dict[str, list[str]]) -> list[dict]:
    stocks_by_ticker = {str(item["ticker"]): deepcopy(item) for item in curated}
    for ticker, sources in insights.items():
        if ticker in stocks_by_ticker:
            existing = stocks_by_ticker[ticker]
            existing["source_refs"] = sorted(set(existing.get("source_refs", []) + sources))
            existing["lens_ids"] = sorted(set(existing.get("lens_ids", []) + _lens_ids_for_sources(sources)))
            continue
        stocks_by_ticker[ticker] = _default_stock(ticker, sources)
    return sorted(stocks_by_ticker.values(), key=lambda item: str(item["ticker"]))


def _default_stock(ticker: str, sources: list[str]) -> dict:
    return {
        "ticker": ticker,
        "company": _company_name(ticker),
        "sector": _sector_from_sources(sources),
        "lens_ids": _lens_ids_for_sources(sources),
        "thesis": f"{', '.join(sources[:2])}에서 관리 중인 관찰 대상. 아직 상세 투자 메모는 보강 전입니다.",
        "metrics": {
            "valuation": 50,
            "quality": 50,
            "growth": 50,
            "revision": 50,
            "momentum": 50,
        },
        "evidence": [f"Market Insights 연결: {source}" for source in sources[:3]],
        "bull_case": ["관련 인사이트에서 반복 등장해 후속 점검 universe에 포함."],
        "bear_case": ["가격, 실적, 가치평가, 촉매가 아직 대시보드에 자동 보강되지 않음."],
        "gaps": ["가격·실적·가치평가 자동 보강 필요"],
        "next_action": "가격, 최근 실적, 다음 확인 포인트를 채운 뒤 관찰/제외를 결정.",
        "source_refs": sources,
        "peer_group": _sector_from_sources(sources),
    }


def _parse_tickers(raw: str) -> list[str]:
    return [item.strip().strip("\"'") for item in raw.split(",") if item.strip()]


def _display_label(path: Path, text: str) -> str:
    label_match = re.search(r"^label:\s*\"?([^\"\n]+)\"?\s*$", text, re.MULTILINE)
    if label_match:
        return label_match.group(1)
    return path.stem


def _lens_ids_for_sources(sources: list[str]) -> list[str]:
    joined = " ".join(sources).lower()
    lens_ids: list[str] = []
    if any(key in joined for key in ("semiconductor", "반도체", "memory", "메모리")):
        lens_ids.append("semiconductors")
    if any(key in joined for key in ("power", "utilities", "전력", "data center", "데이터센터")):
        lens_ids.append("ai_power_bottleneck")
    if any(key in joined for key in ("hyperscaler", "ai agent", "ai factory", "ai 서비스")):
        lens_ids.append("ai_agent_compute")
    if any(key in joined for key in ("stablecoin", "스테이블코인", "financial", "금융")):
        lens_ids.append("stablecoin_rails")
    if any(key in joined for key in ("valuation", "value", "rerating", "밸류", "가치")):
        lens_ids.append("low_per_revision")
    return lens_ids or ["risk_on_liquidity"]


def _sector_from_sources(sources: list[str]) -> str:
    first = sources[0] if sources else "관찰 대상"
    return first.replace(" (Semiconductors)", "")


def _company_name(ticker: str) -> str:
    names = {
        "005930": "Samsung Electronics",
        "000660": "SK hynix",
        "035420": "NAVER",
        "034020": "Doosan Enerbility",
        "042700": "Hanmi Semiconductor",
        "TSM": "TSMC",
        "AMD": "AMD",
        "MU": "Micron",
        "AVGO": "Broadcom",
        "COIN": "Coinbase",
        "CRCL": "Circle",
        "V": "Visa",
        "MA": "Mastercard",
        "MSFT": "Microsoft",
        "GOOGL": "Alphabet",
        "AMZN": "Amazon",
        "META": "Meta",
        "PLTR": "Palantir",
        "SNOW": "Snowflake",
        "GLW": "Corning",
        "FLNC": "Fluence",
        "HPE": "Hewlett Packard Enterprise",
        "SMCI": "Super Micro Computer",
    }
    return names.get(ticker, ticker)
