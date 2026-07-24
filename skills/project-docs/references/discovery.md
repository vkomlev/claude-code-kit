# Discovery — чеклист сканирования проекта

Задача этапа: собрать карту проекта для последующей генерации документации.
Результат держим в рабочей памяти skill, не записываем на диск.

## 1. Корень проекта
- Аргумент команды: `/project-docs full /path/to/project`
- Или `pwd` (текущая директория)
- Проверить что есть хотя бы один из: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `.git/`

## 2. Стек технологий
Определить язык и фреймворк через маркер-файлы:

| Файл | Язык/экосистема |
|---|---|
| `package.json` | Node.js — смотреть `dependencies` и `scripts` |
| `pyproject.toml` | Python — `[project]` и `[tool.poetry]` |
| `requirements.txt` | Python — без poetry |
| `go.mod` | Go — `module` и `require` |
| `Cargo.toml` | Rust |
| `composer.json` | PHP |
| `Gemfile` | Ruby |
| `pom.xml` / `build.gradle` | Java/Kotlin |

Для Python дополнительно: FastAPI/Django/Flask/aiogram (поиск в `requirements.txt` или `pyproject.toml`).
Для Node: Next.js/Express/NestJS/aiogram-эквивалент.

## 3. Топ-уровневая структура
```bash
ls -la <root>
```
Выделить:
- Source dirs: `src/`, `app/`, `lib/`, `internal/`, `cmd/`
- Tests: `tests/`, `test/`, `__tests__/`, `spec/`
- Docs: `docs/`, `documentation/`
- Config: `config/`, `.config/`, `settings/`
- CI: `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`
- Infrastructure: `docker-compose.yml`, `Dockerfile`, `k8s/`, `terraform/`

## 4. Entry points
Glob-поиск типичных точек входа:
- Python: `main.py`, `app.py`, `manage.py`, `__main__.py`, `run.py`
- Node: `index.ts`, `index.js`, `server.ts`, `src/main.ts`
- Go: `cmd/*/main.go`
- FastAPI: ищем `app = FastAPI(`
- aiogram: ищем `Bot(token=` или `Dispatcher()`

## 5. Конфигурация и env
- `.env.example`, `.env.sample` — читать полностью, это карта env-переменных
- `config/`, `settings.py`, `config.yaml`
- Не читать `.env` (секреты)

## 6. База данных и миграции
- `alembic/` или `alembic.ini` → SQLAlchemy + Alembic
- `migrations/` → Django/Rails/Prisma
- `prisma/schema.prisma` → Prisma
- `schema.sql`, `*.sql` в корне → raw SQL
- Проверить наличие ORM моделей: `models/`, `entities/`

## 7. Существующая документация
Glob:
- `README*` (md, rst, txt)
- `CLAUDE*`, `AGENTS*`, `CONTEXT*`
- `docs/**/*.md`
- `CHANGELOG*`, `CONTRIBUTING*`, `LICENSE*`

Если есть — в режиме update их содержимое становится основой.

## 8. Команды
Источники команд:
- `package.json` → `scripts`
- `pyproject.toml` → `[tool.poetry.scripts]` или `[project.scripts]`
- `Makefile` → targets
- `justfile` → recipes
- `docker-compose.yml` → services и их команды
- `.github/workflows/*.yml` → CI шаги (для prod/test команд)

Собрать самые частые: dev, test, build, lint, migrate, deploy.

## 9. Git-контекст
```bash
git log --oneline -20
git log --pretty=format:"%h %s" --since="1 month ago" | head -30
```
Цель: понять области активной разработки. Эти области должны быть точнее описаны в CLAUDE.md.

## 10. Известные интеграции
Поиск по имени файлов и зависимостей:
- Redis: `redis` в deps или `REDIS_URL` в env
- PostgreSQL: `psycopg`, `asyncpg`, `pg` в deps
- Celery/RQ/BullMQ: очереди задач
- S3/MinIO: object storage
- Sentry/Datadog: observability
- Telegram: `aiogram`, `telegraf`, `grammy`

## Gap-детектор
Если discovery не смог определить:
- Назначение проекта (нет README, нет описания в package.json/pyproject)
- Как запустить (нет scripts, нет Makefile, нет инструкций)
- Режимы работы (нет docker-compose.yml, нет CI)

→ в Шаге 2 обязательно спросить пользователя.
