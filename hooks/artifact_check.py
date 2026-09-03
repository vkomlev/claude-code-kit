#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PostToolUse-проверка ЗАПИСАННОГО артефакта: первая пост-проверка в обвязке.

ПОЧЕМУ ЭТОТ ХУК ВООБЩЕ ПОЯВИЛСЯ
Все пять прежних гейтов (db_write_gate, chip_tree_gate, index_scope_gate,
skill_engage_gate, id_claim_gate) — PreToolUse, то есть ЗАПРЕЩАЮЩИЕ: они не дают
совершить опасное действие. Проверки РЕЗУЛЬТАТА не было ни одной. Агент работает
циклом, и качество цикла определяется тем, какой сигнал об ошибке он получает; без
пост-проверки сигнал приходит от оператора через часы или не приходит совсем.

Тот же класс отказа, что лечили Pre-гейты, но с другой стороны: правила вида
«проверь ПОСЛЕ правки» живут в CLAUDE.md/SKILL.md только текстом и потому
нарушаются. Механизируются здесь ровно четыре уже задокументированные боли:
  1) «валидировать JSON после каждой правки» (claude-booster, Правила качества);
  2) «проверять encoding UTF-8, mojibake недопустима» (~/.claude/CLAUDE.md);
  3) frontmatter скилла должен быть валиден (claude-booster, шаги A8 и D4);
  4) «`id` обязан совпадать с именем файла» (~/.claude/CLAUDE.md § трекер) —
     ловилось только pre-commit'ом В Root, а файлы задач пишутся из любой сессии.
Плюс защита генерируемых зеркал (§ «Зеркала не править руками») — правило, которое
до сих пор держалось исключительно на памяти агента.

ЧЕГО ХУК СОЗНАТЕЛЬНО НЕ ДЕЛАЕТ
- НЕ проверяет размер скилла (правило «≤200 строк» из Режима D). На 2026-09-03 его
  нарушают 31 из 69 SKILL.md. Механизировать правило, которое нарушено у половины
  парка, — значит выдавать шум на каждой правке. Сначала решение оператора: чистить
  парк или менять правило; пока — не проверяем.
- НЕ дублирует id_claim_gate: тот смотрит НОМЕР В ПУТИ (свой ли он этой сессии),
  здесь — совпадение `id:` ВНУТРИ frontmatter с именем файла. Разные отказы.

КОНТРАКТ CLAUDE CODE (PostToolUse)
- Вход: JSON на stdin. Поля: tool_name, tool_input (file_path), tool_response,
  cwd, transcript_path, session_id, hook_event_name.
- exit 0 — молчим. exit 2 + stderr — текст замечания уходит АГЕНТУ (запись уже
  произошла: это сигнал «почини», а не блокировка).
- Fail-open на любой внутренней ошибке: сломанный валидатор не должен мешать работе.

ЛОЖНЫЕ СРАБАТЫВАНИЯ — ГЛАВНЫЙ РИСК
Шумящий хук отключают, и вместе с ним теряются полезные срабатывания. Поэтому
каждая проверка здесь имеет высокий порог, а детектор mojibake ослабляется на
файлах, которые сами ПИШУТ про кодировки (этот файл, /encoding-guard, реестры
ошибок) — иначе он ловил бы собственные примеры.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Windows: консоль по умолчанию cp1251 — принудительно UTF-8, чтобы русский текст
# (stderr) дошёл до Claude Code без mojibake, а stdin читался как UTF-8.
# Проверено живьём: без этого блока пробник вернул крокозябры (артефакт того самого
# класса, который этот хук и ловит).
for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

MAX_BYTES = 2_000_000  # файлы крупнее не читаем: пост-проверка не должна тормозить цикл

TEXT_SUFFIXES = {
    ".md", ".json", ".py", ".txt", ".yml", ".yaml", ".ts", ".tsx", ".js", ".jsx",
    ".sql", ".ps1", ".sh", ".html", ".css", ".ini", ".cfg", ".toml", ".env",
}

