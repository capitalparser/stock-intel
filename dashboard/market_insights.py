"""Build dashboard input from the local Market Insights vault."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from dashboard.kr_universe import kr_screen_stocks
from dashboard.models import DashboardInput, parse_dashboard_input
from dashboard.policy_lens import policy_lenses, low_pbr_seed_stocks
from dashboard.sample_data import SAMPLE_DASHBOARD


DEFAULT_MARKET_INSIGHTS_DIR = Path(__file__).resolve().parents[3] / "02_Areas" / "Market_Insights"
TICKER_CACHE_PATH = Path(__file__).resolve().parents[1] / "cache" / "tickers.json"

_FALLBACK_COMPANY_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "034020": "두산에너빌리티",
    "042700": "한미반도체",
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


def build_market_insights_payload(
    insights_dir: str | Path = DEFAULT_MARKET_INSIGHTS_DIR,
    *,
    include_kr_screen: bool = True,
    include_policy_lens: bool = True,
) -> dict:
    """Curated SAMPLE payload merged with tickers discovered in the vault.

    Returns the raw payload dict (pre-parse) so callers like ``live.py`` can
    overlay a real-data snapshot before parsing.
    """
    payload = deepcopy(SAMPLE_DASHBOARD)
    insights = _collect_related_tickers(Path(insights_dir))
    merged = _merge_stocks(payload["stocks"], insights)
    payload["stocks"] = _merge_kr_screen(merged, kr_screen_stocks()) if include_kr_screen else merged
    if include_policy_lens:
        payload["lenses"] = _merge_lenses(payload["lenses"], _policy_lens_payloads())
        payload["stocks"] = _merge_kr_screen(
            payload["stocks"],
            low_pbr_seed_stocks(),
        )
    return payload


def load_market_insights_dashboard_input(
    insights_dir: str | Path = DEFAULT_MARKET_INSIGHTS_DIR,
) -> DashboardInput:
    return parse_dashboard_input(build_market_insights_payload(insights_dir))


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


def _merge_kr_screen(existing: list[dict], kr_stocks: list[dict]) -> list[dict]:
    stocks_by_ticker = {str(item["ticker"]): deepcopy(item) for item in existing}
    for kr_stock in kr_stocks:
        ticker = str(kr_stock["ticker"])
        if ticker in stocks_by_ticker:
            current = stocks_by_ticker[ticker]
            current["source_refs"] = sorted(
                set(current.get("source_refs", []) + kr_stock.get("source_refs", []))
            )
            current["lens_ids"] = sorted(
                set(current.get("lens_ids", []) + kr_stock.get("lens_ids", []))
            )
            continue
        stocks_by_ticker[ticker] = deepcopy(kr_stock)
    return sorted(stocks_by_ticker.values(), key=lambda item: str(item["ticker"]))


def _merge_lenses(existing: list[dict], additions: list[dict]) -> list[dict]:
    by_id = {str(item["id"]): deepcopy(item) for item in existing}
    for lens in additions:
        lens_id = str(lens["id"])
        if lens_id not in by_id:
            by_id[lens_id] = deepcopy(lens)
    return list(by_id.values())


def _policy_lens_payloads() -> list[dict]:
    payloads: list[dict] = []
    for lens in policy_lenses():
        item = asdict(lens)
        item["kind"] = lens.kind.value
        item.pop("description", None)
        payloads.append(item)
    return payloads


def _default_stock(ticker: str, sources: list[str]) -> dict:
    company = _company_name(ticker)
    sector = _sector_from_sources(sources)
    lens_ids = _lens_ids_for_sources(sources)
    return {
        "ticker": ticker,
        "company": company,
        "sector": sector,
        "lens_ids": lens_ids,
        "thesis": _default_thesis(company, sources, lens_ids),
        "metrics": {
            "valuation": 50,
            "quality": 50,
            "growth": 50,
            "revision": 50,
            "momentum": 50,
        },
        "evidence": [f"Market Insights 연결: {source}" for source in sources[:3]],
        "bull_case": _default_bull_case(sources, lens_ids),
        "bear_case": _default_bear_case(lens_ids),
        "gaps": _default_gaps(lens_ids),
        "next_action": _default_next_action(lens_ids),
        "source_refs": sources,
        "peer_group": sector,
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
    normalized = _normalize_kr_ticker(ticker)
    if normalized:
        return _korean_ticker_names().get(
            normalized,
            _FALLBACK_COMPANY_NAMES.get(normalized, normalized),
        )
    return _FALLBACK_COMPANY_NAMES.get(ticker, ticker)


def _default_thesis(company: str, sources: list[str], lens_ids: list[str]) -> str:
    source_text = ", ".join(sources[:2])
    if "ai_power_bottleneck" in lens_ids:
        return (
            f"{company}: {source_text} 관점에서 전력 인프라 병목과 데이터센터 전력 투자 흐름을 "
            "확인하기 위한 관찰 카드입니다."
        )
    if "semiconductors" in lens_ids:
        return (
            f"{company}: {source_text} 관점에서 HBM·메모리·반도체 장비 사이클의 확산 여부를 "
            "점검하기 위한 관찰 카드입니다."
        )
    if "stablecoin_rails" in lens_ids:
        return (
            f"{company}: {source_text} 관점에서 결제 레일, 네트워크 효과, 규제 수혜가 실제 매출로 "
            "연결되는지 보기 위한 관찰 카드입니다."
        )
    if "low_per_revision" in lens_ids:
        return (
            f"{company}: {source_text} 관점에서 이익 상향과 낮은 밸류에이션이 동시에 붙는지 "
            "확인하기 위한 관찰 카드입니다."
        )
    return (
        f"{company}: {source_text}에서 반복 언급된 후보로, 현재 매크로 상태와 섹터 테마가 "
        "주가 모멘텀으로 이어지는지 추적합니다."
    )


def _default_bull_case(sources: list[str], lens_ids: list[str]) -> list[str]:
    cases = [f"Market Insights의 {', '.join(sources[:2])} 테마와 직접 연결됨."]
    if "ai_power_bottleneck" in lens_ids:
        cases.append("AI 데이터센터 전력 수요가 변압기·전력기기·발전 인프라 투자로 확산될 때 수혜 가능.")
    if "semiconductors" in lens_ids:
        cases.append("HBM과 메모리 업사이클이 장비·소재·후공정 체인까지 번질 경우 재평가 여지.")
    if "stablecoin_rails" in lens_ids:
        cases.append("스테이블코인 결제·정산 레일 채택이 늘면 거래량과 네트워크 가치가 함께 부각될 수 있음.")
    if "low_per_revision" in lens_ids:
        cases.append("이익 추정치 상향이 확인되면 저평가 해소 구간에서 상대수익률이 개선될 수 있음.")
    return cases[:3]


def _default_bear_case(lens_ids: list[str]) -> list[str]:
    cases = ["가격·실적·밸류에이션 자동 연결이 제한되어 테마 강도와 투자 판단을 분리해서 봐야 함."]
    if "ai_power_bottleneck" in lens_ids:
        cases.append("전력 인프라 투자 기대가 수주·마진보다 앞서면 단기 과열로 되돌림 가능.")
    if "semiconductors" in lens_ids:
        cases.append("메모리·장비 사이클은 피크 기대가 먼저 반영되면 실적 개선 중에도 주가가 흔들릴 수 있음.")
    if "stablecoin_rails" in lens_ids:
        cases.append("규제 방향, 수수료율, 경쟁 구도 변화가 테마의 지속성을 약화시킬 수 있음.")
    return cases[:3]


def _default_gaps(lens_ids: list[str]) -> list[str]:
    gaps = ["최근 가격·거래대금·상대강도 자동 보강 필요", "최근 분기 실적과 컨센서스 변화 확인 필요"]
    if "ai_power_bottleneck" in lens_ids:
        gaps.append("수주잔고, 전력 인프라 CAPEX, 납기 병목 근거 확인 필요")
    if "semiconductors" in lens_ids:
        gaps.append("HBM/메모리 ASP, 장비 발주, 재고 사이클 확인 필요")
    if "stablecoin_rails" in lens_ids:
        gaps.append("거래량, 규제 이벤트, 파트너십 공시 확인 필요")
    return gaps[:4]


def _default_next_action(lens_ids: list[str]) -> str:
    if "ai_power_bottleneck" in lens_ids:
        return "최근 가격 위치와 수주·CAPEX 뉴스를 확인한 뒤 전력 병목 수혜가 실적으로 이어지는지 점검."
    if "semiconductors" in lens_ids:
        return "최근 가격 위치, 메모리 가격, HBM/장비 발주 신호를 함께 확인해 추격보다 눌림 후보인지 판단."
    if "stablecoin_rails" in lens_ids:
        return "최근 가격 위치와 규제·거래량 이벤트를 확인해 테마 기대가 실제 수익화로 연결되는지 점검."
    return "최근 가격 위치, 실적 업데이트, 연결 테마의 강도를 확인한 뒤 관찰/제외를 결정."


def _normalize_kr_ticker(ticker: str) -> str | None:
    raw = ticker.split(":", 1)[1] if ":" in ticker else ticker
    return raw if re.fullmatch(r"\d{6}", raw) else None


@lru_cache(maxsize=1)
def _korean_ticker_names() -> dict[str, str]:
    if not TICKER_CACHE_PATH.exists():
        return {}
    try:
        rows = json.loads(TICKER_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(row.get("code")): str(row.get("name"))
        for row in rows
        if row.get("code") and row.get("name")
    }
