---
name: tech-spec-composer
version: 1.7.1
description: |
  Формирует техническое задание для Tier L агентов (Cursor/Codex): явный контекст,
  ограничения, правила стека, критерии приемки и артефакты передачи.
  Использовать при постановке задач для API, ботов, парсеров.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - AskUserQuestion
---

# Tech Spec Composer

## Назначение
Скилл готовит короткое, однозначное ТЗ, которое можно исполнять без догадок: что менять, где менять, как проверять и какие доказательства приложить к ревью.

## Принцип работы: НЕ ДОДУМЫВАТЬ
Если на любом шаге недостаточно информации для однозначного решения — **СТОП**.
Задать уточняющий вопрос и дождаться ответа. Никогда не выбирать за пользователя:
- архитектурный подход (если есть альтернативы)
- границы scope (если неясно, входит ли фича)
- технологию/библиотеку (если нет явного указания)
- поведение при ошибках и edge cases (если не описано в плане)
- структуру данных или модель (если не зафиксирована)

## Формат уточняющего вопроса
Каждый вопрос строго по формату:
- **Контекст:** на каком шаге и почему возник вопрос
- **Проблема:** что именно неясно, какие варианты видны
- **Варианты:** A) ... B) ... C) другое
- **Рекомендация:** какой вариант предпочтительнее и почему (если есть обоснование)
- **СТОП — жду ответа перед продолжением.**

## Порядок работы

### Шаг 0: Якорь контекста
Перед составлением ТЗ — восстановить полный контекст задачи:
1. Прочитать `~/.claude/projects/{project-dir}/memory/MEMORY.md` (если есть).
2. Найти последние JSONL-беседы проекта (`ls -lt ~/.claude/projects/{project-dir}/*.jsonl | head -3`).
3. Извлечь: исходные цели, спек (`/spec-writer`), план (`/change-plan-architect`), решения из review.
4. Зафиксировать как **контекстные якоря** — каждый якорь обязан быть отражён в ТЗ или явно исключён.
5. Особое внимание: нюансы и edge cases из обсуждений — именно они теряются при декомпозиции.
6. **Cross-project memory** (если ТЗ затрагивает CB / LMS / SPW / tg-bot): прочитать `~/projects/content-service\docs\cross-project\STATE.md` + `CHANGELOG.md` (последние 14 дней) + `contracts/<свой>.md` + `contracts/<смежный>.md` ОБЯЗАТЕЛЬНО. ТЗ опирается на актуальный mirror контрактов в `cross-project/contracts/*.md`, не на устаревший CB-spec. Стандарт — [cross-project-memory-standard.md](../claude-booster/references/cross-project-memory-standard.md).

### Основные шаги

**На каждом шаге:** если информации недостаточно — СТОП, задать вопрос по формату выше, дождаться ответа.

1. **Цель.** Сформулировать цель и пользовательский результат в одном абзаце.
   - СТОП если цель можно трактовать двояко → уточнить у пользователя.
2. **Контекст.** Зафиксировать: репозиторий, затронутые модули, текущее поведение, внешние зависимости.
   - СТОП если текущее поведение неизвестно и не восстанавливается из кода → спросить.
3. **Границы.** Жёстко задать:
   - что входит;
   - что не входит;
   - какие зоны не трогать.
   - СТОП если граница неясна (фича может быть и в scope, и вне) → спросить.
4. **Предметные зависимости.** Для migration/operator/CLI-задач собрать карту:
   - какие данные, классификаторы, состояния и правила нужны;
   - что уже есть в target system, а что нужно перенести.
   - СТОП если обнаружены данные, которых нет ни в legacy ни в target → спросить откуда брать.
5. **Доменный режим.** Выбрать из [references/domain-modes.md](references/domain-modes.md).
   - СТОП если задача не вписывается ни в один режим → предложить варианты.
6. **Шаги реализации.** Детерминированные, с привязкой к файлам/модулям **и к skill-исполнителю** из `~/.claude/skills/claude-booster/references/skills-registry.md`. Каждый существенный параграф ТЗ (раздел реализации, под-задача) обязан содержать **inline-маркер** `**Исполнитель:** /skill-name`; для security/contracts/migrations/race-conditions путей — также `**Ревью:** /skill-name` (см. парные связки в [skill-routing-standard.md §5](../claude-booster/references/skill-routing-standard.md)).
   - СТОП если есть архитектурная развилка (2+ равноценных подхода) → показать варианты с trade-offs.
   - СТОП если для шага нет подходящего skill → сначала прогнать Before-Б check ([operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md)); только если шаг true-Б — пометить "ручное исполнение" с обоснованием, иначе назначить skill-исполнителя.
