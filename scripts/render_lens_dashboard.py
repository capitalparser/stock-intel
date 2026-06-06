"""Render the lens investment dashboard.

DEPRECATED (legacy): 구 다크 테마 HTML/MD 렌더러 CLI. design-kit Lane B React cockpit
(``cd web && npm run dev``)과 Snapshot Export(``npm run export:snapshot``)로 대체됨.
회귀 테스트/하위호환용으로만 유지한다.

Prefers the cached real-data snapshot (``dashboard.live``); transparently
falls back to the curated sample input when no snapshot exists. Use
``--sample`` to force the curated input regardless of cache.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dashboard.live import load_live_dashboard_input
from dashboard.market_insights import load_market_insights_dashboard_input
from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.screeners import build_dashboard

DEFAULT_OUTPUT_DIR = Path("state/dashboard/reports")


def write_dashboard_reports(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    use_snapshot: bool = True,
) -> tuple[Path, Path, bool]:
    if use_snapshot:
        source_input, used_snapshot = load_live_dashboard_input()
    else:
        source_input, used_snapshot = load_market_insights_dashboard_input(), False

    dashboard = build_dashboard(source_input)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    html_path = target / f"{dashboard.as_of}-lens-dashboard.html"
    md_path = target / f"{dashboard.as_of}-lens-dashboard.md"
    html_path.write_text(render_dashboard_html(dashboard), encoding="utf-8")
    md_path.write_text(render_dashboard_markdown(dashboard), encoding="utf-8")
    return html_path, md_path, used_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the lens investment dashboard.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for HTML and Markdown reports.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Force curated sample input (ignore cached snapshot).",
    )
    args = parser.parse_args()
    html_path, md_path, used_snapshot = write_dashboard_reports(
        args.output_dir, use_snapshot=not args.sample
    )
    print(f"Data source: {'real-data snapshot' if used_snapshot else 'curated sample (no snapshot)'}")
    print(f"HTML: {html_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
