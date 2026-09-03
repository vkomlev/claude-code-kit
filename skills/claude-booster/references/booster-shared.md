# Общие паттерны booster-skills

Единый свод инвариантов для `claude-booster`, `cursor-booster`, `codex-booster`. Каждый booster ссылается сюда вместо дублирования правил у себя. При разногласиях — этот файл источник истины.

## 1. Mandatory improvement loop

Любая правка агента/skill в ответ на дефект проходит цикл:

1. **Register log** — запись инцидента в соответствующий реестр ошибок:
   - Claude skill-дефект → `~/.claude/skills/claude-booster/references/skills-errors.md`
   - Response-дефект → `~/projects/IDE_booster/Docs/ai/ANSWER_ERRORS.md`
   - Cursor agent-дефект → реестр Cursor (см. cursor-booster references)
   - Codex skill-дефект → реестр Codex (см. codex-booster references)

2. **5 Whys** — довести симптом до корня. Протокол: [rca-protocol.md](rca-protocol.md).

3. **Культурация корня** — instruction gap / context gap / execution gap. Execution gap не правим skill (это ограничение модели).

4. **Culprit patch** — правка на стороне виновника. Если culprit на другой платформе —
   cross-handoff через межагентный реестр (см. §7): handoff-документ в
   `~/projects/Root\agents\handoff\`, запись в `_ledger.md`. Маршруты:
   - Claude → cursor-booster / codex-booster
   - Cursor → codex-booster (если через mirror)
   - Codex → cursor-booster (если Cursor-агент породил)

5. **Verification** — воспроизводимая проверка что фикс устраняет класс дефекта.

**Вывод инструмента/skill из реестра — Verification обязана покрыть оба слоя.**
Grep на упоминания выводимого имени не ограничивать `~/.claude/skills/**/*.md` — тем же
паттерном пройти и `~/.claude/hooks/*.json` (`skill_routing.json` — второй, независимый
носитель той же маршрутизирующей информации, читается `skill_routing_hint.py` и
`skill_engage_gate.py` напрямую, а не через SKILL.md) плюс любые другие JSON/py-конфиги
хуков под `~/.claude/hooks/`. Задача вывода инструмента считается незакрытой, пока не
сверены оба слоя. (внутренней задаче, 2026-08-06: `gstack` продержался в `skill_routing.json` 17 дней
после полного вывода из `skills/**/*.md` — верификация 2026-07-20 грепала только второй слой.)

## 2. Anti-bloat refactor pass (обязателен перед закрытием улучшения)

Перед коммитом правки ответить на 5 вопросов:

1. **Покрыто ли существующим правилом?** Если да — усилить формулировку, не клонировать.
2. **Локальное или глобальное?** Локальное → в SKILL.md; глобальное → в `~/.claude/CLAUDE.md` или shared references.
3. **Вынести в reference?** Чеклист 3+ пунктов → `references/*.md`, в SKILL.md только 1-строчный указатель.
4. **Дубль соседнего skill?** Если да — искать общего родителя, выносить в shared.
5. **Устаревшее убрано?** При добавлении нового инварианта — проверить, не стал ли старый избыточным.

**Правила:**
- Предпочитать компактные инварианты длинным спискам incident-specific исключений
- Обновление checklist / reference → лучше расширения top-level prompt/rules
- Удалять формулировки, дублирующие существующие guardrails без новой зоны покрытия
- Закрытие улучшения считается неполным, если inflation инструкций не нормализован после фикса

## 3. UTF-8 encoding discipline (Windows/PowerShell)

Обязательно при правках non-ASCII файлов через CLI:

- Явный UTF-8 на входе/выходе всех shell-driven read/write/validation путях
- Python из CLI — `PYTHONUTF8=1`
- PowerShell — `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
- **Не доверять терминальному рендерингу** для кириллицы — проверять байты (`xxd`, `file -i`)
- При замене `?` характеров в местах, где в canonical source кириллица — **фейлить задачу**, не продолжать

Детальный протокол восстановления — `~/.claude/skills/encoding-guard/SKILL.md`.

## 4. Ownership и runtime classification (cross-platform)

При правке skill с mirror-копиями:

- **Canonical source-of-truth** — где живёт мастер
- **Required mirrors** — проектные / runtime-копии, требующие синхронизации
- **Runtime class:**
  - `claude-runtime` (`~/.claude/skills/`)
  - `codex-runtime` (`~/.codex/skills/`)
  - `cursor-runtime` (плагины Cursor)
  - `project-runtime` (проектные `.claude/skills/`, `.cursor/rules/`)
  - `external-runtime` (внешние пакеты типа gstack, не править бинарники)

**Правило:** не патчить только одну копию, если у skill есть обязательные mirrors. После правки — parity check (hash/bytes, не терминальный текст).

**Зеркала не править руками.** `Root\skills\core\`, `{repo}\skills\core\`, `~\.codex\skills\`,
`AGENTS.md` генерирует `IDE_booster\scripts\package-skills.py` из Codex-канона
(`~/projects/IDE_booster\skills\`). Claude-канон — `~/.claude\skills\`, зеркал не имеет.
Раскатка live → зеркала перезатрёт упаковщик (`внутренней задаче`, откат 99 файлов).

Ownership на уровне portfolio (какие ресурсы вообще общие, кто вправе писать) —
`~/projects/Root\agents\ownership.md`. Этот §4 — про mirrors внутри skills; карта — шире.

## 5. Fact-check для "latest" capability claims

Любое утверждение "последняя версия умеет X" требует:
- Даты claim (YYYY-MM-DD)
- Официального источника платформы (Anthropic docs / Cursor docs / OpenAI docs)
- Различения GA vs preview/experimental features
- Подтверждения через library fact-check reference (если API usage критичен)

## 6. Общие quality rules для boosters

- **Никогда не закрывать** improvement task без: register entry + 5 Whys + culprit patch + verification
- **Никогда не применять** platform-specific assumptions к другим runtimes без явных доказательств или запроса пользователя
- **Fleet updates неполны** до проверки/синхронизации mirrors во всех затронутых проектах
- **Anti-bloat** обязателен — если правка добавила >10 строк в SKILL.md, пересмотреть: вынести в references или откатить

## 7. Межагентная координация (Claude ↔ Codex ↔ Cursor)

Агенты пишут в общие ресурсы параллельно. Единый реестр — `~/projects/Root\agents\`
(ADR-0005), аналог кросс-проектного трекера задач:

| Файл | Что |
|---|---|
| `ownership.md` | карта: ресурс → чей канон → кто вправе писать → зеркала |
| `_index.md` | активные захваты (claim) с TTL |
| `_ledger.md` | журнал действий, append-only: что сделал другой агент |
| `handoff/` | межагентные передачи (спецификации, ТЗ, сверки) |

**Шаг 0-А (hard-stop) перед правкой ресурса из `ownership.md`:** grep `_index.md` →
занято другим и TTL жив → СТОП, к оператору. Свободно → прочитать `_ledger.md` (что уже
сделано) → записать захват → работа → **снять захват + запись в `_ledger.md`**.
Полный протокол — `~/projects/Root\agents\README.md`. Не дублировать его здесь.

**Как безопасно писать в `_ledger.md` (Windows/PowerShell/Bash):** НИКОГДА не через
`printf`/`echo` с Windows-путями в аргументе — `\e` в пути (`...5-11\exports`) может
интерпретироваться шеллом как literal ESC-байт и портит путь в журнале молча (было дважды
за внутренней задаче: `informatika-5-11xports`, исправлено вручную по сырым байтам). Всегда: `Write`
создаёт временный `.py`-скрипт с текстом строки как Python-строка → `Bash python <скрипт>`
дописывает файл (`open(path, "a", encoding="utf-8")`). Тот же приём — для любой
многострочной кириллицы с Windows-путями, не только для ledger.

Enforcement: `Root\tools\validate_agents.py` в pre-commit hook Root.
Правило для Codex живёт в `Root\docs\ai\PROJECT_MEMORY.md` (в генерируемый `AGENTS.md` не писать).

Проверочный вопрос: **может ли моё действие удивить другого агента завтра?**
Да → регистрировать. Нет → не засорять реестр. Чтение не регистрируется никогда.

**Стандарт «второй взгляд» (dual-track, ADR-0006).** Для критичных решений (архитектура,
стандарты скиллов/инфраструктуры, ревью курса перед публикацией, критичные рефакторинги) +
по запросу оператора — задача идёт через двух агентов параллельно: изолированный прогон
(не читать чужое до обмена) → обмен видениями → своя реализация → сведение в единую версию →
согласие не эскалируется, спор → оператору. Полный протокол — `~/projects/Root\agents\second-opinion.md`.

## Как ссылаться из SKILL.md

В каждом booster-skill достаточно 1 строки в Workflow или Quality Rules:

> Применить общий протокол `~/.claude/skills/claude-booster/references/booster-shared.md` (loop + anti-bloat + encoding + fact-check + ownership + межагентный реестр).

Детальные правила, специфичные для конкретной платформы (Cursor features, Codex packaging, Claude Режим C), остаются в SKILL.md соответствующего booster'а.
