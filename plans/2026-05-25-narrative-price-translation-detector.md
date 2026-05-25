# Narrative-to-Price Translation Detector 구현 계획서

작성일: 2026-05-25  
대상 프로젝트 후보: `01_Projects/04_stock_intel`  
상태: design / implementation not started

## 1. 결론

**권장안: `04_stock_intel`에 바로 흡수하지 말고, `04`의 Telegram/alert surface를 재사용하는 부가 모듈로 시작한다.**

이 기능은 단일 종목 리서치 봇이 아니라 테마 바스켓의 가격 번역을 감지하는 시스템이다. 따라서 `04_stock_intel`의 기존 책임인 “종목명 -> 단일 종목 리서치 메시지”와는 다르다.

다만 개인용 Telegram 알림, 종목 데이터 조회, 기술적 지표 계산, graceful degradation 패턴은 `04_stock_intel`과 잘 맞는다. 그래서 v0는 `04` 안에 `rotation/` 패키지와 `/rotation` 명령을 추가하는 방식이 가장 빠르다. 기능이 커지면 `03_tradingview_companion` 또는 별도 `19_rotation_detector`로 분리한다.

## 2. 제품 정의

### 목표

사용자가 이미 보유한 내러티브가 시장에서 가격·거래량·상대강도·바스켓 확산으로 번역되기 시작하는 순간을 조기 감지한다.

### 비목표

- 자동매매 아님.
- 매수/매도 추천 아님.
- 뉴스 기반 종목 추천기 아님.
- “오르기 전 완전 선취”가 목표가 아님.

### 정확한 제품 문장

`Narrative-to-Price Translation Detector`는 vault의 Market Insights 테마 바스켓을 가격 데이터와 연결해, `WATCH -> SPARK -> ROTATION -> CONFIRMED` 상태 변화를 Telegram으로 알려주는 개인용 조기 감지기다.

## 3. 왜 지금 필요한가

Mooni 계정 사례에서 보듯, 내러티브 자체보다 중요한 것은 시장이 그 내러티브를 가격에 반영하기 시작하는 타이밍이다.

사용자는 이미 내러티브를 찾는 능력이 있고, vault에는 다음 자료가 축적되어 있다.

- Mooni / X 투자계정 source notes
- `02_Areas/Market_Insights/` 테마 카드
- sector/theme별 watchlist
- TradingView companion / Telegram bot 인프라

따라서 새 기능의 핵심은 “새 서사 발굴”이 아니라 “기존 서사의 가격화 감지”다.

## 4. 프로젝트 배치 옵션

| 옵션 | 설명 | 장점 | 단점 | 판단 |
|---|---|---|---|---|
| A. `04_stock_intel` 내부 기능 | `rotation/` 패키지와 Telegram 명령/알림 추가 | 가장 빠름, 기존 Telegram surface 재사용 | 기존 단일 종목 리서치 책임과 섞일 수 있음 | v0 권장 |
| B. `03_tradingview_companion` 기능 | TradingView 가격/차트 감지 중심으로 구현 | 가격 데이터와 가장 자연스러움 | Telegram 리서치 봇과 별도 운영 필요 | v1 후보 |
| C. Market Insights Harness 기능 | vault card와 바로 연결 | 내러티브 owner와 정합성 높음 | 실시간 알림/가격 수집에는 부적합 | 보조 레이어 |
| D. 신규 프로젝트 | 독립 detector로 설계 | 책임 명확, 확장 쉬움 | 초기 구현/운영 비용 큼 | v2 또는 제품화 때 |

**추천:** v0는 `04_stock_intel`에 부가 기능으로 시작하되, 코드 책임을 완전히 분리한다.

## 5. 핵심 개념

### Narrative Basket

테마 하나를 대표하는 종목 묶음이다.

예:

