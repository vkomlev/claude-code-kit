# -*- coding: utf-8 -*-
"""Тесты хука tests_guard.py: сравнение версий, git-режим, режим снимков, точка входа."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS))
import tests_guard as tg  # noqa: E402

BASE = """
def test_paid():
    assert paid() == 0

def test_refund():
    assert refund() == 1
    assert refund() > 0
"""


def test_is_test_file() -> None:
    assert tg.is_test_file(Path("a/test_x.py"))
    assert tg.is_test_file(Path("a/x_test.py"))
    assert tg.is_test_file(Path("proj/tests/helpers.py"))
    assert not tg.is_test_file(Path("proj/app/x.py"))
    assert not tg.is_test_file(Path("proj/tests/data.json"))


def test_compare_no_change() -> None:
    assert tg.compare(BASE, BASE) == []


def test_compare_removed_function() -> None:
    after = "\ndef test_paid():\n    assert paid() == 0\n"
    notes = tg.compare(BASE, after)
    assert any("уменьшилось" in n for n in notes)
    assert any("test_refund" in n for n in notes)


def test_compare_skip_added() -> None:
    after = "import pytest\n@pytest.mark.skip\n" + BASE.lstrip()
    notes = tg.compare(BASE, after)
    assert any("skip" in n for n in notes)


def test_compare_xfail_and_runtime_skip() -> None:
    after = BASE + "\ndef test_x():\n    pytest.skip('later')\n    assert 1\n"
    assert any("skip" in n for n in tg.compare(BASE, after))


def test_compare_asserts_dropped() -> None:
    after = BASE.replace("    assert refund() > 0\n", "")
    notes = tg.compare(BASE, after)
    assert any("assert" in n for n in notes)


def test_compare_rename_is_silent() -> None:
    after = BASE.replace("test_refund", "test_refund_full")
    assert tg.compare(BASE, after) == []


def test_compare_flip_not_detected() -> None:
    """Переворот проверки сознательно не ловится — только чтением глазами."""
    after = BASE.replace("== 0", "== 1")
    assert tg.compare(BASE, after) == []


def test_compare_moved_is_silent() -> None:
    after = "\ndef test_paid():\n    assert paid() == 0\n"
    assert tg.compare(BASE, after, moved={"test_refund"}) == []


def test_compare_total_ok_silences_count_but_not_skip() -> None:
    after = "import pytest\n@pytest.mark.xfail\ndef test_paid():\n    assert paid() == 0\n"
    notes = tg.compare(BASE, after, total_ok=True)
    assert len(notes) == 1 and "skip" in notes[0]


# --- git-режим --------------------------------------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_pay.py").write_text(BASE, encoding="utf-8")
    (tmp_path / "tests" / "test_other.py").write_text(
        "def test_other():\n    assert True\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_git_deletion_signals(repo: Path) -> None:
    f = repo / "tests" / "test_pay.py"
    f.write_text("\ndef test_paid():\n    assert paid() == 0\n", encoding="utf-8")
    notes = tg.evaluate(str(f))
    assert any("test_refund" in n for n in notes)


def test_git_move_to_other_file_is_silent(repo: Path) -> None:
    f = repo / "tests" / "test_pay.py"
    f.write_text("\ndef test_paid():\n    assert paid() == 0\n", encoding="utf-8")
    (repo / "tests" / "test_refund.py").write_text(
        "def test_refund():\n    assert refund() == 1\n    assert refund() > 0\n",
        encoding="utf-8")
    assert tg.evaluate(str(f)) == []


def test_git_untouched_is_silent(repo: Path) -> None:
    assert tg.evaluate(str(repo / "tests" / "test_pay.py")) == []


def test_non_test_file_ignored(repo: Path) -> None:
    f = repo / "app.py"
    f.write_text("x = 1\n", encoding="utf-8")
    assert tg.evaluate(str(f)) == []


# --- режим снимков (без git) ------------------------------------------------

def test_snapshot_first_touch_then_compare(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    f = proj / "test_new.py"
    f.write_text(BASE, encoding="utf-8")
    # первое касание: база создаётся, сигнала нет
    assert tg.evaluate(str(f), cwd=str(proj)) == []
    snap = proj / tg.SNAPSHOT_DIR / "test_new.py"
    assert snap.is_file()
    # вторая правка: удаление ловится
    f.write_text("\ndef test_paid():\n    assert paid() == 0\n", encoding="utf-8")
    notes = tg.evaluate(str(f), cwd=str(proj))
    assert any("test_refund" in n for n in notes)
    # снимок обновился: повторная проверка того же состояния молчит
    assert tg.evaluate(str(f), cwd=str(proj)) == []


# --- точка входа ------------------------------------------------------------

def _run(payload: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("TESTS_GUARD_OFF", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(HOOKS / "tests_guard.py")],
                          input=payload.encode("utf-8"), capture_output=True, env=env)


def test_main_empty_payload() -> None:
    assert _run("{}").returncode == 0
    assert _run("").returncode == 0
    assert _run("не json").returncode == 0


def test_main_signals_and_bypass(repo: Path) -> None:
    f = repo / "tests" / "test_pay.py"
    f.write_text("def test_paid():\n    assert paid() == 0\n", encoding="utf-8")
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(f)},
                          "cwd": str(repo)})
    res = _run(payload)
    assert res.returncode == 2
    assert "TESTS_GUARD_OFF=1" in res.stderr.decode("utf-8")
    assert _run(payload, {"TESTS_GUARD_OFF": "1"}).returncode == 0
