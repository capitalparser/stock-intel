# HANDOFF — Macro Regime Engine (Plan 1)

> Claude(Opus)가 도메인 grill·plan·cross-model 리뷰까지 완료. 코드 구현·테스트·디버그를 Codex가 인수한다.

## 인수 범위
**Plan 1만** 구현한다. Plan 2~7은 건드리지 않는다.

- 구현 plan: `docs/superpowers/plans/2026-06-04-macro-regime-engine.md` (2판, Codex 리뷰 반영 완료)
- 도메인 사전: `CONTEXT.md` § Macro/Dashboard Terms
- 결정 기록: `docs/adr/0001-macro-regime-thresholds.md`

## 실행 방법
- `superpowers:executing-plans` 또는 task-by-task로 plan의 **Task 1~7**(전부)를 순서대로.
- **테스트 파일은 plan에 적힌 파일명 그대로**: `tests/test_percentile.py`(Task1~2), `tests/test_regime_engine.py`(Task3·6), `tests/test_regime_history.py`(Task4~5), `tests/test_dashboard_models.py`(Task7, 추가만). 단일 파일로 합치지 말 것.
- 각 Task는 TDD 스텝(red→green→commit)이 명시돼 있다. 그대로 따른다.
- **모든 명령은 프로젝트 루트에서:** `cd /Users/kjun/vault/01_Projects/04_stock_intel && uv run ...`

## Isolation 불변식 (위반 시 무효)
Plan 1은 100% additive다. 다음을 **변경 금지**:
- `dashboard/macro_state.py`의 기존 `build_macro_state`/`DIMENSIONS`/`SYMBOL_DIMENSION`
- `dashboard/providers/macro.py`의 `_derive_regime` (Plan 2에서 제거)
- `dashboard/live.py`, `dashboard/render.py`
- `tests/test_macro_state.py`, `tests/test_providers.py`, `tests/test_dashboard_render.py`

추가만: `dashboard/percentile.py`(신규), `dashboard/regime_history.py`(신규), `macro_state.py`에 새 함수 append, `models.py`에 새 dataclass append, 신규 테스트 파일.

## 완료 게이트
- 각 주요 Task 후 `uv run pytest -q` **전체 그린**(기존 테스트 0 변경).
- 최종: `uv run pytest -q` 전체 통과 + Plan의 모든 체크박스 완료.
- 상태 변경 시 `Harness/progress.md`/`session-handoff.md` 갱신은 Claude가 인수(코드 완료 후 핸드백).

## 핸드백 트리거 (Codex → Claude)
- 8개 Task 구현·테스트 완료 시: Claude가 (a) `code-reviewer`+`security-auditor` agent 리뷰, (b) `/codex:adversarial-review` 차이 머지 후 Plan 2 착수.
- 구현 중 plan 결함 발견 시: 수정 제안을 남기고 멈춤(plan을 임의로 확장하지 말 것).
