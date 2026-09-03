#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PreToolUse-гейт: блокирует правку исходного КОДА мимо профильного скилла.

Механический контроль поверх правила из ~/.claude/CLAUDE.md
(§ «Автоподбор skills (обязательно)» + § «Hard-stop для работы с кодом и БД»:
«профильный скилл авто-выбирается и выполняется ДО действия»).

Правило держалось только на дисциплине модели и обходилось практически всегда, если
оператор не называл скилл явно. Инцидент внутренней задаче: полный цикл (диагностика ботов ->
правка бэкенда LMS -> прод-скрипт правки данных) выполнен без единого профильного скилла.
Тот же класс отказа уже вылечен механически для соседних классов:
  - db_write_gate.py     — прод-запись в БД без /db-check (DBCHECK_OK=1);
  - skill_route_gate.py  — контент курса мимо /methodist (.authoring-note.md);
  - chip_tree_gate.py    — tree-global destructive в общем дереве (CHIP_SOLO=1).

ENFORCEMENT gap, а не instruction gap: правило-текст есть и не срабатывает. Лечение —
внешний механизм, а не ещё один абзац в CLAUDE.md (anti-bloat).

DATA-DRIVEN: правила НЕ захардкожены. Что считать исходником и какие
скиллы профильные — в `skill_routing.json`. Первая версия хука знала только `.py` под
`app/`/`src/` и покрывала 2 проекта из 17 (content-service с пакетными каталогами, SPW на
TS/TSX и Avito пролетали мимо). Теперь новый проект = строка в JSON, правка кода не нужна.

Контракт Claude Code (форма payload ПРОВЕРЕНА эмпирически 2026-07-16, не предположена):
- Вход: JSON на stdin. Реальные поля PreToolUse/UserPromptSubmit:
  cwd, hook_event_name, permission_mode, prompt, prompt_id, session_id, transcript_path
  (+ tool_name, tool_input для PreToolUse).
- `transcript_path` присылается всегда (реальное значение вида
  `~/.claude\projects\D--Work-SPW\<session-id>.jsonl`) — на нём держится
  силансер. Если бы поле не приходило, гейт стал бы слишком строгим (блок даже когда
  скилл задействован), поэтому факт проверен зондом, а не взят из документации.
- Блокировка: exit code 2 + текст причины на stderr (показывается агенту).
- Пропуск: exit code 0.

Живая проверка сквозного цикла (2026-07-16, сессия D--Work-SPW): правка
`components/course/CourseFeed.tsx` без скилла -> БЛОК; агент прочитал причину, выбрал
`/executor-lite` (путь «рутинный инкремент» из текста блока); силансер увидел вызов в
транскрипте -> правка прошла. Ровно тот класс (SPW на TS/TSX), что был слеп в v1.
Домены проверены живьём 2026-07-16 (content + marketing): блок сработал, `/executor-lite`
блок с материала курса НЕ снял, `/methodist` снял.

КАК ПРОВЕРЯТЬ ЭТОТ ХУК (грабли, стоившие двух ложных выводов):
- Харнесс валидирует `old_string` у Edit ДО запуска PreToolUse-хуков. Edit с заведомо
  НЕсуществующей строкой (кажется «безопасным» способом проверки) обрывается раньше —
  хук НЕ вызывается, и это выглядит как «гейт не сработал». Ложный вывод.
- Проверять только так: **Write нового файла** в гейтимый путь ИЛИ Edit с РЕАЛЬНО
  существующей строкой.
- Хуки перечитываются на лету: правка settings.json действует в ТЕКУЩЕЙ сессии, без
  перезапуска (проверено Write-пробником в сессии, где хук был добавлен). Прежний вывод
  «PreToolUse берётся из снимка на старте» — ОШИБОЧЕН, он был артефактом граблей выше.

Логика:
  1. Не Write/Edit -> пропустить.
  2. Файл не совпал с исходником проекта из реестра -> пропустить.
  3. Env-override SKILL_ENGAGED=1 -> пропустить (операторский/headless обход).
  4. Свежий (<=24 ч) маркер .skill-engaged-note.md в дереве проекта -> пропустить.
  5. В транскрипте сессии был вызов инженерного Skill -> пропустить.
  6. Иначе -> БЛОК с подсказкой ИМЕННО для этого проекта.

Решение оператора: блок снимает ЛЮБОЙ инженерный скилл из silencing_skills —
правило про ОСОЗНАННОЕ задействование, а не про угадывание точного имени. Профильный скилл
проекта при этом называется в тексте блока (поле hint реестра).

Fail-open: при ошибке разбора входа/реестра хук пропускает. Но «нет сигнала о скилле»
трактуется как БЛОК — иначе гейт молча выродится в не-enforcement, ровно ту болезнь,
что лечим. Обход дешёвый (один /skill или маркер).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import skill_routing as sr