```yaml
id: power_semis_800v
label: "전력반도체 / 800V HVDC"
owner_card: "semiconductors"
benchmark: "SOXX"
symbols:
  - ticker: "ON"
    role: leader
    market: US
  - ticker: "NVTS"
    role: high_beta
    market: US
  - ticker: "WOLF"
    role: stressed_peer
    market: US
  - ticker: "2577.HK"
    role: china_gan
    market: HK
  - ticker: "VRT"
    role: infra_adjacent
    market: US
```

### Price Impulse

개별 종목의 가격·거래량 충격이다.

핵심 지표:

- 1D / 3D / 5D 수익률
- benchmark 대비 초과수익
- 거래량 z-score
- 20D / 52W 신고가 여부
- 종가가 VWAP 또는 전일 고점 위에 유지되는지

### Breadth / Diffusion

테마 바스켓 전체로 가격 반응이 퍼지는 정도다.

예:

- 10개 중 1개 급등: 단일 종목 이벤트
- 10개 중 3개 이상 benchmark 대비 초과수익: SPARK
- leader + high beta + equipment/material peer 동시 상승: ROTATION
- 미국/한국/홍콩 peer 동시 반응: 글로벌 테마화 가능성

### Narrative Confirmation

가격 반응 후 시장 언어가 붙는지 확인하는 레이어다.

소스:

- Market Insights card last_signal
- X 수동 capture / Mooni 계정
- yMB daily brief
- 공식 IR / earnings call / press release
- 증권사 리포트 제목 또는 주요 미디어 headline

## 6. Alert 상태 정의

| 상태 | 의미 | 조건 예시 | 알림 여부 |
|---|---|---|---|
| WATCH | 내러티브는 있으나 가격 반응 없음 | 카드 존재, 바스켓 정의 완료 | 리포트만 |
| SPARK | leader 1~2개 거래량 동반 상승 | leader 3D excess return > 5%, volume z > 2 | Telegram 낮은 강도 |
| ROTATION | 바스켓 확산 시작 | basket 30~40% 이상 excess return positive, 평균 volume z > 1.5 | Telegram 주요 알림 |
| CONFIRMED | 가격 확산 + 공식/기관 언어화 + 실적/수주 | ROTATION + confirmation source + revenue/order KPI | Telegram 주요 알림 + Market note |
| FADE | 초기 반응 실패 | SPARK 후 3~5일 내 breadth 미확산 또는 leader reversal | Telegram 요약 |

## 7. v0 범위

### 포함

- 수동 YAML 바스켓 8~12개
- EOD 또는 하루 2회 스코어링
- 가격/거래량 기반 상태 판정
- Telegram `/rotation` 명령
- `ROTATION` 이상 자동 알림
- JSONL event ledger 저장
- Markdown daily report 생성

### 제외

- 실시간 tick streaming
- 자동매매
- 옵션 flow
- X 자동 크롤링
- LLM 기반 매매 판단
- 복잡한 portfolio sizing

## 8. v0 바스켓 후보

| basket_id | 라벨 | 초기 종목 |
|---|---|---|
| `power_semis_800v` | 전력반도체 / 800V HVDC | ON, NVTS, WOLF, PI, POWI, STM, VRT, ETN |
| `rf_ntn_satellite` | RF / NTN / 위성통신 | QCOM, GCTS, ASTS, GSAT, SATS, VSAT, IRDM |
| `glass_substrate` | 유리기판 / TGV | GLW, 009150.KS, 011790.KS, 161580.KQ, 039030.KQ, 036930.KQ, 420770.KQ |
| `optical_interconnect` | 광인터커넥트 / CPO | LITE, COHR, MRVL, GLW, FN, POET, MAY |
| `sram_inference` | SRAM / inference accelerator | CBRS, GSIT, MRAM, NVDA, AMD |
| `ai_factory_deployment` | Dell AI Factory / 랙 통합 | DELL, HPE, SMCI, VRT, ETN, ANET |
| `stablecoin_rails` | 스테이블코인 결제 레일 | COIN, HOOD, PYPL, SQ, NAVER/KRX proxy |
| `korea_robotics_lastmile` | 로봇 / 라스트마일 | NAVER/KRX proxy, 277810.KQ, 108490.KQ, 454910.KS |