7. **Пользовательский поток** (если есть):
   - `Контракт навигации`;
   - `Запрещённые элементы управления` на happy-path.
   - СТОП если happy-path неоднозначен → уточнить сценарий.
8. **Приёмка.** Зафиксировать:
   - критерии;
   - команды проверки;
   - минимальные артефакты review-gate;
   - rollback и меры снижения риска.
   - СТОП если критерий приёмки нельзя проверить командой → переформулировать или спросить.
9. **Дублирование.** Проверить, не допускает ли ТЗ дублирование общей инфраструктуры без явного архитектурного исключения.

## Формат результата
- `Цель`
- `Контекст`
- `Границы задачи`
- `Стек и ограничения`
- `Обязательные скиллы/правила`
- `Шаги реализации` — каждый существенный параграф/раздел реализации обязан содержать **inline-маркер** `**Исполнитель:** /skill-name` из `skills-registry.md`. Для security/contracts/migrations/race-conditions путей — также `**Ревью:** /skill-name` (парные связки см. [skill-routing-standard.md §5](../claude-booster/references/skill-routing-standard.md)).
- `Контракт навигации`
- `Запрещённые элементы управления`
- `Критерии приёмки`
- `Команды проверки`
- `Артефакты review-gate`
- `Переиспользование общей инфраструктуры`
- `Артефакты передачи`
- `Риски и откат`

