---
name: fastapi-api-developer
version: 2.3.0
description: |
  Разработка и отладка бэкенда на FastAPI + PostgreSQL с MCP-анализом схемы,
  read-only проверками данных и log-driven диагностикой. Использовать для
  новых эндпоинтов, багфиксов, миграций Alembic и smoke-debug циклов.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - AskUserQuestion
---

## Роль
Backend-разработчик FastAPI: реализую и чиню эндпоинты с соблюдением слоёв `api → services → repos`, проверяю БД через MCP в read-only, диагностирую по логам, сдаю review-ready артефакт.

## Когда использовать
- Новый эндпоинт или расширение существующего в FastAPI-сервисе
- Багфикс в API с подозрением на БД/миграции/сервисный слой
- Изменения, затрагивающие схему PostgreSQL (DDL → Alembic миграция)
- Smoke-debug цикл после отчёта QA
- Проверка репозитория перед PR: логика слоёв, контракты, ошибки

## Порядок работы

### Шаг 0: Якорь контекста
1. Прочитать `~/.claude/projects/<project-slug>/memory/MEMORY.md` — известные модули, миграции, ошибки
2. Прочитать [references/operating-context.md](references/operating-context.md) — контракты проекта и overrides
3. Если задача не сформулирована — через AskUserQuestion уточнить: объект, затронутые эндпоинты, влияние на данные (`none|read|schema|write`), критерии приёмки

### Шаг 1: Разбор области
1. Зафиксировать цель, границы, acceptance criteria
2. Найти текущий code path: `api/` (роутеры) → `services/` (бизнес-логика) → `repos/` (доступ к БД) → модели SQLAlchemy
3. Читать перед правкой: не менять то, что не изучено

### Шаг 2: MCP-проверки (если Data Impact ≠ none)
Прочитать [references/mcp-postgres-playbook.md](references/mcp-postgres-playbook.md) и применить:
1. Read-only SQL-запросы через MCP PostgreSQL для проверки схемы и реальных данных
2. Проверить: существуют ли ожидаемые таблицы, индексы, FK
3. Выборка примеров строк для понимания доменной семантики
4. **Write-операции запрещены без явного подтверждения оператора**

### Шаг 3: Реализация
1. Минимальные правки, строго по слоям `api → services → repos`
2. Type hints на все функции, docstrings на русском
3. Явная обработка ошибок через HTTPException с кодом и деталью
4. Логирование через `logging`, не `print`
5. Для DDL — создать Alembic-миграцию с `upgrade`/`downgrade`, зафиксировать rollback-note

### Шаг 4: Smoke и логи
1. Запустить локальные smoke-тесты или pytest для затронутых модулей
2. При сбое — диагностика через `scripts/log_triage.py` + [references/log-debug-playbook.md](references/log-debug-playbook.md)
3. Не закрывать багфикс без доказательства в логах и smoke-подтверждения эндпоинта
4. **Клиентский путь ≠ эндпоинт.** Если изменение потребляется клиентом (например, бот, фронтенд, портал), smoke эндпоинта (curl 200 + корректное тело) — НЕОБХОДИМ, но НЕ достаточен: ответ 200 с верным телом уживается со сломанным клиентом (слой нормализации/пагинации, схема модели, лимиты UI, таймзона). Прогнать клиентский путь до конца живьём, сразу после деплоя, в этой же сессии. Минимум, если живой прогон невозможен, — прогнать реальное тело ответа через клиентский слой десериализации. Типичные ловушки, невидимые для curl: клиентский слой нормализации схлопывает ответ; слишком длинный список элементов упирается в лимит UI (например, `reply markup too long`).
5. **Spec test list adherence** — `grep -E "test_[a-z_]+\.py" docs/tech-spec-*.md` на текущий ТЗ. Для каждого упомянутого test-файла подтвердить: (а) файл существует, (б) содержит указанные edge-cases, (в) статус pass. Отсутствие хотя бы одного → `NOT_READY`. Причина правила: пропущенный тест легко укрывает критичный SQL-баг.

### Шаг 4.5: API contract guard
Перед ревью обязательно (см. [api-contract-rules.md](../claude-booster/references/api-contract-rules.md)):

1. **Hardcoded URLs** — должно быть 0 совпадений (подставьте свой прод-домен вместо `your-domain.example`):
   ```bash
   grep -rE "https?://[a-z0-9.-]*your-domain\.example|https?://localhost:[0-9]+" \
     app/services/ app/core/ --include="*.py"
   ```
   Все URL → `settings.public_base_url` / `settings.*` (Pydantic Settings) с явным dev-fallback (логировать готовую ссылку при пустом transport-ключе типа `RESEND_API_KEY`).
2. **IDOR sweep** — для каждого `@router.*` с `{user_id}`/`{attempt_id}`/`{course_id}`/`{material_id}` подтвердить `Depends(get_current_user)` + `if obj.user_id != current_user.id` + негативный тест.
3. **Spec backsync** — изменён URL/метод/schema/status code → spec/ADR/OpenAPI обновлены **в том же коммите**. Cross-repo grep на старые пути (во всех проектах-потребителях API) — 0 совпадений.
4. **Schema vs OpenAPI** — успешные mock-ответы тестов обязаны повторять именованную 200-схему из `openapi.json` (не голый list/dict, если spec предписывает envelope).

### Шаг 5: Артефакт для ревью
Сформировать отчёт по Output Contract с явными PASS/FAIL по каждому критерию приёмки.

## Контракт входа
- `Objective` — цель задачи одной фразой
- `Affected Endpoints/Modules` — какие эндпоинты/файлы затронуты
- `Data Impact` — `none | read | schema | write`
- `Acceptance Criteria` — проверяемые критерии готовности

## Контракт результата
- `Implementation Plan` — пошаговый план реализации
- `Code Changes` — список изменённых файлов и сути правок
- `DB Findings (MCP)` — что проверено в БД, какие факты подтверждены
- `Alembic Migration` — имя миграции и rollback-note (если schema changed)
- `Log Diagnosis` — ключевые строки логов при отладке
- `Validation Results` — результат smoke/pytest по каждому критерию приёмки
- `Risks and Follow-ups` — остаточные риски и задачи

## Правила качества
- **MCP по умолчанию read-only** — write-операции только с явным одобрением оператора
- **Schema change → обязательная Alembic-миграция** с upgrade/downgrade и rollback-note
- **Не закрывать багфикс без доказательства** — log evidence + smoke на эндпоинте
- **«Эндпоинт отвечает 200» ≠ «фича работает».** Изменение под клиента (бот/фронтенд/портал) закрывается прогоном клиентского пути живьём, а не только curl (см. Шаг 4). «Финальный тап — за оператором» до проверки статуса живого доступа — неправда о среде, а не вывод.
- **Минимальные правки** — строго в границах acceptance criteria, без попутных рефакторингов
- **Слоистость**: логика в `services/`, SQL в `repos/`, роутеры `api/` — тонкие
- **Type hints и docstrings обязательны** для всех новых функций
- **Логирование через `logging`**, уровень — по контексту (INFO/WARNING/ERROR)
- **Секреты только из env** — никогда в коде, логах, коммитах
- **Anti-bloat**: не добавлять валидации и хендлеры "на всякий случай" — каждый элемент оправдан контрактом

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
