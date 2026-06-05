from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from dashboard.providers.catalyst import _days_until, _supply_contract_catalysts, fetch_catalysts


def test_days_until_future_and_past():
    assert _days_until("2026-06-17", "2026-06-05") == 12
    assert _days_until("2026-05-28", "2026-06-05") == -8


def test_supply_contract_catalysts_filters_and_shapes():
    dart_list = [
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "20260528", "flr_nm": "삼성전자"},
        {"report_nm": "분기보고서", "rcept_dt": "20260515", "flr_nm": "삼성전자"},
        {"report_nm": "[정정]단일판매ㆍ공급계약체결", "rcept_dt": "20260601", "flr_nm": "삼성전자"},
    ]
    out = _supply_contract_catalysts(dart_list, "2026-06-05")
    assert len(out) == 2
    first = out[0]
    assert first["type"] == "supply_contract"
    assert first["direction"] == "recent"
    assert first["date"] == "2026-06-01"
    assert "공급계약" in first["label"]
    assert first["days"] == 4


def test_supply_contract_skips_malformed_dates_row_by_row():
    dart_list = [
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "20261340", "flr_nm": "bad month"},
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "2026-0601", "flr_nm": "bad format"},
        {"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "20260601", "flr_nm": "valid"},
    ]

    out = _supply_contract_catalysts(dart_list, "2026-06-05")

    assert len(out) == 1
    assert out[0]["detail"] == "valid"


def test_supply_contract_empty_when_none():
    assert _supply_contract_catalysts([], "2026-06-05") == []


def test_kr_fetch_caps_to_one_hundred_and_annotates_gap(monkeypatch, caplog):
    import dashboard.providers.catalyst as catalyst

    captured_params = {}

    def fake_get(url, *, params, timeout):
        captured_params.update(params)
        return SimpleNamespace(
            json=lambda: {
                "status": "000",
                "total_count": "101",
                "list": [
                    {
                        "report_nm": "단일판매ㆍ공급계약체결",
                        "rcept_dt": "20260601",
                        "flr_nm": "SK하이닉스",
                    }
                ],
            }
        )

    monkeypatch.setenv("DART_API_KEY", "key")
    monkeypatch.setattr(catalyst, "find_corp_code", lambda api_key, ticker: "00126380")
    monkeypatch.setattr(catalyst.requests, "get", fake_get)

    out = fetch_catalysts("000660", market="KR", today="2026-06-05")

    assert captured_params["page_count"] == 100
    assert captured_params["bgn_de"] == "20260307"
    assert captured_params["end_de"] == "20260605"
    assert out[0]["data_gap"] == "공급계약 100건 초과 — 최신만"
    assert "공급계약 100건 초과" in caplog.text


def test_us_fetch_reads_yfinance_dict_calendar(monkeypatch):
    import sys

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        @property
        def calendar(self):
            return {"Earnings Date": [date(2026, 6, 17)]}

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    out = fetch_catalysts("NVDA", market="US", today="2026-06-05")

    assert out == [
        {
            "type": "earnings",
            "direction": "upcoming",
            "date": "2026-06-17",
            "days": 12,
            "label": "실적 D-12",
            "detail": "",
        }
    ]


def test_kr_fetch_no_gap_annotation_when_under_cap(monkeypatch):
    # total_count <= 100이면 data_gap을 달지 않는다 (cap 네거티브 — Opus review should-fix).
    import dashboard.providers.catalyst as catalyst

    def fake_get(url, *, params, timeout):
        return SimpleNamespace(json=lambda: {
            "status": "000", "total_count": "3",
            "list": [{"report_nm": "단일판매ㆍ공급계약체결", "rcept_dt": "20260601", "flr_nm": "SK하이닉스"}],
        })

    monkeypatch.setenv("DART_API_KEY", "key")
    monkeypatch.setattr(catalyst, "find_corp_code", lambda api_key, ticker: "00126380")
    monkeypatch.setattr(catalyst.requests, "get", fake_get)

    out = fetch_catalysts("000660", market="KR", today="2026-06-05")

    assert out and "data_gap" not in out[0]


def test_us_fetch_drops_past_earnings(monkeypatch):
    # 실적일이 과거(days<0)면 stale catalyst를 보이지 않는다 (Opus review should-fix).
    import sys

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        @property
        def calendar(self):
            return {"Earnings Date": [date(2026, 6, 1)]}

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    out = fetch_catalysts("NVDA", market="US", today="2026-06-05")

    assert out == []
