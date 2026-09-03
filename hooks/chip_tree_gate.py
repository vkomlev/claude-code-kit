#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PreToolUse-гейт: блокирует tree-global разрушительные команды, опасные в ОБЩЕМ дереве.

Механический контроль поверх правила из ~/.claude/CLAUDE.md
(§ «Параллельные фоновые чипы в одном рабочем дереве»). Инцидент 2026-07-15:
5 фоновых чипов работали в одном `~/projects/SPW`; чип создал временный git-worktree,
`node_modules` там был junction-ссылкой, и `git worktree remove --force` прошёл сквозь
ссылку и снёс РЕАЛЬНЫЙ общий `node_modules` — заблокировав среду всем пяти чипам.
Плюс гонки сборок, конфликт dev-сервера на порту 3000 и `git stash`, сметавший чужой WIP.

Тот же класс отказа, что и с /db-check и авто-подбором скиллов: правило-текст на память
агента не срабатывает под нагрузкой. Хук не полагается на память — он ловит именно тот
узкий набор команд, что уничтожает или сметает чужую работу в общем дереве.

Контракт Claude Code:
- Вход: JSON на stdin с полями tool_name и tool_input.command (для Bash).
- Блокировка: exit code 2 + текст причины на stderr (показывается агенту).
- Пропуск: exit code 0.

Логика (узкий блок-лист — решение оператора внутренней задаче):
  1. Не Bash → пропустить.
  2. Явный override (CHIP_SOLO=1 в команде или в окружении) → пропустить
     (агент подтвердил: он один в этом дереве, операция осознанная).
  3. Команда содержит одну из tree-global разрушительных сигнатур → БЛОК:
       - git worktree remove --force / -f  (снос сквозь junction — реальный вектор потери)
       - rm -r(f) ... node_modules         (снос общих зависимостей)
       - bare git stash / stash push / stash save БЕЗ pathspec (`--`) — сметает чужой WIP
       - git reset --hard                  (откат чужих незакоммиченных правок)
       - git clean -f...                   (удаление чужих untracked-файлов)
  4. Иначе → пропустить.

НЕ блокируем (сознательно, узкий список): `rm -rf .next` (рутинная чистка сборки),
`git stash pop/apply/list/show/drop`, обычные git add/commit/build/dev-server.

