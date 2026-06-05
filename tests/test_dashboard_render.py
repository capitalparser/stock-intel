from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard
from dashboard.models import parse_dashboard_input
from dashboard.market_insights import load_market_insights_dashboard_input
from scripts.render_lens_dashboard import write_dashboard_reports


def _dual_regime_dashboard():
    dashboard_input = parse_dashboard_input(
        {
            "as_of": "2026-06-04",
            "price_time": "2026-06-04T00:00:00+09:00",
            "market_indicators": [],
            "dual_regime": {
                "as_of": "2026-06-04",
                "us": {
                    "market": "US",
                    "regime": "risk-on",
                    "why_it_matters": "미국 주요 축이 위험자산에 우호적",
                    "next_action": "가격 매력 후보부터 검토",
                    "axis_reads": [
                        {"dimension": "breadth", "label": "시장 폭", "state": "supportive",
                         "pctile": 0.72, "read": "시장 폭 우호", "symbols": ["S5FI"]}
                    ],
                    "data_gaps": [],
                },
                "kr": {
                    "market": "KR",
                    "regime": "fragile rally",
                    "why_it_matters": "한국 지수는 강하지만 수급 프록시 확인 필요",
                    "next_action": "국장 후보 압축",
                    "axis_reads": [
                        {"dimension": "flow", "label": "외국인 수급", "state": "warning",
                         "pctile": 0.18, "read": "EWY 프록시 — 실제 외국인 순매수 아님",
                         "symbols": ["FOREIGN_NET"], "source_kind": "proxy"}
                    ],
                    "data_gaps": [],
                },
                "transitions": {
                    "us": {"changed": False, "from": "risk-on", "to": "risk-on",
                           "streak": 3, "whipsaw": False, "axis_changes": []},
                    "kr": {"changed": True, "from": "conditional", "to": "fragile rally",
                           "streak": 1, "whipsaw": True, "axis_changes": []},
                },
            },
            "lenses": [],
            "stocks": [],
        }
    )
    return build_dashboard(dashboard_input)


def test_render_dashboard_html_contains_core_sections_and_no_raw_json():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "<!doctype html>" in html
    assert "개인 투자 상황판" in html
    assert "투자 관점 지도" in html
    assert "시장 온도판" in html
    assert "전체 종목 총괄표" in html
    assert "후보별 판단 메모" in html
    assert "ON Semiconductor" in html
    assert "핵심 판단" in html
    assert "다음 확인" in html
    assert "가격/PER" in html
    assert "동종군 비교" in html
    assert "동종군 대비" in html
    assert "raw JSON" not in html
    assert "Verdict" not in html
    assert "Gap" not in html
    assert "data-asset-purpose" not in html


def test_render_dashboard_markdown_is_compact_briefing():
    dashboard = build_dashboard(load_sample_dashboard_input())

    text = render_dashboard_markdown(dashboard)

    assert text.startswith("# 개인 투자 상황판")
    assert "## 시장 온도판" in text
    assert "## 상위 후보" in text
    assert "핵심 판단" in text
    assert "다음 확인" in text
    assert "PER" in text
    assert "동종군" in text
    assert "ON" in text


def test_markdown_renders_dual_regime():
    md = render_dashboard_markdown(_dual_regime_dashboard())
    assert "미국 국면" in md and "한국 국면" in md
    assert "영업일째" in md or "→" in md
    assert "프록시" in md


def test_html_renders_dual_regime():
    html = render_dashboard_html(
        _dual_regime_dashboard(), db_path="/tmp/missing-stock-intel-state.db"
    )
    assert "한국 국면" in html
    assert "잠정 전이" in html or "영업일째" in html
    assert "프록시" in html


