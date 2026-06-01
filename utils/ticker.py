"""
utils/ticker.py — 종목명 → 종목코드 매핑 + rapidfuzz 퍼지 매칭

캐시 전략:
  - 파일: {프로젝트루트}/cache/tickers.json
  - TTL: 7일 (파일 mtime 기준)
  - 대상: KOSPI + KOSDAQ 전 종목 (ETF/ETN/인버스/레버리지 등 제외)
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from rapidfuzz import fuzz, process

# ─── 경로 상수 ───────────────────────────────────────────────────────────────
_CACHE_PATH: Path = Path(__file__).parent.parent / "cache" / "tickers.json"
_TTL_SECONDS: int = 7 * 24 * 3600  # 7일

# ETF·파생상품 필터 키워드 (종목명 포함 시 제외)
_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "ETF",
    "ETN",
    "인버스",
    "레버리지",
    "선물",
    "합성",
)


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def _is_derivative(name: str) -> bool:
    """파생/ETF 성격의 종목명이면 True."""
    return any(k in name for k in _EXCLUDE_KEYWORDS)


def _cache_is_fresh() -> bool:
    """캐시 파일이 존재하고 TTL 이내이며 비어있지 않으면 True."""
    if not _CACHE_PATH.exists():
        return False
    age = time.time() - os.path.getmtime(_CACHE_PATH)
    if age > _TTL_SECONDS:
        return False
    # 빈 캐시([] 또는 0바이트)는 무효
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        return isinstance(data, list) and len(data) > 0
    except (json.JSONDecodeError, OSError):
        return False


# ─── 공개 API ─────────────────────────────────────────────────────────────────

def refresh_ticker_cache() -> list[dict]:
    """pykrx로 KOSPI+KOSDAQ 전 종목 목록을 조회해 cache/tickers.json에 저장.

    KRX 공식 API (get_market_ticker_list) 대신 상장종목검색 직접 호출을 사용한다.
    이유: get_market_ticker_list는 날짜 기반 시세 API를 사용해 영업일 외 조회 시
    빈 결과를 반환하지만, 상장종목검색은 날짜 불필요하며 안정적으로 전 종목을 반환함.

    Returns:
        저장된 종목 리스트 (dict per ticker).
    """
    # pykrx는 optional 의존 — 호출 시점에만 import
    from pykrx.website.krx.market.ticker import 상장종목검색

    df = 상장종목검색().fetch(mktsel="ALL", searchText="")

    # KOSPI(유가증권) + KOSDAQ만 포함; KONEX 제외
    target_markets = {"KOSPI", "KOSDAQ"}

    records: list[dict] = []
    for _, row in df.iterrows():
        market_eng = str(row.get("marketEngName", "")).strip()
        # "KOSDAQ GLOBAL" 등 변형도 포함
        normalized_market: str | None = None
        if "KOSPI" in market_eng:
            normalized_market = "KOSPI"
        elif "KOSDAQ" in market_eng:
            normalized_market = "KOSDAQ"

        if normalized_market not in target_markets:
            continue

        code = str(row["short_code"]).strip()
        name = str(row["codeName"]).strip()

        if not code or not name or _is_derivative(name):
            continue

        records.append({"code": code, "name": name, "market": normalized_market})

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return records


def load_ticker_cache() -> list[dict]:
    """캐시 파일을 로드한다. 없거나 만료됐으면 refresh_ticker_cache()를 자동 호출.

    Returns:
        종목 리스트 (dict per ticker).
    """
    if not _cache_is_fresh():
        return refresh_ticker_cache()

    raw = _CACHE_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


def search_ticker(name: str) -> list[dict]:
    """종목명 또는 종목코드 퍼지 검색.

    검색 우선순위:
      1. 6자리 숫자 → 코드 직접 매칭 (005930 등)
      2. 전체 입력 WRatio >= 90 고신뢰 매칭
      3. 입력을 토큰으로 분리해 각 토큰별 WRatio >= 90 결과 취합 (자연어 혼재 대응)
      4. 전체 입력 WRatio >= 75 저신뢰 매칭 (fallback)

    Args:
        name: 검색할 종목명·코드 또는 자연어 문장.

    Returns:
        [{"code": "005930", "name": "삼성전자", "market": "KOSPI", "score": 100.0}, ...]
    """
    query = name.strip()
    cache = load_ticker_cache()
    candidates: dict[str, dict] = {item["name"]: item for item in cache}
    code_map: dict[str, dict] = {item["code"]: item for item in cache}

    def _to_output(matched_name: str, score: float) -> dict:
        item = candidates[matched_name]
        return {
            "code": item["code"],
            "name": item["name"],
            "market": item["market"],
            "score": round(score, 1),
        }

    # 1. 6자리 숫자 → 코드 직접 매칭
    if query.isdigit() and len(query) == 6 and query in code_map:
        item = code_map[query]
        return [{"code": item["code"], "name": item["name"], "market": item["market"], "score": 100.0}]

    def _fuzzy_extract(q: str, cutoff: float) -> list[dict]:
        hits = process.extract(q, candidates.keys(), scorer=fuzz.WRatio, limit=5, score_cutoff=cutoff)
        return [_to_output(n, s) for n, s, _ in hits]

    words = query.split()

    if len(words) == 1:
        # 단일 토큰: 직접 퍼지 매칭
        # 2a. 고신뢰
        results = _fuzzy_extract(query, 90)
        if results:
            return sorted(results, key=lambda x: x["score"], reverse=True)
        # 2b. 저신뢰 fallback
        results = _fuzzy_extract(query, 75)
        return sorted(results, key=lambda x: x["score"], reverse=True)

    # 다단어: 전체 문장 퍼지는 부분 문자열 오매칭 위험 — 토큰별로 검색
    # 3. 각 토큰 WRatio >= 90 결과 취합
    seen: dict[str, dict] = {}
    for token in words:
        if len(token) < 2:
            continue
        for hit in _fuzzy_extract(token, 90):
            code = hit["code"]
            if code not in seen or hit["score"] > seen[code]["score"]:
                seen[code] = hit
    if seen:
        return sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:5]

    # 4. 전체 입력 저신뢰(>= 75) fallback
    results = _fuzzy_extract(query, 75)
    return sorted(results, key=lambda x: x["score"], reverse=True)
