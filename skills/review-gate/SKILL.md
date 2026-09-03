---
name: review-gate
version: 2.2.2
description: |
  Независимая проверка перед слиянием: строгое решение ПРИНЯТО или ОТКЛОНЕНО
  с приоритизированными находками и обязательными исправлениями. Использовать
  перед слиянием, релизом или любым рискованным развёртыванием.
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

## Роль
Независимый рецензент: принимаю решение ПРИНЯТО/ОТКЛОНЕНО без предвзятости к автору.

## Когда использовать
- Ветка готова к слиянию в основную
- Перед созданием релиза или тега
- После крупного рефакторинга
- При любых изменениях в схеме базы данных или конфигурации

## Порядок проверки

### Шаг 0: Якорь контекста
Перед проверкой кода — восстановить исходные требования:
1. Прочитать `~/.claude/projects/{project-dir}/memory/MEMORY.md` (если есть).
2. Найти последние JSONL-беседы проекта — извлечь acceptance criteria и ключевые решения.
3. Сверить: реализация покрывает ВСЕ исходные требования, а не только очевидные.
4. Отклонения от исходных целей — отдельная категория находок (DRIFT).
5. (Опционально) `references/content-analyzer-findings.md`, если существует — курируемые внешние находки по практикам ревью (knowledge-pipeline, внутренней задаче/208).

### Шаг 0.5: Проверка реестра ошибок
Прочитать реестр известных ошибок проекта — не повторять уже зафиксированные паттерны:
1. `{project}/docs/ai/ERRORS.md` — проектный реестр.
2. `~/projects/IDE_booster/Docs/ai/ERRORS.md` — мастер-реестр (если проектного нет).
3. Для каждой prevention action из реестра — проверить, что она соблюдена в текущем коде.
4. Если найден повторяющийся паттерн ошибки — автоматически ОТКЛОНЕНО + ссылка на реестр.

### Основные проверки (12 измерений)
1. **Соответствие целям** — acceptance criteria из Шага 0 покрыты полностью (DRIFT детекция)
2. **Корректность** — edge cases, скрытое состояние, regression risk
3. **Безопасность данных и миграций** — транзакции, rollback, schema drift
4. **Безопасность и секреты** — инъекции, credentials, trust boundaries; **IDOR sweep** для всех endpoints с user-data — см. [api-contract-rules.md §5-6](../claude-booster/references/api-contract-rules.md)
5. **Покрытие тестами** — адекватность, граничные случаи; **mock-only на external write-path = блокирующий FAIL** (без live smoke с env-gate) — см. [api-contract-rules.md §7-8](../claude-booster/references/api-contract-rules.md). Если изменение **user-facing и уже задеплоено** на авторизованный прод (SPW/LMS, ТГ, ВК) — проверить его **на живой странице самому** (ветвь А, `live-browse.mjs`), см. [live-browser-testing.md](../claude-booster/references/live-browser-testing.md). Зелёные тесты + верный код ≠ работает у ученика: внутренней задаче нашёл ровно такой разрыв (бэкенд не засчитывает без вложения, а UI отправку не блокирует). **ПРИНЯТО по живому поведению без живой проверки — это гипотеза, а не вердикт.**
6. **Docs/Config/Runtime Drift** — документация соответствует коду? README, CLAUDE.md, конфиги актуальны? При переименовании ADR (rename/renumber) — `grep -rn "ADR-<старый_номер>\|<старый_номер>-<slug>"` по `docs/ tests/ scripts/ monolith/ docker/` обязан вернуть **0 совпадений** (иначе читатель попадает не в тот ADR) — см. CB ERRORS 2026-05-25.
7. **Phase Integrity** — все фазы работы завершены? Нет TODO, заглушек, незакрытых задач? **Scope staged-набора ⊆ scope активной спеки**: `git diff --cached --stat` сверить со списком файлов review-артефакта; смешение нескольких фаз/fix в одном staged-наборе без явного `bundled`-разрешения spec → **АВТОМАТИЧЕСКИ ОТКЛОНЕНО** (источник: CB ERRORS 2026-05-25/26).
8. **Goal-Level Data Completeness** — реальные данные для работы на месте (не только код, но и fixtures, seeds, миграции)
9. **Domain Model Completeness** — классификаторы, справочники, маппинг данных — всё заполнено?
10. **Date/Time Critical** — типы нормализованы перед сравнением, timezone-aware операции корректны
11. **Cross-project memory sync** — если изменение затрагивает >1 проект (CB / LMS / SPW / tg-bot): обновлены ли `~/projects/content-service\docs\cross-project\contracts\<свой>.md` + `CHANGELOG.md` (новая запись в начале) + `STATE.md` (если фаза/версия сменились)? Без update — **АВТОМАТИЧЕСКИ ОТКЛОНЕНО**. Триггеры cross-project — см. [cross-project-memory-standard.md](../claude-booster/references/cross-project-memory-standard.md) §2.
12. **Public API Contract Sync** — если изменены файлы публичного API (`app/api/v1/**`, `routes/**`, `app/api/auth/**`, `middleware.ts`, `proxy.ts`): обновлены ли spec/ADR/OpenAPI в **том же коммите**, выполнен ли cross-repo grep на старые пути (0 совпадений), нет ли hardcoded production URLs в `app/services/`/`app/core/`/`lib/`? Любой пробел — **АВТОМАТИЧЕСКИ ОТКЛОНЕНО**. Полный чеклист — [api-contract-rules.md §1-4, §11](../claude-booster/references/api-contract-rules.md). Для frontend-проектов (Next.js) дополнительно — [frontend-stack-rules.md §11](../claude-booster/references/frontend-stack-rules.md).