바스켓은 투자 추천 목록이 아니라 감시 universe다.

## 9. 데이터 소스 전략

### v0

| 시장 | 가격 소스 | 비고 |
|---|---|---|
| 한국 | `pykrx` / 기존 `data.technical` | 이미 프로젝트 dependency 있음 |
| 미국 | TradingView companion 또는 Stooq/yfinance 대체 | `04` 단독으로는 US 데이터 의존성 부족 |
| 홍콩 | TradingView companion 우선 | pykrx 불가 |
| Benchmark | SOXX, QQQ, KOSPI, KOSDAQ | US/HK는 TradingView 필요 |

### 권장

v0에서 `04_stock_intel` 단독으로 미국/홍콩 데이터를 해결하려 하지 않는다. `03_tradingview_companion`의 watchlist/price capability를 adapter로 쓰거나, 최소한 CSV snapshot을 받아 계산한다.

## 10. 아키텍처

```text
04_stock_intel/
  rotation/
    baskets.py          # YAML 로드, basket schema validation
    price_adapter.py    # market data adapter interface
    pykrx_adapter.py    # KR price adapter
    snapshot_adapter.py # CSV/JSON snapshot adapter for US/HK v0
    metrics.py          # returns, excess return, volume z, high breakouts
    scoring.py          # WATCH/SPARK/ROTATION/CONFIRMED/FADE 판정
    ledger.py           # JSONL event append/read
    formatter.py        # Telegram + Markdown report formatting
    runner.py           # daily scan orchestration
  configs/
    rotation_baskets.yaml
  reports/
    rotation/
      2026-05-25.md
  data/
    ...
  bot.py                # /rotation command 추가
  alert_server.py       # optional webhook push
```

## 11. 책임 분리

| 모듈 | 책임 | 금지 |
|---|---|---|
| `baskets.py` | 바스켓 정의 로드와 검증 | 가격 조회 금지 |
| `price_adapter.py` | 가격 데이터 인터페이스 | scoring logic 금지 |
| `metrics.py` | deterministic metric 계산 | 외부 API 호출 금지 |
| `scoring.py` | 상태 판정 | Telegram formatting 금지 |
| `ledger.py` | 이벤트 저장 | 상태 판정 금지 |
| `formatter.py` | 사용자 메시지 조립 | 가격 조회 금지 |
| `runner.py` | orchestration | metric formula 직접 구현 금지 |

## 12. 데이터 모델

### Basket

```python
class BasketSymbol(BaseModel):
    ticker: str
    market: Literal["KR", "US", "HK", "JP"]
    role: Literal["leader", "high_beta", "equipment", "material", "infra_adjacent", "stressed_peer"]
    weight: float = 1.0

class NarrativeBasket(BaseModel):
    id: str
    label: str
    owner_card: str
    benchmark: str
    symbols: list[BasketSymbol]
```

### SymbolSignal

```python
class SymbolSignal(BaseModel):
    ticker: str
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    excess_3d: float | None
    volume_z: float | None
    high_20d: bool
    close_above_prev_high: bool | None
```

### BasketSignal

```python
class BasketSignal(BaseModel):
    basket_id: str
    as_of: date
    state: Literal["WATCH", "SPARK", "ROTATION", "CONFIRMED", "FADE"]
    breadth_3d: float
    avg_volume_z: float
    leader_count: int
    high_beta_count: int
    score: int
    reasons: list[str]
    symbols: list[SymbolSignal]
```

## 13. Scoring v0

### Symbol score

| 조건 | 점수 |
|---|---:|
| 3D excess return > 5% | +2 |
| 1D return > 4% | +1 |
| volume z-score > 2 | +2 |
| 20D high breakout | +1 |
| close above previous high | +1 |
| 3D excess return < -3% | -1 |

### Basket score