MARKER_NAME = ".skill-engaged-note.md"
# «Протухание» маркера: 24 ч (как TTL захватов межагентного реестра). Свежий маркер =
# осознанное решение ТЕКУЩЕЙ работы; вчерашний не должен молча отключать enforcement.
MARKER_MAX_AGE_SEC = 24 * 3600
MAX_WALK_UP = 12

# Маркер выведенного skill_route_gate. Сохранён намеренно (решение оператора при сведении
# гейтов): конвенция задокументирована в CLAUDE.md и привычна. Его семантика ИСХОДНАЯ —
# постоянный, на курс, без протухания. Поэтому честен только для домена content:
# пускать постоянный обход в код было бы ослаблением, которого раньше не существовало.
LEGACY_MARKER_NAME = ".authoring-note.md"
LEGACY_MARKER_DOMAINS = frozenset({"content"})

OVERRIDE_ENV_RE = re.compile(r"^(1|true|yes)$", re.IGNORECASE)


def _env_override() -> bool:
    return bool(OVERRIDE_ENV_RE.match(os.environ.get("SKILL_ENGAGED", "").strip()))


def _override_marker_fresh(path: str, domain: str = "") -> str | None:
    """Путь действующего маркера осознанной прямой правки, иначе None.

    .skill-engaged-note.md — любой домен, действует 24 ч.
    .authoring-note.md    — только content, постоянный (наследие skill_route_gate).

    Возвращает ПУТЬ, а не bool: вызывающему нужно показать, ЧЕЙ маркер заглушил
    гейт. Истинность сохранена (None ложно, непустая строка истинна), поэтому
    `if _override_marker_fresh(...)` работает как раньше.
    """
    parts = [seg for seg in sr.norm(path).split("/") if seg]
    now = time.time()
    legacy_ok = domain in LEGACY_MARKER_DOMAINS
    for step, i in enumerate(range(len(parts) - 1, 0, -1)):
        if step >= MAX_WALK_UP:
            break
        directory = "/".join(parts[:i])
        try:
            marker = directory + "/" + MARKER_NAME
            if os.path.isfile(marker) and (now - os.path.getmtime(marker)) <= MARKER_MAX_AGE_SEC:
                return marker
            legacy = directory + "/" + LEGACY_MARKER_NAME
            if legacy_ok and os.path.isfile(legacy):
                return legacy
        except OSError:
            continue
    return None


