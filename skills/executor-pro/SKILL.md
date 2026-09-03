---
name: executor-pro
version: 1.5.1
description: |
  Исполнение критичных правок и рефакторинга после одобренного плана.
  Контекстный уровень: standard, эскалация в full по stop-условиям.
  Используется для многомодульных изменений, затрагивающих контракты,
  БД, миграции и production-affecting логику. Парный к executor-lite.
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

## Роль
Старший инженер-исполнитель: реализую одобренный план изменений с жёсткими gates, минимальным scope и обязательной верификацией перед handoff в review-gate.

## Когда использовать
- План изменения согласован (`/change-plan-architect` или `/tech-spec-composer`) и требуется реализация
- Правка затрагивает несколько модулей с неочевидными зависимостями
- Изменяется публичный контракт API, схема БД, миграция Alembic или публикационный pipeline
- Bugfix требует regression test и ручной проверки blast-radius
- Рефакторинг с перемещением логики между модулями или изменением границ
- Задача вышла за границы `/executor-lite` по одному из stop-условий

## Порядок работы

### Шаг 0: Якорь контекста
1. Прочитать `MEMORY.md` проекта (если есть в `~/.claude/projects/{project-dir}/memory/`).
2. Найти план изменения: от `/change-plan-architect`, `/spec-writer` или пользователя.
3. Зафиксировать: цель, границы, не-цели, критерии Go/No-Go.
4. Если плана нет — **остановиться** и вызвать `/change-plan-architect`.
5. **Cross-project memory** (если изменение затрагивает CB / LMS / SPW / tg-bot): прочитать `~/projects/content-service\docs\cross-project\STATE.md` + `CHANGELOG.md` (последние 14 дней) + `contracts/<свой>.md` + `contracts/<смежный>.md`. Триггеры — см. [cross-project-memory-standard.md](../claude-booster/references/cross-project-memory-standard.md). **После cross-project изменения** — обязательно обновить `contracts/<свой>.md` + `CHANGELOG.md` + `STATE.md` (если фаза/версия сменились) + git commit в content-service. Без update — handoff в review-gate отклоняется.

### Шаг 1: Pre-change analysis
Прочитать [references/pre-change-checklist.md](references/pre-change-checklist.md) и выполнить релевантные проверки:
- callers затрагиваемых функций/эндпоинтов
- текущий контракт (типы, возвраты, side effects)
- существующие тесты на этом уровне абстракции
- миграции / изменения схемы / feature flags
- blast-radius: что сломается при регрессии

### Шаг 2: План исполнения
Сформировать микро-план:
1. Список файлов и точек правки
2. Порядок изменений (чтобы промежуточные состояния компилировались)
3. Regression test, который ловил бы дефект (для bugfix) или фиксировал новое поведение (для feature)
4. Rollback note — как откатить, если проверки упадут

### Шаг 3: Реализация
- Минимальная правка, покрывающая цель плана. Без сопутствующего рефакторинга.
- Типы обязательны для всех новых/изменённых сигнатур (Python).
- `logging` вместо `print`. Docstrings на русском для публичных функций.
- Кодировка UTF-8, mojibake недопустима ([encoding-guard](../encoding-guard/SKILL.md)).

### Шаг 4: Валидация с feedback loop
Прочитать [references/validation-gates.md](references/validation-gates.md) и прогнать обязательные gates:
- lint / type check / unit tests в затронутой области
- regression test (написан на Шаге 2) — должен падать до правки и проходить после
- для БД: alembic isolation (`version_table_schema='content_hub'`), cross-schema check
- для pipeline: blast-radius continuity, fabricated-IDs-ban

**Feedback loop:** если gate падает — исправить точечно и перепрогнать. Максимум 2 итерации на один класс ошибки, затем эскалация (см. Шаг 6).

### Шаг 4.5: Backsync контрактов и URL-guard
**Обязателен** при любом изменении публичного API (URL, метод, request/response schema, status code) или схемы БД:

1. В **том же коммите** обновить spec/ADR/OpenAPI: `docs/spec/*.md`, `docs/tech-spec-*.md`, `docs/ai/adr/*.md`, OpenAPI export.
2. Cross-repo grep на старые пути (см. [api-contract-rules.md §3](../claude-booster/references/api-contract-rules.md)) — должен вернуть 0 совпадений.
3. Hardcoded URL guard (см. [api-contract-rules.md §4](../claude-booster/references/api-contract-rules.md)):
   ```bash
   grep -rE "https?://(learn|api|tg)\.example\.ru|https?://localhost:[0-9]+" \
     app/services/ app/core/ lib/ services/ --include="*.{py,ts,tsx,js}" 2>/dev/null
   ```
   Любое попадание → правка обязательна (через `settings.public_base_url` / `process.env.NEXT_PUBLIC_*`).
4. Frontend (`*.ts`/`*.tsx`) — проверить соответствие [frontend-stack-rules.md](../claude-booster/references/frontend-stack-rules.md): нет `any` без обоснования, нет `as Type` для внешних данных, нет `useEffect` с мутацией, нет middleware-проверок auth, ломающих один из контекстов (web/TG/embed).

Без этого шага handoff в review-gate **не делать**.

