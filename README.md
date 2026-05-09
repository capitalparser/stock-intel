# 04_stock_intel

Telegram에서 종목명만 보내면 국내 주식 투자 판단에 필요한 핵심 지표를 한 번에 묶어 돌려주는 개인용 리서치 봇입니다.

급하게 모바일에서 종목을 확인해야 하는 상황을 기준으로 설계했습니다. 종목명 입력 -> 티커 매칭 -> 수급, 공매도, 기술적 위치, 감사법인 정보를 통합 조회해 하나의 메시지로 응답합니다.

## Features

- 종목명 퍼지 검색
  - `삼성전자`, `SK이터닉스`, `NAVER` 같은 자연어 종목명 입력
  - 복수 후보가 있으면 Telegram 인라인 버튼으로 선택
- 기관/외국인 수급 현황
  - 최근 기준일 요약
  - 최근 10거래일 순매수 테이블
  - KRX 수급 API 장애 시 네이버 금융 투자자별 매매동향 fallback
- 공매도 현황
  - 당일 공매도 비율
  - 20일 평균 대비 방향
  - KRX 공매도 iframe JSON endpoint 기반 조회
- 기술적 위치
  - 현재가, 5/20/60일 이동평균
  - RSI(14), 볼린저 밴드 위치
  - 간단한 진입/매도/손절/중립 판단
- 감사법인 현황
  - 로컬 `kreports` DB 기반 당해/직전 감사인 표시
  - 미수집 종목은 로컬 `kreports` collector로 감사인 이력을 한 번 수집 후 재조회
- 운영 편의
  - 허용 chat id 화이트리스트
  - 매일 07:00 KST 종목 캐시 갱신 스케줄
  - 데이터 소스 장애 시 섹션별 graceful degradation

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
  현재가: 51,100원
  5/20/60 이평: 54,140 / 55,365 / 44,823 (혼조)
  RSI(14): 45  |  볼린저: 하단(5%)
  → 판단: 중립 (진입 조건 미충족)
  손절선: 49,098원

🏢 감사법인
  당해(2025): 삼정회계법인
  직전(2024): 삼정회계법인  (변경 없음)
```

## Architecture

```text
bot.py
  Telegram polling entrypoint
  asyncio.to_thread()로 동기 data layer 호출

data/
  supply.py       기관/외국인 수급
  short_sell.py   공매도 비율
  technical.py    가격/TA 지표
  audit_firm.py   kreports 감사인 이력

utils/
  ticker.py       종목명 -> 티커 캐시/검색
  formatter.py    Telegram 메시지 포맷
```

## Data Sources

| 영역 | 1차 소스 | fallback / 보정 |
|---|---|---|
| 종목 검색 | KRX 상장종목검색 | 로컬 `cache/tickers.json` |
| 수급 | 네이버 금융 투자자별 매매동향 | pykrx KRX 수급 API |
| 공매도 | KRX 공매도 iframe JSON | 네이버 일별 거래량으로 비율 분모 보정 |
| 기술적 지표 | pykrx OHLCV | 섹션 단위 에러 처리 |
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
```

`ALLOWED_CHAT_IDS`가 비어 있으면 모든 chat id를 허용합니다. 실사용 서버에서는 반드시 설정하는 것을 권장합니다.

## Local Run

```bash
uv sync
uv run python bot.py
```

봇은 polling 방식으로 동작합니다. 로컬 맥북에서 실행 중이면 맥북이 잠자기 상태가 되거나 네트워크가 끊겼을 때 모바일 Telegram 응답도 중단됩니다.

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
