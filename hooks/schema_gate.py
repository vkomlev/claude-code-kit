#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""PreToolUse-гейт «схема до SQL».

Три недели подряд (15.09, 22.09, 29.09) один и тот же класс: SQL пишут по УГАДАННОЙ
схеме и ловят `column/relation ... does not exist` (за неделю 22–29.09 — 14 сессий в двух
проектах; выдуманные имена повторяются: participant_id, charges, homework, identity_links).
Текстовое правило «схема ДО SQL» живёт только в /db-check и не держит: в 8 сессиях SQL
писали мимо скилла, в 4 — скилл был, а information_schema смотрели уже ПОСЛЕ ошибки.

ЧТО ДЕЛАЕТ. Перед SQL-вызовом извлекает таблицы из FROM/JOIN/UPDATE/INSERT INTO/DELETE
FROM (схемы вида `content_hub.x` и алиасы учитываются, CTE-имена — не таблицы) и требует,
чтобы в ТЕКУЩЕЙ сессии раньше была видна схема каждой из них. Иначе — блок с готовым
запросом к information_schema по этим таблицам.

«СХЕМА ВИДНА» (история — транскрипт сессии, как в index_scope_gate):
  - запрос к information_schema.columns / pg_attribute с `table_name = 'x'` / `IN (...)`
    / `'x'::regclass`, psql `\d x`, `DESCRIBE x`;
  - такой же запрос БЕЗ фильтра по таблице (по всей схеме) — тогда известными считаются
    имена из его результата;
  - успешный `SELECT * FROM x` (столбцы видны в выводе);
  - `CREATE TABLE x` в этой же сессии.

ГДЕ ИЩЕТ SQL. MCP-инструменты БД (`mcp__*db*__query`, правило — schema_gate.json);
Bash с клиентом (psql, python, sqlite3): SQL-строки в команде, heredoc, `psql -f file`,
и тело запускаемого .py — но только ad-hoc скрипта (во временном каталоге/скратчпаде или
созданного этой сессией). Штатные скрипты проекта не разбираются: их SQL не угадан
сейчас, а гейт на каждом `python -m app` был бы шумом.

НЕ ТРОГАЕТ: SELECT без FROM (`SELECT 1`, `now()`), системные каталоги (information_schema,
pg_catalog, pg_*), функции в FROM (generate_series, unnest, EXTRACT(x FROM y)), `from x
import` в Python, alembic/pytest/pip, test_*.py и tests/.

Обход: `SCHEMA_OK=1` в Bash-команде; в SQL MCP-запроса — комментарий `-- SCHEMA_OK`.
Fail-open: любая ошибка разбора -> пропуск (exit 0). Вход — JSON на stdin (tool_name,
tool_input, transcript_path, cwd); блок — exit 2 + причина в stderr.
Прогон по транскриптам: `python schema_gate.py --replay <jsonl>...`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

for _stream in (sys.stdin, sys.stderr, sys.stdout):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

RULES_PATH = Path(__file__).with_name("schema_gate.json")
SCRIPT_MAX_BYTES = 300_000
SQL_KEYWORDS = frozenset({
    "select", "lateral", "only", "where", "values", "set", "on", "using", "as", "group",
    "order", "limit", "having", "union", "join", "left", "right", "inner", "outer", "cross",
    "full", "natural", "and", "or", "not", "in", "is", "null", "true", "false", "case",
    "when", "then", "else", "end", "from", "into", "update", "delete", "insert", "with",
    "returning", "offset", "fetch", "window", "except", "intersect", "table", "default",
})


def load_rules() -> dict[str, Any]:
    """Читает правила гейта из schema_gate.json."""
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


RULES: dict[str, Any] = load_rules()
MCP_TOOL_RE = re.compile(RULES["mcp_tool_regex"], re.IGNORECASE)
CLIENT_RE = re.compile(RULES["bash_client_regex"], re.IGNORECASE)
BASH_SKIP_RE = re.compile(RULES["bash_skip_regex"], re.IGNORECASE)
SQL_VERB_RE = re.compile(RULES["sql_verb_regex"], re.IGNORECASE)
OVERRIDE_RE = re.compile(RULES["override_regex"], re.IGNORECASE)
SYSTEM_SCHEMAS = frozenset(s.lower() for s in RULES["system_schemas"])
SYSTEM_PREFIXES = tuple(p.lower() for p in RULES["system_table_prefixes"])
FROM_FUNCS = frozenset(f.lower() for f in RULES["from_functions"])
SCRIPT_DIR_MARKERS = tuple(m.lower() for m in RULES["script_dir_markers"])