## Правила качества
- **Не додумывать.** Если информации нет — СТОП и вопрос. Лучше задать 5 вопросов, чем написать ТЗ с 5 допущениями.
- **Строго следовать плану.** Если есть спек или план от `/change-plan-architect` — ТЗ реализует именно его, не своё видение.
- Основной язык: русский.
- Требования должны быть исполнимыми без догадок и без расплывчатых формулировок.
- Не подменять предметную функциональность списком команд/экранов, если не закрыты доменные предпосылки.
- Один основной документ по умолчанию; дополнительные матрицы и заметки допустимы только при реальной необходимости.
- Для next/queue-потоков отсутствие forbidden controls должно быть проверяемым критерием приёмки.
- **Каждое допущение = вопрос.** Если при написании ТЗ приходится предполагать — это сигнал остановиться.
- **Preflight / Deployment Checklist обязателен.** Для задач с новыми зависимостями, конфигами или внешними сервисами ТЗ обязано содержать секцию «Preflight / Deployment Checklist», включающую: (1) верификацию установки зависимостей в target env (`pip install` evidence), (2) проверку config-readiness (реальные значения, `enabled: true`, не placeholder), (3) проверку доступности внешних сервисов. Без этой секции — ТЗ считается неполным.
- **Live smoke test для внешних write-path.** Если pipeline/client пишет во внешний API, ТЗ обязано требовать минимум один optional live smoke test (gated по env-переменной, например `CB_LMS_TEST_*`) как acceptance criterion. 100% mock coverage на внешних write-path недостаточно.
- **Явный mode на каждом boundary.** Для pipeline parse-path ТЗ обязано явно фиксировать mode (edit/rendered, raw/processed) на каждом boundary (fetch, normalize, parse). Несогласованность mode между вызовами — дефект спецификации.
- **Inline-маркеры исполнителей обязательны.** Каждая существенная под-задача ТЗ (раздел реализации, файл, эндпоинт, миграция) обязана иметь строку `**Исполнитель:** /skill-name` из `~/.claude/skills/claude-booster/references/skills-registry.md`. Generic-формулировки («разработчик», «agent», «инженер») запрещены — см. [skill-routing-standard.md §4](../claude-booster/references/skill-routing-standard.md). Парные `**Ревью:**` обязательны для security/contracts/migrations/race-conditions путей (§5 standard).
- **ТЗ без inline-маркеров на каждой существенной под-задаче считается NEEDS-MORE-INFO, не COMPLETE.**
- **Skill name в inline-маркере обязан быть user-invocable в текущей среде.** Перед вписыванием `**Исполнитель:** /skill-name` или `**Ревью:** /skill-name` — сверить имя с **available-skills** списком из system reminder текущей сессии Claude Code. `skills-registry.md` перечисляет ВСЕ известные skills (включая проектные SKILL.md в `<project>/skills/core/`), но slash-командой запускаются только глобальные (`~/.claude/skills/`) и активные проектные. Если в проекте есть локальный `/tg-lms-bot-developer`, но он не виден как slash-команда — указывать **глобальный аналог** (`/executor-pro`, `/fastapi-api-developer`, `/techlead-code-reviewer`), который через `AGENTS.md` проекта автоматически подхватит проектные правила. Источник: `~/.claude/skills/claude-booster/references/skills-errors.md` 2026-05-21.
- **`Исполнитель: operator` / `категория Б` — только после Before-Б check.** Прежде чем назначить шагу ТЗ исполнителя «operator» или пометить «категория Б» — прогнать через [operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md) Before-Б check (5 п.). Runtime-evidence на **dev** БД (`prep`/`pipeline` против dev DSN), read-only SQL через MCP, LLM-computation (solver-tier / `/ege-master` / `llm_client`) — **категория А**, исполнитель `/executor-pro`/`/executor-lite`. «operator»/«категория Б» — только prod-write approval, 3rd-party UI signup, creds/2FA. Live-smoke на dev ≠ Б. Источник: skills-errors.md 2026-05-27.
- **Tracker-task в `~/projects/Root\tasks\` — категория А operator-handoff, выполнять без AskUserQuestion.** Создание `tsk-NNN-{slug}.md` с валидным frontmatter в рамках согласованного плана задачи — рутинное действие (см. [operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md) белый список «Создание/правка файлов в рамках согласованного плана»). ТЗ **не должен** содержать раздел «Pre-impl operator action: завести задачу tsk-NNN» — вместо этого агент создаёт `tsk-NNN.md` сам ДО или ПАРАЛЛЕЛЬНО с написанием ТЗ, и ТЗ ссылается на уже созданный номер. Источник: skills-errors.md 2026-05-21.
- **Frontend Route ≠ API Endpoint.** В ТЗ публичных API обязательны **две отдельные таблицы**: «Frontend Routes» (UX-имена страниц SPA/Next.js, например `/auth/magic-link/request`) и «API Endpoints» (контракт между frontend и backend, например `POST /api/v1/auth/magic-link/send`). Слияние в одно имя — дефект спеки. См. [api-contract-rules.md §1](../claude-booster/references/api-contract-rules.md). Источник дефекта: LMS ERRORS 2026-04-28 #2.
- **Тип токена/клиента для внешних API явный.** Для VK/Telegram/Dzen/WP flows ТЗ обязано фиксировать тип используемого токена (community/user/bot) и его ограничения по доступным методам. Mock в тестах не должен противоречить реальным платформенным ограничениям. См. [api-contract-rules.md §8](../claude-booster/references/api-contract-rules.md). Источник: CB ERRORS 2026-04-22 (`wall.get` недоступен community-token).
- **Concurrency и идемпотентность явные.** Для каждого endpoint, принимающего mutation (особенно multi-step pipelines, submit, queue), ТЗ обязано содержать sub-section «Concurrency & Idempotency»: queue / rate-limit / idempotency-key / locking / race-condition.
- **Stage Dependency Graph (BLOCKED_BY) для multi-stage задач.** Если ТЗ описывает ≥2 фазы/этапа, обязательна явная таблица зависимостей вида `Stage X BLOCKED_BY Stage Y` или Mermaid-граф. Acceptance criteria каждой фазы должны включать ссылку на БЛОКИРУЮЩУЮ предыдущую фазу. Без этого фаза может быть закрыта частично, а downstream stage запущен без полной готовности upstream — повторение паттерна CB Stage Handoff Continuity. Источник: дельта-анализ 29.04 (Y-3 VK linking — substages не связаны явно через BLOCKED_BY).
- **SQL formula verification для window-functions / gap-detection / рекурсивных CTE.** Если ТЗ включает raw SQL с `ROW_NUMBER()`, `LAG/LEAD`, gap-detection (`d - rn*1d`, `d + rn*1d`, `date_trunc + interval`), рекурсивными CTE — обязателен **mental trace на 3-input примере**: расписать вход/промежуточные значения/результат словами в комментарии под SQL. Запрещено копировать формулу из upstream-spec без проверки. Источник: LMS ERRORS 2026-04-29 #2 — формула streak gap-detection `d - rn*1d` для `ORDER BY d DESC` математически неверна (каждый день в своей grp → streak=1 для всех multi-day users); скопирована verbatim из CB authority spec без validation; bug пошёл бы на prod без edge-тестов. См. [api-contract-rules.md §14](../claude-booster/references/api-contract-rules.md).

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
