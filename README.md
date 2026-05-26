# 04_stock_intel

Telegram에서 종목명만 보내면 국내 주식 투자 판단에 필요한 핵심 지표를 한 번에 묶어 돌려주는 개인용 리서치 봇입니다.

급하게 모바일에서 종목을 확인해야 하는 상황을 기준으로 설계했습니다. 종목명 입력 -> 티커 매칭 -> 수급, 공매도, 기술적 위치, 감사법인 정보를 통합 조회해 하나의 메시지로 응답합니다.

## Features

- 종목명 퍼지 검색
  - `삼성전자`, `SK이터닉스`, `NAVER` 같은 자연어 종목명 입력
  - 복수 후보가 있으면 Telegram 인라인 버튼으로 선택
- 기관/외국인 수급 현황
  - 최근 기준일 요약
  - 최근 10거래일 순매수 정렬 테이블
  - KRX 수급 API 장애 시 네이버 금융 투자자별 매매동향 fallback
- 공매도 현황
  - 당일 공매도 비율
  - 20일 평균 대비 방향
  - KRX 공매도 iframe JSON endpoint 기반 조회
- 기술적 위치
  - 현재가, 20/50/150/200일 이동평균
  - 52주 고점/저점 위치, 거래량 50일 평균 대비 배수
  - 성장주 트렌드 템플릿 기반 진입/리스크 코멘트
- 펀더멘탈
  - DART 최근 3개년 매출, 영업이익, 영업활동현금흐름
  - KRX PER/PBR/EPS/BPS/DPS/배당수익률
  - 이익과 영업현금흐름 품질 코멘트
- 감사법인 현황
  - 로컬 `kreports` DB 기반 당해/직전 감사인 표시
  - 미수집 종목은 로컬 `kreports` collector로 감사인 이력을 한 번 수집 후 재조회
- 운영 편의
  - 허용 chat id 화이트리스트
  - 매일 07:00 KST 종목 캐시 갱신 스케줄
  - 데이터 소스 장애 시 섹션별 graceful degradation
- TradingView 시그널 알림
  - private indicator v6.2 JSON webhook 수신
  - BUY/진입 시그널 필터와 중복 저장
  - 한국 종목은 `kreports` 감사인 정보로 독립성 차단 여부 표시
  - 미국/일본 종목은 알림을 보내되 원천 감사인 수동 확인 필요로 표시
  - 차단 감사인이면 `🚫 독립성 차단 — 매입 검토 금지` 알림 발송
- Telegram 시그널 콘솔
  - `/signals` 버튼형 Lazy Alpha 콘솔
  - `/buy`, `/sell` 빠른 후보 조회
  - `/signal <ticker>` 특정 종목의 최신 지표 판단 조회
  - 기본 화면은 현재 활성 시그널, `recent` 옵션은 최근 발생 이벤트

## Example

```text
📊 SK이터닉스 (475150)  2026-05-08 기준

💰 수급현황 (D-1)
  기관: 순매도 -6억  (5일: -83억 ▼)
  외국인: 순매수 +20억  (5일: -145억 ▼)
  최근 10거래일 순매수(억원)
  날짜        기관     외국인
  --------------------------
  05.08       -6       +20
  05.07      -20       -18
  05.06      -12       -19

🔻 공매도
  오늘 비율: 4.9%  (20일 평균 2.79% 대비 ▲)

📈 기술적 위치
  현재가: 51,100원  |  셋업: 관찰
  20/50/150/200일선: 55,365 / 48,120 / 42,300 / 39,800
  단기 5/20/60 배열: 54,140 / 55,365 / 44,823 (혼조)
  트렌드 템플릿: 통과  |  52주 위치: 고점 -9.4%, 저점 +66.7%
  거래량: 50일 평균 대비 1.62x (돌파급 증가)
  RSI(14): 45  |  볼린저: 하단(5%)
  → 판단: 중립/관찰
  코멘트: 20/50/150/200일 구조가 성장주 추세 템플릿에 부합 · 52주 고점 대비 -9.4%로 신고가권 유지 · 거래량 1.6배로 돌파 확인권
  손절선: 49,098원

📚 펀더멘탈
  최근 3개년 재무(억원)
  연도       매출   영업익   영업CF
  ------------------------------
  2023      1,245      +82     +104
  2024      1,713     +136     +128
  2025      2,084     +221     +240
  지표: PER 32.40x | PBR 4.12x | EPS 1,576 | BPS 12,403
        배당수익률 0.00% | DPS 0
  코멘트: 3년 매출 +67.4% · 영업이익 +169.5% · 이익과 영업현금흐름 동반 양호 · PBR 4.12배

🏢 감사법인
  당해(2025): 삼정회계법인
  직전(2024): 삼정회계법인  (변경 없음)
```

## Architecture

