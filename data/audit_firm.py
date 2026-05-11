"""
data/audit_firm.py — kreports를 통한 감사법인 조회.

의존:
  - pip install kreports>=0.1.0
  - DB_URL 환경변수: kreports.db SQLite 경로
    예) DB_URL=sqlite:////path/to/kreports_dart_mcp/kreports.db

kreports.db는 kreports_dart_mcp 프로젝트의 collector가 채운 DB.
DB_URL 미설정 시 ~/Library/Application Support/kreports/kreports.db (macOS) 기본값.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def _try_collect_auditors(corp_code: str | None) -> None:
    if not corp_code or not os.getenv("DART_API_KEY"):
        return

    try:
        from kreports.collector.audit_collector import collect_auditors

        collect_auditors(corp_code)
    except Exception:
        # 감사인 정보는 보조 데이터이므로, 수집 실패 시 기존 "데이터 없음"
        # 경로로 graceful degrade한다.
        return


RECENT_YEARS = 3  # 표시할 최근 회계연도 수 (당해 + 직전 2개년)


def fetch_audit_firm(ticker: str) -> dict:
    """kreports로 감사법인 직전 3개년 정보 조회.

    Args:
        ticker: KRX 종목코드 (예: "005930")

    Returns:
        {
            "recent": [  # 최신 → 과거 순, 최대 3개
                {"year": 2025, "firm": "삼정회계법인", "changed_from_prev": False},
                {"year": 2024, "firm": "삼정회계법인", "changed_from_prev": False},
                {"year": 2023, "firm": "한영회계법인", "changed_from_prev": True},
            ],
            # backward-compat (구 호출자용)
            "current_year": 2025,
            "current_firm": "삼정회계법인",
            "prev_year": 2024,
            "prev_firm": "삼정회계법인",
            "changed": False,
        }
        데이터 없음: {"error": "감사법인 데이터를 찾을 수 없습니다."}
        kreports DB 미접근: {"error": "kreports DB에 접근할 수 없습니다. DB_URL을 확인하세요."}
    """
    try:
        from kreports import get_audit_history
    except ImportError:
        return {"error": "kreports 패키지가 설치되지 않았습니다. pip install kreports"}

    try:
        result = get_audit_history(ticker)
    except Exception as e:
        err_str = str(e)
        if "no such table" in err_str or "OperationalError" in err_str:
            return {"error": "kreports DB에 접근할 수 없습니다. DB_URL을 확인하세요."}
        return {"error": f"감사법인 데이터를 가져올 수 없습니다: {err_str}"}

    history = result.get("history", [])
    if not history:
        _try_collect_auditors(result.get("corp_code"))
        try:
            result = get_audit_history(ticker)
            history = result.get("history", [])
        except Exception:
            history = []

    if not history:
        return {"error": "감사법인 데이터를 찾을 수 없습니다."}

    # CFS(연결) 우선, 없으면 OFS(별도)
    cfs = [h for h in history if h.get("구분") == "CFS"]
    target = cfs if cfs else history

    # 최신 연도 내림차순 정렬, 상위 RECENT_YEARS개
    target_sorted = sorted(target, key=lambda h: h.get("회계연도", 0), reverse=True)
    top = target_sorted[:RECENT_YEARS]

    # 직전(다음 인덱스) 행과 비교해 firm 교체 여부 계산
    recent: list[dict] = []
    for i, row in enumerate(top):
        firm = row.get("감사인")
        next_row = top[i + 1] if i + 1 < len(top) else None
        changed = (
            next_row is not None
            and next_row.get("감사인") is not None
            and firm is not None
            and next_row.get("감사인") != firm
        )
        recent.append({
            "year": row.get("회계연도"),
            "firm": firm,
            "changed_from_prev": changed,
        })

    current = top[0]
    prev = top[1] if len(top) > 1 else None
    return {
        "recent": recent,
        # backward-compat
        "current_year": current.get("회계연도"),
        "current_firm": current.get("감사인"),
        "prev_year": prev.get("회계연도") if prev else None,
        "prev_firm": prev.get("감사인") if prev else None,
        "changed": current.get("교체여부") not in ("유지", None),
    }
