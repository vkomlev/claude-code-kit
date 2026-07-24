# Инфраструктура claude-booster — карта references

Навигация по reference-файлам. Источник истины для инфраструктуры skills Claude Code.

## Основные файлы

| Файл | Назначение | Кто читает |
|---|---|---|
| [`standard.md`](standard.md) | Единый стандарт структуры skill (секции, frontmatter, язык) | `/claude-booster` Режим A при аудите |
| [`audit-checklist.md`](audit-checklist.md) | Чеклист S1/S2/S3 проверки skill | `/claude-booster` при аудите, `/response-quality-coach` при калибровке |
| [`skills-registry.md`](skills-registry.md) | Ролевая модель: какой skill для чего + матрицы QA/review | **Все планировщики** (spec-writer, change-plan-architect, tech-spec-composer, ceo-review, eng-review) |
| [`skills-errors.md`](skills-errors.md) | Реестр OPEN/FIXED дефектов skills (формат записи, классы, жизненный цикл) | `/response-quality-coach` пишет OPEN, `/claude-booster` Режим D обрабатывает |
| [`rca-protocol.md`](rca-protocol.md) | Протокол 5 Whys + классификация корня + anti-bloat check | `/claude-booster` Режим D, любой skill перед исправлением инцидента |
| [`booster-shared.md`](booster-shared.md) | Общие правила booster-skills (improvement loop, UTF-8, ownership) | `/claude-booster` |
| [`improvement-log.md`](improvement-log.md) | Хронологический лог изменений skills (вводится `/claude-booster`) | Оператор при ревизии истории, `/retro` при недельном обзоре |
| [`model-routing.md`](model-routing.md) | Критерии выбора контекстного уровня (minimal/standard/full) | Планировщики, `/ai-orchestrator` |
| [`operator-handoff-rules.md`](operator-handoff-rules.md) | Стандарт делегирования действий между агентом и оператором | Все skills (через ссылку из CLAUDE.md) |
| [`skill-routing-standard.md`](skill-routing-standard.md) | Маршрутизация под-задач плана к skill-исполнителям | `/spec-writer`, `/change-plan-architect`, `/tech-spec-composer` |
| [`project-brief-template.md`](project-brief-template.md) | Шаблон брифа проекта для ревью плана | `/ceo-review`, `/eng-review` |
| [`auto-audit-config.md`](auto-audit-config.md) | Конфигурация регулярного аудита skills (Режим E) | `/claude-booster` Режим E |
| [`scheduled-tasks-windows.md`](scheduled-tasks-windows.md) | Грабли плановых заданий Windows Task Scheduler | Любой skill, заводящий плановое задание |

## Специализированные (стек и контент)

| Файл | Назначение |
|---|---|
| [`ai-humanness.md`](ai-humanness.md) | Чеклист человечности для копирайтерских skills (14 AI-маркеров). Используется копирайт-скиллами (напр. `travel-copywriter`). |
| [`content-skill-template.md`](content-skill-template.md) | Шаблон для генерации нового контент-skill. Используется `/claude-booster` Режим C. |
| [`api-contract-rules.md`](api-contract-rules.md) | Правила публичных API-контрактов (HTTP/REST). Для backend/full-stack задач. |
| [`frontend-stack-rules.md`](frontend-stack-rules.md) | Правила Next.js + TypeScript + React. Для frontend-задач. |
| [`telegram-bot-rules.md`](telegram-bot-rules.md) | Правила Telegram-ботов (aiogram + aiogram-dialog + Redis FSM). |
| [`ux-flow-rules.md`](ux-flow-rules.md) | Правила сокращения целевого пути пользователя (UX-flow). |

> Примечание: при правках skills `/claude-booster` кладёт резервные копии в `references/backups/` — эта папка создаётся по мере работы.

## Потоки и связи

### Pipeline работы над задачей
```
spec-writer → change-plan-architect → tech-spec-composer → executor → review-gate → ship
                                                                    ↓
                                              Все читают skills-registry.md
```

### Контур обратной связи (feedback loop)
```
дефект обнаружен
    ↓
response-quality-coach (классификация + 5 Whys)
    ↓
skills-errors.md (OPEN)
    ↓
claude-booster Режим D
    ├── rca-protocol.md (5 Whys → instruction/context/execution gap)
    ├── anti-bloat check (5 вопросов)
    └── минимальная правка SKILL.md
    ↓
skills-errors.md (FIXED) + improvement-log.md
    ↓
retro (еженедельный обзор FIXED-записей)
```

## Когда править что

- **Новый паттерн обнаружен в дефекте**: запись в `skills-errors.md` → RCA → правка SKILL.md или references
- **Новое правило для планировщиков**: дополнить `skills-registry.md`, не копировать в каждый планировщик
- **Правка standard**: `standard.md` + пересверить `audit-checklist.md`

## Якоря для новых инженеров

1. Хочу понять экосистему skills → начать с [`skills-registry.md`](skills-registry.md)
2. Хочу исправить дефект в skill → [`rca-protocol.md`](rca-protocol.md) + [`skills-errors.md`](skills-errors.md) для формата записи
3. Хочу создать новый skill → [`standard.md`](standard.md) + [`audit-checklist.md`](audit-checklist.md) + Режим A claude-booster
4. Хочу понять историю → [`improvement-log.md`](improvement-log.md)