Fail-open: при любой ошибке разбора хук пропускает (exit 0) — productivity-гейт
не должен заклинивать работу из-за собственного бага.
"""
from __future__ import annotations

import json
import os
import re
import sys

# Windows: консоль по умолчанию cp1251 — принудительно UTF-8, чтобы русский текст
# причины (stderr) дошёл до Claude Code без mojibake, а stdin читался как UTF-8.
for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

OVERRIDE_TOKEN_RE = re.compile(r"\bCHIP_SOLO\s*=\s*(1|true|yes)\b", re.IGNORECASE)

# Контексты-«данные», где эти команды упоминаются как ТЕКСТ, а не выполняются:
# тело heredoc (`<<'EOF' … EOF`) и аргумент сообщения коммита/тега (`-m "…"`).
# Их вырезаем перед матчингом — иначе `git commit -m "…git worktree remove --force…"`
# и `echo`-документация ложно блокируются. Кавычки в АРГУМЕНТАХ пути НЕ трогаем
# (чтобы `rm -rf "node_modules"` по-прежнему ловился).
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$", re.DOTALL | re.MULTILINE)
_MSG_ARG_SQ_RE = re.compile(r"(?:-a?m|--message|-C)\s+'[^']*'")
_MSG_ARG_DQ_RE = re.compile(r'(?:-a?m|--message|-C)\s+"[^"]*"')


def _strip_data_contexts(cmd: str) -> str:
    """Убрать тело heredoc и текст сообщения коммита — там команды лишь упомянуты."""
    cmd = _HEREDOC_RE.sub(" ", cmd)
    cmd = _MSG_ARG_SQ_RE.sub(" ", cmd)
    cmd = _MSG_ARG_DQ_RE.sub(" ", cmd)
    return cmd

# --- Сигнатуры tree-global разрушительных команд -----------------------------
# 1) git worktree remove --force / -f  — прошёл сквозь junction node_modules и снёс
#    реальную папку (вектор «случайного удаления» в инциденте).
WORKTREE_FORCE_RE = re.compile(
    r"\bgit\s+worktree\s+remove\b(?=.*(?:--force|(?<!\w)-f\b|-\w*f))",
    re.IGNORECASE | re.DOTALL,
)

# 2) rm -r(+f) ... node_modules  — снос общих зависимостей. Требуем рекурсивный флаг
#    (иначе rm без -r на директории и так не сработает) и токен node_modules.
RM_NODE_MODULES_RE = re.compile(
    r"\brm\b(?=[^\n;&|]*(?:-\w*r|--recursive))[^\n;&|]*\bnode_modules\b",
    re.IGNORECASE,
)

# 3) git reset --hard  — откат незакоммиченных правок (в т.ч. чужих в общем дереве).
GIT_RESET_HARD_RE = re.compile(r"\bgit\s+reset\b(?=[^\n;&|]*--hard)", re.IGNORECASE)

# 4) git clean -f...  — удаление untracked-файлов (git без -f и не станет чистить).
GIT_CLEAN_FORCE_RE = re.compile(
    r"\bgit\s+clean\b(?=[^\n;&|]*(?:--force|(?<!\w)-\w*f))",
    re.IGNORECASE,
)


def _is_bare_git_stash(cmd: str) -> bool:
    """True для `git stash` / `git stash push|save` БЕЗ pathspec (`--`).

    Bare-stash кладёт в стек ВСЕ незакоммиченные правки рабочего дерева, включая чужие
    (инцидент: обход отметил «untracked new files orphaned»). Точечный
    `git stash push -- <файлы>` безопасен — его пропускаем.
    Read-only/восстановительные подкоманды (pop/apply/list/show/drop/branch) — не трогаем.
    """
    for m in re.finditer(r"\bgit\s+stash\b([^\n;&|]*)", cmd, re.IGNORECASE):
        rest = m.group(1).strip()
        first = rest.split()[0].lower() if rest.split() else ""
        # Безопасные подкоманды stash.
        if first in {"pop", "apply", "list", "show", "drop", "branch", "clear"}:
            continue
        # Точечный stash с pathspec — не сметает чужое.
        if "--" in rest:
            continue
        # bare `git stash`, `git stash push [-u/-a/-k]`, `git stash save "msg"` — блок.
        return True
    return False


def _override_present(cmd: str) -> bool:
    if OVERRIDE_TOKEN_RE.search(cmd):
        return True
    return os.environ.get("CHIP_SOLO", "").strip().lower() in {"1", "true", "yes"}


def _matched_rule(cmd: str) -> str:
    """Имя сработавшего правила или пустая строка."""
    if WORKTREE_FORCE_RE.search(cmd):
        return "git worktree remove --force (снос сквозь junction — вектор потери файлов)"
    if RM_NODE_MODULES_RE.search(cmd):
        return "rm -rf node_modules (снос общих зависимостей — блокирует все чипы в дереве)"
    if GIT_RESET_HARD_RE.search(cmd):
        return "git reset --hard (откат незакоммиченных правок, в т.ч. чужих)"
    if GIT_CLEAN_FORCE_RE.search(cmd):
        return "git clean -f (удаление untracked-файлов, в т.ч. чужих)"
    if _is_bare_git_stash(cmd):
        return "git stash без pathspec (сметает чужой незакоммиченный WIP в общем дереве)"
    return ""


REASON = """\
[chip_tree_gate] Опасная для ОБЩЕГО рабочего дерева команда:
  правило: {rule}

Инцидент внутренней задаче (2026-07-15): несколько фоновых чипов делили одно дерево;
такая команда снесла общий node_modules и смела чужой WIP. Правило —
~/.claude/CLAUDE.md § «Параллельные фоновые чипы в одном рабочем дереве».

Прежде чем выполнять, убедись что ты ОДИН в этом дереве:
  1) Ты — единственный чип/сессия, работающий в этом каталоге прямо сейчас?
     (другой чип может собирать, держать dev-сервер или иметь незакоммиченный код)
  2) Нет ли безопаснее? — точечный `git stash push -- <файлы>` вместо bare stash;
     `rm -rf .next` вместо сноса node_modules; свой git worktree вместо общего дерева.

Если ты осознанно один в дереве и операция нужна — добавь префикс CHIP_SOLO=1
к команде (напр. `CHIP_SOLO=1 git reset --hard origin/master`).

Это механический гейт (как db_write_gate для БД): правило-текст на память агента
под нагрузкой не срабатывает. Маркер = осознанное решение, а не молчаливый снос.
"""


def evaluate(cmd: str) -> str:
    """Возвращает имя правила для блокировки, или '' для пропуска."""
    if not cmd:
        return ""
    if _override_present(cmd):
        return ""
    # Матчим по команде БЕЗ тел heredoc и сообщений коммита — там команды лишь упомянуты.
    return _matched_rule(_strip_data_contexts(cmd))


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "") or ""

    rule = evaluate(command)
    if rule:
        sys.stderr.write(REASON.format(rule=rule) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
