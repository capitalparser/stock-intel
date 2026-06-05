# Lane B React Cockpit — design-kit 정합 상황판 (Plan 8 / lens-dashboard 고도화)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans. 체크박스로 추적. **React 빌드는 Codex primary.**
>
> **모든 명령(Python):** `cd /Users/kjun/vault/01_Projects/04_stock_intel && uv run ...`. **React:** `cd 04_stock_intel/web && npm ...`.

**Goal:** 개인 투자 상황판을 어제 고도화한 design-kit **Lane B(React)** 양식으로 재구축한다 — Vite+React19+TS+Tailwind v4 + design-kit pasTokens/cockpit 프로필을 사용해, Python 스냅샷 JSON을 소비하는 매일 인터랙티브 대시보드 + 단일 HTML **Snapshot Export**. 현재 bespoke `render.py`(다크, design-kit 미준수)를 대체.

**Architecture:** Python 파이프라인(Plan 1~7)은 **데이터 계약**으로 유지 — `scripts/build_dashboard_snapshot.py`가 `state/dashboard/cache/snapshot-latest.json`을 계속 생성. 새 `web/` React 앱이 그 JSON을 로드해 design-kit cockpit shell(5공통탭 재해석) + pasTokens 라이트 테마로 렌더하고, Recharts 스파크라인·TanStack Table 후보 테이블을 그린다. Snapshot Export(`dashboard-snapshot-export-kit`)로 단일 HTML 산출(README/전달용).

**Tech Stack(design-kit web-app-kit Dashboard Stack 고정):** Vite + React 19 + TypeScript, Tailwind CSS v4, `design-kit/typescript/src/tokens.ts`(pasTokens)→tailwind theme, TanStack Table v8 / Router / Query, Recharts, Lucide React, zod(스냅샷 스키마 검증). shadcn/ui 선택.

**근거:** [CONTEXT.md](../../../CONTEXT.md) `상황판 Lane B (React Cockpit)`, design-kit `dashboard-kit.md`(Lane 선택)·`web-app-kit.md`(Dashboard Stack)·`dashboard-cockpit-kit.md`(5공통탭/프로필)·`dashboard-snapshot-export-kit.md`·`interactive-patterns-kit.md`·`typescript/src/{tokens,cockpitProfiles,visualModes}.ts`.

---

## Scope

### 포함
- `web/` 신규 React 앱(Vite+React19+TS+Tailwind v4). `web/package.json`, `vite.config.ts`, `tailwind.config.ts`(pasTokens 주입).
- 스냅샷 데이터 계약: zod 스키마 + 로더(빌드 시 `state/dashboard/cache/snapshot-latest.json`을 `web/public/`로 복사하거나 dev 프록시).
- cockpit shell: 5공통탭(요약/진행현황/주의 필요/근거/다음 행동) 재해석 + `data-cockpit-profile` + 로컬 라벨 `개인 투자 상황판 Cockpit`.
- 탭 컴포넌트(아래 매핑) + Recharts 스파크라인 + TanStack Table 후보/근거 테이블 + badge(독립성 🚫/🟡, 기대치 verdict, catalyst).
- **Snapshot Export** 기능: 현재 뷰/전체 → 단일 self-contained HTML(interactive-patterns 마이크로런타임, footer: 소스·ISO8601 KST 타임스탬프·데이터 윈도우).
- 테스트(Vitest + React Testing Library): 스키마 파싱, 탭 렌더, export 산출.

### 비범위 (v1.1)
- `render.py`(구 다크 렌더) 즉시 삭제 — Lane B 검증 후 별도 정리(이번엔 병행 유지, 신규 진입점은 React).
- design-kit `cockpitProfiles.ts`에 `investment_cockpit` 신설(사용자가 "5공통탭 재해석" 선택 — 신규 프로필 enum 추가 안 함).
- 실시간 backend fetch(스냅샷은 frozen view, export 시 re-fetch 금지 — 정석).
- Telegram 전달.

---

## 데이터 계약 (스냅샷 JSON, 확정)

`state/dashboard/cache/snapshot-latest.json`:
```
{ as_of, generated_at,
  macro: { dual_regime: { as_of, us:{regime,why_it_matters,next_action,axis_reads[{dimension,label,state,pctile,read,symbols,source_kind?}],data_gaps}, kr:{...},
                          transitions:{us:{changed,from,to,streak,whipsaw,axis_changes},kr:{...}} },
           market_indicators[{symbol,name,group,price,day_change_pct,read,series?}], errors[] },
  stocks: { "<ticker>": { source, price, day_change_pct, pe, pbr, peer_pe, peer_group, short_ratio,
                          net_flow_signal, independence_status, auditor, independence_reason,
                          catalysts[{type,direction,date,days,label,detail}], metrics{valuation,quality,growth,revision,momentum},
                          expectation_verdict?, data_quality{missing,proxy,errors,as_of} } },
  valuation_expectations?: [{ticker,forward_pe,rev_growth_pct,eps_growth_pct,fcf_margin_pct,verdict,read,data_gaps}] }
```
주: candidate 카드 narrative(thesis/lens/evidence)는 현재 Python `live.py`가 payload에 합쳐 렌더했음. **Lane B는 스냅샷 JSON만으로 충분치 않다** → 스냅샷에 narrative/lens/evidence를 포함하도록 `build_dashboard_snapshot`을 확장하거나(권장), React가 `market_insights` 산출 payload(JSON)를 별도 소비. **Task 1에서 데이터 계약 확정**(스냅샷에 candidate narrative+lens 포함 export 추가).

