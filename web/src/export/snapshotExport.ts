import { pasTokens } from "../../../../00_personal_agent_system/design-kit/typescript/src/tokens";
import { commonCockpitTabs } from "../../../../00_personal_agent_system/design-kit/typescript/src/cockpitProfiles";
import { DashboardSnapshot } from "../data/snapshot";
import { attentionCategories, getAttentionCategories } from "../lib/risk";

type ExportScope = "current_tab" | "all_tabs";

export type ExportSnapshotOptions = {
  scope: ExportScope;
  currentTab: (typeof commonCockpitTabs)[number];
  snapshot: DashboardSnapshot;
  generatedAt: Date;
  source: { dashboardName: string; userOrService: string };
  dataWindow: { from: string; to: string };
};

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function hashSnapshot(snapshot: DashboardSnapshot) {
  const json = JSON.stringify(snapshot);
  let hash = 2166136261;
  for (let index = 0; index < json.length; index += 1) {
    hash ^= json.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function kstIso(date: Date) {
  const shifted = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  return `${shifted.toISOString().slice(0, 19)}+09:00`;
}

function runtimeScript() {
  return `<script>
  (function () {
    document.querySelectorAll('[data-switcher]').forEach(function (nav) {
      var box = document.querySelector('[data-switcher-panels="' + nav.dataset.switcher + '"]');
      if (!box) return;
      var isSideNav = nav.classList.contains('side-nav');
      var attr = isSideNav ? 'aria-current' : 'aria-selected';
      var val = isSideNav ? 'page' : 'true';
      nav.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-target]');
        if (!btn || !nav.contains(btn)) return;
        nav.querySelectorAll('[data-target]').forEach(function (b) { b.removeAttribute(attr); });
        btn.setAttribute(attr, val);
        box.querySelectorAll('[data-panel]').forEach(function (p) { p.hidden = true; });
        var panel = box.querySelector('[data-panel="' + btn.dataset.target + '"]');
        if (panel) panel.hidden = false;
      });
    });
    document.querySelectorAll('[data-toggle]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (el.tagName === 'A') e.preventDefault();
        var t = document.querySelector(el.dataset.toggle);
        if (t) t.hidden = !t.hidden;
      });
    });
    document.querySelectorAll('[data-filter-control]').forEach(function (ctrl) {
      var tgt = document.querySelector(ctrl.dataset.filterControl);
      if (!tgt) return;
      ctrl.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-filter]');
        if (!btn) return;
        var key = btn.dataset.filter;
        ctrl.querySelectorAll('[data-filter]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
        btn.setAttribute('aria-pressed', 'true');
        tgt.querySelectorAll('[data-tags]').forEach(function (item) {
          item.hidden = key !== 'all' && (' ' + item.dataset.tags + ' ').indexOf(' ' + key + ' ') < 0;
        });
      });
    });
  })();
</script>`;
}

function css() {
  return `<style>
    :root{--bg:${pasTokens.color.bg};--surface:${pasTokens.color.surface};--surfaceAlt:${pasTokens.color.surfaceAlt};--line:${pasTokens.color.line};--text:${pasTokens.color.text};--muted:${pasTokens.color.textMuted};--info:${pasTokens.color.info};--risk:${pasTokens.color.risk};--warn:${pasTokens.color.warn};--ok:${pasTokens.color.ok};--accentSoft:${pasTokens.color.accentSoft};}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:${pasTokens.typography.font};letter-spacing:${pasTokens.typography.bodyLetterSpacing};line-height:${pasTokens.typography.bodyLineHeight}} main{max-width:1180px;margin:0 auto;padding:24px} .shell,.card{background:var(--surface);border:1px solid var(--line);border-radius:${pasTokens.radius.md};padding:16px}.grid{display:grid;gap:16px}.two{grid-template-columns:repeat(2,minmax(0,1fr))}.tabs{display:flex;flex-wrap:wrap;gap:8px;border-bottom:1px solid var(--line);padding-bottom:8px}.tabs button{border:0;border-bottom:2px solid transparent;background:transparent;padding:8px;color:var(--muted);font:inherit;font-weight:700}.tabs button[aria-selected=true]{border-color:var(--info);color:var(--text)}.badge{display:inline-block;border:1px solid var(--line);border-radius:${pasTokens.radius.sm};padding:2px 8px;margin:2px;font-size:12px}.muted{color:var(--muted)}.kpis{grid-template-columns:repeat(4,minmax(0,1fr))} table{width:100%;border-collapse:collapse} th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top} .filters button{margin-right:8px;border:1px solid var(--line);border-radius:${pasTokens.radius.sm};background:var(--surface);padding:4px 8px} .filters button[aria-pressed=true]{border-color:var(--info);color:var(--info)} footer{margin-top:24px;border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:12px}@media(max-width:760px){main{padding:12px}.two,.kpis{grid-template-columns:1fr}}@media print{.tabs,.filters{display:none}details>*:not(summary){display:block}}
  </style>`;
}

function header(snapshot: DashboardSnapshot) {
  return `<header class="grid two"><div><p class="muted">현재 상태</p><h1>개인 투자 상황판</h1><p>미국 ${escapeHtml(snapshot.dual_regime.us.regime)} · 한국 ${escapeHtml(snapshot.dual_regime.kr.regime)} · 기준일 ${escapeHtml(snapshot.as_of)}</p></div><div><p class="muted">왜 중요한가</p><p>${escapeHtml(snapshot.dual_regime.us.why_it_matters)}</p><p>${escapeHtml(snapshot.dual_regime.kr.why_it_matters)}</p></div></header>`;
}

function summaryPanel(snapshot: DashboardSnapshot) {
  const regimes = [
    ["미국 국면", snapshot.dual_regime.us, snapshot.dual_regime.transitions.us],
    ["한국 국면", snapshot.dual_regime.kr, snapshot.dual_regime.transitions.kr],
  ] as const;
  const regimeHtml = regimes
    .map(
      ([label, regime, transition]) =>
        `<article class="card"><h2>${label}</h2><p>${escapeHtml(regime.regime)}</p><span class="badge">${transition.changed ? "전환" : "유지"}</span><span class="badge">${transition.streak ?? 0}일 연속</span><span class="badge">${transition.whipsaw ? "whipsaw" : "안정"}</span>${regime.axis_reads
          .map((axis) => `<p><strong>${escapeHtml(axis.label)}</strong> ${axis.pctile == null ? "-" : Math.round(axis.pctile * 100) + "%"} · ${escapeHtml(axis.read)}</p>`)
          .join("")}</article>`,
    )
    .join("");
  const kpis = snapshot.market_indicators
    .slice(0, 4)
    .map((item) => `<article class="card"><p class="muted">${escapeHtml(item.group || item.symbol)}</p><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.price ?? "-")}</p><p>${escapeHtml(item.day_change_pct == null ? "-" : item.day_change_pct.toFixed(2) + "%")}</p></article>`)
    .join("");
  return `<section class="grid"><div class="grid two">${regimeHtml}</div><div class="grid kpis">${kpis}</div></section>`;
}

function progressPanel(snapshot: DashboardSnapshot) {
  const rows = snapshot.candidates
    .slice()
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
    .slice(0, 50)
    .map((candidate) => `<tr data-toggle="#detail-${escapeHtml(candidate.ticker)}"><td>${escapeHtml(candidate.ticker)}<br><span class="muted">${escapeHtml(candidate.company)}</span></td><td>${escapeHtml(candidate.score ?? "-")}</td><td>${escapeHtml(candidate.pe ?? "-")}</td><td>${escapeHtml(candidate.strongest_lens || candidate.linked_lenses[0]?.name || "-")}</td><td>${candidate.status.toUpperCase().includes("BLOCK") ? "BLOCKED" : "BLOCKED 확인"}</td></tr><tr id="detail-${escapeHtml(candidate.ticker)}" class="detail-row" hidden><td colspan="5">${escapeHtml(candidate.thesis)}</td></tr>`)
    .join("");
  return `<table><thead><tr><th>종목</th><th>매력도</th><th>PER</th><th>렌즈</th><th>상태</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function attentionPanel(snapshot: DashboardSnapshot) {
  const rows = snapshot.candidates
    .map((candidate) => ({ candidate, categories: getAttentionCategories(candidate) }))
    .filter((row) => row.categories.length > 0)
    .map(({ candidate, categories }) => `<tr data-tags="${categories.map(escapeHtml).join(" ")}"><td>${escapeHtml(candidate.ticker)}</td><td>${escapeHtml(candidate.company)}</td><td>${categories.map((category) => `<span class="badge">${escapeHtml(category)}</span>`).join("")}</td><td>${escapeHtml(candidate.risk_flags.join(" · ") || candidate.bear_case[0] || "")}</td></tr>`)
    .join("");
  return `<div class="filters" data-filter-control="#attention-export"><button data-filter="all" aria-pressed="true">전체</button>${attentionCategories
    .map((category) => `<button data-filter="${category}" aria-pressed="false">${category}</button>`)
    .join("")}</div><table id="attention-export"><tbody>${rows}</tbody></table>`;
}

function evidencePanel(snapshot: DashboardSnapshot) {
  const candidate = snapshot.candidates[0];
  if (!candidate) return "<p>표시할 후보가 없습니다.</p>";
  return `<article class="card"><h2>${escapeHtml(candidate.ticker)} 근거</h2><p>${escapeHtml(candidate.thesis)}</p><p><strong>독립성</strong> ${escapeHtml(candidate.independence_status || "확인된 제한 없음")}</p><p><strong>catalyst</strong> ${escapeHtml(candidate.catalysts.map((item) => item.label).join(" · ") || "없음")}</p><p><strong>밸류에이션 기대치</strong> ${escapeHtml(candidate.expectation_verdict || candidate.pe || "-")}</p><p><strong>gaps</strong> ${escapeHtml(candidate.gaps.join(" · ") || "미해결 갭 없음")}</p><details><summary>기술 세부정보</summary><pre>${escapeHtml(JSON.stringify(candidate, null, 2))}</pre></details></article>`;
}

function nextPanel(snapshot: DashboardSnapshot) {
  const candidateItems = snapshot.candidates
    .filter((candidate) => candidate.next_action)
    .slice(0, 30)
    .map((candidate) => `<li><strong>${escapeHtml(candidate.ticker)}</strong> ${escapeHtml(candidate.next_action)}</li>`)
    .join("");
  return `<section class="grid two"><article class="card"><h2>후보별 다음 행동</h2><ul>${candidateItems}</ul></article><article class="card"><h2>국면 다음 행동</h2><p>미국: ${escapeHtml(snapshot.dual_regime.us.next_action)}</p><p>한국: ${escapeHtml(snapshot.dual_regime.kr.next_action)}</p></article></section>`;
}

function panelFor(tab: string, snapshot: DashboardSnapshot) {
  if (tab === "진행현황") return progressPanel(snapshot);
  if (tab === "주의 필요") return attentionPanel(snapshot);
  if (tab === "근거") return evidencePanel(snapshot);
  if (tab === "다음 행동") return nextPanel(snapshot);
  return summaryPanel(snapshot);
}

export function exportSnapshot(opts: ExportSnapshotOptions): string {
  const tabs = opts.scope === "current_tab" ? [opts.currentTab] : [...commonCockpitTabs];
  const nav = tabs
    .map((tab, index) => `<button data-target="${escapeHtml(tab)}" aria-selected="${index === 0 ? "true" : "false"}">${escapeHtml(tab)}</button>`)
    .join("");
  const panels = tabs
    .map((tab, index) => `<section data-panel="${escapeHtml(tab)}"${index === 0 ? "" : " hidden"}>${panelFor(tab, opts.snapshot)}</section>`)
    .join("");

  return `<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(opts.source.dashboardName)}</title>${css()}</head>
<body><main><section class="shell" data-cockpit-profile="executive_cockpit">${header(opts.snapshot)}<nav class="tabs" data-switcher="main" aria-label="상황판 탭">${nav}</nav><div data-switcher-panels="main">${panels}</div><footer>source: ${escapeHtml(opts.source.dashboardName)} · ISO 8601 KST timestamp: ${kstIso(opts.generatedAt)} · userOrService: ${escapeHtml(opts.source.userOrService)} · data window: ${escapeHtml(opts.dataWindow.from)}..${escapeHtml(opts.dataWindow.to)} · data hash: ${hashSnapshot(opts.snapshot)}</footer></section></main>${runtimeScript()}</body>
</html>`;
}

export function extractInlineScripts(html: string) {
  return [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
}

export function validateSwitcherContracts(html: string) {
  const withoutScripts = html.replace(/<script>[\s\S]*?<\/script>/g, "");
  const targets = [...withoutScripts.matchAll(/data-target="([^"]+)"/g)].map((match) => match[1]).sort();
  const panels = [...withoutScripts.matchAll(/data-panel="([^"]+)"/g)].map((match) => match[1]).sort();
  return JSON.stringify(targets) === JSON.stringify(panels) ? [] : [`targets=${targets.join(",")} panels=${panels.join(",")}`];
}
