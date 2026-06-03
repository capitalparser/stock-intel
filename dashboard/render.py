"""Render lens dashboard outputs."""

from __future__ import annotations

import json
import random
import re
import shutil
import sqlite3
import tempfile
from html import escape
from pathlib import Path

from dashboard.models import Candidate, Dashboard

# ── Lazy Alpha DB path (project root / state.db) ──────────────────────────
# render.py lives at: <project>/dashboard/render.py
# state.db lives at:  <project>/state.db
_DB_PATH = Path(__file__).resolve().parent.parent / "state.db"


# ── Lens ID → sector-filter tag mapping ──
_LENS_FILTER_TAG: dict[str, str] = {
    "ai_agent_compute": "AI에이전트",
    "ai_power_bottleneck": "AI전력",
    "semiconductors": "반도체",
    "power_analog": "전력아날로그",
    "stablecoin_rails": "스테이블코인",
}

# ── Conviction/direction → heat class ──
_HEAT_CLASS: dict[tuple[str, str], str] = {
    ("high", "improving"): "h-hi",
    ("high", "stable"): "h-hi",
    ("medium", "improving"): "h-mid",
    ("medium", "stable"): "h-neu",
    ("medium", "weakening"): "h-neu",
    ("low", "improving"): "h-neu",
    ("low", "stable"): "h-neu",
}

