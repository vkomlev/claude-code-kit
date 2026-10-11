#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PostToolUse-сторож тестов: ловит удаление и ослабление тестов агентом.

ПОЧЕМУ ЭТОТ ХУК ПОЯВИЛСЯ
Самый дешёвый способ для агента «починить» красный тест — убрать тест. На живом
прогоне учебного курса агент пять раз удалял тесты (переписывал test_*.py целиком,
стирал функции test_*), добавлял skip/xfail — и отчитывался «все тесты проходят».
Отчёт был честным по форме и ложным по сути. Правило «не трогай тесты, чтобы
позеленить» в инструкциях есть, но держится только на дисциплине.

ЧТО ЛОВИТ (сравнение файла ДО и ПОСЛЕ правки)
  1) уменьшилось число функций test_*;
  2) пропала функция test_* с прежним именем (и это не переименование);
  3) появились новые skip/xfail (pytest.mark.skip/skipif/xfail, pytest.skip(),
     unittest.skip);
  4) уменьшилось число проверок (assert, self.assert*).

ЧЕГО НЕ ЛОВИТ
«Переворот» проверки (`assert paid == 0` -> `assert paid == 1`): число проверок
то же, имена те же. Это видно только при чтении диффа теста глазами.

ОТКУДА БЕРЁТСЯ «ДО»
- Файл под git и есть в HEAD -> версия из HEAD (`git show HEAD:<путь>`). Сравнение
  идёт с последним коммитом, то есть накопительно за всю незакоммиченную работу.
- Иначе -> снимок в `<корень проекта>/.claude-tests-snapshot/<относительный путь>`.
  Хук срабатывает ПОСЛЕ записи, поэтому при первом касании файла «до» уже не
  восстановить: снимок создаётся из текущего состояния и служит базой для всех
  следующих правок (после каждой проверки снимок обновляется). Значит, первая
  правка нового незакоммиченного файла не проверяется. Каталог снимков стоит
  добавить в .gitignore.

ЗАЩИТА ОТ ШУМА (перенос и переименование)
- Переименование внутри файла (число функций то же, имя сменилось) — не сигнал.
- Пропавшие функции нашлись в ДРУГОМ тест-файле проекта — это перенос, молчим
  (и про просевшие assert'ы тоже).
- Под git: если общее число функций test_* во всех тест-файлах проекта не
  уменьшилось относительно HEAD — молчим о падении числа функций и assert'ов.

КОНТРАКТ CLAUDE CODE (PostToolUse)
- Вход: JSON на stdin (tool_name, tool_input.file_path, cwd, ...).
- exit 0 — молчим. exit 2 + stderr — текст уходит АГЕНТУ. Запись уже произошла:
  это сигнал «верни тест или объясни оператору», а не блокировка.
- Fail-open на любой внутренней ошибке.
- Обход: TESTS_GUARD_OFF=1 (осознанно, например при переносе тестов).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

SNAPSHOT_DIR = ".claude-tests-snapshot"
MAX_BYTES = 2_000_000
MAX_SCAN_FILES = 2000  # предел обхода проекта при поиске перенесённых тестов
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", SNAPSHOT_DIR,
             ".tox", ".mypy_cache", ".pytest_cache", "build", "dist"}

