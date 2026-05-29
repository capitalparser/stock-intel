"""Render the v1 lens investment dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from dashboard.render import render_dashboard_html, render_dashboard_markdown
from dashboard.sample_data import load_sample_dashboard_input
from dashboard.screeners import build_dashboard


DEFAULT_OUTPUT_DIR = Path("state/dashboard/reports")


def write_dashboard_reports(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    dashboard = build_dashboard(load_sample_dashboard_input())
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    html_path = target / f"{dashboard.as_of}-lens-dashboard.html"
    md_path = target / f"{dashboard.as_of}-lens-dashboard.md"
    html_path.write_text(render_dashboard_html(dashboard), encoding="utf-8")
    md_path.write_text(render_dashboard_markdown(dashboard), encoding="utf-8")
    return html_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the lens investment dashboard.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for HTML and Markdown reports.",
    )
    args = parser.parse_args()
    html_path, md_path = write_dashboard_reports(args.output_dir)
    print(f"HTML: {html_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