# ── Dark-mode CSS (not an f-string; use literal { } freely) ──
_DARK_CSS = """<style>
:root {
  --bg: #0f172a; --surface: #1e293b; --surface-2: #263548;
  --border: #334155; --text: #f1f5f9; --muted: #94a3b8;
  --up: #22c55e; --down: #ef4444; --accent: #3b82f6;
  --accent-dim: rgba(59,130,246,0.12); --warn: #f59e0b;
  --radius-sm: 6px; --radius-md: 10px; --radius-lg: 14px;
}
*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--text);
  font-family: Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  line-height: 1.6; letter-spacing: -0.02em; font-variant-numeric: tabular-nums;
  overflow-x: hidden;
}
.topbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(15,23,42,0.92); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border); padding: 0 28px;
  height: 56px; display: flex; align-items: center; gap: 16px;
}
.topbar-brand { font-size: 15px; font-weight: 700; letter-spacing: 0; }
.topbar-brand em { color: var(--accent); font-style: normal; }
.topbar-dot { color: var(--border); }
.topbar-meta { font-size: 12px; color: var(--muted); }
.topbar-badge {
  margin-left: auto; font-size: 11px; font-weight: 600;
  padding: 3px 10px; border-radius: 100px;
  background: rgba(34,197,94,0.12); color: var(--up);
  border: 1px solid rgba(34,197,94,0.2);
}
main { max-width: 1320px; margin: 0 auto; padding: 28px 24px 80px; }
.sh { display: flex; align-items: center; gap: 12px; margin: 36px 0 14px; }
.sh h2 {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--muted); white-space: nowrap;
}
.sh::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.macro-strip {
  display: flex; gap: 10px; overflow-x: auto;
  padding-bottom: 4px; scrollbar-width: none;
}
.macro-strip::-webkit-scrollbar { display: none; }
.mkpi {
  flex: 0 0 auto; min-width: 144px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 14px 18px; transition: border-color 0.15s;
}
.mkpi:hover { border-color: var(--accent); }
.mkpi.verdict {
  border-color: var(--accent); background: rgba(59,130,246,0.07);
  min-width: 160px;
}
.mkpi-label {
  font-size: 10px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;
}
.mkpi-val { font-size: 19px; font-weight: 700; line-height: 1.2; }
.mkpi-sub { font-size: 12px; font-weight: 600; margin-top: 4px; }
.up { color: var(--up); } .down { color: var(--down); } .neut { color: var(--muted); }
.regime-notes { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.regime-note {
  font-size: 12px; color: var(--muted);
  padding-left: 16px; position: relative;
}
.regime-note::before {
  content: '·'; position: absolute; left: 4px;
  color: var(--accent); font-weight: 700;
}
.heatmap { display: grid; grid-template-columns: repeat(auto-fill,minmax(196px,1fr)); gap: 10px; }
.hcell {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 14px 16px;
  border-left-width: 3px; border-left-style: solid;
  transition: transform 0.15s, box-shadow 0.15s;
}
.hcell:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
.hcell.h-hi  { border-left-color: var(--up);    background: rgba(34,197,94,0.05); }
.hcell.h-mid { border-left-color: var(--accent); background: rgba(59,130,246,0.05); }
.hcell.h-neu { border-left-color: var(--border); }
.hcell-name { font-size: 13px; font-weight: 700; margin-bottom: 7px; }
.hcell-badges { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 8px; }
.hbadge {
  font-size: 10px; font-weight: 600; padding: 2px 8px;
  border-radius: 100px; background: rgba(255,255,255,0.05); color: var(--muted);
}
.hbadge.bhi  { background: rgba(34,197,94,0.12);  color: var(--up); }
.hbadge.bmid { background: rgba(59,130,246,0.12); color: var(--accent); }
.hbadge.bneu { background: rgba(148,163,184,0.08);color: var(--muted); }
.hcell-risk { font-size: 10px; color: var(--muted); font-style: italic; }
.stabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
.stab {
  font-size: 12px; font-weight: 600; padding: 5px 14px;
  border-radius: 100px; border: 1px solid var(--border);
  background: transparent; color: var(--muted);
  cursor: pointer; font-family: inherit; letter-spacing: -0.01em;
  transition: all 0.15s;
}
.stab:hover { border-color: var(--accent); color: var(--text); }
.stab.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.cgrid { display: grid; grid-template-columns: repeat(auto-fill,minmax(272px,1fr)); gap: 12px; }
.ccard {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: 18px; cursor: pointer;
  transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
}
.ccard:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 10px 32px rgba(0,0,0,0.45); }
.ccard.off { display: none; }
.cc-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.cc-ticker { font-size: 22px; font-weight: 800; letter-spacing: -0.01em; line-height: 1; }
.cc-co { font-size: 11px; color: var(--muted); margin-top: 3px; }
.cc-stag {
  font-size: 10px; font-weight: 600; padding: 3px 9px;
  border-radius: 100px; background: var(--accent-dim); color: var(--accent);
  white-space: nowrap; margin-left: 8px; flex: none;
}
.cc-price { font-size: 24px; font-weight: 700; letter-spacing: -0.01em; line-height: 1; }
.cc-change { font-size: 13px; font-weight: 600; }
.cc-per { font-size: 11px; color: var(--muted); margin: 4px 0 10px; }
.cc-score-row { display: flex; align-items: center; gap: 9px; margin-bottom: 10px; }
.score-lbl { font-size: 10px; color: var(--muted); flex: none; }
.score-bar { flex: 1; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
.score-fill { height: 100%; background: linear-gradient(90deg,var(--accent),var(--up)); border-radius: 2px; }
.score-num { font-size: 13px; font-weight: 700; flex: none; }
.cc-spark { height: 54px; margin: 0 -3px; }
.cc-lenses { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 9px; }
.ltag {
  font-size: 9px; font-weight: 600; padding: 2px 7px;
  border-radius: 100px; border: 1px solid var(--border);
  color: var(--muted); background: rgba(255,255,255,0.03);
}
.twrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-md); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead tr { background: var(--surface-2); }
th {
  padding: 9px 14px; text-align: left; font-size: 10px; font-weight: 700;
  color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em;
  white-space: nowrap; border-bottom: 1px solid var(--border);
}
td { padding: 10px 14px; border-bottom: 1px solid rgba(51,65,85,0.45); vertical-align: middle; }
tbody tr:hover { background: rgba(255,255,255,0.02); }
.td-t { font-weight: 700; font-size: 14px; }
.td-co { font-size: 11px; color: var(--muted); margin-top: 1px; }
.st-research { font-size: 10px; font-weight: 700; color: var(--warn); }
.st-watch    { font-size: 10px; font-weight: 700; color: var(--muted); }
.st-setup    { font-size: 10px; font-weight: 700; color: var(--up); }
.st-avoid    { font-size: 10px; font-weight: 700; color: var(--down); }
.doverlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.55);
  z-index: 200; opacity: 0; pointer-events: none; transition: opacity 0.25s;
}
.doverlay.on { opacity: 1; pointer-events: all; }
.dpanel {
  position: fixed; top: 0; right: -460px;
  width: 460px; max-width: 96vw; height: 100vh;
  background: var(--surface); border-left: 1px solid var(--border);
  z-index: 201; transition: right 0.3s cubic-bezier(0.32,0.72,0,1);
  overflow-y: auto; padding: 32px 28px 56px;
}
.dpanel.on { right: 0; }
.dclose {
  position: absolute; top: 18px; right: 18px; width: 32px; height: 32px;
  border-radius: 50%; background: rgba(255,255,255,0.06);
  border: 1px solid var(--border); color: var(--muted); font-size: 20px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-family: inherit; transition: background 0.15s, color 0.15s;
}
.dclose:hover { background: rgba(255,255,255,0.12); color: var(--text); }
.dt { font-size: 32px; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 2px; }
.dco { font-size: 13px; color: var(--muted); margin-bottom: 16px; }
.dp-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; }
.dp { font-size: 28px; font-weight: 700; letter-spacing: -0.01em; }
.dc { font-size: 15px; font-weight: 600; }
.dper { font-size: 11px; color: var(--muted); margin-bottom: 16px; }
.d-spark { height: 80px; margin: 0 -4px 20px; }
.dl {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted); margin: 18px 0 8px; padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.d-thesis { font-size: 13px; line-height: 1.7; color: var(--text); margin-bottom: 10px; }
.d-list { list-style: none; display: flex; flex-direction: column; gap: 5px; margin-bottom: 10px; }
.d-list li { font-size: 12px; line-height: 1.5; padding-left: 18px; position: relative; color: var(--muted); }
.d-list li::before { position: absolute; left: 0; }
.bull li::before { content: '↑'; color: var(--up); }
.bear li::before { content: '↓'; color: var(--down); }
.gap  li::before { content: '○'; color: var(--warn); }
.d-lenses { display: flex; flex-wrap: wrap; gap: 6px; }
.d-ltag {
  font-size: 11px; font-weight: 600; padding: 4px 12px;
  border-radius: 100px; border: 1px solid var(--accent); color: var(--accent);
}
.d-action {
  font-size: 12px; line-height: 1.65;
  background: rgba(59,130,246,0.07); border: 1px solid rgba(59,130,246,0.2);
  border-radius: var(--radius-sm); padding: 10px 14px; color: var(--text);
}
@media (max-width: 768px) {
  main { padding: 20px 16px 56px; }
  .dpanel { width: 100%; max-width: 100%; }
}
</style>"""

