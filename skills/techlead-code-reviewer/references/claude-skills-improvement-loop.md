# Claude Skills Improvement Loop

## Goal
Capture significant Claude skill failures during review and convert them into preventive improvements to the skill catalogue (`~/.claude/skills/`) or project rules (`.claude/CLAUDE.md`).

Этот цикл замыкает review на апгрейд скиллов-разработчиков (`/executor-lite`, `/executor-pro`, `/fastapi-api-developer`, `/spec-writer`, `/change-plan-architect`, `/tech-spec-composer`, `/techlead-code-reviewer` и смежные).

## What To Log
Log when at least one condition is true:
- скилл выдал реализацию, нарушающую контракт задачи или acceptance criteria
- использован устаревший/несуществующий API библиотеки или фреймворка
- нарушены архитектурные границы проекта (layering, слой-ответственность, cross-schema DB)
- небезопасный паттерн работы с БД/схемой/миграциями (включая Alembic isolation, write-операции без rollback)
- отсутствие или некорректность тестов, создающие регрессионный риск
- повторяющееся копипаст-нарушение DRY, которого скилл должен был избежать
- скилл проигнорировал Шаг 0 (якорь контекста / MEMORY.md / предыдущие решения)
- скилл нарушил правила оформления: кодировка UTF-8, русские коммиты, запрет хардкода секретов

## Where To Log
1. Project-specific register (preferred):
- `<project>/docs/ai/ERRORS.md`

2. If project register is unavailable:
- `~/.claude/ERRORS.md` (глобальный реестр)

## Minimum Entry Fields
- Date
- Project
- Skill (точное имя, например `/executor-pro`, `/fastapi-api-developer`)
- Context (что скилл должен был сделать)
- Symptom (что реально произошло)
- Root Cause (почему скилл провалился — размытая инструкция, отсутствие Шага 0, слабый output contract и т.д.)
- Class (см. ниже)
- Severity (S1/S2/S3)
- Detection Method (где поймали — review-gate, тесты, смоук, MCP-проверка)
- Fix (правка в текущем PR)
- Prevention Action (какая правка скилла предотвратит повтор)
- Status (open / applied / verified)

## Classification
- `scope-violation` — скилл вышел за границы задачи или не покрыл acceptance criteria
- `api-drift` — использован неактуальный API
- `architecture-breach` — нарушены слои/границы
- `db-unsafe` — небезопасная работа с БД/миграциями
- `test-gap` — нет регрессионного теста на уровне дефекта
- `context-skip` — проигнорирован Шаг 0 / MEMORY / предыдущие ревью
- `style-breach` — UTF-8, русские коммиты, секреты, форматирование
- `dry-violation` — повторяющийся копипаст

## Required Follow-Up
Для каждой залогированной ошибки скилла — минимум одно из:
- обновить инструкцию соответствующего `SKILL.md` (уточнить Шаги, Правила качества, Output Contract)
- добавить/усилить чек-лист в `references/*.md` данного скилла
- ужесточить проектные правила в `<project>/.claude/CLAUDE.md` или `~/.claude/CLAUDE.md`
- добавить обязательную validation/test команду в Output Contract скилла
- вынести reusable helper/template, снимающий двусмысленность

Если одна и та же ошибка встречается ≥2 раз подряд в одном скилле — эскалировать в `/claude-booster` для аудита скилла (Режим A).

## Output in Review
В секции `Skill Improvement Actions` ревью явно перечислить:
- имя скилла → предлагаемая правка (файл SKILL.md или references/*)
- ссылка на запись в ERRORS.md
- приоритет (immediate / next-iteration / backlog)