# --- разбор SQL ---------------------------------------------------------------------------
IDENT = r'[A-Za-z_][\w$]*'
# (?![\w$]) — без неё `unnest(` давал обрубок `unnes`: откат на символ обходил проверку `(`.
QIDENT = rf'(?:"[^"]+"|{IDENT}(?![\w$]))'
TABLE_REF_RE = re.compile(rf'\s*(?:only\s+)?({QIDENT})(?:\s*\.\s*({QIDENT}))?(?!\s*\()', re.I)
INTO_REF_RE = re.compile(rf'\s*({QIDENT})(?:\s*\.\s*({QIDENT}))?', re.I)
NEXT_IN_LIST_RE = re.compile(
    rf'\s*(?:(?:as\s+)?(?!(?:where|on|join|left|right|inner|cross|full|group|order|limit|set|using)\b){IDENT})?'
    rf'\s*,\s*(?:only\s+)?({QIDENT})(?:\s*\.\s*({QIDENT}))?(?!\s*\()', re.I)
KW_RE = re.compile(r'\b(from|join|update|into)\b', re.I)
CTE_RE = re.compile(
    rf'(?:\bwith\s+(?:recursive\s+)?|,\s*)({IDENT})\s*(?:\([^)]*\)\s*)?as\s*(?:not\s+)?(?:materialized\s*)?\(',
    re.I)
SQL_START_RE = re.compile(r'^\s*(?:--[^\n]*\n\s*)*(?:select|with|update|insert|delete|explain)\b', re.I)
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\b", re.S)
PSQL_FILE_RE = re.compile(r'\bpsql\b[^|;&]*?\s-f\s*["\']?([^\s"\']+)')
PY_TOKEN_RE = re.compile(r"""["']([^"']+\.py)["']|(?:^|[\s=])([^\s"';|&<>]+\.py)\b""")
CD_RE = re.compile(r"""\s*cd\s+(?:/d\s+)?["']?([^"'&;|]+?)["']?\s*(?:&&|;)""", re.I)


def _strip_noise(sql: str) -> str:
    """Убирает комментарии и содержимое строковых литералов (имена в них — не таблицы)."""
    s = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    s = re.sub(r'--[^\n]*', ' ', s)
    return re.sub(r"'(?:[^']|'')*'", "''", s)


def _unquote(name: str) -> str:
    return name.strip('"').lower()


def _inside_function(s: str, pos: int) -> bool:
    """FROM внутри EXTRACT(...)/SUBSTRING(...)/TRIM(...) — не источник строк."""
    depth = 0
    for i in range(pos - 1, -1, -1):
        ch = s[i]
        if ch == ')':
            depth += 1
        elif ch == '(':
            if depth == 0:
                m = re.search(rf'({IDENT})\s*$', s[:i])
                return bool(m and m.group(1).lower() in FROM_FUNCS)
            depth -= 1
    return False


def _prev_word(s: str, pos: int) -> str:
    m = re.search(rf'({IDENT})\s*$', s[:pos])
    return m.group(1).lower() if m else ""


def _is_system(schema: str | None, table: str) -> bool:
    if schema and schema in SYSTEM_SCHEMAS:
        return True
    return table.startswith(SYSTEM_PREFIXES) or table in SQL_KEYWORDS


def extract_tables(sql: str) -> set[str]:
    """Имена пользовательских таблиц (без схемы, нижний регистр), к которым обращается SQL."""
    s = _strip_noise(sql)
    ctes = {c.lower() for c in CTE_RE.findall(s)}
    out: set[str] = set()
    for m in KW_RE.finditer(s):
        kw = m.group(1).lower()
        prev = _prev_word(s, m.start())
        if kw == "from" and (prev == "distinct" or _inside_function(s, m.start())):
            continue
        if kw == "into" and prev != "insert":
            continue
        if kw == "update" and prev in ("for", "do", "key", "on"):
            continue
        pos = m.end()
        # INSERT INTO t(col, ...) — скобка после имени это список столбцов, не вызов функции.
        ref = (INTO_REF_RE if kw == "into" else TABLE_REF_RE).match(s, pos)
        while ref:
            a, b = ref.group(1), ref.group(2)
            schema, table = (_unquote(a), _unquote(b)) if b else (None, _unquote(a))
            if table == "import" or (kw == "from" and s[ref.end():ref.end() + 8].strip().lower().startswith("import")):
                break
            if table not in ctes and not _is_system(schema, table) and schema != "lateral":
                out.add(table)
            if kw != "from":
                break
            ref = NEXT_IN_LIST_RE.match(s, ref.end())
    return out


