# Operating Context

## Source of Truth
Актуальные для проекта документы (адаптируйте под свою структуру):
- `docs/ai/AGENTS.md` — правила для AI-агентов
- `docs/ai/PROJECT_OVERRIDES.md` — проектные override-правила
- `docs/ai/WORKFLOWS/feature.md`, `bugfix.md`, `db-change.md` — рабочие процессы
- `.mcp.json` — конфигурация MCP-серверов (в т.ч. PostgreSQL)

## Key Constraints
- Stack: Python + FastAPI + PostgreSQL.
- Layering rule: `api -> services -> repos`.
- DB schema changes only via Alembic migrations.
- MCP alias: `postgresql` (или имя вашего MCP-сервера БД из `.mcp.json`).
- DB interactions are read-only by default for analysis/debug.
- `review-gate` required before integration to `main/master`.

## Validation Baseline
- Relevant tests (`pytest tests/...`).
- Smoke checks for health + changed endpoints.
- Log validation from `logs/app.log`.
- DB checks through MCP for data/state verification.