# --- 2. Mojibake -------------------------------------------------------------
# UTF-8, прочитанный как cp1251/latin-1 и записанный обратно. Две сигнатуры:
#   «Ð°», «Ã©»  — латиница-1: заглавная из \u00c0-\u00ff + символ из \u0080-\u00bf;
#   «Рї», «вЂ» — кириллица: Р/С/в + РЕДКАЯ (не русская) буква кириллического блока.
# Второй символ во втором правиле намеренно сужен: пары вида «Ра», «Со», «Ве»
# встречаются в любом русском тексте, и широкий диапазон \u0400-\u045f давал бы
# ложное срабатывание почти всегда.
MOJI_LATIN1 = re.compile(r"[\u00c0-\u00ff][\u0080-\u00bf]")
#
# Два выреза из диапазона редких букв сделаны ПО ИТОГАМ ПРОГОНА по 2674 реальным
# файлам (124 ложных срабатывания, все — одна причина):
#   - «ё» (U+0451) из диапазона исключена: она не редкая. Пара «вё» («привёл»,
#     «вёрстка», «навёл») дала 39 попаданий и была единственной причиной шума;
#   - типографские знаки (U+2010-203A) убраны совсем: пара «Р — это» встречается
#     в обычных перечислениях, а настоящая порча типографики даёт «вЂ™», то есть
#     ловится через «Ђ» из диапазона U+0402-040F.
MOJI_CYR = re.compile(r"[\u0420\u0421\u0432][\u0450\u0452-\u045f\u0402-\u040f]")
REPLACEMENT = "\ufffd"

MOJI_THRESHOLD = 3       # обычный файл
MOJI_THRESHOLD_META = 25  # файл, который сам пишет про кодировки
META_WORDS = ("mojibake", "кодировк", "encoding-guard", "cp1251")

# --- 5. Генерируемые файлы («не править руками») -----------------------------
# ЗАПОЛНИ ПОД СЕБЯ. Сюда вносят пути, которые собирает скрипт или генератор:
# автодокументация, собранные индексы, копии общего кода в подпроектах.
# Такую правку легко сделать по ошибке — она выглядит как обычная, но живёт
# до следующего запуска генератора. Пустые списки = проверка выключена.
# Хранятся нормализованными: прямые слэши, нижний регистр.
MIRROR_PATTERNS: tuple[tuple[str, str], ...] = (
    # ("/skills/core/", "канон живёт в ~/projects/my-skills/"),
)
MIRROR_INDEX_FILES: tuple[str, ...] = ()  # напр. ("~/projects/app/docs/api-generated.md",)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _read(path: Path) -> str | None:
    """Текст файла или None, если читать не нужно/нельзя. Fail-open."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _frontmatter(text: str) -> dict[str, str]:
    """Плоский разбор YAML-frontmatter: ключ -> строковое значение. Без зависимостей."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line or line.startswith((" ", "\t", "#", "-")):
            continue
        key, sep, value = line.partition(":")
        if sep:
            out[key.strip()] = value.strip().strip("'\"")
    return out


def check_json(path: Path, text: str) -> str | None:
    """1. Валидность JSON. Битый settings.json/.mcp.json ломает всю сессию."""
    if path.suffix.lower() != ".json":
        return None
    try:
        json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return (f"JSON НЕВАЛИДЕН после правки: {exc}\n"
                f"   Файл: {path}\n"
                f"   Почини сейчас — битый конфиг ломает сессию целиком "
                f"(settings.json, .mcp.json, skill_routing.json).")
    return None


def check_mojibake(path: Path, text: str) -> str | None:
    """2. Порча кириллицы. Мы её ловим глазами через часы после записи."""
    if REPLACEMENT in text:
        return (f"В файле символ-замена U+FFFD ({REPLACEMENT}) — текст записан с потерей.\n"
                f"   Файл: {path}\n"
                f"   Перечитай источник в правильной кодировке и перезапиши (см. /encoding-guard).")
    lowered = text[:200_000].lower()
    threshold = MOJI_THRESHOLD_META if any(w in lowered for w in META_WORDS) else MOJI_THRESHOLD
    hits = len(MOJI_LATIN1.findall(text)) + len(MOJI_CYR.findall(text))
    if hits >= threshold:
        return (f"Похоже на mojibake: {hits} подозрительных последовательностей "
                f"(«Ð°», «Рї», «вЂ»).\n"
                f"   Файл: {path}\n"
                f"   Это UTF-8, прочитанный как cp1251. Проверь исходник и перезапиши "
                f"(см. /encoding-guard).")
    return None