def _marker_notice(path: str) -> str | None:
    """Строка «гейт пропустил по маркеру: возраст + о чём он», иначе None.

    ЗАЧЕМ. Пропуск по маркеру был МОЛЧАЛИВЫМ, и это дороже, чем кажется. Маркер
    живёт 24 ч по mtime ФАЙЛА, а mtime не связан с тем, что в маркере написано:
    `git worktree add` / checkout выкладывает отслеживаемый маркер со свежим
    mtime, и заметка трёхдневной давности про ЧУЖУЮ задачу молча авторизует
    сегодняшнюю работу в новом дереве. Ровно это и произошло: агент правил бэкенд LMS всю сессию без профильного скилла,
    потому что гейт снял маркер от внутренней задаче, приехавший вместе с worktree.

    Возраста и первой содержательной строки достаточно, чтобы человек и агент
    увидели «это не мой маркер». Читать содержимое ДЛЯ РЕШЕНИЯ гейт по-прежнему
    не пытается: жёсткая привязка к номеру задачи давала бы ложные блокировки на
    работе без номера.
    """
    reg = sr.load_registry()
    if not reg:
        return None
    rule = sr.match_project(path, reg)
    if rule is None:
        return None
    marker = _override_marker_fresh(path, str(rule.get("domain", "")))
    if not marker:
        return None
    try:
        age_h = (time.time() - os.path.getmtime(marker)) / 3600
        first = ""
        with open(marker, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip().lstrip("#-").strip()
                if stripped and not stripped.startswith("---"):
                    first = stripped[:100]
                    break
    except OSError:
        return None
    return (
        f"[skill_engage_gate] Правка пропущена по маркеру {marker} "
        f"(обновлён {age_h:.0f} ч назад): «{first}». "
        f"Если маркер не про текущую задачу — профильный скилл НЕ задействован."
    )


# Формулировки блока живут в РЕЕСТРЕ (`domain_wording`), не здесь: «исходный код» +
# /executor-lite верны для инженерии и бессмысленны для статьи или стратегии, а домен
# добавляется строкой в JSON — текст обязан ехать вместе с ним.
#
# Раньше словарь был захардкожен тут и для незнакомого домена подставлял ИНЖЕНЕРНЫЙ
# вариант. Домен infra получил текст «любой инженерный скилл снимает блок, напр.
# /executor-lite» — прямую ложь (executor-lite infra не открывает), которая толкала агента
# к маркеру-обходу мимо /claude-booster. Нашёл чип живой проверки.
# Поэтому fallback теперь БЕЗОПАСНЫЙ: ссылается на скиллы самого правила и ничего не
# выдумывает. Молчаливая подстановка чужого домена больше невозможна.


def _wording(registry: dict, domain: str, skills: str) -> dict[str, str]:
    w = (registry.get("domain_wording") or {}).get(domain)
    if isinstance(w, dict) and w.get("subject") and w.get("routine"):
        return {"subject": str(w["subject"]), "routine": str(w["routine"]),
                "extra": str(w.get("extra", ""))}
    return {
        "subject": "артефакт под профильным скиллом",
        "routine": f"блок снимает скилл этого домена — {skills}",
        "extra": "",
    }

REASON = """\
[skill_engage_gate] Правка напрямую — {subject}, «{project}»:
  {path}

Правило (~/.claude/CLAUDE.md § «Автоподбор skills»): профильный скилл авто-выбирается
и выполняется ДО работы. В этой сессии скилл домена «{domain}» ещё не задействован.

Профильные скиллы: {skills}
  {hint}

Сделай одно из трёх:
  1) Задействуй профильный скилл и работай через него
     ({routine}).
{extra}  2) Осознанно правишь напрямую (правка по образцу, механика)? Зафиксируй решение —
     создай файл .skill-engaged-note.md В ДЕРЕВЕ ПРАВИМОГО ФАЙЛА, а не в cwd: гейт
     идёт вверх от него (для правок ~/.claude — маркер в ~/.claude/, а не в корне
     проекта, из которого работаешь). 1-2 строки: какой скилл использован ИЛИ почему
     напрямую. Гейт пропустит правки на ближайшие сутки.{legacy}
  3) Операторский/headless обход — префикс окружения SKILL_ENGAGED=1.

Это механический гейт (как db_write_gate для БД): правило-текст на память агента
не срабатывало почти никогда. Маркер = осознанное залогированное решение, не обход.
"""

LEGACY_HINT = ("\n     Для курса работает и прежний маркер courses/<slug>/.authoring-note.md "
               "(постоянный).")


def evaluate(tool_name: str, path: str, transcript_path: str,
             registry: dict | None = None) -> dict | None:
    """Возвращает правило для блокировки, или None для пропуска. Чистая функция (тесты)."""
    if tool_name not in ("Write", "Edit") or not path:
        return None
    reg = sr.load_registry() if registry is None else registry
    if not reg:
        return None  # fail-open: нет реестра — не мешаем работе
    rule = sr.match_project(path, reg)
    if rule is None:
        return None
    domain = str(rule.get("domain", ""))
    if _env_override():
        return None
    if _override_marker_fresh(path, domain):
        return None
    # Силансит только скилл СВОЕГО домена: /executor-lite не снимает блок с материала
    # урока, /methodist — с кода бэкенда.
    if sr.skill_engaged(transcript_path, reg, domain):
        return None
    return rule


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open: кривой вход не должен ломать сессию

    if payload.get("tool_name") not in ("Write", "Edit"):
        return 0

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    transcript_path = payload.get("transcript_path", "") or ""

    try:
        rule = evaluate(payload.get("tool_name", ""), path, transcript_path)
    except Exception:
        return 0  # fail-open на непредвиденной ошибке

    if rule:
        domain = str(rule.get("domain", ""))
        skills = ", ".join("/" + s for s in rule.get("skills", [])) or "(см. CLAUDE.md)"
        words = _wording(sr.load_registry(), domain, skills)
        sys.stderr.write(REASON.format(
            subject=words["subject"], project=rule.get("name", "?"), path=path,
            domain=domain, skills=skills, hint=rule.get("hint", ""),
            routine=words["routine"], extra=words["extra"],
            legacy=LEGACY_HINT if domain in LEGACY_MARKER_DOMAINS else "",
        ))
        return 2

    # Гейт ПРОПУСТИЛ. Если пропуск случился по маркеру — не молчать: показать
    # оператору (`systemMessage`) и вернуть в контекст модели (`additionalContext`),
    # чтобы устаревший/чужой маркер (напр. приехавший с worktree) не выключал
    # дисциплину скиллов беззвучно. permissionDecision НЕ выставляем: пусть
    # обычный permission-флоу решает про запись, хук лишь уведомляет.
    try:
        notice = _marker_notice(path)
    except Exception:
        notice = None
    if notice:
        try:
            sys.stdout.write(json.dumps({
                "systemMessage": notice,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": notice,
                },
            }, ensure_ascii=False))
        except Exception:
            pass  # уведомление — не критичный путь, не ломаем запись
    return 0


if __name__ == "__main__":
    sys.exit(main())