---

## 5공통탭 재해석 (stock dashboard)

| 탭 | 내용 |
|---|---|
| **요약** | 듀얼 국면(미국/한국 4-state, 전이 배지·streak·whipsaw, 축별 percentile) + KPI strip(시장 온도판 주요 지표) + verdict-first 헤더(현재/왜/다음 행동) |
| **진행현황** | 후보 universe 테이블(TanStack Table): 종목·매력도·가격·PER vs 동종군·연결 렌즈·스파크라인. 정렬/필터(시장·렌즈·상태) |
| **주의 필요** | 독립성 🚫 차단 + 밸류에이션 과열/위험 + 수급 순매도/공매도 과다 + 데이터 부족 후보만 |
| **근거** | 선택 종목 inspector: 지표 5축·독립성 사유·catalyst·밸류에이션 기대치 read·data gaps(기술 세부정보 접이식) |
| **다음 행동** | 후보별 next_action + 국면 next_action 집계 |

---

## File Structure (web/)

```
web/
├── package.json, vite.config.ts, tsconfig.json, tailwind.config.ts(pasTokens), index.html
├── src/
│   ├── main.tsx, App.tsx (cockpit shell + 탭 라우팅)
│   ├── data/ snapshot.ts(zod 스키마·로더), types.ts
│   ├── cockpit/ Shell.tsx, Tabs.tsx(commonCockpitTabs), Header.tsx(verdict-first), KpiStrip.tsx
│   ├── tabs/ Summary.tsx, Progress.tsx, Attention.tsx, Evidence.tsx, NextActions.tsx
│   ├── components/ RegimePanel.tsx, CandidateTable.tsx, Sparkline.tsx, Badges.tsx(독립성/verdict/catalyst), Inspector.tsx
│   ├── export/ snapshotExport.ts(단일 HTML 직렬화, interactive-patterns)
│   └── lib/ tokens(=design-kit pasTokens 재export), format.ts
├── public/ snapshot-latest.json(빌드 시 복사) 
└── tests/ (Vitest)
```

---

## Tasks (개략 — Codex가 TDD/세부 구현; 각 Task 후 `npm test` + `npm run build` 그린)

- [ ] **Task 0 — 데이터 계약 확장(Python):** `build_dashboard_snapshot`(또는 새 `export_dashboard_json`)이 candidate narrative(thesis/lens_ids/evidence/gaps/next_action/score/status/risk_flags)+lenses+valuation_expectations까지 한 JSON으로 export. 기존 `live.py`/`screeners.build_dashboard` 결과를 직렬화. pytest로 JSON 스키마 검증. (React가 소비할 단일 계약 확정.)
- [ ] **Task 1 — Vite 스캐폴드 + Tailwind v4 + pasTokens:** `web/` 생성, design-kit `tokens.ts` import해 `tailwind.config.ts theme.extend`에 주입(토큰 값 재선언 금지). 빈 App 렌더 + `npm run build` 성공.
- [ ] **Task 2 — 스냅샷 로더 + zod 스키마:** `data/snapshot.ts` zod 스키마(위 계약), 로더(public JSON fetch), 파싱 실패 시 Error 패널. Vitest 스키마 테스트(fixture = 실제 snapshot 축약).
- [ ] **Task 3 — cockpit shell + 5탭 라우팅:** `cockpit/Shell.tsx`+`Tabs.tsx`(commonCockpitTabs from cockpitProfiles), `data-cockpit-profile`, 로컬 라벨, verdict-first Header. TanStack Router. 탭 전환 테스트.
- [ ] **Task 4 — 요약 탭:** RegimePanel(듀얼 국면, 전이/streak/whipsaw 배지, 축 percentile) + KpiStrip. 렌더 테스트(미국/한국 국면·전이 문구).
- [ ] **Task 5 — 진행현황 탭:** CandidateTable(TanStack Table, 정렬/필터) + Sparkline(Recharts, series). 매력도·PER·렌즈 컬럼. BLOCKED 강등 정렬 유지.
- [ ] **Task 6 — 주의 필요 탭:** 차단/과열/위험/공매도/데이터부족 필터 뷰 + badge.
- [ ] **Task 7 — 근거 탭 + Inspector:** 선택 종목 5축·독립성·catalyst·밸류에이션·gaps(기술 세부정보 접이식 details).
- [ ] **Task 8 — 다음 행동 탭:** 후보 next_action + 국면 next_action.
- [ ] **Task 9 — Snapshot Export:** `export/snapshotExport.ts` 현재 뷰/전체 → 단일 HTML(no CDN, interactive-patterns 마이크로런타임, footer 소스·ISO8601 KST·데이터 윈도우). 재현성(정렬·whitespace 정규화). 산출 파일 테스트.
- [ ] **Task 10 — 통합 스모크 + README 갱신:** 실제 snapshot으로 `npm run dev` 육안 확인(desktop/mobile, first-viewport verdict/KPI), export HTML 스크린샷으로 README 교체. `npm run build`+`npm test` 그린.

