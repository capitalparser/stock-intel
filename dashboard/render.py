"""Render lens dashboard outputs."""

from __future__ import annotations

from html import escape

from dashboard.models import Candidate, Dashboard


def render_dashboard_markdown(dashboard: Dashboard) -> str:
    lines = [
        "# Lens Investment Dashboard",
        "",
        f"기준일: {dashboard.as_of}",
        "",
        "## 시장 국면",
        f"- verdict: {dashboard.regime.verdict}",
        f"- risk appetite: {dashboard.regime.risk_appetite}",
        f"- rates: {dashboard.regime.rates}",
        f"- dollar: {dashboard.regime.dollar}",
        f"- volatility: {dashboard.regime.volatility}",
        "",
        "## 상위 후보",
    ]
    for candidate in dashboard.candidates[:10]:
        lens_names = ", ".join(lens.name for lens in candidate.linked_lenses)
        lines.append(
            f"- {candidate.ticker} {candidate.company}: "
            f"{candidate.status.value}, score {candidate.score:.1f}, lenses {lens_names}"
        )
    return "\n".join(lines) + "\n"


def render_dashboard_html(dashboard: Dashboard) -> str:
    candidate_rows = "\n".join(_candidate_row(candidate) for candidate in dashboard.candidates)
    lens_cards = "\n".join(
        f"<article><h3>{escape(lens.name)}</h3>"
        f"<p>{escape(lens.kind.value)} · {escape(lens.conviction)} · {escape(lens.direction)}</p>"
        f"<p>{escape(', '.join(lens.risks) or '-')}</p></article>"
        for lens in dashboard.lenses
    )
    notes = "\n".join(f"<li>{escape(note)}</li>" for note in dashboard.regime.notes)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lens Investment Dashboard</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --ink: #111827;
      --muted: #5b6472;
      --line: #d9dee7;
      --panel: #ffffff;
      --accent: #0f766e;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 24px; }}
    h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; letter-spacing: 0; }}
    h3 {{ font-size: 15px; margin: 0 0 4px; letter-spacing: 0; }}
    .muted {{ color: var(--muted); }}
    .kpis {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .kpi, article {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .kpi strong {{ display: block; font-size: 18px; }}
    .lens-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); }}
    th, td {{ padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 13px; }}
    .status-Setup {{ color: var(--accent); font-weight: 700; }}
    .status-Research {{ color: var(--warn); font-weight: 700; }}
    .status-Blocked, .status-Avoid {{ color: var(--bad); font-weight: 700; }}
    @media (max-width: 760px) {{
      main {{ padding: 18px 12px 36px; }}
      .kpis {{ grid-template-columns: 1fr 1fr; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="muted">기준일 {escape(dashboard.as_of)}</p>
    <h1>Lens Investment Dashboard</h1>
    <p>Thesis, sector, macro, factor lens가 같은 후보를 가리키는지 점검합니다.</p>
  </header>
  <section>
    <h2>시장 국면</h2>
    <div class="kpis">
      <div class="kpi"><span>Verdict</span><strong>{escape(dashboard.regime.verdict)}</strong></div>
      <div class="kpi"><span>Risk</span><strong>{escape(dashboard.regime.risk_appetite)}</strong></div>
      <div class="kpi"><span>Rates</span><strong>{escape(dashboard.regime.rates)}</strong></div>
      <div class="kpi"><span>Dollar</span><strong>{escape(dashboard.regime.dollar)}</strong></div>
      <div class="kpi"><span>Volatility</span><strong>{escape(dashboard.regime.volatility)}</strong></div>
    </div>
    <ul>{notes}</ul>
  </section>
  <section>
    <h2>렌즈 맵</h2>
    <div class="lens-grid">{lens_cards}</div>
  </section>
  <section>
    <h2>렌즈 중첩 후보</h2>
    <table>
      <thead><tr><th>종목</th><th>상태</th><th>점수</th><th>렌즈</th><th>강한 렌즈</th><th>Gap</th></tr></thead>
      <tbody>{candidate_rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def _candidate_row(candidate: Candidate) -> str:
    lens_names = ", ".join(lens.name for lens in candidate.linked_lenses)
    gaps = "; ".join(candidate.gaps) or "-"
    return (
        "<tr>"
        f"<td><strong>{escape(candidate.ticker)}</strong><br>{escape(candidate.company)}"
        f"<br><span class=\"muted\">{escape(candidate.sector)}</span></td>"
        f"<td class=\"status-{escape(candidate.status.value)}\">{escape(candidate.status.value)}</td>"
        f"<td>{candidate.score:.1f}</td>"
        f"<td>{escape(lens_names)}</td>"
        f"<td>{escape(candidate.strongest_lens)}</td>"
        f"<td>{escape(gaps)}</td>"
        "</tr>"
    )
