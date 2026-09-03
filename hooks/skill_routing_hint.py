#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""UserPromptSubmit-хук: проактивная подсказка профильных скиллов для упомянутого проекта.

Пара к skill_engage_gate.py, читают ОДИН реестр `skill_routing.json`:
  - gate  — реактив: бьёт по рукам ПОСЛЕ того, как агент полез в код без скилла;
  - hint  — проактив: называет профильные скиллы ДО начала работы.

Зачем проактив (решение оператора, внутренней задаче): корень обхода авто-подбора не только в том,
что агента не останавливают, но и в том, что он не держит в голове карту «проект ->
профильный скилл». Гейт лечит симптом, подсказка — причину.

Почему не SessionStart: сессии здесь кросс-проектные (cwd = ~/.claude, а работа в
~/projects/LMS), поэтому привязка к cwd ненадёжна. Триггер — упоминание проекта в промпте
оператора (имя или путь), матч консервативный по границе слова, чтобы не сыпать
подсказками на каждый промпт.

Контракт Claude Code (UserPromptSubmit):
- Вход: JSON на stdin с полем prompt.
- exit 0 + stdout -> текст добавляется в контекст сессии.
- Молчание (пустой stdout) -> ничего не добавляется.

Хук НИКОГДА не блокирует (всегда exit 0): это подсказка, а не гейт.

Молчит, если:
  - проект в промпте не упомянут;
  - инженерный скилл в сессии уже задействован (подсказка не нужна — правило соблюдено).
"""
from __future__ import annotations

import json
import sys

import skill_routing as sr

TEMPLATE = """\
[Маршрутизация скиллов] Промпт касается проекта(ов) с кодом. Правило ~/.claude/CLAUDE.md
§ «Автоподбор skills»: профильный скилл выбирается и выполняется ДО работы с кодом/БД,
и выбор называется оператору первой строкой. Профильные скиллы:

{blocks}
Если задача — не правка кода (вопрос, чтение, обсуждение), подсказку игнорируй.
"""

BLOCK = """\
  • {name}: {skills}
    {hint}
"""

# Компактная карта для многоканальных проектов (marketing = 8 правил на один корень,
# courses-project = 4). Без группировки упоминание «marketing» выдало бы 8 блоков подряд —
# подсказка превратилась бы в шум и её перестали бы читать.
GROUP_BLOCK = """\
  • {root} ({domain}) — куда что писать:
{lines}"""
GROUP_LINE = "      {dirs}/ → {skills}\n"

# Тематические указатели на справочники (topic_hints в реестре) — НЕзависимы от проекта.
# Всплывают по ключевым словам в промпте, чтобы чип нырял в готовый справочник, а не
# переоткрывал грабли. Не гейт: только подсказка.
TOPIC_TEMPLATE = "[Справочник — ныряй сюда, не переоткрывай] {hint}\n"


def _topic_hints(prompt: str, registry: dict) -> str:
    """Строки topic_hints, чьи keywords встретились в промпте (регистронезависимо)."""
    low = prompt.lower()
    out: list[str] = []
    for topic in registry.get("topic_hints", []):
        keywords = topic.get("keywords", [])
        if any(str(k).lower() in low for k in keywords):
            out.append(TOPIC_TEMPLATE.format(hint=topic.get("hint", "")))
    return "".join(out)


def _group_rules(rules: list[dict]) -> list[str]:
    """Правила -> блоки подсказки. Один корень = один блок."""
    order: list[str] = []
    by_root: dict[str, list[dict]] = {}
    for r in rules:
        root = str(r.get("root", ""))
        if root not in by_root:
            by_root[root] = []
            order.append(root)
        by_root[root].append(r)

    blocks: list[str] = []
    for root in order:
        group = by_root[root]
        if len(group) == 1:
            r = group[0]
            blocks.append(BLOCK.format(
                name=r.get("name", "?"),
                skills=", ".join("/" + s for s in r.get("skills", [])) or "(см. CLAUDE.md)",
                hint=r.get("hint", ""),
            ))
            continue
        lines = "".join(
            GROUP_LINE.format(
                dirs="|".join(r.get("source_dirs", [])),
                skills=", ".join("/" + s for s in r.get("skills", [])),
            )
            for r in group
        )
        blocks.append(GROUP_BLOCK.format(
            root=root.rstrip("/").rsplit("/", 1)[-1],
            domain=group[0].get("domain", ""),
            lines=lines,
        ))
    return blocks


def build_hint(prompt: str, transcript_path: str, registry: dict | None = None) -> str:
    """Текст подсказки или '' (молчим). Чистая функция (тесты)."""
    if not prompt.strip():
        return ""
    reg = sr.load_registry() if registry is None else registry
    if not reg:
        return ""
    parts: list[str] = []
    rules = sr.find_projects_in_text(prompt, reg)
    # Молчим по каждому домену, где правило уже соблюдено: если скилл контента взят,
    # незачем напоминать про контент — но напоминание про код всё ещё уместно.
    rules = [r for r in rules
             if not sr.skill_engaged(transcript_path, reg, str(r.get("domain", "")))]
    if rules:
        parts.append(TEMPLATE.format(blocks="".join(_group_rules(rules))))
    # Тематические справочники — независимо от проекта и от того, взят ли скилл:
    # указатель на справочник уместен, даже когда профильный скилл уже работает.
    topic = _topic_hints(prompt, reg)
    if topic:
        parts.append(topic)
    return "\n".join(parts)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open: молча пропускаем

    prompt = payload.get("prompt", "") or ""
    transcript_path = payload.get("transcript_path", "") or ""

    try:
        hint = build_hint(prompt, transcript_path)
    except Exception:
        return 0  # fail-open: подсказка не должна ломать сессию

    if hint:
        sys.stdout.write(hint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
