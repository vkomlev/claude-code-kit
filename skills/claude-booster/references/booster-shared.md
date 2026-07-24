# Общие паттерны booster-skills

Единый свод инвариантов для инфраструктурных skills (`claude-booster` и его родня). Skill ссылается сюда вместо дублирования правил у себя. При разногласиях — этот файл источник истины.

## 1. Mandatory improvement loop

Любая правка агента/skill в ответ на дефект проходит цикл:

1. **Register log** — запись инцидента в реестр ошибок:
   - Skill-дефект → `~/.claude/skills/claude-booster/references/skills-errors.md`
   - Response-дефект → ваш реестр дефектов ответов (если ведёте)

2. **5 Whys** — довести симптом до корня. Протокол: [rca-protocol.md](rca-protocol.md).

3. **Классификация корня** — instruction gap / context gap / execution gap. Execution gap не правим skill (это ограничение модели).

4. **Culprit patch** — правка на стороне виновника (SKILL.md или reference).

5. **Verification** — воспроизводимая проверка что фикс устраняет класс дефекта.

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

## 4. Ownership и mirror-копии

При правке skill, у которого есть несколько копий (например, глобальная в `~/.claude/skills/` и проектная в `<проект>/.claude/skills/`):

- **Canonical source-of-truth** — где живёт мастер
- **Required mirrors** — проектные / runtime-копии, требующие синхронизации
- **Runtime class:**
  - `claude-runtime` (`~/.claude/skills/`)
  - `project-runtime` (проектные `.claude/skills/`)
  - `external-runtime` (внешние пакеты с бинарниками — не править сборку)

**Правило:** не патчить только одну копию, если у skill есть обязательные mirrors. После правки — parity check (hash/bytes, не терминальный текст).

## 5. Fact-check для "latest" capability claims

Любое утверждение "последняя версия умеет X" требует:
- Даты claim (YYYY-MM-DD)
- Официального источника платформы (Anthropic docs и т.п.)
- Различения GA vs preview/experimental features
- Подтверждения через library fact-check reference (если API usage критичен)

## 6. Общие quality rules

- **Никогда не закрывать** improvement task без: register entry + 5 Whys + culprit patch + verification
- **Никогда не применять** platform-specific assumptions к другим runtimes без явных доказательств или запроса пользователя
- Правки неполны до проверки/синхронизации mirrors во всех затронутых копиях
- **Anti-bloat** обязателен — если правка добавила >10 строк в SKILL.md, пересмотреть: вынести в references или откатить

## Как ссылаться из SKILL.md

В booster-skill достаточно 1 строки в Workflow или Quality Rules:

> Применить общий протокол `~/.claude/skills/claude-booster/references/booster-shared.md` (loop + anti-bloat + encoding + fact-check + ownership).

Детальные правила, специфичные для конкретного режима, остаются в SKILL.md.
