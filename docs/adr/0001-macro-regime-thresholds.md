# 0001 — 매크로 국면 임계값: percentile 1급 + 절대 가드레일 하이브리드

- 상태: accepted
- 일자: 2026-06-03
- 맥락: lens dashboard 고도화 grill (축① 매크로 시간축/국면 전이)

## 결정

매크로 6축의 state 판정 기준을 다음 하이브리드로 한다.

1. **percentile을 1급 판정 기준으로 둔다.** 각 축 지표를 자기 1년(기본 lookback) 일별 분포 대비 상위/하위 percentile로 평가한다.
2. **절대 가드레일을 보조로 유지한다.** 구조적 위험 구간(예: VIX 30 위, 유가 급등 절대선)은 percentile과 무관하게 강제 state를 부여한다.
3. percentile 계산용 데이터는 `providers/macro.py`의 `_load_quotes`를 `period="1y"`로 확장해 조달한다 (yfinance 그대로, 추가 의존 없음).

## 대안

- **순수 절대치 유지 (기존 v1):** 구현 단순하나 시점 무관 고정 잣대 — "현재가 평소 대비 어디인지"를 못 보여줘 사용자의 객관성 요구와 반대.
- **순수 percentile:** 시대 편향은 제거하나 "지난 1년이 비정상이면 비정상이 새 기준"이 되는 맹점. 구조적 위험을 놓칠 수 있음.
- **Z-score (이동평균 대비 표준편차):** 분포가 정규에서 벗어난 지표(VIX 등 두꺼운 꼬리)에서 왜곡. percentile이 분포 가정에 더 강건.

## 근거

사용자가 매크로를 먼저 보려는 동기 자체가 "시장 현상황을 객관적으로 보기"였다. 절대 상수는 객관적으로 *보이지만* 임의값이라 시대 편향을 내장한다. percentile은 지표를 자기 역사 대비로 정규화해 그 편향을 제거한다. 다만 percentile 단독은 비정상 레짐을 정상화하는 맹점이 있어, 절대 가드레일을 병행해 구조적 위험만 강제로 잡는다.

## 확정 절대 가드레일 값 (2026-06-04)

percentile과 무관하게 강제 판정하는 구조적 위험선. 사용자(감사·재무 전문) 설정값:

- sentiment: **VIX ≥ 20** → 강제 경고선 (제안 30에서 하향). percentile은 이 위로 stressed escalate 가능.
- fx: **USDKRW ≥ 1450** → 한국 부담 강제 (제안 1500에서 하향). 현재 ~1529라 이미 가드레일 위.
- rates: 미 10년물 ≥ 5.0% → warning (plan에서 재확인)
- oil: Brent ≥ 100 / WTI ≥ 95 → stressed (plan에서 재확인)
- breadth·commodities: 절대 가드레일 없음, percentile만.

## Percentile 밴드 (2026-06-04 ratified)

축 state를 percentile로 매핑하는 컷오프(Plan 1에서 확정, 여기 ratify):

- RISK_HIGH(값↑=위험): pctile ≥ 0.95 → stressed, ≥ 0.85 → warning, 그 외 supportive.
- RISK_LOW(값↓=위험): pctile ≤ 0.05 → stressed, ≤ 0.15 → warning, 그 외 supportive.
- percentile state와 절대 가드레일 state 중 **더 심한 것** 채택.
- series < 30(`MIN_SERIES`)이면 percentile 산출 불가 → 가드레일만 적용, 가드레일도 미발동이면 `unavailable`(supportive로 단정 안 함).
- **다중 심볼 축의 대표 percentile:** 한 축에 심볼이 여럿이면(US breadth=RSP/S5FI/QQQ/IWM 등) 축 state는 worst-state 심볼이 정하고, `axis_reads.pctile`도 **그 worst-state 심볼의 percentile**로 잡는다(동률이면 먼저 본 심볼). pctile↔state가 근거-결론으로 일치해야 함(code review 2026-06-04 should-fix).

## KR 데이터 경로 (2026-06-04)

한국 국면 입력은 **KRX API 직연동**으로 간다(사용자 결정). pykrx 지수/펀더멘탈/외국인 순매수 엔드포인트는 **KRX_ID/KRX_PW 인증**이 있어야 동작함을 라이브로 확인. 이로써:

- 새 의존: `.env`에 `KRX_ID`/`KRX_PW` (민감정보 — 절대 커밋 금지, CLAUDE.md §7).
- KR 국면 축: 외국인 순매수(KRX real) · 원화(USDKRW, yfinance) · VKOSPI(KRX 인증 후 ticker 가용성 재확인 필요 — 불가 시 KOSPI 실현변동성 대체) · KOSPI breadth(전종목 %>MA, KRX).
- 운영 제약: KRX 세션은 봇이 네이버 fallback을 쓰는 바로 그 이유(불안정)다. KR 매크로 축은 KRX 실패 시 축 단위 graceful degradation(`확인 필요`) 필수.

## 영향

- 임계값 체계가 바뀌면 국면 판정과 전이 신호 해석 전체가 바뀌므로 되돌리기 비용이 크다 — 그래서 ADR로 못박는다.
- percentile baseline(1년치)을 어디에 저장/캐시할지는 국면 이력 저장소(별도 결정)와 함께 다룬다.