---

## design-kit 준수 체크 (harness-ui-gate / critique-checklist)

- Pretendard, 본문 letter-spacing -0.02em, line-height 1.6 (pasTokens).
- verdict-first 헤더 + KPI strip + 5공통탭 + evidence 테이블 + gap 분류(Required/Recommended).
- 한글 우선 UI, 기계용어(JSON/raw field) 기본 화면 비노출 → `기술 세부정보` 보조 영역.
- self-contained export(no CDN), desktop/mobile overlap·first-viewport 확인.
- 색상은 토큰 기반(CSS custom properties); 다크↔라이트는 토큰 전환.

## Cross-model review 예정
(b) Codex plan 리뷰(스택·데이터 계약·Task 0 필요성·export 재현성) → 머지 → Codex 구현(React, multi-file) → (a) Opus code 리뷰 + design-kit critique-checklist.

## Cross-model review 반영 v2 (2026-06-06, Codex leg) — **본 섹션이 위 태스크 본문에 우선**

Codex 리뷰: REJECT(blocker 2 + should-fix 8). React 착수 전 plan 보강. 반영:

- **H-01 (B1, typo):** 데이터 계약 확정은 **Task 0**(위 "데이터 계약" 주석의 "Task 1"은 오기 → Task 0).
- **H-02 (B2, sparkline series):** 스냅샷 stock에 가격 series가 없음(macro indicator에만 존재). **Task 0에 per-stock 가격 series export 추가**(KR/US provider가 metrics 계산 시 이미 closes를 받음 → 최근 ~60개 close를 stock에 carry). 불가/지연 시 **Task 5 sparkline은 series 있으면 그리고 없으면 생략(v1.1)** — degrade-friendly로 명시.
- **H-03 (S1·S2, 데이터 계약 소스):** Task 0 직렬화 대상 = `market_insights.build_market_insights_payload()` + `live.overlay_snapshot()` 결과(candidate narrative/lens_ids/evidence/thesis/score/status/risk_flags + lenses) **+ valuation_expectations**. **build_dashboard_snapshot이 valuation을 실제 호출·carry하는지 점검**(현재 top-level에 0개 — 미배선 가능성). Task 0 acceptance: 재생성 후 JSON에 top-level `valuation_expectations` + stock별 narrative/lens + (가능 시)series 존재 assert.
- **H-04 (S3, Radix):** Tech Stack·Task 3에 **Radix UI**(shadcn/ui 기반) 추가(web-app-kit Required).
- **H-05 (S4·S5, cockpit profile):** `data-cockpit-profile="executive_cockpit"`(총괄현황 = 시장/포트폴리오 overview에 가장 근접한 기존 enum)으로 고정 + display label은 로컬 "개인 투자 상황판". 신규 enum 미추가, **로컬 라벨은 기존 CockpitProfile 값을 wrap**(TS union 충돌 회피).
- **H-06 (S6·S7, export 엄밀성):** Task 9 footer에 `소스 대시보드명 · ISO8601 KST 타임스탬프 · userOrService · 데이터 윈도우 · data hash`. acceptance에 export-kit 체크: `node --check`(인라인 JS), `data-target↔data-panel` 일치, `file://` 오프라인 동작, HTTP/CDN asset 부재 grep, diff 재현성(타임스탬프 제외), 파일 크기, A4 print preview.
- **H-07 (S8, 검증 분리):** 최종 검증 = `uv run pytest tests/test_snapshot.py`(Python 데이터계약) + `cd web && npm test && npm run build`(React). bot.py/insight_lookup 미접촉 acceptance에 명시.
- **H-08 (nit):** "현재 뷰" = 현재 탭 + 현재 필터 상태.

## 다음
v1.1: render.py(구 다크) 정리/삭제, per-stock series 미구현 시 sparkline, investment_cockpit 프로필 정식화 검토, Telegram 전달, 실시간 backend.