```text
bot.py
  Telegram polling entrypoint
  asyncio.to_thread()로 동기 data layer 호출

alert_server.py
  FastAPI alert endpoint
  /webhook/tradingview 로 TradingView private indicator v6.2 JSON 수신

data/
  supply.py       기관/외국인 수급
  short_sell.py   공매도 비율
  technical.py    가격/TA 지표
  fundamental.py  DART/pykrx 재무정보
  audit_firm.py   kreports 감사인 이력

utils/
  ticker.py       종목명 -> 티커 캐시/검색
  formatter.py    Telegram 메시지 포맷

signals/
  payload.py       TradingView v6.2 payload schema
  filtering.py     BUY/품질 필터
  independence.py  독립성 차단/확인 필요 판정
  storage.py       SQLite signal event store
  pipeline.py      webhook -> Telegram orchestration
```

## Data Sources

| 영역 | 1차 소스 | fallback / 보정 |
|---|---|---|
| 종목 검색 | KRX 상장종목검색 | 로컬 `cache/tickers.json` |
| 수급 | 네이버 금융 투자자별 매매동향 | pykrx KRX 수급 API |
| 공매도 | KRX 공매도 iframe JSON | 네이버 일별 거래량으로 비율 분모 보정 |
| 기술적 지표 | pykrx OHLCV | 섹션 단위 에러 처리 |
| 펀더멘탈 | DART Open API / pykrx 기본지표 | DART 미설정 시 KRX 지표만 표시 |
| 감사법인 | `kreports` SQLite DB | 미수집 종목은 `collect_auditors()` 후 재조회 |

KRX 일부 JSON endpoint는 세션 정책 변경에 따라 `LOGOUT` 또는 JSON decode 오류를 낼 수 있습니다. 이 프로젝트는 모바일 조회 안정성을 우선해서 가능한 범위에서 대체 소스를 사용합니다.

## Requirements

- Python 3.12+
- `uv`
- Telegram bot token
- DART API key
- 로컬 또는 서버의 `kreports.db`

## Environment

`.env` 파일을 프로젝트 루트에 둡니다.

```env
TELEGRAM_BOT_TOKEN=...
DART_API_KEY=...
ALLOWED_CHAT_IDS=123456789,987654321
DB_URL=sqlite:////absolute/path/to/kreports.db
WEBHOOK_SECRET=...
STATE_DB_PATH=./state.db
SIGNAL_CHAT_IDS=123456789
TRADINGVIEW_SCAN_CACHE_PATH=./state/tradingview_scan_cache.sqlite3
TRADINGVIEW_SCAN_CACHE_TTL_SECONDS=600
```

`ALLOWED_CHAT_IDS`가 비어 있으면 모든 chat id를 허용합니다. 실사용 서버에서는 반드시 설정하는 것을 권장합니다.

`SIGNAL_CHAT_IDS`가 비어 있으면 `ALLOWED_CHAT_IDS`를 TradingView 시그널 알림 대상 chat id로 재사용합니다.

`/추천`은 TradingView 직접 스캔 결과를 기본 10분간 캐시합니다. 반복 조회 때 같은 watchlist 묶음을 빠르게 재사용하고, `/추천 us 10 동기화`처럼 `동기화`/`sync`를 붙이면 universe와 스캔 캐시를 우회해 새로 읽습니다.

## Local Run

```bash
uv sync
uv run python bot.py
```

봇은 polling 방식으로 동작합니다. 로컬 맥북에서 실행 중이면 맥북이 잠자기 상태가 되거나 네트워크가 끊겼을 때 모바일 Telegram 응답도 중단됩니다.

## TradingView Webhook

TradingView Alert의 webhook URL:

```text
https://<host>/webhook/tradingview?secret=<WEBHOOK_SECRET>
```

Message에는 private indicator 제작자가 제공한 v6.2 JSON 템플릿을 넣습니다. 서버는 JSON 안의 `action`, `type`, `ticker`, `exchange`, `price`, `score`, `conviction`, `atr_dot`, `sb_z_score` 등을 사용합니다. 지표 내부 로직은 읽지 않고 webhook payload만 신뢰합니다.

알림 정책:

```text
🚫 독립성 차단 — 매입 검토 금지
🟡 독립성 확인 필요 — 원천 확인 전 매입 보류
🟢 매수 시그널 — 독립성 차단 없음
```

한국 종목은 `kreports` 감사인 이력으로 차단 감사인을 확인합니다. 미국/일본 종목은 v1에서 자동 감사인 조회를 하지 않으므로 `🟡 독립성 확인 필요`로 보냅니다.

TradingView watchlist는 `/Users/kjun/code/tradingview-mcp`의 CLI로 보조 관리할 수 있습니다.

```bash
cd /Users/kjun/code/tradingview-mcp
node src/cli/index.js watchlist get
node src/cli/index.js watchlist create "Intel Alert Candidates" --file list.txt
```

이 CLI 작업은 TradingView Desktop이 로그인된 상태로 `--remote-debugging-port=9222`에 떠 있어야 합니다.

## KR Sector Candidate Scoring

국장 관심종목 후보군은 섹터별로 먼저 넓게 선별한 뒤, 펀더멘탈/수주 가시성/현금흐름/재무안정성/감사인 상태를 붙여 watch tier로 압축합니다.

