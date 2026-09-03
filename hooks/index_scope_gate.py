#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PreToolUse-гейт: `git commit` без pathspec уносит чужие файлы из ОБЩЕГО индекса.

Параллельные сессии делят рабочий каталог и один `.git/index`. `git add <свой файл>` +
`git commit` без pathspec коммитит ВЕСЬ индекс — включая то, что успела застейджить
соседняя сессия. Точечный `git add` не гарантия: он добавляет в индекс, но не чистит его.

За 2026-07-16 — 4 эпизода в обе стороны (codex унёс мой task-файл; я унёс чужой; чужая
сессия унесла мою запись CHANGELOG; я унёс 8 файлов чужой работы в SPW — через час после
того, как сам записал правило в ADR-0008). Правило-текст есть и не срабатывает: тот же
класс «soft-rule обходится под нагрузкой», что у db_write_gate / chip_tree_gate /
skill_engage_gate.

ПРИЗНАК ВЛАДЕНИЯ — ТРАНСКРИПТ СЕССИИ. Git владение не даёт: автор у всех сессий один,
привязки файл↔сессия в индексе нет. Сессия владеет файлом, если в ЕЁ транскрипте есть
`Edit`/`Write`/`NotebookEdit` этого файла ИЛИ её собственный `git add <путь>`.

Контракт Claude Code:
- Вход: JSON на stdin; поля tool_name, tool_input.command, transcript_path, cwd.
- Блокировка: exit code 2 + причина на stderr (её читает агент).
- Пропуск: exit code 0.

Логика:
  1. Не Bash / не `git commit` -> пропустить.
  2. Override `CHIP_SOLO=1` (в команде или окружении) -> пропустить. Семантика та же, что у
     chip_tree_gate («я один в этом дереве»), поэтому второй флаг под тот же смысл не заводим.
  3. Есть pathspec (`git commit ... -- <пути>`) -> пропустить: коммитятся только названные
     файлы. ВНИМАНИЕ: pathspec берёт РАБОЧЕЕ ДЕРЕВО и игнорирует индекс — в смешанном файле
     он присвоит чужие КУСКИ (ADR-0008 § «Общий файл»). Здесь мы ловим ФАЙЛОВЫЙ вектор.
  4. Иначе: staged = `git diff --cached --name-only`; если в нём есть файлы, которых нет во
     владении сессии -> БЛОК со списком.

НЕ покрывает (осознанно):
- Codex/Cursor — они Claude-хуки не исполняют. Для Root есть git-level `staged_scope_guard`.
- chunk-level в общем файле — техника из ADR-0008 § «Общий файл», гейтом не ловится.
- `git commit -a` — стейджит в момент коммита, `git diff --cached` его не видит; предупреждаем.

Fail-open: любая ошибка разбора/git -> пропустить (exit 0). Productivity-гейт не должен
заклинивать работу из-за собственного бага.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Windows: консоль по умолчанию cp1251 — принудительно UTF-8, иначе русский текст причины
# приходит агенту кракозябрами и гейт бесполезен (поймано живой проверкой, не тестами).
for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

OVERRIDE_RE = re.compile(r"\bCHIP_SOLO\s*=\s*(1|true|yes)\b", re.IGNORECASE)
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# Команда — git commit (возможен префикс env/пробелы, `git -C <path> commit`).
GIT_COMMIT_RE = re.compile(r"\bgit\b(?:\s+-C\s+\S+)?(?:\s+--\S+)*\s+commit\b")

# Файлы, которые pre-commit-хук САМ стейджит в общий индекс, — не работа сессии и не
# clobber-able. Их нельзя считать «чужими»: сессия их не касалась по определению, но
# и присвоить чужое ими нельзя (append-only машинный вывод, который штатно уезжает в
# любой коммит). `tasks/_audit.log` дописывается и `git add`-ается хуком Root
# audit_log.py на каждом коммите со сменой status задачи; в pathspec-коммите
# он орфанится в общем `.git/index` и выглядит чужим для следующей сессии — 6 из 8
# срабатываний гейта за 17–18.07.2026 были ровно этим ложным блоком (находка внутренней задаче).
# Ключи — в нормализованном виде (_norm): нижний регистр, прямые слэши, repo-relative.
SYSTEM_GENERATED = frozenset({"tasks/_audit.log"})


