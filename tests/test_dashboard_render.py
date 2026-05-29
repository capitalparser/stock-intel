from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard
from scripts.render_lens_dashboard import write_dashboard_reports


def test_render_dashboard_html_contains_core_sections_and_no_raw_json():
    dashboard = build_dashboard(load_sample_dashboard_input())

    html = render_dashboard_html(dashboard)

    assert "<!doctype html>" in html
    assert "Lens Investment Dashboard" in html
    assert "시장 국면" in html
    assert "렌즈 맵" in html
    assert "렌즈 중첩 후보" in html
    assert "ON Semiconductor" in html
    assert "raw JSON" not in html
    assert "data-asset-purpose" not in html


def test_render_dashboard_markdown_is_compact_briefing():
    dashboard = build_dashboard(load_sample_dashboard_input())

    text = render_dashboard_markdown(dashboard)

    assert text.startswith("# Lens Investment Dashboard")
    assert "## 시장 국면" in text
    assert "## 상위 후보" in text
    assert "ON" in text


def test_write_dashboard_reports_creates_html_and_markdown(tmp_path):
    html_path, md_path = write_dashboard_reports(output_dir=tmp_path)

    assert html_path == tmp_path / "2026-05-29-lens-dashboard.html"
    assert md_path == tmp_path / "2026-05-29-lens-dashboard.md"
    assert "Lens Investment Dashboard" in html_path.read_text(encoding="utf-8")
    assert "## 상위 후보" in md_path.read_text(encoding="utf-8")