| 조건 | 점수 |
|---|---:|
| breadth positive >= 30% | +2 |
| breadth positive >= 50% | +3 |
| avg volume z > 1.5 | +2 |
| leader positive and high_beta positive | +2 |
| at least 2 roles positive | +1 |
| benchmark negative but basket positive | +2 |
| leader reversal after SPARK | -3 |

### State threshold

```text
WATCH      score < 4
SPARK      score 4-6 and breadth < 30%
ROTATION   score >= 7 and breadth >= 30%
CONFIRMED  ROTATION + narrative confirmation flag
FADE       prior SPARK/ROTATION + score drop >= 4 or leader reversal
```

## 14. Narrative confirmation v0

v0에서는 LLM 자동 confirmation을 넣지 않는다. 대신 다음 중 하나가 있으면 `confirmation_flag=true`로 둘 수 있다.

- 해당 basket의 `owner_card`가 최근 7일 내 `last_signal` 업데이트
- 사용자가 Mooni/X 글을 해당 theme으로 capture
- yMB daily brief에 같은 theme tag 존재
- 공식 IR/press release가 source note로 capture

v1에서 LLM이 `price move -> matching Market Insight card -> source notes`를 요약한다.

## 15. Telegram UX

### `/rotation`

최근 스캔 결과 상위 5개 바스켓 표시.

```text
📡 Narrative → Price Translation
as of 2026-05-25

🔥 ROTATION — 전력반도체 / 800V HVDC
score 9 | breadth 58% | avg volume z 2.1
• ON +6.2% / 3D +11.4% / vol z 2.3
• NVTS +14.8% / 3D +22.1% / vol z 3.8
• VRT +4.9% / 3D +8.2% / vol z 1.9
판단: 주도섹터 확정 아님. AI 인프라 후행 순환매 진입 가능성.
확인: ON AI DC revenue, NVIDIA 800V references, peer breadth 유지
```

### `/rotation power_semis_800v`

특정 바스켓 상세.

### Push alert

`ROTATION` 이상만 자동 발송. `SPARK`는 설정으로 켜기.

## 16. 저장 위치

| 산출물 | 위치 |
|---|---|
| basket config | `01_Projects/04_stock_intel/configs/rotation_baskets.yaml` |
| event ledger | `01_Projects/04_stock_intel/logs/rotation_events.jsonl` |
| daily report | `01_Projects/04_stock_intel/reports/rotation/YYYY-MM-DD.md` |
| optional vault summary | `02_Areas/Market_Insights/_rotation_dashboard.md` |

## 17. 구현 단계

### Phase 0 — 바스켓 정의와 fixture

- `configs/rotation_baskets.yaml` 작성
- 3개 바스켓만 시작: `power_semis_800v`, `rf_ntn_satellite`, `ai_factory_deployment`
- CSV fixture로 가격 데이터 30일치 생성
- expected output을 수동으로 정의

완료 조건:

- 바스켓 schema validation 통과
- fixture 기반 score 계산 가능

### Phase 1 — deterministic engine

- `rotation/metrics.py`
- `rotation/scoring.py`
- `rotation/formatter.py`
- unit tests

완료 조건:

- `uv run pytest tests/test_rotation_scoring.py`
- false positive fixture / true rotation fixture 모두 통과

### Phase 2 — data adapter

- KR: 기존 `pykrx`/technical 재사용
- US/HK: CSV/JSON snapshot adapter 먼저
- 이후 TradingView companion adapter 추가

완료 조건:

- 3개 바스켓 EOD scan 가능
- 데이터 실패 시 해당 symbol만 degraded

### Phase 3 — Telegram surface

- `/rotation`
- `/rotation {basket_id}`
- `ROTATION` push alert

완료 조건:

- Telegram message 4000자 이하 chunking
- 섹션 실패가 전체 응답을 막지 않음

### Phase 4 — Market Insights linkage

- basket config의 `owner_card`를 읽어 카드 backlink 표시
- daily report에 “관련 vault card” 표시
- v1에서 source note confirmation 연결