```bash
set -a; source .env; set +a
uv run python scripts/evaluate_kr_watch_candidates.py
```

출력:

```text
state/kr_watch_candidates_YYYY-MM-DD.md
state/tradingview_kr_watch_candidates_YYYY-MM-DD.txt
```

TradingView Desktop이 CDP로 열린 상태라면 생성된 파일을 섹터 섹션이 있는 watchlist로 넣을 수 있습니다.

```bash
cd /Users/kjun/code/tradingview-mcp
node src/cli/index.js watchlist create "KR Sector Candidates" --file /Users/kjun/vault/01_Projects/04_stock_intel/state/tradingview_kr_watch_candidates_YYYY-MM-DD.txt
```

상태는 `Core Watch`, `Watch`, `Hold for Proof`, `Exclude`를 기본으로 하며, 삼정/KPMG 등 독립성 차단 가능성이 있으면 `Blocked Core Watch`처럼 접두 상태로 표시합니다. v0의 수주/계약 가시성 점수는 섹터 thesis seed 기반이며, DART 공시검색의 `단일판매ㆍ공급계약체결` 자동 반영은 후속 보강 대상입니다.

테스트 fixture `tests/fixtures/tradingview_watchlist_kr_actual.json`은 TradingView custom watchlist `국장`에서 2026-05-25에 읽은 실제 관심 심볼을 기준으로 합니다. 6자리 `KRX:` 종목은 감사인 자동조회 대상으로 정규화하고, `KRX:S0X1!`처럼 상장사 종목코드가 아닌 항목은 독립성 수동 확인으로 처리합니다.

`/sync_universe`는 TradingView Desktop에 로그인된 상태의 모든 custom/color watchlist를 읽어 `state/universe_snapshot.json`으로 저장합니다. `국장`, `관심`, `예비 버블종목`, color list 등을 물리적으로 합치지 않고, 봇 내부에서 합집합 universe로 사용합니다. 국장 6자리 종목은 감사인 자동조회 대상이고, ETF/지수/코인/선물/환율 심볼은 universe에는 남기되 감사인 자동조회에서는 제외합니다.

## Telegram Signal Console

Telegram에서 저장된 Lazy Alpha webhook ledger와 현재 활성 시그널 상태를 탐색할 수 있습니다. v1은 TradingView webhook으로 들어온 이벤트를 기준으로 active state를 갱신하며, TradingView 차트의 현재 상태를 실시간으로 다시 계산하지 않습니다.

```text
/signals
/universe
/sync_universe
/buy
/buy kr 8h
/sell 24h
/signals recent
/signals review us 24h
/signal 005930
시그널
```

`/signals`는 버튼형 콘솔을 띄웁니다. 기본 보기는 `현재 활성`입니다. `BUY` 계열 webhook이 들어오면 active 상태가 생성 또는 갱신되고, `SELL` webhook이 들어오면 해당 종목의 active 상태가 종료됩니다. 버튼은 같은 메시지를 갱신하며, 보기 전환은 `현재 활성`/`최근 발생`, 탭은 `매수`, `매도`, `확인필요`, 시장은 `전체`, `국장`, `미국`, `일본`, 기간은 `4h`, `8h`, `24h`를 지원합니다.

Universe snapshot이 있으면 `/signals`는 TradingView 전체 watchlist 합집합 안에 있는 종목만 보여줍니다. snapshot이 없으면 기존처럼 저장된 모든 webhook 이벤트를 보여줍니다.

`시그널`, `신호`, `signals` 같은 일반 텍스트도 종목 검색으로 보내지 않고 `/signals` 콘솔을 엽니다.

## Production Direction

개인 실사용은 작은 VPS 1대에 올리는 구성이 가장 단순합니다.

추천 구성:

```text
Hetzner CX23
├─ stock-intel Telegram bot
├─ kreports MCP HTTP server
├─ kreports.db SQLite
├─ systemd services
└─ daily SQLite backup
```

초기에는 SQLite로 충분합니다. 사용자가 늘거나 MCP를 외부 서비스로 안정 운영해야 할 때 Postgres 분리를 고려합니다.

## Operations Checklist

- [ ] VPS 생성
- [ ] `/opt/stock-intel`에 코드 배포
- [ ] `/opt/kreports/kreports.db` 배치
- [ ] `.env` 설정
- [ ] `stock-intel-bot.service` 등록
- [ ] `kreports-mcp.service` 등록
- [ ] HTTPS reverse proxy 설정
- [ ] SQLite daily backup 설정
- [ ] Telegram 모바일 조회 테스트
- [ ] MCP 연결 테스트

## Notes

이 봇은 투자 결정을 보조하기 위한 개인용 정보 집계 도구입니다. 데이터 소스 지연, 공시 수집 누락, KRX/네이버 응답 변경 가능성이 있으므로 주문 전 원천 데이터를 확인하는 습관을 유지해야 합니다.