# ── Static JS (placeholders replaced at render time) ──
# Placeholders: __CANDIDATES__ __TABLE_EXTRA__
_DARK_JS = """\
<script>
const CANDIDATES = __CANDIDATES__;
const TABLE_EXTRA = __TABLE_EXTRA__;
const TABLE_ALL = [...CANDIDATES, ...TABLE_EXTRA];

/* helpers */
function fmtP(v) {
  if (v === null) return '—';
  return '$' + v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function fmtC(v) {
  if (v === null) return {txt:'—',cls:'neut'};
  return {txt:(v>=0?'+':'')+v.toFixed(2)+'%', cls:v>=0?'up':'down'};
}
function spkColor(d) { return d[d.length-1]>=d[0]?'#22c55e':'#ef4444'; }
function spkBg(d) { return d[d.length-1]>=d[0]?'rgba(34,197,94,0.08)':'rgba(239,68,68,0.08)'; }

const CR = {};
function drawSpark(id,data,minimal=true) {
  const el = document.getElementById(id);
  if (!el||!data) return;
  if (CR[id]) { CR[id].destroy(); }
  const c = spkColor(data);
  CR[id] = new Chart(el,{
    type:'line',
    data:{labels:data.map((_,i)=>i),datasets:[{
      data,borderColor:c,borderWidth:minimal?1.5:2,
      pointRadius:0,fill:true,backgroundColor:spkBg(data),tension:0.35
    }]},
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:500},
      plugins:{legend:{display:false},tooltip:minimal?{enabled:false}:{
        enabled:true,callbacks:{label:ctx=>fmtP(ctx.raw)},
        backgroundColor:'#0f172a',borderColor:'#334155',borderWidth:1,
        titleColor:'#94a3b8',bodyColor:'#f1f5f9'
      }},
      scales:{x:{display:false},y:{display:false}}}
  });
}

/* cards */
function renderCards() {
  const grid = document.getElementById('cgrid');
  grid.innerHTML = '';
  CANDIDATES.forEach(c => {
    const {txt:chT,cls:chC} = fmtC(c.change);
    const id = 'sp-'+c.ticker;
    const lh = (c.lenses||[]).map(l=>`<span class="ltag">${l}</span>`).join('');
    const div = document.createElement('div');
    div.className = 'ccard';
    div.dataset.tags = JSON.stringify(c.tags||[]);
    div.innerHTML = `
      <div class="cc-top">
        <div><div class="cc-ticker">${c.display_name}</div><div class="cc-co">${c.display_meta}</div></div>
        <span class="cc-stag">${c.sector}</span>
      </div>
      <div style="display:flex;align-items:baseline;gap:10px;margin:8px 0 2px">
        <span class="cc-price">${fmtP(c.price)}</span>
        <span class="cc-change ${chC}">${chT}</span>
      </div>
      <div class="cc-per">PER ${c.pe!==null?c.pe+'x':'—'} · 동종군 대비 ${c.peer_pe!==null?c.peer_pe+'x':'—'}</div>
      <div class="cc-score-row">
        <span class="score-lbl">매력도</span>
        <div class="score-bar"><div class="score-fill" style="width:${c.score}%"></div></div>
        <span class="score-num">${c.score}</span>
      </div>
      <div class="cc-spark"><canvas id="${id}"></canvas></div>
      <div class="cc-lenses">${lh}</div>`;
    div.addEventListener('click',()=>openDetail(c));
    grid.appendChild(div);
    requestAnimationFrame(()=>drawSpark(id,c.spark));
  });
}

/* filter */
document.querySelectorAll('.stab').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.stab').forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');
    const f=btn.dataset.f;
    document.querySelectorAll('.ccard').forEach(card=>{
      const tags=JSON.parse(card.dataset.tags||'[]');
      card.classList.toggle('off',f!=='all'&&!tags.includes(f));
    });
  });
});

/* table */
function renderTable() {
  const tb = document.getElementById('ttbody');
  TABLE_ALL.forEach(c=>{
    const {txt:chT,cls:chC}=fmtC(c.change);
    const lT=(c.lenses||[]).slice(0,2).join(', ')||'—';
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td><div class="td-t">${c.display_name}</div><div class="td-co">${c.display_meta}</div></td>
      <td><span class="st-${c.status}">${c.status_label}</span></td>
      <td>${fmtP(c.price)}${c.change!==null?` <span class="${chC}" style="font-size:10px">${chT}</span>`:''}</td>
      <td style="color:var(--muted)">${c.pe!==null?c.pe+'x':'—'}</td>
      <td style="font-weight:700">${(c.score||0).toFixed(1)}</td>
      <td style="color:var(--muted);font-size:11px">${lT}</td>`;
    tb.appendChild(tr);
  });
}

/* detail */
let dChart=null;
function openDetail(c) {
  const ov=document.getElementById('doverlay');
  const pn=document.getElementById('dpanel');
  const ct=document.getElementById('dcontent');
  const {txt:chT,cls:chC}=fmtC(c.change);
  const bH=(c.bull||[]).map(b=>`<li>${b}</li>`).join('');
  const beH=(c.bear||[]).map(b=>`<li>${b}</li>`).join('');
  const gH=(c.gaps||[]).map(g=>`<li>${g}</li>`).join('');
  const lH=(c.lenses||[]).map(l=>`<span class="d-ltag">${l}</span>`).join('');
  ct.innerHTML=`
    <div class="dt">${c.display_name}</div>
    <div class="dco">${c.display_meta}</div>
    <div class="dp-row"><span class="dp">${fmtP(c.price)}</span><span class="dc ${chC}">${chT}</span></div>
    <div class="dper">PER ${c.pe!==null?c.pe+'x':'—'} · 동종군 대비 ${c.peer_pe!==null?c.peer_pe+'x':'—'} · 매력도 ${c.score}</div>
    <div class="d-spark"><canvas id="d-sp"></canvas></div>
    ${c.thesis?`<div class="dl">핵심 판단</div><div class="d-thesis">${c.thesis}</div>`:''}
    ${bH?`<div class="dl">상승 근거</div><ul class="d-list bull">${bH}</ul>`:''}
    ${beH?`<div class="dl">주의 신호</div><ul class="d-list bear">${beH}</ul>`:''}
    ${gH?`<div class="dl">보강할 근거</div><ul class="d-list gap">${gH}</ul>`:''}
    <div class="dl">연결 관점</div><div class="d-lenses">${lH}</div>
    ${c.next?`<div class="dl">다음 확인</div><div class="d-action">${c.next}</div>`:''}`;
  ov.classList.add('on'); pn.classList.add('on');
  if(dChart){dChart.destroy();dChart=null;}
  setTimeout(()=>{
    const cv=document.getElementById('d-sp');
    if(cv&&c.spark){
      const col=spkColor(c.spark);
      dChart=new Chart(cv,{type:'line',
        data:{labels:c.spark.map((_,i)=>i),datasets:[{
          data:c.spark,borderColor:col,borderWidth:2,pointRadius:0,
          fill:true,backgroundColor:spkBg(c.spark),tension:0.35}]},
        options:{responsive:true,maintainAspectRatio:false,animation:{duration:400},
          plugins:{legend:{display:false},tooltip:{enabled:true,
            callbacks:{label:ctx=>fmtP(ctx.raw)},
            backgroundColor:'#0f172a',borderColor:'#334155',borderWidth:1,
            titleColor:'#94a3b8',bodyColor:'#f1f5f9'}},
          scales:{x:{display:false},y:{display:false}}}});
    }
  },60);
}
function closeDetail(){
  document.getElementById('doverlay').classList.remove('on');
  document.getElementById('dpanel').classList.remove('on');
}
document.getElementById('doverlay').addEventListener('click',closeDetail);
document.getElementById('dclose').addEventListener('click',closeDetail);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail();});

renderCards();
renderTable();
</script>"""

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
        f"가격 기준: {dashboard.price_time}",
        "",
        "## 시장 국면",
        f"- 현재 판단: {_regime_value(dashboard.regime.verdict)}",
        f"- 위험자산 선호: {_regime_value(dashboard.regime.risk_appetite)}",
        f"- 금리: {_regime_value(dashboard.regime.rates)}",
        f"- 달러: {_regime_value(dashboard.regime.dollar)}",
        f"- 변동성: {_regime_value(dashboard.regime.volatility)}",
    ]
    if dashboard.macro_state:
        state = dashboard.macro_state
        lines += [
            "",
            "## 매크로 현재 상태",
            f"- 현재 상태: {_macro_current_state_label(state.current_state)}",
            f"- 왜 중요한가: {state.why_it_matters}",
            f"- 다음 행동: {state.next_action}",
            "",
            "## 오늘의 주요 이슈",
        ]
        for issue in state.issues:
            lines.append(f"- {issue.theme}: {issue.title} · {issue.summary}")
        lines += [
            "",
            "## 종목 후보 영향",
            f"- 성장/AI: {state.watchlist_impact.growth_ai}",
            f"- 경기민감: {state.watchlist_impact.cyclicals}",
            f"- 에너지/방산: {state.watchlist_impact.energy_defense}",
            f"- 한국시장: {state.watchlist_impact.korea}",
        ]
    lines += [
        "",
        "## 시장 온도판",
    ]
    for item in dashboard.market_indicators:
        lines.append(
            f"- {item.symbol} {item.name}: {_money(item.price)}, {_pct(item.day_change_pct)} · {item.read}"
        )
    lines += [
        "",
        "## 상위 후보",
    ]
    for candidate in _top_candidates(dashboard)[:10]:
        view_names = ", ".join(lens.name for lens in candidate.linked_lenses)
        lines.append(
            f"- {_markdown_stock_label(candidate)}: "
            f"{_status_label(candidate)}, 매력도 {candidate.score:.1f}, "
            f"가격 {_money(candidate.price)}, PER {_multiple(candidate.pe)} "
            f"(동종군 {_multiple(candidate.peer_pe)}), 연결 관점 {view_names}"
        )
        if candidate.thesis:
            lines.append(f"  - 핵심 판단: {candidate.thesis}")
        if candidate.next_action:
            lines.append(f"  - 다음 확인: {candidate.next_action}")
    return "\n".join(lines) + "\n"