TEST_FUNC = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+(test\w*)[ \t]*\(", re.M)
SKIP_MARK = re.compile(
    r"pytest\.mark\.(?:skip|skipif|xfail)\b|pytest\.(?:skip|xfail)\s*\(|"
    r"unittest\.skip\w*|@skip(?:If|Unless)?\b|\.skipTest\s*\("
)
ASSERT = re.compile(r"(?<![\w.])assert\b|\bself\.assert\w+\s*\(|\bpytest\.raises\s*\(")


def is_test_file(path: Path) -> bool:
    """Тест-файл: test_*.py, *_test.py или любой .py внутри каталога tests/."""
    if path.suffix.lower() != ".py":
        return False
    name = path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(part.lower() == "tests" for part in path.parent.parts)


def _git(args: list[str], cwd: Path) -> str | None:
    """Вывод git-команды или None при ошибке."""
    try:
        res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.decode("utf-8", errors="replace")


def git_root(path: Path) -> Path | None:
    out = _git(["rev-parse", "--show-toplevel"], path.parent)
    return Path(out.strip()) if out and out.strip() else None


def git_head_text(root: Path, path: Path) -> str | None:
    """Содержимое файла в HEAD или None, если файла там нет."""
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    return _git(["show", f"HEAD:{rel}"], root)


def analyze(text: str) -> dict:
    """Метрики тест-файла: имена функций, число skip-меток и проверок."""
    return {
        "funcs": TEST_FUNC.findall(text),
        "skips": len(SKIP_MARK.findall(text)),
        "asserts": len(ASSERT.findall(text)),
    }


def _read(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def iter_test_files(root: Path):
    """Тест-файлы проекта (с пределом, без служебных каталогов)."""
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if is_test_file(p):
                seen += 1
                if seen > MAX_SCAN_FILES:
                    return
                yield p


def names_elsewhere(root: Path, exclude: Path, names: set[str]) -> set[str]:
    """Какие из имён функций есть в других тест-файлах проекта (перенос)."""
    found: set[str] = set()
    if not names:
        return found
    ex = exclude.resolve()
    for p in iter_test_files(root):
        if p.resolve() == ex:
            continue
        text = _read(p)
        if text:
            found |= names & set(TEST_FUNC.findall(text))
            if found == names:
                break
    return found


def git_total_funcs(root: Path) -> tuple[int, int] | None:
    """(число test_* в HEAD, число сейчас) по всем тест-файлам проекта."""
    listing = _git(["ls-tree", "-r", "--name-only", "HEAD"], root)
    if listing is None:
        return None
    head_total = 0
    files = [f for f in listing.splitlines() if is_test_file(Path(f))][:MAX_SCAN_FILES]
    for rel in files:
        text = _git(["show", f"HEAD:{rel}"], root)
        if text:
            head_total += len(TEST_FUNC.findall(text))
    now_total = 0
    for p in iter_test_files(root):
        text = _read(p)
        if text:
            now_total += len(TEST_FUNC.findall(text))
    return head_total, now_total


def snapshot_path(root: Path, path: Path) -> Path | None:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return root / SNAPSHOT_DIR / rel


def compare(before: str, after: str, *, moved: set[str] | None = None,
            total_ok: bool = False) -> list[str]:
    """Чистое сравнение двух версий тест-файла. Список замечаний.

    moved — имена пропавших функций, найденные в других файлах проекта;
    total_ok — общее число тестов в проекте не уменьшилось.
    """
    b, a = analyze(before), analyze(after)
    moved = moved or set()
    notes: list[str] = []
    lost = [n for n in dict.fromkeys(b["funcs"]) if n not in set(a["funcs"])]
    added = [n for n in dict.fromkeys(a["funcs"]) if n not in set(b["funcs"])]
    truly_lost = [n for n in lost if n not in moved]
    is_move = bool(lost) and not truly_lost
    count_drop = len(a["funcs"]) < len(b["funcs"])

    if count_drop and not is_move and not total_ok:
        notes.append(f"Число тестов в файле уменьшилось: {len(b['funcs'])} -> "
                     f"{len(a['funcs'])}.")
    # Пропавшее имя — сигнал, только если это не переименование (новых имён меньше)
    if truly_lost and len(added) < len(lost) and not total_ok:
        notes.append("Пропали тесты: " + ", ".join(truly_lost[:10]) +
                     (" ..." if len(truly_lost) > 10 else "") + ".")
    if a["skips"] > b["skips"]:
        notes.append(f"Добавлены skip/xfail: было {b['skips']}, стало {a['skips']}. "
                     f"Пропущенный тест не проверяет ничего.")
    if a["asserts"] < b["asserts"] and not is_move and not total_ok:
        notes.append(f"Проверок (assert) стало меньше: {b['asserts']} -> "
                     f"{a['asserts']}.")
    return notes


def evaluate(file_path: str, cwd: str = "") -> list[str]:
    """Замечания по записанному тест-файлу. Обновляет снимок вне git."""
    if not file_path:
        return []
    path = Path(file_path)
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    if not is_test_file(path):
        return []
    after = _read(path)
    if after is None:
        return []

    root = git_root(path)
    before = git_head_text(root, path) if root else None
    using_git = before is not None
    snap: Path | None = None
    if not using_git:
        root = root or (Path(cwd) if cwd else path.parent)
        snap = snapshot_path(root, path)
        if snap is None:
            return []
        before = _read(snap)
        try:
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_text(after, encoding="utf-8")
        except OSError:
            pass
        if before is None:
            return []  # первое касание: база создана, сравнивать не с чем

    assert before is not None and root is not None
    notes = compare(before, after)
    if not notes:
        return []
    b_names = set(TEST_FUNC.findall(before))
    lost = b_names - set(TEST_FUNC.findall(after))
    moved = names_elsewhere(root, path, lost)
    total_ok = False
    if using_git:
        totals = git_total_funcs(root)
        if totals and totals[1] >= totals[0]:
            total_ok = True
    return compare(before, after, moved=moved, total_ok=total_ok)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0
    if os.environ.get("TESTS_GUARD_OFF") == "1":
        return 0
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    try:
        notes = evaluate(file_path, payload.get("cwd") or "")
    except Exception:
        return 0
    if not notes:
        return 0
    sys.stderr.write(
        f"Сторож тестов: правка ослабила тесты в {file_path}\n\n- " +
        "\n- ".join(notes) +
        "\n\nЗапись уже произошла. Если тест мешает — почини КОД, а не тест. "
        "Если тест действительно устарел — верни его или прямо скажи оператору, "
        "какой тест убран и почему; не пиши «все тесты проходят».\n"
        "Осознанный перенос/удаление: TESTS_GUARD_OFF=1.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
