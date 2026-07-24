# Шаблоны AI-слоя документации

Шаблоны для `CLAUDE.md` и `docs/ai/*`. Все плейсхолдеры в `{{двойных фигурных скобках}}`.

## Принципы AI-документации

1. **Плотность фактов**: каждая строка должна отвечать "удалил — Claude ошибётся?"
2. **Без мотивации**: никаких "этот проект поможет команде..." — только факты
3. **Ссылки вместо копии**: `см. docs/ai/architecture.md` лучше, чем повтор
4. **Конкретика**: имена файлов, функций, env-переменных, команд
5. **Без очевидного**: не писать "используйте типы Python" — это глобальный контекст

---

## Шаблон `CLAUDE.md`

```markdown
# {{Project Name}}

## Project Overview
{{1-2 строки: что делает проект, главная ценность. Пример:
"FastAPI сервис для импорта и валидации уроков из CSV. Точка входа для контент-пайплайна."}}

## Tech Stack
- **Язык**: {{Python 3.11}}
- **Фреймворк**: {{FastAPI 0.110, SQLAlchemy 2.0, Alembic}}
- **БД**: {{PostgreSQL 15, Redis 7}}
- **Очереди**: {{Celery / RQ / нет}}
- **Тесты**: {{pytest, pytest-asyncio}}
- **Деплой**: {{Docker, docker-compose}}

## Architecture
{{Краткое описание: 2-4 главных компонента и как они связаны.
Пример:
- `app/api/` — HTTP endpoints (FastAPI routers)
- `app/services/` — бизнес-логика, отвязанная от HTTP
- `app/models/` — SQLAlchemy модели
- `app/workers/` — Celery таски для долгих операций}}

Детали: [docs/ai/architecture.md](docs/ai/architecture.md)

## Directory Structure
```
app/
├── api/v1/          # HTTP роуты, по одному файлу на ресурс
├── services/        # Бизнес-логика
├── models/          # SQLAlchemy ORM
├── schemas/         # Pydantic DTO для API
├── workers/         # Celery таски
└── core/            # config, db-session, security
migrations/          # Alembic миграции
tests/               # pytest
```

## Key Commands
```bash
# Dev
uvicorn app.main:app --reload             # dev сервер на :8000
alembic upgrade head                       # применить миграции
alembic revision --autogenerate -m "..."   # новая миграция

# Test
pytest                                     # все тесты
pytest tests/api/ -k test_lessons          # выборочно

# Lint
ruff check app/
mypy app/
```

## Coding Conventions
{{Только неочевидное. Примеры:
- Все async handlers: `async def`, никогда `def` в FastAPI роутерах
- Миграции никогда не редактируем после применения на staging
- SQL только через ORM, raw SQL только в `app/core/db.py`}}

## Workflows
{{Типовые сценарии с указателями. Примеры:
- **Новый эндпоинт**: добавить schema в `app/schemas/` → router в `app/api/v1/` → service в `app/services/`
- **Изменение модели БД**: правка `app/models/` → `alembic revision --autogenerate` → ревью миграции → `alembic upgrade head`
- **Перед рефакторингом `services/`**: запустить `pytest tests/services/` и проверить зелёный}}

## References
- [docs/ai/architecture.md](docs/ai/architecture.md) — компоненты и потоки данных
- [docs/ai/data-model.md](docs/ai/data-model.md) — схемы таблиц и контракты API
- [docs/ai/workflows.md](docs/ai/workflows.md) — пошаговые типовые флоу
- [docs/ai/errors.md](docs/ai/errors.md) — known issues и антипаттерны
- [docs/ai/glossary.md](docs/ai/glossary.md) — доменные термины

## Environment Variables
{{Только ИМЕНА переменных, никогда значения. Ссылка на .env.example.
Пример:
См. `.env.example`. Критичные: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.}}
```

---

## Шаблон `docs/ai/architecture.md`

```markdown
# Архитектура

## Компоненты
{{Развёрнутый список компонентов с описанием 2-4 строки каждый.
Для каждого: назначение, входы, выходы, зависимости.}}

## Потоки данных
{{Текстом или ASCII-диаграммой опишите 2-3 главных потока.
Пример:
1. **Импорт урока**: HTTP POST /api/v1/lessons → LessonService.create → validate_csv() → LessonModel → Celery task "index_lesson" → Elasticsearch
2. **Поиск**: HTTP GET /api/v1/lessons?q=... → SearchService → Elasticsearch → DTO через LessonSchema}}

## Границы и инварианты
{{Что НЕ пересекает какие слои. Пример:
- `models/` никогда не импортируют `api/` и `services/`
- `api/` не пишут напрямую в БД, только через `services/`
- Внешние HTTP-клиенты живут в `app/integrations/`, не в `services/`}}

## Точки расширения
{{Где безопасно добавлять новое. Пример:
- Новый endpoint → создать файл в `app/api/v1/` и зарегистрировать в `app/api/v1/__init__.py`
- Новая фоновая задача → `app/workers/tasks.py`}}
```

