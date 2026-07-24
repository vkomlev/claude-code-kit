#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Общая библиотека маршрутизации скиллов: читает skill_routing.json.

Единая логика для двух хуков (чтобы правила жили в ОДНОМ месте — данных, не в коде):
  - skill_engage_gate.py  — PreToolUse Write|Edit: блок правки кода без скилла (реактив);
  - skill_routing_hint.py — UserPromptSubmit: подсказка профильных скиллов (проактив).

Почему данные, а не код: раскладки проектов разные (одни держат код в `app/`, другие в
`src/` или пакетных каталогах; языки — Python, TS/TSX и т.д.). Захардкоженный хук покрыл бы
пару проектов. Здесь новый проект = строка в JSON, новый скилл = имя в списке.

Матчинг по СЕГМЕНТУ каталога (а не glob) — намеренно: так и worktree-копии проекта
(`.../.claude/worktrees/x/app/services/y.py`) попадают под гейт, чего glob `app/**/*.py`
от корня не дал бы.
"""
from __future__ import annotations

import json
import os
import re
import sys
from fnmatch import fnmatch
from typing import Any

# Служебные вставки харнесса в промпте (<system-reminder>…</system-reminder>): это НЕ слова
# оператора, а контекст от Claude Code. Их надо вырезать перед матчингом проектов, иначе
# подсказка ловит имена проектов из чужого текста (например, из напоминания харнесса про
# другой проект). Поэтому служебные вставки вырезаем: матчим по смыслу промпта оператора,
# а не по всему сырому тексту.
_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL | re.IGNORECASE)

# Операторский запуск скилла: харнесс пишет `<command-name>/skill</command-name>`.
# Ведущий слэш опционален, имя — скилл или plugin:skill (буквы/цифры/дефис/двоеточие).
_COMMAND_NAME_RE = re.compile(r"<command-name>\s*/?([a-z0-9:_-]+)\s*</command-name>", re.IGNORECASE)

# Windows: консоль по умолчанию cp1251 — принудительно UTF-8, чтобы русский текст
# дошёл до Claude Code без mojibake, а stdin читался как UTF-8.
for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_routing.json")


def norm(path: str) -> str:
    """Путь -> нижний регистр со слешами вперёд для сопоставления."""
    return path.replace("\\", "/").lower()


def strip_injected(text: str) -> str:
    """Убрать служебные вставки харнесса (<system-reminder>) — там не слова оператора."""
    return _SYSTEM_REMINDER_RE.sub(" ", text)


def load_registry(path: str = REGISTRY_PATH) -> dict[str, Any]:
    """Читает реестр. При любой ошибке — пустой реестр (fail-open у вызывающего)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def match_project(path: str, registry: dict[str, Any]) -> dict[str, Any] | None:
    """Находит правило, чей артефакт правится. None — файл не под гейтом.

    Условия: путь под root И содержит сегмент из source_dirs И имеет расширение
    из extensions И не попал ни в одно исключение (глобальное или доменное).

    `source_dirs` можно опустить/оставить пустым — тогда правило накрывает ВЕСЬ
    поддеревом root. Нужно для инфраструктуры: `settings.json` и `CLAUDE.md` лежат
    в корне `~/.claude` и ни в какой каталог-сегмент не попадают.

    Побеждает ПЕРВОЕ совпавшее правило — частные правила в реестре стоят выше общих
    (wp-blocks выше exports, output/smm выше output).

    Исключения ДОМЕННЫЕ, а не общие, и это принципиально: для кода `/output/` и
    `/docs/` — мусор, а для контента `/output/` — ровно то место, где живут статьи
    и посты. Один общий список вырезал бы весь контентный домен.
    """
    p = norm(path)

    for seg in registry.get("exclude_global", []):
        if seg in p:
            return None

    base = p.rsplit("/", 1)[-1]
    for pat in registry.get("exclude_file_patterns", []):
        if fnmatch(base, pat):
            return None

    by_domain = registry.get("exclude_by_domain", {})
    files_by_domain = registry.get("exclude_files_by_domain", {})

    for rule in registry.get("rules", []):
        root = norm(str(rule.get("root", "")))
        if not root or not p.startswith(root.rstrip("/") + "/"):
            continue
        exts = rule.get("extensions", [])
        if not any(p.endswith(str(e).lower()) for e in exts):
            continue
        # Сегмент каталога где угодно в пути (ловит и worktree-копии).
        # Пустой source_dirs = всё поддерево root (нужно для корневых файлов infra).
        dirs = rule.get("source_dirs", [])
        if dirs and not any(f"/{str(d).lower()}/" in p for d in dirs):
            continue
        domain = str(rule.get("domain", ""))
        # Доменные исключения — только для домена этого правила.
        if any(seg in p for seg in by_domain.get(domain, [])):
            continue
        # Исключения по ИМЕНИ файла тоже доменные: `claude.md` надо игнорировать для
        # контента (проектный CLAUDE.md — не урок), но ОБЯЗАТЕЛЬНО гейтить для infra
        # (глобальный ~/.claude/CLAUDE.md — сердце поведения агента).
        if any(fnmatch(base, pat) for pat in files_by_domain.get(domain, [])):
            continue
        return rule
    return None


