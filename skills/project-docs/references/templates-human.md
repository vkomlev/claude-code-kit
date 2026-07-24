# Шаблоны human-слоя документации

Шаблоны для `README.md` и `docs/*`. Плейсхолдеры в `{{двойных фигурных скобках}}`.

## Принципы human-документации

1. **Читатель не знает проекта** — писать как для нового человека
2. **Быстрый старт первым** — максимум 5 минут от клона до запуска
3. **Конкретные команды** — копипаст, а не описание
4. **Примеры важнее теории** — 1 пример лучше 3 абзацев объяснения
5. **Устранение, а не идеализация** — troubleshooting реальных проблем
6. **Не дублировать CLAUDE.md** — README это нарратив, CLAUDE.md это справочник

---

## Шаблон `README.md`

```markdown
# {{Project Name}}

{{Одна строка: что это и для кого. Пример:
"Сервис импорта уроков из CSV с валидацией и индексацией в Elasticsearch."}}

{{Опционально badges: сборка, покрытие, версия}}

## Что это

{{2-3 абзаца для человека:
- Какую проблему решает
- Кто целевой пользователь (разработчик? админ? конечный юзер?)
- Чем отличается от альтернатив (если актуально)}}

## Быстрый старт

Минимальные шаги от нуля до запуска:

```bash
# 1. Клон
git clone {{repo-url}}
cd {{project-dir}}

# 2. Зависимости
{{pip install -e ".[dev]"}}
# или: {{npm install, poetry install, go mod download}}

# 3. Конфигурация
cp .env.example .env
# Отредактируйте .env: как минимум {{DATABASE_URL, SECRET_KEY}}

# 4. База данных (если применимо)
{{alembic upgrade head}}

# 5. Запуск
{{uvicorn app.main:app --reload}}
```

Откройте {{http://localhost:8000}} — готово.

## Режимы запуска

### Development
```bash
{{uvicorn app.main:app --reload --port 8000}}
```
Авто-перезагрузка при изменении кода. Не использовать в проде.

### Production
```bash
{{gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker}}
```
См. [docs/configuration.md](docs/configuration.md) — полный список env-переменных.

### Docker
```bash
docker-compose up -d
```
Поднимает {{app + postgres + redis}}. Логи: `docker-compose logs -f app`.

### Тесты
```bash
pytest
pytest --cov=app  # с покрытием
```

## Документация

- [docs/install.md](docs/install.md) — детальная установка и требования
- [docs/usage.md](docs/usage.md) — команды, примеры использования, API
- [docs/configuration.md](docs/configuration.md) — все env-переменные и настройки
- [docs/troubleshooting.md](docs/troubleshooting.md) — типовые проблемы и решения

## Стек
{{Python 3.11, FastAPI, PostgreSQL, Redis, Docker}}

## Лицензия
{{MIT / Proprietary / ...}}

## Контакты
{{Владелец проекта, канал поддержки}}
```

---

## Шаблон `docs/install.md`

```markdown
# Установка

## Требования

### Обязательные
- {{Python 3.11+}}
- {{PostgreSQL 15+}}
- {{Redis 7+}}
- {{Git}}

### Опционально
- {{Docker 24+ и Docker Compose v2 — для быстрого старта}}
- {{Node.js 20+ — только если нужен фронтенд}}

## Пошаговая установка

### 1. Системные зависимости

**macOS:**
```bash
brew install python@3.11 postgresql@15 redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv postgresql-15 redis-server
```

**Windows:**
{{рекомендация по WSL2 или инструкции для нативной установки}}

### 2. Клонирование и окружение
```bash
git clone {{repo-url}}
cd {{project-dir}}

python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

### 3. База данных
```bash
createdb {{db_name}}
cp .env.example .env
# Отредактируйте DATABASE_URL в .env
alembic upgrade head
```

### 4. Проверка установки
```bash
pytest tests/smoke/
uvicorn app.main:app --reload
curl http://localhost:8000/health
# Ожидается: {"status": "ok"}
```