def test_render_dashboard_uses_korean_company_name_as_primary_for_kr_stocks():
    dashboard_input = parse_dashboard_input(
        {
            "as_of": "2026-06-03",
            "price_time": "2026-06-03T00:00:00+09:00",
            "regime": {
                "verdict": "conditional",
                "risk_appetite": "risk-on",
                "rates": "stable",
                "dollar": "stable",
                "volatility": "low",
                "notes": [],
            },
            "market_indicators": [],
            "lenses": [
                {
                    "id": "semiconductors",
                    "kind": "sector",
                    "name": "반도체",
                    "conviction": "high",
                    "direction": "stable",
                    "weights": {
                        "valuation": 0.2,
                        "quality": 0.2,
                        "growth": 0.2,
                        "revision": 0.2,
                        "momentum": 0.2,
                    },
                    "risks": [],
                }
            ],
            "stocks": [
                {
                    "ticker": "005930",
                    "company": "삼성전자",
                    "sector": "반도체",
                    "lens_ids": ["semiconductors"],
                    "metrics": {
                        "valuation": 60,
                        "quality": 80,
                        "growth": 70,
                        "revision": 65,
                        "momentum": 55,
                    },
                    "evidence": ["HBM·메모리 사이클 점검 대상"],
                    "gaps": [],
                    "thesis": "메모리 업사이클 기준 종목.",
                    "bull_case": ["메모리 가격 상승과 HBM 증설 수혜."],
                    "bear_case": ["원화 약세와 CAPEX 부담."],
                    "next_action": "HBM 출하와 메모리 ASP를 확인.",
                    "price": 82000,
                    "day_change_pct": 1.2,
                    "pe": 18,
                    "peer_pe": 22,
                    "peer_group": "메모리",
                }
            ],
        }
    )
    dashboard = build_dashboard(dashboard_input)

    html = render_dashboard_html(dashboard, db_path="/tmp/missing-stock-intel-state.db")
    text = render_dashboard_markdown(dashboard)

    assert '"display_name": "삼성전자"' in html
    assert '"display_meta": "005930 · 반도체"' in html
    assert '<div class="cc-ticker">${c.display_name}</div><div class="cc-co">${c.display_meta}</div>' in html
    assert '<td><div class="td-t">${c.display_name}</div><div class="td-co">${c.display_meta}</div></td>' in html
    assert '<div class="dt">${c.display_name}</div>' in html
    assert '<div class="dco">${c.display_meta}</div>' in html
    assert "- 삼성전자 (005930):" in text


def test_render_dashboard_includes_unpriced_market_insight_stocks_as_cards(tmp_path):
    insights = tmp_path / "Market_Insights"
    (insights / "themes").mkdir(parents=True)
    (insights / "themes" / "power.md").write_text(
        "---\n"
        "label: \"AI 전력 병목\"\n"
        "related_tickers: [034020]\n"
        "---\n",
        encoding="utf-8",
    )
    dashboard = build_dashboard(load_market_insights_dashboard_input(insights))

    html = render_dashboard_html(dashboard, db_path="/tmp/missing-stock-intel-state.db")

    assert '"ticker": "034020"' in html
    assert '"display_name": "두산에너빌리티"' in html
    assert '"price": null' in html
    assert '"thesis": "두산에너빌리티: AI 전력 병목 관점' in html


def test_render_shows_independence_badges():
    dashboard_input = parse_dashboard_input(
        {
            "as_of": "2026-06-05",
            "price_time": "2026-06-05T00:00:00+09:00",
            "market_indicators": [],
            "lenses": [],
            "stocks": [
                {
                    "ticker": "000660",
                    "company": "SK하이닉스",
                    "sector": "반도체",
                    "lens_ids": [],
                    "metrics": {
                        "valuation": 50,
                        "quality": 50,
                        "growth": 50,
                        "revision": 50,
                        "momentum": 50,
                    },
                    "evidence": ["blocked"],
                    "gaps": [],
                    "blocked": True,
                    "independence_status": "BLOCKED_CONFIRMED",
                    "auditor": "삼정회계법인",
                },
                {
                    "ticker": "NVDA",
                    "company": "NVIDIA",
                    "sector": "Semis",
                    "lens_ids": [],
                    "metrics": {
                        "valuation": 50,
                        "quality": 50,
                        "growth": 50,
                        "revision": 50,
                        "momentum": 50,
                    },
                    "evidence": ["manual"],
                    "gaps": [],
                    "independence_status": "MANUAL_VERIFY",
                },
            ],
        }
    )
    dashboard = build_dashboard(dashboard_input)

    markdown = render_dashboard_markdown(dashboard)
    html = render_dashboard_html(dashboard, db_path="/tmp/missing-stock-intel-state.db")

    assert "🚫" in markdown and "독립성 차단" in markdown
    assert "🟡" in markdown and "독립성 확인 필요" in markdown
    assert "🚫" in html and "독립성 차단" in html
    assert "🟡" in html and "독립성 확인 필요" in html
    assert ".hbadge.bbad" in html
    assert '"cls": "bbad"' in html
    assert '"cls": "bneu"' in html