def find_projects_in_text(text: str, registry: dict[str, Any]) -> list[dict[str, Any]]:
    """ПРАВИЛА, чей проект упомянут в тексте промпта — по имени или по пути корня.

    Используется проактивной подсказкой. Матч намеренно консервативный: только
    явное имя проекта или его путь, чтобы не сыпать подсказками на каждый промпт.
    Служебные вставки харнесса вырезаются — маршрутизируем по словам ОПЕРАТОРА.
    """
    low = strip_injected(text).lower()
    found: list[dict[str, Any]] = []
    for proj in registry.get("rules", []):
        name = str(proj.get("name", "")).lower()
        root = norm(str(proj.get("root", "")))
        # Короткое имя каталога проекта (последний сегмент пути root).
        short = root.rstrip("/").rsplit("/", 1)[-1] if root else ""
        hit = False
        if root and root in low:
            hit = True
        elif root and root.replace("/", "\\") in low:
            hit = True
        elif short and _word_in(low, short):
            hit = True
        elif name and name.lower() in low:
            hit = True
        if hit:
            found.append(proj)
    return found


def _word_in(haystack: str, needle: str) -> bool:
    """Вхождение по границе слова — чтобы 'app' не ловилось внутри 'my_app' и наоборот."""
    if not needle:
        return False
    idx = 0
    while True:
        idx = haystack.find(needle, idx)
        if idx < 0:
            return False
        before = haystack[idx - 1] if idx > 0 else " "
        after_i = idx + len(needle)
        after = haystack[after_i] if after_i < len(haystack) else " "
        if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
            return True
        idx = after_i


def _command_name_invokes(node: object, allowed: frozenset[str]) -> bool:
    """True, если в структурном поле command-name стоит скилл из allowed.

    Оператор запускает скилл слэш-командой, и харнесс пишет её в транскрипт как
    отдельное поле `<command-name>/имя</command-name>` (плюс `<command-message>`,
    `<command-args>`) — а НЕ как `tool_use name=="Skill"`. Поэтому проверка только
    по tool_use не видела операторский запуск: гейт требовал маркер даже когда
    профильный скилл реально работал, и это толкало писать маркеры вместо скиллов.

    Разбираем ТОЛЬКО значение поля `command-name` (структура, которую ставит
    харнесс), а не любой текст сообщения: имя скилла, упомянутое в обсуждении или
    в CLAUDE.md, задействованием не считается — тот же принцип, что у tool_use.
    """
    m = _COMMAND_NAME_RE.search(node) if isinstance(node, str) else None
    if m and m.group(1).strip().lower() in allowed:
        return True
    if isinstance(node, dict):
        # Частый случай: {"type": "text", "text": "<command-name>/x</command-name>"}.
        for value in node.values():
            if _command_name_invokes(value, allowed):
                return True
    elif isinstance(node, list):
        for value in node:
            if _command_name_invokes(value, allowed):
                return True
    return False


def _find_skill_call(node: object, allowed: frozenset[str]) -> bool:
    """Рекурсивно ищет задействование скилла из allowed.

    Два признака, оба структурные (не свободный текст):
      1. `tool_use name=='Skill'` с input.skill из allowed — скилл вызвал агент;
      2. поле `<command-name>/skill</command-name>` — скилл запустил оператор.
    Упоминание имени скилла в обсуждении или в CLAUDE.md задействованием не
    считается ни в одном из случаев.
    """
    if isinstance(node, dict):
        if node.get("type") == "tool_use" and node.get("name") == "Skill":
            inp = node.get("input") or {}
            if isinstance(inp, dict):
                if str(inp.get("skill", "")).strip().lower() in allowed:
                    return True
        for value in node.values():
            if _find_skill_call(value, allowed):
                return True
    elif isinstance(node, list):
        for value in node:
            if _find_skill_call(value, allowed):
                return True
    elif isinstance(node, str):
        return _command_name_invokes(node, allowed)
    return False


def domain_skills(registry: dict[str, Any], domain: str) -> frozenset[str]:
    """Скиллы, снимающие блок для домена. Пустой домен -> объединение всех.

    Домены обязательны: без них инженерный скилл снимал бы блок с маркетингового
    артефакта, и наоборот. Каждый домен силансится только СВОИМИ скиллами.
    """
    by_domain = registry.get("silencing_by_domain", {})
    if domain:
        return frozenset(str(s).lower() for s in by_domain.get(domain, []))
    out: set[str] = set()
    for names in by_domain.values():
        out.update(str(s).lower() for s in names)
    return frozenset(out)


def skill_engaged(transcript_path: str, registry: dict[str, Any], domain: str = "") -> bool:
    """True, если в транскрипте сессии уже был вызов скилла нужного домена."""
    if not transcript_path:
        return False
    allowed = domain_skills(registry, domain)
    if not allowed:
        return False
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if _find_skill_call(event, allowed):
                    return True
    except OSError:
        return False
    return False
