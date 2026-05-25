# 04_stock_intel — Project System Context

This project is a personal Telegram research bot for Korean stocks. It combines
ticker matching, flow, short-selling, technical, fundamental, and auditor
sections into one mobile-readable answer.

## Module Responsibilities

| Module | Responsibility | Location |
|---|---|---|
| Bot Entrypoint | Telegram polling, command routing, async/sync bridge | `bot.py` or project entrypoint |
| Data Modules | Section-specific data retrieval and fallback handling | `data/` |
| Ticker Utilities | Name-to-ticker cache, fuzzy matching, candidate selection | `utils/ticker.py` |
| Formatter | Telegram message assembly and section degradation display | `utils/formatter.py` |
| Cache/Data | Local ticker cache and temporary source artifacts | `cache/`, `data/` |
| Plans | Feature and migration planning records | `plans/` |

## Feature Addition Rules

- Each new research section gets its own data module and formatter section.
- Data retrieval failures must degrade one section, not fail the full answer.
- Do not mix source fetching, investment commentary, and Telegram formatting in
  one function.
- Auditor data must remain traceable to `kreports` or a documented fallback.

## Documentation Gap

- Add `CONTEXT.md` before the next substantive feature. At minimum define:
  ticker candidate, research section, graceful degradation, and auditor section.
- Add `tests/` before changing data or formatter behavior.

## Verification

- Use the project's documented `uv`/Python command when available.
- Until tests exist, run syntax/import checks and document residual risk.