def _is_git_commit(command: str) -> bool:
    return bool(GIT_COMMIT_RE.search(command or ""))


def has_pathspec(command: str) -> bool:
    """True, если в `git commit` есть `--` с путями после него.

    `--` внутри значения -m (напр. текст сообщения) не считаем: смотрим только
    аргументы уровня команды через shlex.
    """
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return False
    try:
        i = parts.index("commit")
    except ValueError:
        return False
    rest = parts[i + 1:]
    if "--" not in rest:
        return False
    return len(rest[rest.index("--") + 1:]) > 0


def has_commit_all(command: str) -> bool:
    """`git commit -a/--all` — стейджит при коммите, индекс до него неполный."""
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return False
    for p in parts:
        if p == "--all" or (re.fullmatch(r"-[a-zA-Z]+", p or "") and "a" in p[1:]):
            return True
    return False


def _msys_to_win(path: str) -> str:
    """`/d/Work/SPW` (стиль Git Bash) -> `~/projects/SPW`. Python в MSYS-путь не зайдёт."""
    m = re.fullmatch(r"/([a-zA-Z])(/.*)?", path or "")
    if m:
        return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return path


def effective_cwd(command: str, payload_cwd: str) -> str:
    """Каталог, в котором РЕАЛЬНО выполнится git.

    Критично: агент почти всегда пишет `cd <репозиторий> && git commit ...`, а `payload.cwd`
    — это cwd СЕССИИ (напр. ~/projects/tg-bot). Без разбора `cd` гейт проверял чужой индекс
    (обычно пустой) и молча пропускал — так он и не сработал при первой живой проверке.
    """
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return payload_cwd
    for i, p in enumerate(parts):
        if p == "cd" and i + 1 < len(parts):
            target = _msys_to_win(parts[i + 1])
            if not Path(target).is_absolute() and payload_cwd:
                target = str(Path(payload_cwd) / target)
            return target
    return payload_cwd