def render_dashboard_html(dashboard: Dashboard, db_path: str | Path | None = None) -> str:
    """Render a dark-mode financial dashboard with Chart.js sparklines.

    Parameters
    ----------
    dashboard : Dashboard
    db_path : optional path to state.db.  Default: auto-detected (_DB_PATH).
    """
    # ── Lazy Alpha: DB에서 종목별 시그널 상태 로딩 ──────────────────────────
    lazy_map = load_lazy_alpha_from_db(db_path)

    candidate_count = len(dashboard.candidates)
    priced_count = sum(1 for c in dashboard.candidates if c.price is not None)
    setup_count = sum(1 for c in dashboard.candidates if c.status.value == "Setup")
    research_count = sum(1 for c in dashboard.candidates if c.status.value == "Research")

    verdict = escape(_regime_value(dashboard.regime.verdict))
    risk_kpi = escape(_regime_value(dashboard.regime.risk_appetite))

    # Regime notes
    regime_notes = "\n".join(
        f'    <div class="regime-note">{escape(n)}</div>'
        for n in dashboard.regime.notes
    )

    # Macro KPI cards
    macro_cards = "\n".join(_mkpi_card(item) for item in dashboard.market_indicators)

    # Heatmap cells
    heatmap_cells = "\n".join(_heatmap_cell(lens) for lens in dashboard.lenses)

    # Determine unique filter tags from lenses for tab buttons
    filter_tags: list[tuple[str, str]] = [("all", "전체")]
    seen: set[str] = set()
    for lens in dashboard.lenses:
        tag = _LENS_FILTER_TAG.get(lens.id)
        if tag and tag not in seen:
            seen.add(tag)
            filter_tags.append((tag, tag))
    filter_tabs = "\n".join(
        f'    <button class="stab{" on" if i == 0 else ""}" data-f="{escape(fid)}">{escape(flabel)}</button>'
        for i, (fid, flabel) in enumerate(filter_tags)
    )

    # Build JS data: every candidate gets a card; missing market data stays visible as "—".
    def _to_js(c: Candidate, full: bool = True) -> dict:
        tags = list({
            _LENS_FILTER_TAG[lns.id]
            for lns in c.linked_lenses
            if lns.id in _LENS_FILTER_TAG
        })
        base: dict = {
            "ticker": c.ticker,
            "company": c.company,
            "display_name": _display_name(c),
            "display_meta": _display_meta(c),
            "sector": c.sector,
            "tags": tags,
            "price": c.price,
            "change": c.day_change_pct,
            "pe": c.pe,
            "peer_pe": c.peer_pe,
            "score": round(c.score, 1),
            "status": c.status.value.lower(),
            "status_label": STATUS_LABELS.get(c.status.value, c.status.value),
            "lenses": [lns.name for lns in c.linked_lenses],
            # Lazy Alpha: DB에서 자동 주입. DB 없거나 종목 없으면 null.
            "lazy": lazy_map.get(c.ticker),
        }
        if full:
            base.update({
                "thesis": c.thesis or "",
                "bull": list(c.bull_case or c.evidence or []),
                "bear": list(c.bear_case or c.risk_flags or []),
                "gaps": list(c.gaps or []),
                "next": c.next_action or "",
                "spark": _fake_sparkline(c.ticker, c.price) if c.price else None,
            })
        return base

    candidates_json = json.dumps(
        [_to_js(c, full=True) for c in dashboard.candidates], ensure_ascii=False
    )
    table_extra_json = json.dumps([], ensure_ascii=False)

    js = (
        _DARK_JS
        .replace("__CANDIDATES__", candidates_json)
        .replace("__TABLE_EXTRA__", table_extra_json)
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>개인 투자 상황판 · {escape(dashboard.as_of)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  {_DARK_CSS}
</head>
<body>
<header class="topbar">
  <div class="topbar-brand">개인 투자 <em>상황판</em></div>
  <span class="topbar-dot">·</span>
  <div class="topbar-meta">{escape(dashboard.as_of)}</div>
  <span class="topbar-badge">{risk_kpi}</span>
</header>
<main>
{_macro_state_html(dashboard)}
  <div class="sh" style="margin-top:0"><h2>시장 국면</h2></div>
  <div class="macro-strip">
    <div class="mkpi verdict">
      <div class="mkpi-label">현재 판단</div>
      <div class="mkpi-val">{verdict}</div>
      <div class="mkpi-sub up">{risk_kpi}</div>
    </div>
{macro_cards}
    <div class="mkpi">
      <div class="mkpi-label">관찰 종목</div>
      <div class="mkpi-val">{candidate_count}</div>
      <div class="mkpi-sub neut">가격 {priced_count}개 · 근거 보강 {research_count}개</div>
    </div>
  </div>
  <div class="regime-notes">
{regime_notes}
  </div>

  <div class="sh"><h2>시장 온도판</h2></div>
  <div class="sh"><h2>투자 관점 지도</h2></div>
  <div class="heatmap">
{heatmap_cells}
  </div>

  <div class="sh"><h2>후보별 판단 메모</h2></div>
  <div class="stabs">
{filter_tabs}
  </div>
  <div class="cgrid" id="cgrid"></div>

  <div class="sh"><h2>전체 종목 총괄표</h2></div>
  <div class="twrap">
    <table>
      <thead>
        <tr>
          <th>종목</th><th>상태</th><th>가격/PER</th>
          <th>동종군 비교</th><th>매력도</th><th>주요 관점</th>
        </tr>
      </thead>
      <tbody id="ttbody"></tbody>
    </table>
  </div>
</main>
<div class="doverlay" id="doverlay"></div>
<div class="dpanel" id="dpanel">
  <button class="dclose" id="dclose">×</button>
  <div id="dcontent"></div>
</div>
{js}
</body>
</html>
"""


# ── New dark-mode helpers ──────────────────────────────────────────────────

def _macro_state_html(dashboard: Dashboard) -> str:
    state = dashboard.macro_state
    if not state:
        return ""
    indicators = "\n".join(
        f"""    <div class="mkpi">
      <div class="mkpi-label">{escape(item.label)}</div>
      <div class="mkpi-val">{escape(_macro_state_label(item.state))}</div>
      <div class="mkpi-sub neut">{escape(item.read)}</div>
    </div>"""
        for item in state.indicator_reads
    )
    issues = "\n".join(
        f"""    <div class="hcell h-neu">
      <div class="hcell-name">{escape(issue.theme)} · {escape(issue.title)}</div>
      <div class="d-thesis">{escape(issue.summary)}</div>
      <div class="hcell-risk">주의 트리거: {escape(" · ".join(issue.triggers) or "확인 필요")}</div>
      <div class="hcell-risk">접근 갭: {escape(" · ".join(issue.source_gaps) or "없음")}</div>
    </div>"""
        for issue in state.issues
    )
    impact = state.watchlist_impact
    return f"""
  <div class="sh" style="margin-top:0"><h2>매크로 현재 상태</h2></div>
  <div class="macro-strip">
    <div class="mkpi verdict">
      <div class="mkpi-label">현재 상태</div>
      <div class="mkpi-val">{escape(_macro_current_state_label(state.current_state))}</div>
      <div class="mkpi-sub neut">{escape(state.next_action)}</div>
    </div>
    <div class="mkpi" style="min-width:360px">
      <div class="mkpi-label">왜 중요한가</div>
      <div class="mkpi-sub neut">{escape(state.why_it_matters)}</div>
    </div>
  </div>

  <div class="sh"><h2>오늘의 주요 이슈</h2></div>
  <div class="heatmap">
{issues}
  </div>

  <div class="sh"><h2>시장 지표 판정</h2></div>
  <div class="macro-strip">
{indicators}
  </div>

  <div class="sh"><h2>종목 후보 영향</h2></div>
  <div class="regime-notes">
    <div class="regime-note">성장/AI: {escape(impact.growth_ai)}</div>
    <div class="regime-note">경기민감: {escape(impact.cyclicals)}</div>
    <div class="regime-note">에너지/방산: {escape(impact.energy_defense)}</div>
    <div class="regime-note">한국시장: {escape(impact.korea)}</div>
  </div>
"""


def _macro_current_state_label(value: str) -> str:
    return {
        "risk-on": "위험자산 우호",
        "conditional": "조건부",
        "risk-off": "위험 회피",
        "fragile rally": "취약한 랠리",
    }.get(value, value)


def _macro_state_label(value: str) -> str:
    return {
        "supportive": "우호",
        "warning": "경고",
        "stressed": "압박",
        "unavailable": "확인 필요",
    }.get(value, value)


def _display_name(candidate: Candidate) -> str:
    return candidate.company if _is_kr_stock(candidate) else candidate.ticker


def _display_meta(candidate: Candidate) -> str:
    if _is_kr_stock(candidate):
        return f"{candidate.ticker} · {candidate.sector}"
    return f"{candidate.company} · {candidate.sector}"


def _markdown_stock_label(candidate: Candidate) -> str:
    if _is_kr_stock(candidate):
        return f"{candidate.company} ({candidate.ticker})"
    return f"{candidate.ticker} {candidate.company}"


def _is_kr_stock(candidate: Candidate) -> bool:
    return bool(re.fullmatch(r"\d{6}", candidate.ticker))


def _fake_sparkline(ticker: str, price: float) -> list[float]:
    """Seeded 20-point fake sparkline ending at current price."""
    rng = random.Random(hash(ticker) & 0xFFFF_FFFF)
    start = price * rng.uniform(0.84, 0.93)
    pts: list[float] = [start]
    for _ in range(18):
        pts.append(pts[-1] * (1 + rng.uniform(-0.013, 0.019)))
    pts.append(price)
    return [round(v, 2) for v in pts]


def _mkpi_card(item) -> str:
    sign = "+" if item.day_change_pct >= 0 else ""
    cls = "up" if item.day_change_pct >= 0 else "down"
    return (
        f'    <div class="mkpi">\n'
        f'      <div class="mkpi-label">{escape(item.symbol)} · {escape(item.group)}</div>\n'
        f'      <div class="mkpi-val">{escape(_money(item.price))}</div>\n'
        f'      <div class="mkpi-sub {cls}">{sign}{item.day_change_pct:.2f}%</div>\n'
        f'    </div>'
    )


def _heatmap_cell(lens) -> str:
    heat = _HEAT_CLASS.get((lens.conviction, lens.direction), "h-neu")
    conv_label = CONVICTION_LABELS.get(lens.conviction, lens.conviction)
    dir_label = DIRECTION_LABELS.get(lens.direction, lens.direction)
    kind_label = KIND_LABELS.get(lens.kind.value, lens.kind.value)
    dir_arrow = {"improving": "↑", "stable": "→", "weakening": "↓"}.get(
        lens.direction, ""
    )
    # Badge classes
    if lens.conviction == "high":
        conv_cls = "bhi"
    elif lens.conviction == "medium" and lens.direction == "improving":
        conv_cls = "bmid"
    else:
        conv_cls = "bneu"
    dir_cls = "bhi" if lens.direction == "improving" and lens.conviction == "high" else (
        "bmid" if lens.direction == "improving" else "bneu"
    )
    risks_txt = escape(", ".join(lens.risks) or "—")
    return (
        f'    <div class="hcell {heat}">\n'
        f'      <div class="hcell-name">{escape(lens.name)}</div>\n'
        f'      <div class="hcell-badges">\n'
        f'        <span class="hbadge {conv_cls}">확신 {escape(conv_label)}</span>\n'
        f'        <span class="hbadge {dir_cls}">{dir_arrow} {escape(dir_label)}</span>\n'
        f'        <span class="hbadge bneu">{escape(kind_label)}</span>\n'
        f'      </div>\n'
        f'      <div class="hcell-risk">리스크: {risks_txt}</div>\n'
        f'    </div>'
    )


# ── Lazy Alpha DB helpers ──────────────────────────────────────────────────
# NOTE: scripts/inject_lazy.py는 이미 생성된 HTML을 후처리로 갱신하는 수동 도구임.
# render_dashboard_html()이 load_lazy_alpha_from_db()를 직접 호출하므로
# 최초 렌더링 시 inject_lazy.py를 별도 실행할 필요 없음.
# inject_lazy.py는 생성된 HTML을 재처리(수동 갱신)할 때만 사용.

_LAZY_EMOJI_RE = re.compile(
    r"^[\U0001F300-\U0001FFFF"
    r"\U00002600-\U000027BF"
    r"☀-➿"
    r"︀-️"
    r"‍"
    r"⚠️✅🔴🟢🟡🔵⚫☁️📈🐂"
    r"\s]+",
    re.UNICODE,
)


def _lazy_clean_label(label: str) -> str:
    """선행 이모지·공백 제거."""
    return _LAZY_EMOJI_RE.sub("", label).strip()


def _lazy_pattern_from_label(label: str) -> str:
    """라벨 텍스트에서 짧은 패턴명 도출."""
    clean = _lazy_clean_label(label)
    if "돌파" in clean:
        return "돌파 진입"
    if "피라미딩" in clean or "추매" in clean:
        return "피라미딩 추가"
    if "진입" in clean:
        return "신규 진입"
    if "청산" in clean or "분할" in clean:
        return "청산"
    if "이탈" in clean:
        return "이탈"
    if "셋업" in clean:
        return "셋업 관찰"
    if clean in ("라벨 없음", "-", ""):
        return "신호 없음"
    return clean or "확인"


def _lazy_default_penalty(state_key: str) -> int:
    return {
        "ACTIVE_BUY":  0,
        "CAUTION_BUY": 20,
        "BLOCKED_BUY": 40,
        "EXIT":        25,
    }.get(state_key, 0)


_LAZY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS lazy_alpha_symbol_states (
    symbol       TEXT PRIMARY KEY,
    market       TEXT NOT NULL,
    state_key    TEXT NOT NULL,
    label        TEXT NOT NULL,
    label_date   TEXT NOT NULL,
    verdict      TEXT NOT NULL,
    action       TEXT NOT NULL,
    observed_at  INTEGER NOT NULL
);
"""


def load_lazy_alpha_from_db(db_path: str | Path | None = None) -> dict[str, dict | None]:
    """state.db의 lazy_alpha_symbol_states 테이블에서 종목별 최신 상태 조회.

    Returns
    -------
    dict[ticker, lazy_dict | None]
        active 종목: {state_key, last_label, last_label_date, penalty, pattern, verdict}
        IDLE 종목:   None
    DB 없거나 테이블 없으면 빈 dict 반환 (graceful fallback).
    """
    path = Path(db_path) if db_path else _DB_PATH
    if not path.exists():
        print(f"[render] ⚠ state.db not found at {path} — lazy alpha skipped", flush=True)
        return {}

    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            tmp = Path(tf.name)
        shutil.copy(path, tmp)
        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        con.executescript(_LAZY_TABLE_SQL)
        con.commit()

        rows = con.execute(
            "SELECT symbol, state_key, label, label_date, verdict "
            "FROM lazy_alpha_symbol_states"
        ).fetchall()
        con.close()

        result: dict[str, dict | None] = {}
        for row in rows:
            symbol: str = row["symbol"]
            state_key: str = row["state_key"]
            # exchange prefix 제거: "KRX:267260" → "267260", "NASDAQ:NVDA" → "NVDA"
            parts = symbol.split(":", 1)
            ticker = parts[1] if len(parts) == 2 else parts[0]

            if state_key == "IDLE":
                result[ticker] = None  # IDLE → lazy null (의미 있는 시그널 없음)
                continue

            result[ticker] = {
                "state_key":      state_key,
                "last_label":     _lazy_clean_label(row["label"]),
                "last_label_date": row["label_date"],
                "penalty":        _lazy_default_penalty(state_key),
                "pattern":        _lazy_pattern_from_label(row["label"]),
                "verdict":        row["verdict"],
            }

        active = sum(1 for v in result.values() if v is not None)
        print(
            f"[render] Lazy Alpha: {len(rows)} symbols loaded ({active} active)",
            flush=True,
        )
        return result

    except Exception as exc:  # noqa: BLE001
        print(f"[render] ⚠ Lazy Alpha DB read failed: {exc} — continuing without lazy", flush=True)
        return {}
    finally:
        if tmp and tmp.exists():
            tmp.unlink(missing_ok=True)


# ── Legacy helpers (used by render_dashboard_markdown and kept for compatibility) ──

def _candidate_row(candidate: Candidate) -> str:
    lens_names = ", ".join(lens.name for lens in candidate.linked_lenses)
    gaps = "; ".join(candidate.gaps) or "-"
    return (
        "<tr>"
        f"<td><strong>{escape(candidate.ticker)}</strong><br>{escape(candidate.company)}"
        f"<br><span class=\"muted\">{escape(candidate.sector)}</span></td>"
        f"<td class=\"{escape(_state_class(candidate))}\">{escape(_status_label(candidate))}</td>"
        f"<td>{escape(_money(candidate.price))}<br><span class=\"muted\">PER {escape(_multiple(candidate.pe))}</span></td>"
        f"<td>{escape(_peer_read(candidate))}<br><span class=\"muted\">{escape(candidate.peer_group or '-')}</span></td>"
        f"<td>{candidate.score:.1f}</td>"
        f"<td>{escape(lens_names)}</td>"
        f"<td>{escape(gaps)}<br><span class=\"muted\">{escape(_sources(candidate))}</span></td>"
        "</tr>"
    )


def _candidate_card(candidate: Candidate) -> str:
    return (
        '<article class="candidate-card">'
        f"<h3>{escape(candidate.ticker)} · {escape(candidate.company)}</h3>"
        f"<p class=\"muted\">가격 {_money(candidate.price)} · 하루 변화 {_pct(candidate.day_change_pct)} · PER {_multiple(candidate.pe)} · 동종군 {_multiple(candidate.peer_pe)} · 가장 강한 관점 {escape(candidate.strongest_lens)}</p>"
        f"<p><strong>핵심 판단</strong><br>{escape(candidate.thesis or '핵심 판단을 보강해야 합니다.')}</p>"
        f"<p><strong>다음 확인</strong><br>{escape(candidate.next_action or '다음 공시와 가격 위치를 확인합니다.')}</p>"
        f"<p class=\"muted\">인사이트 출처: {escape(_sources(candidate))}</p>"
        "<strong>상승 근거</strong>"
        f"{_list(candidate.bull_case or candidate.evidence)}"
        "<strong>주의 신호</strong>"
        f"{_list(candidate.bear_case or candidate.risk_flags or candidate.gaps)}"
        "</article>"
    )


def _market_row(item) -> str:
    return (
        "<tr>"
        f"<td><strong>{escape(item.symbol)}</strong><br>{escape(item.name)}<br><span class=\"muted\">{escape(item.group)}</span></td>"
        f"<td>{escape(_money(item.price))}</td>"
        f"<td>{escape(_pct(item.day_change_pct))}</td>"
        f"<td>{escape(item.read)}</td>"
        "</tr>"
    )


def _top_candidates(dashboard: Dashboard) -> list[Candidate]:
    priced = [candidate for candidate in dashboard.candidates if candidate.price is not None]
    return priced or dashboard.candidates


def _list(items: list[str]) -> str:
    if not items:
        return "<ul><li>-</li></ul>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _sources(candidate: Candidate) -> str:
    if not candidate.source_refs:
        return "-"
    return ", ".join(candidate.source_refs[:4])


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


def _money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.2f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _multiple(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}x"


def _peer_read(candidate: Candidate) -> str:
    if candidate.pe is None or candidate.peer_pe is None or candidate.peer_pe == 0:
        return "비교 전"
    spread = (candidate.pe / candidate.peer_pe - 1) * 100
    if spread >= 20:
        return f"동종군 대비 +{spread:.0f}%"
    if spread <= -20:
        return f"동종군 대비 {spread:.0f}%"
    sign = "+" if spread > 0 else ""
    return f"동종군 근처 ({sign}{spread:.0f}%)"