---

## Шаблон `docs/ai/data-model.md`

```markdown
# Модель данных

## Таблицы
{{Для каждой таблицы:
- Имя
- Назначение (1 строка)
- Ключевые поля и их типы
- Foreign keys
- Индексы (если нетривиальные)}}

### {{table_name}}
- **Назначение**: {{1 строка}}
- **PK**: {{id UUID}}
- **Поля**: {{title VARCHAR, created_at TIMESTAMPTZ, status ENUM(draft|published|archived)}}
- **FK**: {{author_id → users.id}}
- **Индексы**: {{idx_status_created — для сортировки по статусу}}

## API-контракты
{{Для каждого ключевого endpoint:
- Метод + путь
- Request schema
- Response schema
- Коды ошибок}}

### POST /api/v1/lessons
- **Request**: `LessonCreateSchema` ({{см. app/schemas/lesson.py:LessonCreate}})
- **Response 201**: `LessonSchema`
- **Errors**: 400 (validation), 409 (duplicate slug), 422 (invalid CSV)

## Enums и константы
{{Значения enum и что каждое означает.
LessonStatus: draft (не опубликован), published (виден пользователям), archived (скрыт, не удалён)}}
```

---

## Шаблон `docs/ai/workflows.md`

```markdown
# Типовые флоу разработки

## Добавление нового HTTP-эндпоинта
1. Описать request/response в `app/schemas/<resource>.py`
2. Добавить router-функцию в `app/api/v1/<resource>.py`
3. Бизнес-логика — в `app/services/<resource>_service.py`
4. Тест — `tests/api/test_<resource>.py`
5. Запустить `pytest tests/api/test_<resource>.py`

## Изменение схемы БД
1. Править модель в `app/models/`
2. `alembic revision --autogenerate -m "описание"`
3. Прочитать сгенерированную миграцию в `migrations/versions/` — проверить downgrade
4. `alembic upgrade head` на dev
5. Прогнать `pytest tests/db/`

## Добавление Celery-задачи
1. Описать в `app/workers/tasks.py`
2. Зарегистрировать в `celery_app.autodiscover_tasks`
3. Вызов из сервиса: `task.delay(...)`, результат через `AsyncResult`

## {{Доменно-специфичный флоу}}
{{Что из особенных для этого проекта сценариев стоит формализовать.}}
```

---

## Шаблон `docs/ai/errors.md`

```markdown
# Known issues и антипаттерны

## Антипаттерны
- **Не делать**: {{импортировать `models/` внутри `api/` — нарушает слои}}
- **Вместо этого**: {{работать через сервис}}

## Типовые ошибки
### {{Кратко: ошибка}}
- **Симптом**: {{что видно в логах/UI}}
- **Причина**: {{почему случается}}
- **Решение**: {{как исправить}}

### Пример: "session is closed" в Celery task
- **Симптом**: `InvalidRequestError: Session is closed` при работе с ORM внутри таска
- **Причина**: сессия из HTTP-запроса не переживает переход в Celery worker
- **Решение**: в тасках открывать новую сессию через `with SessionLocal() as session:`

## Гейты
{{Что проверять перед коммитом/PR:
- `pytest` зелёный
- `alembic upgrade head` без конфликтов
- `ruff check app/` без ошибок}}
```

---

## Шаблон `docs/ai/glossary.md`

```markdown
# Глоссарий

Доменные термины проекта и их смысл в коде.

## {{Term}}
{{Определение 1-2 строки. Где встречается в коде.}}

### Пример
**Lesson** — единица учебного контента в учебной платформе. Представлена `app/models/lesson.py:Lesson`. Не путать с **Course** (контейнер уроков) и **Unit** (логическая группа внутри course).

**Slug** — человекочитаемый идентификатор урока, уникален в рамках course. Генерируется из title через `app/utils/slug.py:slugify`.
```

---

## Шаблон `AGENTS.md`

Режим Unix (симлинк):
```bash
ln -sf CLAUDE.md AGENTS.md
```

Режим Windows (копия):
```markdown
<!-- AUTO-SYNC: этот файл — копия CLAUDE.md. При изменении CLAUDE.md обновите и этот файл. -->

{{Содержимое CLAUDE.md}}
```
