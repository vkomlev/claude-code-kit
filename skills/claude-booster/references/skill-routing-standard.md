# Skill-routing standard (общий reference)

**Версия:** 1.0
**Дата:** 2026-04-27
**Применяется в:** `/spec-writer`, `/change-plan-architect`, `/tech-spec-composer`
**Источник правды по списку skills:** `~/.claude/skills/claude-booster/references/skills-registry.md`

## Назначение

Любой плановый артефакт (спек, план изменений, ТЗ) должен явно маршрутизировать каждую под-задачу к конкретному skill-исполнителю. Без этого артефакт нельзя считать готовым к передаче — следующему агенту/чату непонятно, кто реально работает над каждым пунктом.

## 1. Инвариант (обязательный)

**Артефакт без явной маршрутизации skill-исполнителей считается NEEDS-MORE-INFO, не COMPLETE.**

Уровень требования зависит от типа артефакта:

| Артефакт | Уровень детализации |
|---|---|
| **Спек** (`/spec-writer`) | Один skill-исполнитель на каждую фазу/основной шаг плана; для multi-phase спеков — мастер-таблица |
| **План изменений** (`/change-plan-architect`) | Мастер-таблица: каждая под-задача каждой фазы → главный исполнитель + ревью/контроль |
| **ТЗ** (`/tech-spec-composer`) | Inline-маркер `**Исполнитель:** /skill-name` на каждой существенной под-задаче (раздел/параграф); парный `**Ревью:** /skill-name` — на security-/contract-/migration-критичных путях |

## 2. Формат мастер-таблицы (для change-plan-architect)

Markdown-таблица с минимум 5 колонками:

```
| Фаза | Под-задача | Главный исполнитель | Ревью / контроль | Примечания |
|---|---|---|---|---|
| Y-1 | Миграции БД (M1-M5) | **PRO** | DB → PRR → RG | DB-check после каждой миграции |
| Y-1 | magic_link_service | **FAPI** | TLR | atomic UPDATE…WHERE |
```

Сокращения skills (декларируются в начале раздела маршрутизации):

| Сокр. | Skill | Когда |
|---|---|---|
| **PRO** | `/executor-pro` | Security/contracts/migrations/race conditions |
| **LITE** | `/executor-lite` | UI-формы, конфиги, scripted задачи |
| **FAPI** | `/fastapi-api-developer` | FastAPI + PostgreSQL backend |
| **TGUX** | `/telegram-ux-flow-designer` | aiogram-dialog UX |
| **DB** | `/db-check` | Pre/post-миграция, read-only DBA |
| **QA** | `/qa-fix` | Тесты + bug fixes |
| **PRR** | `/pr-review` | Pre-landing review PR |
| **TLR** | `/techlead-code-reviewer` | Security/architecture critical review |
| **RG** | `/review-gate` | Final PASS/FAIL gate перед merge |
| **EG** | `/encoding-guard` | UTF-8 sanity |
| **CA** | `/context-auditor` | Соответствие исходным целям |
| **TS** | `/tech-spec-composer` | ТЗ для дочерних под-задач |
| **SHIP** | `/ship` | Release workflow |
| **TGD** | `/travel-copywriter`/etc. | Контент по доменам |

Расширять список при необходимости из актуального `skills-registry.md`.

## 3. Inline-маркеры (для tech-spec-composer)

Каждый существенный параграф ТЗ имеет минимум одну строку:

```markdown
### 4.1. Заголовок под-задачи

**Исполнитель:** `/executor-pro` (security-критичный путь, нужны race-condition-aware UPDATE)
**Ревью:** `/techlead-code-reviewer` (HMAC verify + crypto)

Описание под-задачи...
```

Если задача рутинная и не требует пары — `**Ревью:**` опционален. Если задача требует пары (см. §5) — `**Ревью:**` обязателен.

## 4. Запрещённые формулировки

