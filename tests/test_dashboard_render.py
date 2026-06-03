from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard
from scripts.render_lens_dashboard import write_dashboard_reports


def test_render_dashboard_html_contains_core_sections_and_no_raw_json():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "<!doctype html>" in html
    assert "개인 투자 상황판" in html
    assert "시장 국면" in html
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
    assert "## 시장 국면" in text
    assert "## 시장 온도판" in text
    assert "## 상위 후보" in text
    assert "핵심 판단" in text
    assert "다음 확인" in text
    assert "PER" in text
    assert "동종군" in text
    assert "ON" in text


def test_render_dashboard_html_contains_macro_state_cockpit():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "매크로 현재 상태" in html
    assert "현재 상태" in html
    assert "오늘의 주요 이슈" in html
    assert "시장 폭" in html
    assert "시장 심리" in html
    assert "금리" in html
    assert "환율" in html
    assert "원자재" in html
    assert "유가" in html
    assert "종목 후보 영향" in html
    assert "macro_state" not in html
    assert "Issue Card" not in html


def test_render_dashboard_markdown_contains_macro_state_brief():
    dashboard = build_dashboard(load_sample_dashboard_input())

    text = render_dashboard_markdown(dashboard)

    assert "## 매크로 현재 상태" in text
    assert "## 오늘의 주요 이슈" in text
    assert "## 종목 후보 영향" in text


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
