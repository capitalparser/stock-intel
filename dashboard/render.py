"""Render lens dashboard outputs."""

from __future__ import annotations

from html import escape

from dashboard.models import Candidate, Dashboard


STATUS_LABELS = {
    "Watch": "관찰",
    "Research": "근거 보강",
    "Setup": "검토 우선",
    "Avoid": "제외",
    "Blocked": "차단",
    "Dropped": "보류 해제",
}

KIND_LABELS = {
    "thesis": "투자 가설",
    "sector": "섹터",
    "macro": "거시 환경",
    "factor": "투자 성향",
}

CONVICTION_LABELS = {"high": "강함", "medium": "보통", "low": "약함"}
DIRECTION_LABELS = {"improving": "개선", "stable": "유지", "weakening": "약화"}


def render_dashboard_markdown(dashboard: Dashboard) -> str:
    lines = [
        "# 개인 투자 상황판",
        "",
        f"기준일: {dashboard.as_of}",
        "",
        "## 시장 국면",
        f"- 현재 판단: {_regime_value(dashboard.regime.verdict)}",
        f"- 위험자산 선호: {_regime_value(dashboard.regime.risk_appetite)}",
        f"- 금리: {_regime_value(dashboard.regime.rates)}",
        f"- 달러: {_regime_value(dashboard.regime.dollar)}",
        f"- 변동성: {_regime_value(dashboard.regime.volatility)}",
        "",
        "## 상위 후보",
    ]
    for candidate in dashboard.candidates[:10]:
        view_names = ", ".join(lens.name for lens in candidate.linked_lenses)
        lines.append(
            f"- {candidate.ticker} {candidate.company}: "
            f"{_status_label(candidate)}, 매력도 {candidate.score:.1f}, 연결 관점 {view_names}"
        )
        if candidate.thesis:
            lines.append(f"  - 핵심 판단: {candidate.thesis}")
        if candidate.next_action:
            lines.append(f"  - 다음 확인: {candidate.next_action}")
    return "\n".join(lines) + "\n"