def check_skill(path: Path, text: str) -> str | None:
    """3. Frontmatter скилла. Без него скилл не подхватывается и молча не работает."""
    if path.name != "SKILL.md":
        return None
    fm = _frontmatter(text)
    missing = [k for k in ("name", "description") if not fm.get(k)]
    if not fm:
        return (f"У скилла нет валидного YAML-frontmatter (блок --- ... --- в начале файла).\n"
                f"   Файл: {path}\n"
                f"   Без него скилл не подхватится — отказ молчаливый, увидишь его не сразу.")
    if missing:
        return (f"В frontmatter скилла нет обязательных полей: {', '.join(missing)}.\n"
                f"   Файл: {path}")
    return None


def check_tracker_id(path: Path, text: str) -> str | None:
    """4. `id`/`claim_id` в frontmatter == имя файла. Иначе pre-commit Root отклонит."""
    name = path.name
    m = re.match(r"^(tsk|clm)-(\d+)", name)
    if not m or path.suffix.lower() != ".md":
        return None
    kind, number = m.group(1), m.group(2)
    if "/tasks/" not in _norm(str(path)) and "/claims/" not in _norm(str(path)):
        return None
    fm = _frontmatter(text)
    field = "id" if kind == "tsk" else "claim_id"
    declared = fm.get(field, "")
    if not declared:
        return (f"В файле {name} нет поля `{field}` во frontmatter — pre-commit в Root отклонит.\n"
                f"   Файл: {path}")
    if declared != f"{kind}-{number}":
        return (f"Расхождение идентификатора: во frontmatter `{field}: {declared}`, "
                f"а файл называется {name}.\n"
                f"   Файл: {path}\n"
                f"   Так бывает при копировании шаблона. Pre-commit в Root это отклонит, "
                f"но только при коммите ИМЕННО в Root — почини сейчас.")
    return None


def check_mirror(path: Path, _text: str) -> str | None:
    """5. Правка генерируемого зеркала. Правило было только текстом в CLAUDE.md."""
    norm = _norm(str(path))
    if norm in MIRROR_INDEX_FILES:
        return (f"Это ГЕНЕРИРУЕМЫЙ файл: {path.name}\n"
                f"   Он собирается генератором — посмотри, каким именно.\n"
                f"   Ручная правка будет затёрта. Правь источник — файл захвата или записи.")
    for pattern, canon in MIRROR_PATTERNS:
        if pattern in norm:
            return (f"Это ЗЕРКАЛО, а не канон: {path}\n"
                    f"   Зеркала генерирует package-skills.py; правка живёт до следующей "
                    f"упаковки.\n"
                    f"   {canon}\n"
                    f"   Канон Claude: ~/.claude\\skills\\\n"
                    f"   Правь канон и переупакуй (запуск package-skills.py — общий ресурс, "
                    f"регистрируется в agents/).")
    return None


CHECKS = (check_mirror, check_json, check_mojibake, check_skill, check_tracker_id)


def evaluate(file_path: str) -> list[str]:
    """Список замечаний по записанному файлу. Чистая функция — для тестов."""
    if not file_path:
        return []
    path = Path(file_path)
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "SKILL.md":
        return []
    text = _read(path)
    if text is None:
        return []
    notes = []
    for check in CHECKS:
        try:
            note = check(path, text)
        except Exception:
            note = None  # один сломанный валидатор не отменяет остальные
        if note:
            notes.append(note)
    return notes


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
        return 0
    if os.environ.get("ARTIFACT_CHECK_OFF") == "1":
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    try:
        notes = evaluate(file_path)
    except Exception:
        return 0

    if not notes:
        return 0

    sys.stderr.write(
        "Пост-проверка записанного файла нашла проблему "
        f"({len(notes)} шт.):\n\n" + "\n\n".join(notes) +
        "\n\nЗапись уже произошла — это сигнал «почини», а не блокировка. "
        "Разовый обход: ARTIFACT_CHECK_OFF=1.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