SCHEMA_LOOKUP_RE = re.compile(
    r'information_schema\s*\.\s*columns|\bpg_attribute\b|\bpg_get_tabledef\b|'
    r'(?:^|[\s"\'])\\d\+?\s|\bdescribe\s+\w|\bget_columns\s*\(', re.I)
FILTER_LIT_RE = re.compile(r"(?:table_name|relname|attrelid)\s*(?:=|in\s*\()\s*([^)\n]*)", re.I)
REGCLASS_RE = re.compile(r"'([\w.\"]+)'\s*::\s*regclass", re.I)
PSQL_D_RE = re.compile(r'\\d\+?\s+([\w."]+)')
DESCRIBE_RE = re.compile(r'\bdescribe\s+([\w."]+)', re.I)
SELECT_STAR_RE = re.compile(rf'^\s*select\s+\*\s+from\s+({QIDENT}(?:\s*\.\s*{QIDENT})?)\s*(?:$|;|limit|where|order|as\s|\w+\s*(?:$|;|limit|where|order))', re.I)
CREATE_RE = re.compile(rf'\bcreate\s+(?:temp\w*\s+|unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?({QIDENT}(?:\s*\.\s*{QIDENT})?)', re.I)


def _last_part(name: str) -> str:
    return _unquote(name.split(".")[-1])


def schema_lookup(text: str) -> tuple[bool, set[str]]:
    """(это запрос схемы?, таблицы из его фильтра). Пустое множество = фильтра нет."""
    if not SCHEMA_LOOKUP_RE.search(text):
        return False, set()
    names: set[str] = set()
    for chunk in FILTER_LIT_RE.findall(text):
        names.update(n.lower() for n in re.findall(r"'([\w.]+)'", chunk))
    names.update(_last_part(n) for n in REGCLASS_RE.findall(text))
    names.update(_last_part(n) for n in PSQL_D_RE.findall(text))
    names.update(_last_part(n) for n in DESCRIBE_RE.findall(text))
    names.update(n.lower() for n in re.findall(r"get_columns\s*\(\s*['\"](\w+)", text))
    return True, {n.split(".")[-1] for n in names}


# --- где лежит SQL -----------------------------------------------------------------------
def _sql_chunks(text: str) -> list[str]:
    """SQL-фрагменты из произвольного текста (shell/python): куски между кавычками, начинающиеся с SQL-глагола."""
    out: list[str] = []
    for chunk in re.split(r'"""|\'\'\'|"', text):
        if SQL_START_RE.match(chunk):
            out.append(chunk)
            continue
        out.extend(sub for sub in chunk.split("'") if SQL_START_RE.match(sub))
    return out


def _base_dir(cmd: str, cwd: str) -> str:
    m = CD_RE.match(cmd)
    if not m:
        return cwd
    target = m.group(1).strip()
    if not Path(target).is_absolute() and cwd:
        target = str(Path(cwd) / target)
    return target


def _adhoc_script(path: Path, owned: set[str]) -> bool:
    """Скрипт разбираем, только если он ad-hoc: временный каталог или создан этой сессией."""
    if re.match(r'^(?:test_.+|.+_test)\.py$', path.name, re.I):
        return False
    if "tests" in {p.lower() for p in path.parts}:
        return False
    low = str(path).lower()
    norm = low.replace("\\", "/")
    return any(mk in low or mk in norm for mk in SCRIPT_DIR_MARKERS) or norm in owned