def _walk_tool_uses(node: object, out: list[tuple[str, dict]]) -> None:
    """Рекурсивно собирает структурные tool_use (name, input) из события транскрипта."""
    if isinstance(node, dict):
        if node.get("type") == "tool_use" and isinstance(node.get("name"), str):
            inp = node.get("input")
            out.append((node["name"], inp if isinstance(inp, dict) else {}))
        for value in node.values():
            _walk_tool_uses(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_tool_uses(value, out)


def git_add_paths(command: str) -> list[str]:
    """Пути, названные в `git add <пути>`. Для `-A`/`.`/`-u` путей нет -> пусто."""
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return []
    out: list[str] = []
    i = 0
    while i < len(parts):
        if parts[i] == "git":
            j = i + 1
            while j < len(parts) and parts[j] in ("-C",):
                j += 2
            if j < len(parts) and parts[j] == "add":
                for arg in parts[j + 1:]:
                    if arg.startswith("-") or arg in (".", "*"):
                        continue
                    if arg in ("&&", "||", ";", "|"):
                        break
                    out.append(arg)
        i += 1
    return out


def owned_paths(transcript_path: str) -> set[str]:
    """Файлы, которых касалась ЭТА сессия: Edit/Write + собственные `git add <путь>`."""
    owned: set[str] = set()
    if not transcript_path:
        return owned
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
                uses: list[tuple[str, dict]] = []
                _walk_tool_uses(event, uses)
                for name, inp in uses:
                    if name in EDIT_TOOLS:
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if isinstance(fp, str) and fp:
                            owned.add(fp)
                    elif name == "Bash":
                        cmd = inp.get("command")
                        if isinstance(cmd, str):
                            owned.update(git_add_paths(cmd))
    except OSError:
        return owned
    return owned


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().strip('"').lower()


def normalize_owned(owned: set[str], repo_root: str) -> set[str]:
    """Пути сессии -> repo-relative (как отдаёт `git diff --cached --name-only`)."""
    root = _norm(repo_root).rstrip("/")
    out: set[str] = set()
    for raw in owned:
        n = _norm(raw)
        if root and n.startswith(root + "/"):
            out.add(n[len(root) + 1:])
        else:
            out.add(n.lstrip("./"))
    return out


def _git(args: list[str], cwd: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd or None, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def foreign_staged(staged: list[str], owned_rel: set[str]) -> list[str]:
    """Файлы в индексе, которых сессия не касалась (по basename тоже — на случай
    относительных `git add` из подкаталога).

    SYSTEM_GENERATED исключены: их впрыскивает в общий индекс сам pre-commit-хук
    (не работа сессии, не clobber-able) — иначе они дают ложный блок."""
    owned_bases = {p.rsplit("/", 1)[-1] for p in owned_rel}
    out = []
    for f in staged:
        fn = _norm(f)
        if fn in SYSTEM_GENERATED:
            continue
        if fn in owned_rel:
            continue
        if fn.rsplit("/", 1)[-1] in owned_bases:
            continue
        out.append(f)
    return out


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not _is_git_commit(command):
        return 0
    if OVERRIDE_RE.search(command) or os.environ.get("CHIP_SOLO", "").strip().lower() in {"1", "true", "yes"}:
        return 0
    if has_pathspec(command):
        return 0

    cwd = effective_cwd(command, payload.get("cwd") or os.getcwd())
    root_out = _git(["rev-parse", "--show-toplevel"], cwd)
    if not root_out:
        return 0  # не git-репозиторий — не наше дело
    repo_root = root_out.strip()

    staged_out = _git(["diff", "--cached", "--name-only"], cwd)
    if staged_out is None:
        return 0
    staged = [l.strip() for l in staged_out.splitlines() if l.strip()]
    if not staged:
        return 0

    owned_rel = normalize_owned(owned_paths(payload.get("transcript_path", "") or ""), repo_root)
    if not owned_rel:
        return 0  # владение не восстановилось (нет транскрипта) — не мешаем работать

    foreign = foreign_staged(staged, owned_rel)
    if not foreign:
        return 0

    listed = "\n".join(f"  {f}" for f in foreign[:15])
    more = f"\n  … и ещё {len(foreign) - 15}" if len(foreign) > 15 else ""
    warn_all = (
        "\nВНИМАНИЕ: у команды есть -a/--all — она добавит и НЕотслеженные правки поверх.\n"
        if has_commit_all(command) else ""
    )
    sys.stderr.write(
        "[index_scope_gate] В индексе есть файлы, которых эта сессия НЕ касалась:\n"
        f"{listed}{more}\n{warn_all}"
        "\n`git commit` без pathspec коммитит ВЕСЬ индекс — рабочий каталог общий, и соседняя\n"
        "сессия могла застейджить своё между твоими `git add` и `git commit`. Точечный\n"
        "`git add` не гарантия: он добавляет в индекс, но не чистит его от чужого.\n"
        "\nСделай одно из трёх:\n"
        "  1) Коммить только своё pathspec'ом:\n"
        "     git commit -m \"...\" -- <свои файлы>\n"
        "     (файл целиком твой; в СМЕШАННОМ файле pathspec присвоит чужие куски —\n"
        "      тогда техника из ADR-0008 § «Общий файл»)\n"
        "  2) Сними чужое из индекса: git restore --staged <файл>\n"
        "  3) Ты один в дереве и это осознанно — префикс CHIP_SOLO=1 к команде.\n"
        "\nМеханический гейт: правило ADR-0008 «сперва git diff --cached --name-only»\n"
        "на памяти агента не срабатывало — 4 эпизода за 2026-07-16, в обе стороны.\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — fail-open: гейт не должен ронять работу
        sys.exit(0)
