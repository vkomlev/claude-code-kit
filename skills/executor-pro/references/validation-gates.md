# Validation gates

Обязательные проверки перед handoff в `/review-gate`. Каждый gate имеет чёткий критерий PASS/FAIL.

## Feedback loop

**Паттерн:** run validator → на FAIL точечный fix → re-run. Максимум 2 итерации на один класс ошибки.

На 3-й итерации того же класса ошибки — **эскалация** (см. escalation-triggers.md), не третья попытка.

## Базовые gates (все задачи)

### G1. Lint / format
- **Python:** `ruff check` или `black --check` + `ruff` (если настроено в проекте)
- **Критерий PASS:** exit 0, нет новых warnings в затронутых файлах
- **FAIL → fix:** применить автоформатирование, повторить

### G2. Type check
- **Python:** `mypy <module>` для затронутого пакета
- **Критерий PASS:** нет новых ошибок типизации в diff
- **FAIL → fix:** добавить недостающие аннотации; если тип реально некорректен — исправить сигнатуру

### G3. Unit tests в затронутой области
- `pytest <tests-dir> -x -q` по ближайшему scope
- **Критерий PASS:** все тесты проходят, новые тесты добавлены
- **FAIL → fix:** локализовать причину; если массовая регрессия — эскалация

### G4. Regression test
- Обязателен для bugfix, желателен для feature
- **Критерий PASS:** тест падает на pre-fix коде, проходит на post-fix
- Демонстрация: `git stash && pytest <test> -x` (должен упасть), `git stash pop && pytest <test> -x` (должен пройти)
- **FAIL → fix:** тест слишком high-level или ловит не тот дефект — переписать на правильный уровень абстракции

## БД gates (если затронуты миграции/схема)

### G5. Alembic isolation
- Проверить `version_table_schema='<ваша-схема>'` в `env.py`
- `alembic history` показывает только миграции вашей схемы
- **Критерий PASS:** `public.alembic_version` не упоминается в diff миграций
- **FAIL:** статус `NOT_READY`, не продолжать

### G6. Migration replay/rollback
- `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`
- **Критерий PASS:** обе миграции (up и down) идемпотентны
- **FAIL → fix:** добавить недостающие операции в downgrade или сделать миграцию idempotent

### G7. Cross-schema safety
- `grep -rE "public\.|SET search_path" migrations/versions/<new>.py`
- **Критерий PASS:** никаких операций над схемами вне вашей рабочей схемы
- **FAIL:** статус `NOT_READY`, эскалация

## Pipeline gates (если затронут orchestration)

### G8. Blast-radius continuity
- Smoke-тест: при пустом upstream selection downstream write **не запускается**
- **Критерий PASS:** логи показывают `skip (empty effective set)`, БД без записей
- **FAIL → fix:** добавить guard, не заглушить логом

### G9. No fabricated IDs
- `grep -E "batch_id\s*=\s*0|fake_|sentinel_|FK=-1" <changed-files>`
- **Критерий PASS:** нет fabricated identifiers в коде правки
- **FAIL → fix:** использовать реальные сущности или отложить до создания источника ID

## Meta-gate

### G10a. Verification claim integrity
- Локальный "чистый прогон" на своём окружении НЕ подтверждает совместимость, если проект документирует минимальную версию (Postgres/Python/…) в CLAUDE.md/tech-spec — сверить синтаксис миграции/кода с задокументированным минимумом (например: `NULLS DISTINCT`, `MERGE` и др. version-specific конструкции требуют PG15+; если минимум ниже — FAIL, даже если локально прошло)
- Любое утверждение о способе проверки (в TODOS.md, review-артефакте, финальном summary) должно ссылаться на реально воспроизводимую команду — не описывать метод, невозможный для текущего состояния репозитория (например: `git stash` не может отменить уже запушенный коммит; для отката запушенного — `git worktree`/`git revert`)
- **Критерий PASS:** формулировка верификации проверяема — воспроизводима та же команда с тем же результатом
- **FAIL → fix:** переформулировать на фактически выполненную проверку; если проверка не проводилась — не заявлять, что проводилась

### G10. Review artifact
- `reviews/YYYY-MM-DD-*.md` создан с результатами G1–G9 (raw output, не prose)
- `reviews/YYYY-MM-DD-*.diff` сгенерирован из `git diff --cached` после staging
- **Критерий PASS:** оба файла существуют, diff непустой, md содержит outputs всех применимых gates
- **FAIL → fix:** добавить недостающее, не делать handoff без артефакта

## Итоговый статус

| Все применимые G1–G10 PASS | Решение |
|---|---|
| Да | → handoff в `/review-gate` |
| Нет (fix возможен за 1-2 итерации) | → fix → re-run |
| Нет (3+ итерации одного класса) | → эскалация |
| Manual/pending/not-run в обязательном gate | → `NOT_READY`, handoff запрещён |