def test_render_shows_catalyst():
    dashboard_input = parse_dashboard_input(
        {
            "as_of": "2026-06-05",
            "price_time": "2026-06-05T00:00:00+09:00",
            "market_indicators": [],
            "lenses": [],
            "stocks": [
                {
                    "ticker": "NVDA",
                    "company": "NVIDIA",
                    "sector": "Semis",
                    "lens_ids": [],
                    "metrics": {
                        "valuation": 50,
                        "quality": 50,
                        "growth": 50,
                        "revision": 50,
                        "momentum": 50,
                    },
                    "evidence": ["seed"],
                    "gaps": [],
                    "catalysts": [
                        {
                            "type": "earnings",
                            "direction": "upcoming",
                            "date": "2026-06-17",
                            "days": 12,
                            "label": "실적 D-12",
                        },
                        {
                            "type": "supply_contract",
                            "direction": "recent",
                            "date": "2026-06-01",
                            "days": 4,
                            "label": "공급계약 (6/1)",
                        },
                    ],
                }
            ],
        }
    )
    dashboard = build_dashboard(dashboard_input)

    markdown = render_dashboard_markdown(dashboard)
    html = render_dashboard_html(dashboard, db_path="/tmp/missing-stock-intel-state.db")

    assert "다가오는: 실적 D-12" in markdown
    assert "최근: 공급계약 (6/1)" in markdown
    assert "다가오는: 실적 D-12" in html
    assert "최근: 공급계약 (6/1)" in html


def test_render_shows_valuation_expectations_after_dual_regime_and_candidate_badge():
    dashboard_input = parse_dashboard_input(
        {
            "as_of": "2026-06-06",
            "price_time": "2026-06-06T00:00:00+09:00",
            "market_indicators": [],
            "dual_regime": {
                "as_of": "2026-06-06",
                "us": {"market": "US", "regime": "risk-on", "why_it_matters": "US",
                       "next_action": "검토", "axis_reads": [], "data_gaps": []},
                "kr": {"market": "KR", "regime": "conditional", "why_it_matters": "KR",
                       "next_action": "압축", "axis_reads": [], "data_gaps": []},
                "transitions": {
                    "us": {"changed": False, "from": "risk-on", "to": "risk-on",
                           "streak": 2, "whipsaw": False, "axis_changes": []},
                    "kr": {"changed": False, "from": "conditional", "to": "conditional",
                           "streak": 2, "whipsaw": False, "axis_changes": []},
                },
            },
            "valuation_expectations": [
                {
                    "ticker": "NVDA",
                    "forward_pe": 90.0,
                    "rev_growth_pct": 20.0,
                    "eps_growth_pct": 30.0,
                    "fcf_margin_pct": 20.0,
                    "verdict": "과열",
                    "read": "v1: 성장·FCF only",
                    "data_gaps": ["가이던스 데이터 부족"],
                }
            ],
            "lenses": [],
            "stocks": [
                {
                    "ticker": "NVDA",
                    "company": "NVIDIA",
                    "sector": "Semis",
                    "lens_ids": [],
                    "metrics": {
                        "valuation": 50,
                        "quality": 50,
                        "growth": 50,
                        "revision": 50,
                        "momentum": 50,
                    },
                    "evidence": ["seed"],
                    "gaps": [],
                    "expectation_verdict": "과열",
                }
            ],
        }
    )
    dashboard = build_dashboard(dashboard_input)

    markdown = render_dashboard_markdown(dashboard)
    html = render_dashboard_html(dashboard, db_path="/tmp/missing-stock-intel-state.db")

    assert "## 밸류에이션 기대치 점검" in markdown
    assert "NVDA" in markdown and "과열" in markdown
    assert markdown.index("## 밸류에이션 기대치 점검") < markdown.index("## 시장 온도판")
    assert "밸류에이션 기대치 점검" in html
    assert html.index("밸류에이션 기대치 점검") > html.index("한미 듀얼 국면")
    assert html.index("밸류에이션 기대치 점검") < html.index('<div class="macro-strip">')
    assert '"expectation_badge": {"text": "과열", "cls": "bbad"}' in html


def test_write_dashboard_reports_creates_html_and_markdown(tmp_path):
    # Force curated sample for a deterministic as_of date (no snapshot dependency).
    html_path, md_path, used_snapshot = write_dashboard_reports(
        output_dir=tmp_path, use_snapshot=False
    )

    assert used_snapshot is False
    assert html_path == tmp_path / "2026-05-29-lens-dashboard.html"
    assert md_path == tmp_path / "2026-05-29-lens-dashboard.md"
    assert "개인 투자 상황판" in html_path.read_text(encoding="utf-8")
    assert "## 상위 후보" in md_path.read_text(encoding="utf-8")