def _read(path: Path) -> str:
    try:
        if path.is_file() and path.stat().st_size <= SCRIPT_MAX_BYTES:
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def bash_sql(cmd: str, cwd: str, owned: set[str]) -> list[str]:
    """SQL-тексты, которые выполнит Bash-команда (пусто — команда не про SQL)."""
    if not CLIENT_RE.search(cmd) or BASH_SKIP_RE.search(cmd):
        return []
    base = _base_dir(cmd, cwd)
    texts = [cmd]
    is_psql = bool(re.search(r'\bpsql\b', cmd))
    sqls: list[str] = []
    if is_psql:
        sqls.extend(body for _, body in HEREDOC_RE.findall(cmd))
        for f in PSQL_FILE_RE.findall(cmd):
            p = Path(f) if Path(f).is_absolute() else Path(base) / f
            sqls.append(_read(p))
    for a, b in PY_TOKEN_RE.findall(cmd):
        tok = (a or b).strip()
        p = Path(tok) if Path(tok).is_absolute() else Path(base) / tok
        if _adhoc_script(p, owned):
            texts.append(_read(p))
    for t in texts:
        if SQL_VERB_RE.search(t):
            sqls.extend(_sql_chunks(t))
    return [s for s in sqls if s]


def call_sql(name: str, inp: dict[str, Any], cwd: str, owned: set[str]) -> tuple[list[str], str]:
    """(SQL-тексты вызова, сырой текст для поиска обхода/запроса схемы)."""
    if MCP_TOOL_RE.match(name):
        for key in RULES["mcp_sql_keys"]:
            val = inp.get(key)
            if isinstance(val, str) and val.strip():
                return [val], val
        return [], ""
    if name == "Bash":
        cmd = inp.get("command")
        if isinstance(cmd, str):
            return bash_sql(cmd, cwd, owned), cmd
    return [], ""


# --- знания сессии -----------------------------------------------------------------------
def _result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


class Knowledge:
    """Какие таблицы сессия уже «видела» (схема запрошена/выведена)."""

    def __init__(self) -> None:
        self.known: set[str] = set()
        self.owned: set[str] = set()
        self._harvest: set[str] = set()   # id вызовов: все имена из результата -> известны
        self._star: dict[str, str] = {}   # id успешного SELECT * -> таблица

    def feed_use(self, name: str, inp: dict[str, Any], use_id: str, cwd: str) -> None:
        """Учесть tool_use: запрос схемы, CREATE TABLE, SELECT *, созданный .py."""
        if name in ("Write", "Edit", "NotebookEdit"):
            fp = inp.get("file_path")
            if isinstance(fp, str) and fp.lower().endswith(".py"):
                self.owned.add(fp.lower().replace("\\", "/"))
            return
        sqls, raw = call_sql(name, inp, cwd, self.owned)
        if not raw:
            return
        is_lookup, names = schema_lookup(raw)
        if is_lookup:
            self.known.update(names)
            if not names or re.search(r'\blike\b', raw, re.I):
                self._harvest.add(use_id)
        for s in sqls or [raw]:
            self.known.update(_last_part(n) for n in CREATE_RE.findall(s))
            m = SELECT_STAR_RE.match(_strip_noise(s))
            if m:
                self._star[use_id] = _last_part(m.group(1))

    def feed_result(self, use_id: str, content: Any, is_error: bool) -> None:
        """Учесть результат вызова, если он раскрывает схему."""
        if use_id in self._harvest:
            self.known.update(w.lower() for w in re.findall(r'[A-Za-z_][\w]*', _result_text(content)))
        if use_id in self._star:
            text = _result_text(content)
            if not is_error and not re.search(r'does not exist|error', text, re.I):
                self.known.add(self._star[use_id])

    def missing(self, name: str, inp: dict[str, Any], cwd: str) -> tuple[list[str], str]:
        """(таблицы без увиденной схемы, сырой текст) для предстоящего вызова."""
        sqls, raw = call_sql(name, inp, cwd, self.owned)
        if not sqls or OVERRIDE_RE.search(raw):
            return [], raw
        tables: set[str] = set()
        for s in sqls:
            tables |= extract_tables(s)
        return sorted(t for t in tables if t not in self.known), raw


def iter_events(transcript_path: str) -> Iterable[dict[str, Any]]:
    """События транскрипта по порядку (битые строки пропускаются)."""
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(ev, dict):
                yield ev