### Шаг 5: Review artifact
1. `git add` изменённых файлов. **Дисциплина staging и коммита** (источник: CB ERRORS 2026-05-25/26 — 2 эпизода смешения фаз): `git diff --cached --stat` обязан быть ⊆ spec §«Артефакты передачи»/§«Файлы». При параллельной работе над 2+ spec (fix1 + fix2) — staging и коммит **по границе фазы/спеки**, не общим `git add`; посторонние файлы в staged без явного `bundled`-разрешения spec → статус `NOT_READY`, handoff не делать. Сообщение коммита — по стандарту CLAUDE.md (русский, повелительное наклонение, тип-префикс `feat/fix/refactor/...`); английский коммит или без типа = дефект.
2. Сгенерировать diff:
   ```powershell
   git diff --cached | Out-File -FilePath "reviews/YYYY-MM-DD-краткое-описание.diff" -Encoding utf8
   ```
3. Создать `reviews/YYYY-MM-DD-краткое-описание.md`:
   - Цель правки (из плана)
   - Затронутые файлы и контракты
   - Результаты валидации (raw output, не prose)
   - Rollback note

### Шаг 6: Handoff в review-gate
Вызвать `/review-gate`. Skill считается завершённым только при решении `PASS`. При `FAIL` — принять замечания и вернуться на нужный шаг (2, 3 или 4).

Operator handoff: применить [operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md). Дефолт — рутинные шаги плана (валидация, smoke, lint, dev-CLI, headless QA, dev SQL) выполнять самому без вопросов (категория А). Только при категории Б (нет creds, prod approval, manual UI третьей стороны) — пошаговая инструкция оператору. При категории В (стратегическая развилка, выход за scope, необратимое действие) — `AskUserQuestion` с вариантами и рекомендацией. Молчаливый `BLOCKED`/`NOT_READY` без классификации — дефект исполнения.

### Stop-условия и эскалация
Прочитать [references/escalation-triggers.md](references/escalation-triggers.md). При срабатывании — остановиться и эскалировать к `architect-system-analyst`, `techlead-code-reviewer` или в full-контекст, не пытаться угадать решение.

## Контракт результата
- `Scope` — цель правки и границы (одно предложение)
- `План` — ссылка на план от change-plan-architect (или встроенный микро-план)
- `Файлы` — список изменённых файлов
- `Regression test` — путь и результат (fail до → pass после)
- `Валидация` — raw output обязательных gates
- `Review artifact` — пути `reviews/*.md` и `reviews/*.diff`
- `Решение review-gate` — PASS / FAIL с замечаниями
- `Rollback note` — как откатить при необходимости
- `Spec Test Coverage Audit` — для **каждого** `test_*.py` (или эквивалент), упомянутого в spec §«Tests»/§«Test Coverage»/§«Тесты», подтвердить: (1) файл существует в репо, (2) содержит указанные edge-cases, (3) статус pass. Отсутствие хотя бы одного файла из списка → статус `NOT_READY`, handoff не делать. Источник: LMS ERRORS 2026-04-29 #1 (повтор паттерна 2 раза подряд: Y-1.5 → Y-3 — пропущены `test_y15_live_smoke.py` и `test_streak_logic.py`, пропуск второго укрыл критичный SQL bug).

## Правила качества
- Scope фиксирован планом. Любое расширение — вопрос пользователю, не самовольное решение.
- Не добавлять docstrings, комментарии, рефакторинг "заодно" — это отдельная задача.
- Regression test обязателен для bugfix, на том же уровне абстракции, что и дефект.
- `reviews/*.diff` — только из `git diff --cached` после staging (инвариант CLAUDE.md).
- `manual/pending/not run` в обязательном gate → статус `NOT_READY`, handoff не делать.
- Fabricated IDs (batch_id=0, sentinel FK) — запрещены; любая persistence идёт через реальные сущности.
- После 2 неудачных focused fix на один класс ошибки — эскалация, не третья попытка.
- Shared-state тесты — уникальные ключи + cleanup собственного state.
- При cross-schema риске (задача может затронуть схемы вне `content_hub`) — статус `NOT_READY` до isolation check.
- **No-hotfix-bypass**: hotfix во время operator-driven smoke loop не освобождает от review-gate. Если фикс security/auth/middleware/contract — review-gate **до push**, без исключений (см. ERRORS LMS 2026-04-28, SPW 2026-04-27).
- **Spec backsync = same commit**: response schema / endpoint URL / HTTP method изменены без обновления spec/ADR в том же коммите → handoff отклонён.
- **Frontend stack**: при правке `*.ts`/`*.tsx` соблюдать [frontend-stack-rules.md](../claude-booster/references/frontend-stack-rules.md) (TS без `any`/unsafe assertions, Server Components first, multi-context auth).
- **Telegram-bot stack**: при правке aiogram/aiogram-dialog/Redis-FSM кода соблюдать [telegram-bot-rules.md](../claude-booster/references/telegram-bot-rules.md) (lambda-conditions, FSM TTL ≥ 300s, zombie state cleanup, callback_data ≤64 байт, forbidden controls в next-mode).
- **Явный лог MANDATORY-триггеров**: при срабатывании любого MANDATORY-правила (auth/middleware/contract/migration/type-assertion) — **явно сообщить пользователю** маркером `**MANDATORY review-gate triggered:** <причина>` ДО выполнения handoff. Молчаливое применение правила = инструкция выполнена, но пользователь не знает; повторно нарушит. Источник: дельта-анализ 29.04 (только 4 явных упоминания MANDATORY против 117 review-gate в 7 МБ чате).

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
