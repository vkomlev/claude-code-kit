# C4-Light — лёгкая версия C4 для small projects

Для монолита / модульного монолита обычно достаточно **Level 1 (Context)** и **Level 2 (Container)**. Level 3 (Component) — только для сложных компонентов. Level 4 (Code) — не использовать (UML не окупается).

## Формат: текстом, не диаграммами

Для локальных проектов рисовать PlantUML / Mermaid необязательно. Текстовое описание в markdown читается быстрее и проще держать в актуальном состоянии. При желании — добавить Mermaid-диаграмму отдельной секцией.

## Level 1 — System Context

Что снаружи системы и как с ней взаимодействует.

```markdown
## C4-Context: <Имя системы>

### Акторы (люди)
- **Администратор** — управляет контентом через CLI/scripts
- **Автор курса** — заливает материалы через VK/TG

### Внешние системы
- **CMS / LMS** — источник истины по контенту (REST API)
- **Видеохранилище** — загрузка и хранение видео (OAuth, file upload)
- **Мессенджер** — канал уведомлений (bot API)
- **PostgreSQL `app`** — основная БД (схема `app_content`)

### Границы системы (что внутри)
ContentPipeline — оркестрация pipeline: ingest → normalize → enrich → publish → sync
```

## Level 2 — Container

Деплоируемые единицы: процессы, БД, очереди, frontend-приложения.

```markdown
## C4-Container: <Имя системы>

### Контейнеры

| Контейнер | Технология | Ответственность |
|-----------|------------|-----------------|
| CLI orchestrator | Python | запускает pipeline, CLI для ручных операций |
| Pipeline workers | Python | ingest/normalize/enrich/publish/sync stages |
| app_content DB | PostgreSQL | source-of-truth для публикаций и link_map |
| CMS API client | Python | чтение/запись в CMS / LMS |
| Video adapter | Python | upload видео, получение ссылок |

### Ключевые связи
- CLI → Pipeline workers (прямой вызов, in-process)
- Pipeline → app_content (SQLAlchemy + Alembic, schema=app_content)
- publish stage → CMS API (REST, auth Bearer)
- enrich stage → Video adapter (OAuth, файлы через requests)
```

## Level 3 — Component (опционально)

Только для сложных контейнеров. Пример — декомпозиция `Pipeline workers`:

```markdown
## C4-Component: Pipeline workers

- **IngestStage** — приём сырых материалов, нормализация метаданных
- **NormalizeStage** — приведение к каноническим schemas
- **EnrichStage** — догрузка видео/аудио через VK
- **PublishStage** — запись в app_content + CMS
- **SyncStage** — сверка source-of-truth с целевыми системами

Shared: `ContextAnchor`, `StageResult`, `BlastRadius` — общие контракты между stages.
```

## Правила для small projects

- **Не рисовать то, что не поможет принять решение.** Если Container-уровня достаточно — не делать Component.
- **Не плодить актёров.** Если у вас один оператор — один актёр «Оператор», а не «Admin + Author + Ops».
- **Включать версии контрактов и протоколов** только для внешних API.
- **Связи — конкретные.** Не «взаимодействует», а «POST /v2/publications через Bearer auth».
- **Хранить в `ARCHITECTURE.md`** в корне проекта, обновлять в рамках того же PR, что и изменения.

## Минимальный ARCHITECTURE.md

```markdown
# Architecture

## Overview
<1-2 параграфа: что делает система, на ком держится>

## C4-Context
<Level 1 из шаблона выше>

## C4-Container
<Level 2 из шаблона выше>

## Ключевые решения
- См. `docs/adr/`

## Quality Attributes (NFR)
- См. `references/nfr-categories.md` проекта или секцию ниже

## Boundaries & Non-goals
<что система явно НЕ делает, чтобы не лезли с запросами>
```