def event_blocks(ev: dict[str, Any]) -> list[dict[str, Any]]:
    msg = ev.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def build_knowledge(transcript_path: str, cwd: str) -> Knowledge:
    """Знания о схеме по всему транскрипту сессии."""
    kn = Knowledge()
    if not transcript_path:
        return kn
    try:
        for ev in iter_events(transcript_path):
            for b in event_blocks(ev):
                if b.get("type") == "tool_use":
                    kn.feed_use(str(b.get("name", "")), b.get("input") or {}, str(b.get("id", "")), cwd)
                elif b.get("type") == "tool_result":
                    kn.feed_result(str(b.get("tool_use_id", "")), b.get("content"), bool(b.get("is_error")))
    except OSError:
        pass
    return kn


def block_message(name: str, tables: list[str]) -> str:
    """Причина блока с готовой командой запроса схемы."""
    in_list = ", ".join(f"'{t}'" for t in tables)
    q = ("SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns "
         f"WHERE table_name IN ({in_list}) ORDER BY table_schema, table_name, ordinal_position;")
    how = "тем же MCP-инструментом" if name != "Bash" else "тем же клиентом (psql -c \"...\" / python)"
    return (
        f"[schema_gate] SQL по таблицам без увиденной схемы: {', '.join(tables)}.\n"
        "В этой сессии ещё не было запроса их столбцов — имена колонок/таблиц угадываются "
        "(класс ошибок `column/relation ... does not exist`, 3 недели подряд).\n"
        f"Сначала выполни {how}:\n  {q}\n"
        "Пустой результат = таблицы с таким именем нет — ищи реальное имя "
        "(information_schema.tables), не подставляй догадку.\n"
        "Схема уже известна из надёжного источника в этой сессии — обход: `SCHEMA_OK=1` "
        "перед Bash-командой или комментарий `-- SCHEMA_OK` в SQL MCP-запроса."
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0
    name = str(payload.get("tool_name") or "")
    inp = payload.get("tool_input") or {}
    cwd = str(payload.get("cwd") or "")
    if not isinstance(inp, dict):
        return 0
    # Быстрый выход без чтения транскрипта.
    first, _ = call_sql(name, inp, cwd, set())
    if not first and name == "Bash":
        cmd = inp.get("command") or ""
        if not (isinstance(cmd, str) and PY_TOKEN_RE.search(cmd) and CLIENT_RE.search(cmd)):
            return 0
    elif not first:
        return 0
    kn = build_knowledge(str(payload.get("transcript_path") or ""), cwd)
    missing, _ = kn.missing(name, inp, cwd)
    if missing:
        sys.stderr.write(block_message(name, missing) + "\n")
        return 2
    return 0


def replay(paths: list[str]) -> None:
    """Прогон по готовым транскриптам: что заблокировал бы гейт и ловит ли он реальные ошибки."""
    for path in paths:
        kn = Knowledge()
        pending: dict[str, tuple[list[str], str]] = {}
        calls = blocked = 0
        errors_total = errors_caught = 0
        for ev in iter_events(path):
            cwd = str(ev.get("cwd") or "")
            for b in event_blocks(ev):
                if b.get("type") == "tool_use":
                    name, inp, uid = str(b.get("name", "")), b.get("input") or {}, str(b.get("id", ""))
                    miss, raw = kn.missing(name, inp, cwd)
                    sqls, _ = call_sql(name, inp, cwd, kn.owned)
                    if sqls:
                        calls += 1
                    if miss:
                        blocked += 1
                        kn.known.update(miss)  # агент выполнил подсказку
                    pending[uid] = (miss, raw[:160].replace("\n", " "))
                    kn.feed_use(name, inp, uid, cwd)
                elif b.get("type") == "tool_result":
                    uid = str(b.get("tool_use_id", ""))
                    text = _result_text(b.get("content"))
                    if uid in pending and re.search(r'(?:column|relation) .{0,80}does not exist', text):
                        errors_total += 1
                        miss, snippet = pending[uid]
                        errors_caught += bool(miss)
                        print(f"   {'ПОЙМАН ' if miss else 'ПРОПУЩЕН'} {miss} :: {snippet}")
                    kn.feed_result(uid, b.get("content"), bool(b.get("is_error")))
        print(f"{Path(path).name[:8]}: SQL-вызовов {calls}, блоков {blocked}, "
              f"ошибок does-not-exist {errors_total}, из них пойманы {errors_caught}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--replay":
        replay(sys.argv[2:])
        sys.exit(0)
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — гейт продуктивности не должен ронять сессию
        sys.exit(0)
