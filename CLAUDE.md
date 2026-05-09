# 04_stock_intel

국장(KRX) 종목 투자 데이터 통합 Telegram 봇.

종목명 한 번 입력 → 기관/외국인 수급현황, 공매도 비율, TA 위치, 감사법인 이력 통합 출력.

## 프로젝트 격리 원칙
- 02_audit_safe_signals, 03_tradingview_companion과 코드 import 없음
- 설계 패턴만 참조 (공유 코드 없음)

## 핵심 아키텍처
- data/ — 순수 동기 함수로 작성 (pykrx, requests)
- bot.py — asyncio.to_thread로 data layer 래핑
- utils/ticker.py — 종목명→코드 매핑 + rapidfuzz 퍼지 매칭
- utils/formatter.py — 텔레그램 Markdown 포맷터

## 환경변수
- TELEGRAM_BOT_TOKEN
- DART_API_KEY
- ALLOWED_CHAT_IDS (콤마 구분)

## 실행
uv run python bot.py