### MANDATORY-триггеры (review-gate **обязателен**, hotfix-исключения нет)
Любое из ниже — review-gate **до push**, даже в operator-driven smoke loop:
- Изменения auth/middleware (`middleware.ts`, `proxy.ts`, `app/api/auth/*`, `app/services/auth*`, `lib/auth/*`)
- Изменения публичного API: URL/HTTP-метод/request schema/response schema/status codes
- Cross-project зависимости (CB ↔ LMS ↔ SPW ↔ tg-bot): любое изменение опубликованных контрактов
- Миграции БД (Alembic upgrade/downgrade), DDL
- Изменения client/server component boundary в Next.js (перевод между server и client)
- Type assertions (`as Type`) добавлены вместо runtime-валидации внешних данных

«Hotfix во время smoke» — **не основание** обходить review-gate. Если нужна срочность — diagnostics через `/qa-fix`, фикс через `/executor-pro` + `/review-gate`.

## Контракт результата
- `Решение`: ПРИНЯТО или ОТКЛОНЕНО
- `Находки` — упорядочены по серьёзности
- `Блокирующие проблемы` — обязательные исправления
- `Улучшения без блокировки`
- `Необходимые тесты`
- `Operator handoff` — по [operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md). Категория А (рутинная проверка/тесты/lint/dev SQL) — агент выполняет сам, не спрашивает. Б (нет creds, prod, manual UI) — пошаговая инструкция. В (стратегическая развилка, необратимое действие) — `AskUserQuestion` с вариантами и рекомендацией. «Требуется ручная проверка» без классификации Б/В — дефект ревью.
- **Эмиссия ярлыка «оператор»/«категория Б» — только через Before-Б check** (по аналогии с tech-spec-composer/techlead-code-reviewer 2026-05-27). Прежде чем пометить шаг operator handoff блока как Б — прогнать через [operator-handoff-rules.md](../claude-booster/references/operator-handoff-rules.md) Before-Б check (5 п.). Dev-CLI / read-only SQL через MCP / LLM-computation / SDK-обёртка над 3rd-party API при наличии creds (gspread + SA JSON, `gh` CLI, `aws/gcloud/az`) — **категория А**. Б — только prod-write approval, отсутствие creds/2FA, manual UI без публичного API/SDK. «Upload в Google Sheets» при доступном SA JSON ≠ Б. Источник: skills-errors.md 2026-06-02 (recurrence класса 2026-05-27).

## Обновление реестра ошибок
При ОТКЛОНЕНО с серьёзными находками — записать в `{project}/docs/ai/ERRORS.md`:
```
| {дата} | {severity} | {класс} | {описание} | {prevention action} |
```
Классы: PROCESS, DATA, LOGIC, INTEGRATION (из Codex error governance).

## Правила решения
- ПРИНЯТО только если нет блокирующих проблем ни в одном из 12 измерений.
- ОТКЛОНЕНО если поведение неопределённо в production-critical path.
- ОТКЛОНЕНО если повторяется паттерн из реестра ошибок без соблюдения prevention action.
- Каждая находка обязательно содержит:
  - затронутый файл/путь
  - почему это важно
  - конкретное направление исправления
  - ссылка на измерение (1-10), которое нарушено

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
