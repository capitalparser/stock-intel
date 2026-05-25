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

## Alert Contract

TradingView webhook URL:

```text
/webhook/tradingview?secret=<WEBHOOK_SECRET>
```

v1은 human-in-the-loop 알림입니다. 자동매매 봇은 향후 연관 프로젝트로 다룰 수 있지만, broker adapter와 order execution은 별도 risk gate와 paper-trading 검증을 통과해야 합니다.