def render_dashboard_html(dashboard: Dashboard) -> str:
    candidate_rows = "\n".join(_candidate_row(candidate) for candidate in dashboard.candidates)
    candidate_cards = "\n".join(_candidate_card(candidate) for candidate in dashboard.candidates)
    lens_cards = "\n".join(
        f"<article><h3>{escape(lens.name)}</h3>"
        f"<p>{escape(KIND_LABELS.get(lens.kind.value, lens.kind.value))} · "
        f"확신 {escape(CONVICTION_LABELS.get(lens.conviction, lens.conviction))} · "
        f"흐름 {escape(DIRECTION_LABELS.get(lens.direction, lens.direction))}</p>"
        f"<p>{escape(', '.join(lens.risks) or '-')}</p></article>"
        for lens in dashboard.lenses
    )
    notes = "\n".join(f"<li>{escape(note)}</li>" for note in dashboard.regime.notes)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>개인 투자 상황판</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --ink: #111827;
      --muted: #5b6472;
      --line: #d9dee7;
      --panel: #ffffff;
      --accent: #2563eb;
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
      letter-spacing: -0.02em;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 24px; }}
    h1 {{ font-size: 30px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; letter-spacing: 0; }}
    h3 {{ font-size: 15px; margin: 0 0 4px; letter-spacing: 0; }}
    .muted {{ color: var(--muted); }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0; }}
    .tab {{ border-bottom: 2px solid transparent; padding: 4px 0; color: var(--muted); font-weight: 700; }}
    .tab-active {{ border-color: var(--accent); color: var(--ink); }}
    .section-brief {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 16px 0 18px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .kpi, article {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .kpi strong {{ display: block; font-size: 18px; }}
    .view-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
    .candidate-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 12px; }}
    .candidate-card ul {{ margin: 6px 0 12px 18px; padding: 0; }}
    .candidate-card p {{ margin: 4px 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); }}
    th, td {{ padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 13px; }}
    .state-setup {{ color: var(--accent); font-weight: 700; }}
    .state-research {{ color: var(--warn); font-weight: 700; }}
    .state-blocked, .state-avoid {{ color: var(--bad); font-weight: 700; }}
    @media (max-width: 760px) {{
      main {{ padding: 18px 12px 36px; }}
      .section-brief, .kpis {{ grid-template-columns: 1fr; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="muted">기준일 {escape(dashboard.as_of)}</p>
    <h1>개인 투자 상황판</h1>
    <p>투자 가설, 섹터, 거시 환경, 투자 성향이 같은 후보를 가리키는지 점검합니다.</p>
    <nav class="tabs" aria-label="대시보드 보기">
      <span class="tab tab-active">요약</span>
      <span class="tab">진행현황</span>
      <span class="tab">주의 필요</span>
      <span class="tab">근거</span>
      <span class="tab">다음 행동</span>
    </nav>
  </header>
  <section>
    <h2>시장 국면</h2>
    <div class="section-brief">
      <article><h3>현재 상태</h3><p>AI 인프라 수요는 살아 있으나 주가에는 과열 부담이 함께 반영된 상태입니다.</p></article>
      <article><h3>왜 중요한가</h3><p>좋은 산업도 기대치가 앞서면 조정을 받을 수 있어, 후보를 가격과 근거로 다시 나눠야 합니다.</p></article>
      <article><h3>다음 행동</h3><p>AI 전력 병목과 저PER+이익상향 관점이 동시에 걸리는 후보부터 근거를 보강합니다.</p></article>
    </div>
    <div class="kpis">
      <div class="kpi"><span>현재 판단</span><strong>{escape(_regime_value(dashboard.regime.verdict))}</strong></div>
      <div class="kpi"><span>위험자산 선호</span><strong>{escape(_regime_value(dashboard.regime.risk_appetite))}</strong></div>
      <div class="kpi"><span>금리</span><strong>{escape(_regime_value(dashboard.regime.rates))}</strong></div>
      <div class="kpi"><span>달러</span><strong>{escape(_regime_value(dashboard.regime.dollar))}</strong></div>
      <div class="kpi"><span>변동성</span><strong>{escape(_regime_value(dashboard.regime.volatility))}</strong></div>
    </div>
    <ul>{notes}</ul>
  </section>
  <section>
    <h2>투자 관점 지도</h2>
    <div class="view-grid">{lens_cards}</div>
  </section>
  <section>
    <h2>중첩 후보 요약</h2>
    <table>
      <thead><tr><th>종목</th><th>현재 상태</th><th>매력도</th><th>연결 관점</th><th>가장 강한 관점</th><th>보강할 근거</th></tr></thead>
      <tbody>{candidate_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>후보별 판단 메모</h2>
    <div class="candidate-grid">{candidate_cards}</div>
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
        f"<td class=\"{escape(_state_class(candidate))}\">{escape(_status_label(candidate))}</td>"
        f"<td>{candidate.score:.1f}</td>"
        f"<td>{escape(lens_names)}</td>"
        f"<td>{escape(candidate.strongest_lens)}</td>"
        f"<td>{escape(gaps)}</td>"
        "</tr>"
    )


def _candidate_card(candidate: Candidate) -> str:
    return (
        '<article class="candidate-card">'
        f"<h3>{escape(candidate.ticker)} · {escape(candidate.company)}</h3>"
        f"<p><strong>핵심 판단</strong><br>{escape(candidate.thesis or '핵심 판단을 보강해야 합니다.')}</p>"
        f"<p><strong>다음 확인</strong><br>{escape(candidate.next_action or '다음 공시와 가격 위치를 확인합니다.')}</p>"
        "<strong>상승 근거</strong>"
        f"{_list(candidate.bull_case or candidate.evidence)}"
        "<strong>주의 신호</strong>"
        f"{_list(candidate.bear_case or candidate.risk_flags or candidate.gaps)}"
        "</article>"
    )


def _list(items: list[str]) -> str:
    if not items:
        return "<ul><li>-</li></ul>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _status_label(candidate: Candidate) -> str:
    return STATUS_LABELS.get(candidate.status.value, candidate.status.value)


def _state_class(candidate: Candidate) -> str:
    return {
        "Setup": "state-setup",
        "Research": "state-research",
        "Blocked": "state-blocked",
        "Avoid": "state-avoid",
    }.get(candidate.status.value, "state-watch")


def _regime_value(value: str) -> str:
    return {
        "conditional": "조건부 긍정",
        "pass": "긍정",
        "fail": "부정",
        "risk-on": "위험 선호",
        "neutral": "중립",
        "risk-off": "위험 회피",
        "stable": "유지",
        "down": "하락",
        "up": "상승",
        "low": "낮음",
        "normal": "보통",
        "high": "높음",
    }.get(value, value)