완료 조건:

- report가 `owner_card`, score, reasons, top movers를 포함

### Phase 5 — 운영화

- APScheduler 또는 cron으로 하루 2회 실행
- morning / US close scan
- event ledger 기반 state transition 추적

완료 조건:

- 같은 ROTATION을 매번 중복 알림하지 않음
- WATCH -> SPARK -> ROTATION -> FADE transition 기록

## 18. 테스트 계획

### Unit tests

- basket schema validation
- return / excess return 계산
- volume z-score 계산
- state threshold
- FADE 판정
- formatter output length

### Fixture scenarios

| fixture | 기대 |
|---|---|
| single_stock_spike | SPARK 또는 WATCH, ROTATION 아님 |
| broad_theme_rotation | ROTATION |
| market_beta_rally | benchmark 대비 excess 낮으면 WATCH/SPARK |
| leader_reversal | FADE |
| missing_data | degraded, no crash |

### Verification command

```bash
cd /Users/kjun/vault/01_Projects/04_stock_intel
uv run pytest
python -m compileall rotation
cd /Users/kjun/vault
./Harness/verify.sh
```

## 19. 핵심 리스크와 방어

| 리스크 | 영향 | 방어 |
|---|---|---|
| 단일 종목 펌핑 오탐 | 알림 신뢰도 하락 | breadth와 role diffusion 필수 |
| 시장 전체 risk-on 오탐 | 모든 바스켓이 뜸 | benchmark 대비 excess return 사용 |
| 데이터 소스 실패 | 알림 누락 | symbol-level degradation |
| 너무 많은 바스켓 | 신호 소음 증가 | v0 3개, v1 8~12개 제한 |
| LLM 과잉해석 | 매매 추천처럼 보임 | v0 LLM 제외, v1도 explanation only |
| 04 프로젝트 책임 혼탁 | 유지보수 악화 | `rotation/` 독립 패키지, 기존 data/formatter와 분리 |

## 20. Go / No-Go 기준

### Go

- 사용자가 실제로 매일 보고 싶은 3개 바스켓을 고를 수 있다.
- fixture에서 단일종목 급등과 테마 확산을 구분한다.
- Telegram 메시지가 “바로 행동할 정도로” 짧고 명확하다.
- EOD 기준으로도 missed opportunity를 줄일 수 있다고 느낀다.

### No-Go

- 실시간 tick 없이는 의미 없다고 판단된다.
- 바스켓 정의가 계속 흔들려 비교 가능성이 없다.
- 가격 데이터 소스 확보가 불안정하다.
- 결과가 기존 TradingView watchlist 알림과 차별화되지 않는다.

## 21. 추천 첫 실험

첫 2주 동안 코드는 최소화하고, 다음 3개 바스켓만 돌린다.

1. `power_semis_800v`
2. `rf_ntn_satellite`
3. `glass_substrate`

매일 아침 다음 표만 생성한다.

```text
Basket | State | Score | Breadth | Avg Vol Z | Leader | High Beta | Comment
```

2주 후 판단:

- 실제로 “아, 이건 가격 반응이 시작됐네”라는 감각을 줬는가
- 기존 수동 관찰보다 빠른가
- false positive가 감당 가능한가

이 실험을 통과하면 Telegram 자동 알림으로 넘어간다.

## 22. 최종 권고

`04_stock_intel`에 붙일 수는 있다. 하지만 기존 단일 종목 리서치 기능과 섞으면 안 된다.

가장 좋은 v0 구조는 다음이다.

```text
04_stock_intel = Telegram surface + alert delivery
rotation/ = deterministic detector engine
03_tradingview_companion = optional price adapter
Market_Insights = narrative owner / confirmation layer
```

이렇게 만들면 자동매매 이전 단계의 “서사 가격화 조기 감지기”로 충분히 실용적이다. 단, 성공 기준은 예측률이 아니라 **false positive를 줄이고, ROTATION 전환을 수동 관찰보다 빠르게 잡는가**다.