- ❌ «разработчик», «программист», «исполнитель», «agent», «AI», «ассистент»
- ❌ «команда», «инженер», «специалист»
- ❌ Без указания skill вообще

Только конкретные имена skills из `skills-registry.md`. Если подходящего spec-skill нет:
- ✅ `**Исполнитель:** /executor-pro` (с обоснованием почему generic)
- ✅ `**Исполнитель:** manual` (для оператор-задач: DNS, VPS provisioning, content review)

## 5. Обязательные парные связки

Под-задачи следующих типов **ДОЛЖНЫ** иметь явный `**Ревью:**`/контроль:

| Тип под-задачи | Главный | Парный ревьюер / контроль |
|---|---|---|
| DB-миграция | `/executor-pro` или `/fastapi-api-developer` | `/db-check` (pre + post) → `/pr-review` → `/review-gate` |
| Auth / session / crypto / Fernet / HMAC | `/executor-pro` | `/techlead-code-reviewer` (обязателен) |
| Контракты API (новые endpoints) | `/fastapi-api-developer` | `/pr-review` (минимум) |
| Race conditions / concurrent flow | `/executor-pro` | `/techlead-code-reviewer` |
| IDOR / RBAC | `/executor-pro` | `/techlead-code-reviewer` + `/qa-fix` (sweep test) |
| TG bot dialogs (aiogram-dialog) | `/telegram-ux-flow-designer` + `/executor-pro` | `/pr-review` |
| Финальный merge фазы | — | `/review-gate` + `/context-auditor` |
| Production rollout / release | `/ship` | `/review-gate` |

## 6. Cross-cutting skills (всегда упоминаются отдельной секцией)

В мастер-таблице или ТЗ обязателен sub-раздел «Cross-cutting / параллельные skills», где упоминаются:

- **`/encoding-guard`** — после правок RU-текстов в HTML/SQL/markdown
- **`/context-auditor`** — перед merge каждой фазы (артефакт vs исходные цели)
- **`/tech-spec-composer`** — для написания ТЗ дочерних под-задач до старта фазы
- **`/response-quality-coach`** — при возникновении skill-инцидента
- **`/claude-booster`** — для усиления skills/permissions/MCP по итогам ретроспективы

## 7. Sub-tasks vs phase-level

| Артефакт | Минимум | Можно опустить |
|---|---|---|
| Спек (`/spec-writer`) | Один skill на фазу/основной шаг | Sub-task детализация (это работа `/change-plan-architect`/`/tech-spec-composer`) |
| План (`/change-plan-architect`) | Под-задачи каждой фазы | — (всё детализируется) |
| ТЗ (`/tech-spec-composer`) | Inline-маркер на каждый существенный параграф | Тривиальные boilerplate (импорты, форматирование) |

## 8. Когда НЕ применяется этот стандарт

- Quick-fix задачи (одна правка, один файл, один skill) — достаточно шапочного «Целевой исполнитель»
- Reports/audits/reviews (read-only артефакты без implementation roadmap)
- Документация без implementation-плана
- Memory entries / personal notes

Для таких артефактов skill-routing избыточен.

## 9. Anti-bloat правила

- **Не дублировать** содержание этого стандарта в каждом SKILL.md — только ссылка
- **Не разрастать** список сокращений в каждом артефакте — использовать единый список из §2 (расширять только при необходимости)
- **Не множить** парные связки сверх §5 без явной причины

## 10. История изменений

- **v1.0** — стандарт создан после того, как несколько booster-skill'ов имели разрозненные слабые требования о skill-routing. Anti-bloat решение: единый reference + 1-3 строки усиления в каждом skill вместо клонирования требования.

## 11. Связанные документы

- `~/.claude/skills/claude-booster/references/skills-registry.md` — актуальный список skills
- `~/.claude/skills/claude-booster/references/standard.md` — общий стандарт skills
- `~/.claude/skills/claude-booster/references/booster-shared.md` — общие правила
