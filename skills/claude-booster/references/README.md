# Инфраструктура claude-booster — карта references

Навигация по reference-файлам. Источник истины для инфраструктуры skills IDE_booster.

## Основные файлы

| Файл | Назначение | Кто читает |
|---|---|---|
| [`standard.md`](standard.md) | Единый стандарт структуры skill (секции, frontmatter, язык) | `/claude-booster` Режим A при аудите |
| [`audit-checklist.md`](audit-checklist.md) | Чеклист S1/S2/S3 проверки skill | `/claude-booster` при аудите, `/response-quality-coach` при калибровке |
| [`skills-registry.md`](skills-registry.md) | Ролевая модель: какой skill для чего + матрицы QA/review | **Все планировщики** (spec-writer, change-plan-architect, tech-spec-composer, ceo-review, eng-review) |
| [`skills-errors.md`](skills-errors.md) | Реестр OPEN/FIXED дефектов skills (формат записи, классы, жизненный цикл) | `/response-quality-coach` пишет OPEN, `/claude-booster` Режим D обрабатывает |
| [`rca-protocol.md`](rca-protocol.md) | Протокол 5 Whys + классификация корня + anti-bloat check | `/claude-booster` Режим D, любой skill перед исправлением инцидента |
| [`booster-shared.md`](booster-shared.md) | Общие правила для claude/cursor/codex booster'ов (improvement loop, UTF-8, ownership) | `/claude-booster`, `/cursor-booster`, `/codex-booster` |
| [`improvement-log.md`](improvement-log.md) | Хронологический лог изменений skills (вводится `/claude-booster`) | Оператор при ревизии истории, `/retro` при недельном обзоре |

## Специализированные

| Файл | Назначение |
|---|---|
| [`ai-humanness.md`](ai-humanness.md) | Чеклист человечности для копирайтерских skills (12 AI-маркеров). Используется `digital-copywriter`, `travel-copywriter`. |
| [`content-skill-template.md`](content-skill-template.md) | Шаблон для генерации нового контент-skill. Используется `/claude-booster` Режим C. |
| [`backups/`](backups/) | Резервные копии SKILL.md перед правками (формат `{name}-YYYY-MM-DD.md`) |

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
skills-errors.md / ANSWER_ERRORS.md (OPEN)
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

### Cross-platform улучшения
```
booster-shared.md (общий источник истины)
    ↑
    ├── claude-booster (Claude skills)
    ├── cursor-booster (Cursor agents)
    └── codex-booster (Codex skills)
```

## Когда править что

- **Новый паттерн обнаружен в дефекте**: запись в `skills-errors.md` → RCA → правка SKILL.md или references
- **Дубль в 3+ booster'ах**: вынести в `booster-shared.md`, ссылка в каждом booster'е
- **Новое правило для планировщиков**: дополнить `skills-registry.md`, не копировать в каждый планировщик
- **Новая таксономия дефектов**: в `skills-errors.md` + синхронизировать в `defect-taxonomy.md` (response-quality-coach)
- **Правка standard**: `standard.md` + пересверить `audit-checklist.md`

## Якоря для новых инженеров

1. Хочу понять экосистему skills → начать с [`skills-registry.md`](skills-registry.md)
2. Хочу исправить дефект в skill → [`rca-protocol.md`](rca-protocol.md) + [`skills-errors.md`](skills-errors.md) для формата записи
3. Хочу создать новый skill → [`standard.md`](standard.md) + [`audit-checklist.md`](audit-checklist.md) + Режим A claude-booster
4. Хочу понять историю → [`improvement-log.md`](improvement-log.md)