## Альтернатива: Docker
```bash
docker-compose up -d
docker-compose exec app alembic upgrade head
```
```

---

## Шаблон `docs/usage.md`

```markdown
# Использование

## Основные команды

### Dev-сервер
```bash
uvicorn app.main:app --reload
```
По умолчанию на :8000. Swagger UI: `/docs`, ReDoc: `/redoc`.

### Миграции
```bash
alembic revision --autogenerate -m "описание"  # создать
alembic upgrade head                            # применить все
alembic downgrade -1                            # откатить одну
alembic history                                 # список
```

### Тесты
```bash
pytest                                   # все
pytest tests/api/                        # папка
pytest -k "test_lesson_create"           # по имени
pytest --cov=app --cov-report=html       # с покрытием
```

### Линт и форматирование
```bash
ruff check app/
ruff format app/
mypy app/
```

## Примеры использования API

### Создать урок
```bash
curl -X POST http://localhost:8000/api/v1/lessons \
  -H "Content-Type: application/json" \
  -d '{"title": "Intro", "slug": "intro", "course_id": "..."}'
```

### Получить список
```bash
curl http://localhost:8000/api/v1/lessons?limit=10
```

### {{Импорт из CSV}}
```bash
curl -X POST http://localhost:8000/api/v1/lessons/import \
  -F "file=@lessons.csv" \
  -H "Authorization: Bearer {{TOKEN}}"
```

## CLI (если есть)
```bash
python -m app.cli import-lessons lessons.csv
python -m app.cli reindex
```
```

---

## Шаблон `docs/configuration.md`

```markdown
# Конфигурация

Все настройки через env-переменные. Файл `.env` в корне проекта.
Пример с дефолтами: `.env.example`.

## Обязательные

| Переменная | Описание | Пример |
|---|---|---|
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql://user:pass@localhost:5432/db` |
| `SECRET_KEY` | Ключ для подписи JWT | случайная строка 64+ символов |
| `REDIS_URL` | Строка подключения к Redis | `redis://localhost:6379/0` |

## Опциональные

| Переменная | Дефолт | Описание |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `CORS_ORIGINS` | `[]` | Список разрешённых origins через запятую |
| `SENTRY_DSN` | — | Если задан — ошибки летят в Sentry |

## Профили окружений
- **dev**: `.env.dev` — локальная разработка, DEBUG=true
- **staging**: задаётся переменными среды CI
- **prod**: задаётся secrets manager'ом, никогда не коммитится

## Секреты
Никогда не коммитить реальные значения. `.env` в `.gitignore`.
Для прод используйте {{AWS Secrets Manager / Vault / ...}}.
```

---

## Шаблон `docs/troubleshooting.md`

```markdown
# Troubleshooting

## "Can't connect to database"
**Симптом**: ошибка при старте `sqlalchemy.exc.OperationalError: could not connect to server`

**Причины и решения**:
1. PostgreSQL не запущен → `brew services start postgresql` / `sudo systemctl start postgresql`
2. Неверный `DATABASE_URL` → проверьте host, port, user, password
3. База не создана → `createdb {{db_name}}`

## "Migration conflict"
**Симптом**: `alembic upgrade head` падает с конфликтом

**Решение**:
1. `alembic history` — посмотреть граф
2. Если две ветки миграций → `alembic merge -m "merge" <rev1> <rev2>`
3. Применить: `alembic upgrade head`

## "Redis connection refused"
{{стандартный чеклист запуска}}

## "Module not found after pip install"
**Причина**: не активирован venv или установка была в системный Python.
**Решение**: `source .venv/bin/activate` перед всеми командами.

## {{Проектно-специфичные проблемы}}
{{Что наблюдалось у команды.}}

## Куда обращаться
- Issues: {{repo-url}}/issues
- Чат: {{Slack / Telegram}}
- Владелец: {{name / email}}
```
