# CONTEXT.md — 04_stock_intel

## Project Profile
- 개요: Telegram 종목 리서치와 TradingView private indicator 시그널 알림을 결합한 개인용 주식 인텔리전스 봇입니다.
- 목적: 관심종목의 매수 관점 시그널이 뜰 때 독립성 차단 여부를 먼저 확인하고, 필요한 시장/종목 정보를 Telegram으로 빠르게 전달합니다.

## Current Scope

04_stock_intel이 사용자-facing 주 프로젝트입니다. 02_audit_safe_signals는 webhook/filter/dedup 아이디어의 donor이고, 03_tradingview_companion은 TradingView Desktop/MCP 기반 pull chart companion으로 분리합니다.

## Core Terms

| 용어 | 정의 |
|---|---|
| 시그널 알림 | TradingView private indicator v6.2 webhook을 받아 Telegram으로 보내는 이벤트 |
| 독립성 판정 | 감사인 정보와 차단 감사인 설정을 비교해 `BLOCKED`, `CLEAR`, `MANUAL_VERIFY`, `UNKNOWN_MARKET` 중 하나로 분류하는 결정 |
| 차단 감사인 | 사용자가 직무상 매입 검토를 피해야 하는 감사인. 기본 canonical 값은 `삼정회계법인` |
| 수동 확인 필요 | 감사인 자동조회가 없거나 실패하여 원천 공시 확인 전 매입 검토를 보류해야 하는 상태 |
| 시장 지원 상태 | 한국은 `kreports` 자동 확인, 미국/일본은 v1에서 수동 확인 필요, 그 외는 미분류 |
| TradingView CLI watchlist helper | `/Users/kjun/code/tradingview-mcp`로 TradingView Desktop watchlist를 만들거나 조회하는 운영 보조 경로 |

## Macro / Dashboard Terms

> 2026-06-03 lens dashboard 고도화 grill에서 확정. 빌드 순서는 매크로(국면) 먼저.

| 용어 | 정의 |
|---|---|
| 국면 (Market Regime) | 한 시장의 그날 상태를 4개 중 하나로 부르는 **canonical 판정**: `risk-on`, `conditional`, `fragile rally`, `risk-off`. **시장마다 하나의 canonical 값**을 유지한다(한 시장에 판정 결과 둘 금지 — 구 `_derive_regime.verdict`와 `current_state` 이원화 폐기). |
| 미국 국면 / 한국 국면 (Dual Regime) | 한·미 병행: **미국 국면**과 **한국 국면**을 각각 독립 4-state로 둔다. 한국 주식은 미국이 risk-on이어도 원화·외국인 매도로 따로 망가질 수 있으므로 글로벌 단일 국면으로 국장 후보를 판정하지 않는다. 두 국면은 각자 이력·전이·whipsaw 라벨을 갖는다. **한국 국면 입력 축(rev3, yfinance ETF — KRX 피벗):** 데이터 spine = yfinance ETF(로그인 불필요). sentiment(KODEX200 `069500.KS` 실현변동성) · breadth(`relative_strength(KODEX코스닥150 229200.KS, KODEX200 069500.KS)`, 코스닥 우위=risk-on=양호; leg 순서 주의) · fx(USDKRW=X) · flow(EWY 프록시). yfinance 지수(^KS11/^KS200)는 최신 종가 NaN이라 ETF로 대체. **KRX OPEN API/KRX_API_KEY 비채택**(401·승인 부담). 진짜 외국인 순매수(네이버)·전종목 breadth·KRX 권위값은 v1.1. (이하 rev2 기술은 KRX 경로 히스토리로 보존.)
<!-- rev2(폐기) -->
**한국 국면 입력 축(rev2, KRX OPEN API):** sentiment(KOSPI 실현변동성, VKOSPI 가용 시 우선) · fx(원화 USDKRW, yfinance) · breadth(KOSPI vs KOSPI200 상대강도 경량 프록시) · flow(외국인 — KRX OPEN API 미제공이라 **EWY 프록시**, 실제 순매수 v1.1). 데이터 spine = **KRX OPEN API**(`data-dbg.krx.co.kr`, `AUTH_KEY`). pykrx 웹로그인 폐기. **새 의존 `KRX_API_KEY`**(민감, 커밋 금지). percentile 1년 baseline은 캐시(`state/dashboard/cache/krx_series/`) 또는 yfinance `^KS11` 대체. KRX 실패 시 축 단위 graceful degradation. 상세 [ADR-0001](docs/adr/0001-macro-regime-thresholds.md). |
| 국면 전이 (Regime Transition) | 직전 영업일 국면 → 오늘 국면이 바뀐 사건. 미국·한국 국면 각각에서 따로 추적한다. |
| 상대 위치 판정 (Percentile Read) | 각 매크로 축의 state를 절대 상수가 아니라 **자기 1년 분포 대비 percentile**로 판정하는 1급 기준. 시대 편향 제거가 목적. lookback 기본 1년. |
| 절대 가드레일 (Absolute Guardrail) | percentile과 무관하게 구조적 위험을 강제 판정하는 보조 절대 임계값. **확정값(2026-06-04): VIX ≥ 20, USDKRW ≥ 1450**, 미 10년물 ≥ 5.0%, Brent ≥ 100 / WTI ≥ 95 (뒤 둘은 plan 재확인). percentile이 "비정상이 새 기준"이 되는 맹점을 막는 안전장치. 상세는 [ADR-0001](docs/adr/0001-macro-regime-thresholds.md). |
| 국면 이력 (Regime History) | 전이 감지를 위해 그날 내린 국면 판정을 박제하는 append-only 로그. 위치 `state/dashboard/regime_history.jsonl`, **영업일당 1레코드(재실행 시 덮어쓰기)**. **한 줄에 듀얼 국면 둘 다**: `{as_of, us:{regime, dimensions:{축:{state,pctile}}, raw}, kr:{...}, generated_at}`. percentile baseline은 저장하지 않고 매 실행 라이브 계산. signals 도메인의 `state.db`와 분리 유지. |
| 전이 노출 3층위 | (1) **국면 레벨 전이** = 헤더 배지("어제 X → 오늘 Y"), (2) **축 레벨 전이** = 6축 그리드 내 축별 state 변화 표시, (3) **streak** = "N영업일째 {국면}". 셋 다 노출. |
| 투명 전이 / whipsaw 라벨 | 전이를 확인 게이트로 평활화하지 않고 원시 그대로 노출한다(객관성 보존). 단 전이 시 직전 streak이 ≤1이면 `잠정 전이 — 변동 큼` whipsaw 라벨을 붙여 불안정성 자체를 신호로 표시한다. |
| 컨센서스 리비전 (Consensus Revision) | 셀사이드 추정치 상·하향(up/down/flat/pending). **진짜 데이터.** 소스는 yfinance `info`(forwardPE·targetMeanPrice·numberOfAnalystOpinions 등) 실연결. 미국주 우선, 한국주는 커버리지 희박 시 `데이터 부족`. |
| 이익상향 프록시 (Revision Proxy) | 컨센서스 부재 시 fallback. 수급(net_flow)+추세(ma_trend) 대용. 화면에 반드시 `프록시 — 컨센서스 아님` 표기. **컨센서스 리비전과 하나의 신호로 수렴**(우선순위: 컨센서스 > 프록시)하되 출처를 명시한다. |
| 가치평가 점수 (Trailing Valuation) | 기존 후보 5지표 중 하나. trailing PER vs 동종군 중앙값. 답하는 질문: "**지금 동종군 대비 싼가**". |
| 밸류에이션 기대치 (Valuation Expectations) | forward P/E를 가이던스·컨센서스·현금전환과 대조하는 **별도 렌즈**. 답하는 질문: "**주가가 가이던스·컨센서스가 받쳐주는 것보다 큰 성장을 이미 반영했나**". trailing 가치평가와 수렴하지 않고 별개 섹션(`밸류에이션 기대치 점검`)으로 둔다. v1에서 **매력도 점수(숫자)를 바꾸지 않고** 후보 카드에는 판정을 배지로 교차표기. |
| 기대치 판정 (Expectation Verdict) | 밸류에이션 기대치 섹션의 6-라벨: `정당화 가능`·`기대치 부담`·`과열`·`위험`·`저평가 후보`·`데이터 부족`. multiple-to-growth burden + guidance delta + FCF 전환의 결정적 규칙으로 산출. |
| 라벨 네임스페이스 분리 | 한 후보 카드에 4개 독립 라벨 체계가 공존한다 — **국면**(4: risk-on/conditional/fragile rally/risk-off, 시장 단위), **후보 상태**(CandidateStatus 6: Watch/Research/Setup/Avoid/Blocked/Dropped), **기대치 판정**(6), **독립성**(4: BLOCKED/CLEAR/MANUAL_VERIFY/UNKNOWN_MARKET). 서로 섞지 않는다. |
| catalyst (Catalyst) | 종목에 묶인 시간축 이벤트. **v1 범위: US=다가오는 실적발표일(yfinance), KR=최근 공급계약(DART 단일판매·공급계약체결 공시검색 list.json)**. KR 다가오는 실적발표일은 무료 forward 소스 부재로 **v1.1**(네이버 종목일정 등). 후보 카드에 `다가오는 catalyst: 실적 D-12`, `최근 catalyst: 공급계약 5/28` 형태로 표기. 락업·지수편입·배당락·DART pagination은 defer. |
| 후보 universe (Candidate Universe) | 한·미 병행 합집합. **한국=`kr_watch_candidates` 동적 스크린 결과**, **미국=Market Insights 큐레이션 카드**. KR 카드는 자동 read 기반(narrative는 선택) → US 카드(narrative 풍부)와 비대칭이며 그 사실을 화면에 표기한다. |
| 봇 시그니처 주입 (Signature Injection) | 이 봇만의 차별점인 **감사인 독립성·수급·공매도**를 후보 `Candidate.risk_flags`로 주입. 독립성 `BLOCKED`(삼정 보유 등) 후보는 **universe에서 침묵 제외하지 않고** 🚫 차단 배지 + 랭킹 강등으로 보이게 유지한다(`이건 후보인데 차단`을 사용자가 보게). |
| 통합 후보 객체 (Unified Candidate) | 봇·상황판 통합의 합류점. `dashboard/models.py`의 `Candidate` 하나에 정량 5지표·가격/PER·봇 시그니처·catalyst·밸류에이션 기대치·narrative가 모두 모인다. 상황판은 이를 배치 카드로, 봇 `/signal <ticker>`는 동일 객체를 on-demand로 렌더 — 종목 정보를 두 번 만들지 않는다. |
| 정책 렌즈 (Policy Lens) | **새 `LensKind.POLICY`**. 정부·규제 정책이 드라이버인 수혜주를 추적하는 카테고리. 기존 렌즈(THESIS·SECTOR·MACRO·FACTOR)와 같은 층위. 저PBR을 순수 FACTOR로 보지 않는 이유: `특징`(철강 업황·NAV 할인·자산 보유)이 보여주듯 정책 thesis + 큐레이션 수혜 종목이지 PBR 스크린이 아니다. **일반 프레임**으로 만들어 향후 IRA·CHIPS·K-방산 등도 같은 칸에 슬롯인. |
| 상황판 Lane B (React Cockpit) | 상황판 UI는 design-kit **Lane B**(dashboard-kit.md: 매일 사용+차트 → Lane B). 스택 = Vite+React19+TS+Tailwind v4 + `design-kit/typescript/src` pasTokens/cockpitProfiles + TanStack Table/Router/Query + Recharts + Lucide. 위치 `web/`. Python 스냅샷 JSON(`state/dashboard/cache/snapshot-latest.json`)을 데이터 계약으로 소비. design-kit **5공통탭 재해석**(요약=듀얼국면+KPI / 진행현황=후보 universe / 주의 필요=차단·과열·위험 / 근거=지표·독립성·catalyst·밸류에이션 / 다음 행동). `dashboard-snapshot-export-kit`로 단일 HTML export. 기존 `render.py`(다크 bespoke)는 export-only 또는 폐기 대상(Lane B로 대체). 상세 plan: `docs/superpowers/plans/2026-06-06-lane-b-react-cockpit.md`. |
| 저PBR 밸류업 렌즈 | 정책 렌즈의 **첫 인스턴스**. thesis = "정부 밸류업 프로그램이 저PBR 자산주 재평가를 유도". 멤버십 = **큐레이션 수혜 종목 + PBR<임계 스크린 augment 하이브리드** (둘 다 동일 Candidate 파이프라인). 시드 종목(2026-06-04 사용자 제공): 현대제철·롯데케미칼·금호석유·OCI홀딩스·동국제강·세아베스틸지주·GS·SK·한화·태광산업 (각 PBR 구간 + 특징). 시드 리스트는 `sample_data`/seed에, 용어는 본 CONTEXT에. catalyst(자사주 소각·배당 정책 공시 DART)·trailing 가치평가(PBR)와 연결된다. |

## Alert Contract

TradingView webhook URL:

```text
/webhook/tradingview?secret=<WEBHOOK_SECRET>
```

v1은 human-in-the-loop 알림입니다. 자동매매 봇은 향후 연관 프로젝트로 다룰 수 있지만, broker adapter와 order execution은 별도 risk gate와 paper-trading 검증을 통과해야 합니다.
