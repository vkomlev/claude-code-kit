---
name: document-release
version: 2.0.1
description: |
  Универсальное обновление документации после релиза (stack-agnostic).
  Читает diff, обновляет README/CHANGELOG/CLAUDE.md/docs/ по фактическим
  изменениям, полирует CHANGELOG voice, опционально поднимает VERSION.
  Работает с любым стеком: Python (pyproject.toml), Node (package.json),
  Go (go.mod), Rust (Cargo.toml), standalone VERSION file.
  Опциональные UI/design-gates подключаются только если в проекте есть фронтенд.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
---

## Формат вопроса пользователю

**ВСЕГДА следуй этой структуре для каждого вызова AskUserQuestion:**
1. **Контекст:** Назови проект, текущую ветку и текущую задачу. (1-2 предложения)
2. **Упрощение:** Объясни проблему простым русским языком без внутреннего жаргона.
3. **Рекомендация:** `РЕКОМЕНДАЦИЯ: Выбери [X] потому что [одна строка причины]`
4. **Варианты:** Буквенные варианты: `A) ... B) ... C) ...`

Считай, что пользователь не смотрел в это окно 20 минут. Объяснение должно
быть понятным без чтения исходников.

## Порядок работы

1. **Step 0** — Detect project context (стек, ветка, VERSION, наличие UI)
2. **Step 1** — Pre-flight & Diff Analysis
3. **Step 2** — Per-File Documentation Audit
4. **Step 3** — Apply Auto-Updates
5. **Step 4** — Ask About Risky/Questionable Changes
6. **Step 5** — CHANGELOG Voice Polish
7. **Step 6** — Cross-Doc Consistency & Discoverability Check
8. **Step 7** — TODOS.md Cleanup
9. **Step 8** — VERSION Bump Question
10. **Step 9** — Commit & Output

Детали каждого шага — ниже.

---

## Step 0: Detect project context

Определить стек, ветку и расположение VERSION для адаптации skill под проект.

### 0.1: Detect stack

Проверить наличие маркеров (по приоритету):
- `pyproject.toml` → **Python** (FastAPI / CLI / bot / library)
- `package.json` → **Node** (frontend / backend / monorepo)
- `Cargo.toml` → **Rust**
- `go.mod` → **Go**
- `*.csproj` / `*.sln` → **.NET**
- Иначе → **Generic** (без stack-specific hooks)

### 0.2: Detect base branch

```bash
# Try gh first (if available + PR exists)
gh pr view --json baseRefName -q .baseRefName 2>/dev/null \
  || gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null \
  || git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' \
  || echo "main"
```

Использовать результат как **base branch** во всех `git diff`/`git log`/`git fetch`/`git merge` далее.

### 0.3: Detect VERSION source

Найти место хранения версии (первое присутствующее):
1. Python: `[project] version = "..."` в `pyproject.toml` (или `__version__` в `__init__.py` / `_version.py`)
2. Node: `"version": "..."` в `package.json`
3. Rust: `[package] version = "..."` в `Cargo.toml`
4. Go: tag `v*` через `git describe --tags --abbrev=0` (нет файла)
5. Standalone: `VERSION` файл в корне (одна строка `X.Y.Z`)
6. Нет источника → шаг 8 пропускается (Skipped)

### 0.4: Detect optional UI gates

Проверить наличие фронтенда (для опциональных design/QA шагов в Step 6):
- `*.tsx` / `*.jsx` / `*.vue` / `*.svelte` в diff
- `index.html`, `static/`, `public/`, `frontend/`, `web/`
- Если найдено → флаг **`UI_PRESENT=true`**

### 0.5: Print context

Вывести одной строкой:
```
Project: <stack> | Branch: <name> | Base: <name> | Version: <path or none> | UI: <yes|no>
```

---

# Document Release: Post-Ship Documentation Update

You are running the `/document-release` workflow. This runs **after `/ship`** (code committed, PR
exists or about to exist) but **before the PR merges**. Your job: ensure every documentation file
in the project is accurate, up to date, and written in a friendly, user-forward voice.

You are mostly automated. Make obvious factual updates directly. Stop and ask only for risky or
subjective decisions.

**Only stop for:**
- Risky/questionable doc changes (narrative, philosophy, security, removals, large rewrites)
- VERSION bump decision (if not already bumped)
- New TODOS items to add
- Cross-doc contradictions that are narrative (not factual)

**Never stop for:**
- Factual corrections clearly from the diff
- Adding items to tables/lists
- Updating paths, counts, version numbers
- Fixing stale cross-references
- CHANGELOG voice polish (minor wording adjustments)
- Marking TODOS complete
- Cross-doc factual inconsistencies (e.g., version number mismatch)

**NEVER do:**
- Overwrite, replace, or regenerate CHANGELOG entries — polish wording only, preserve all content
- Bump VERSION without asking — always use AskUserQuestion for version changes
- Use `Write` tool on CHANGELOG.md — always use `Edit` with exact `old_string` matches

---

## Step 1: Pre-flight & Diff Analysis

1. Check the current branch. If on the base branch, **abort**: "You're on the base branch. Run from a feature branch."

2. Gather context about what changed:

```bash
git diff <base>...HEAD --stat
```

```bash
git log <base>..HEAD --oneline
```

```bash
git diff <base>...HEAD --name-only
```

3. Discover all documentation files in the repo:

```bash
find . -maxdepth 3 -name "*.md" \
  -not -path "./.git/*" \
  -not -path "./node_modules/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/.venv/*" \
  -not -path "*/dist/*" \
  -not -path "*/target/*" \
  -not -path "*/build/*" \
  -not -path "*/.gstack/*" \
  -not -path "*/.context/*" \
  -not -path "*/docs/archive/*" \
  | sort
```

Также включить `CLAUDE.md`, `AGENTS.md`, `README.md` явно если они есть в корне.

4. Classify the changes into categories relevant to documentation:
   - **New features** — new files, new commands, new skills, new capabilities
   - **Changed behavior** — modified services, updated APIs, config changes
   - **Removed functionality** — deleted files, removed commands
   - **Infrastructure** — build system, test infrastructure, CI

5. Output a brief summary: "Analyzing N files changed across M commits. Found K documentation files to review."

---

## Step 2: Per-File Documentation Audit

Read each documentation file and cross-reference it against the diff. Use these generic
heuristics (adapt to the project's stack and conventions):

**README.md:**
- Does it describe all features and capabilities visible in the diff?
- Are install/setup instructions consistent with the changes?
- Are examples, demos, and usage descriptions still valid?
- Are troubleshooting steps still accurate?

**ARCHITECTURE.md:**
- Do ASCII diagrams and component descriptions match the current code?
- Are design decisions and "why" explanations still accurate?
- Be conservative — only update things clearly contradicted by the diff. Architecture docs
  describe things unlikely to change frequently.

**CONTRIBUTING.md — New contributor smoke test:**
- Walk through the setup instructions as if you are a brand new contributor.
- Are the listed commands accurate? Would each step succeed?
- Do test tier descriptions match the current test infrastructure?
- Are workflow descriptions (dev setup, contributor mode, etc.) current?
- Flag anything that would fail or confuse a first-time contributor.

**CLAUDE.md / project instructions:**
- Does the project structure section match the actual file tree?
- Are listed commands and scripts accurate?
- Do build/test instructions match what's in package.json (or equivalent)?

**Any other .md files:**
- Read the file, determine its purpose and audience.
- Cross-reference against the diff to check if it contradicts anything the file says.

For each file, classify needed updates as:

- **Auto-update** — Factual corrections clearly warranted by the diff: adding an item to a
  table, updating a file path, fixing a count, updating a project structure tree.
- **Ask user** — Narrative changes, section removal, security model changes, large rewrites
  (more than ~10 lines in one section), ambiguous relevance, adding entirely new sections.

---

## Step 3: Apply Auto-Updates

Make all clear, factual updates directly using the Edit tool.

For each file modified, output a one-line summary describing **what specifically changed** — not
just "Updated README.md" but "README.md: added /new-skill to skills table, updated skill count
from 9 to 10."

**Never auto-update:**
- README introduction or project positioning
- ARCHITECTURE philosophy or design rationale
- Security model descriptions
- Do not remove entire sections from any document

---

## Step 4: Ask About Risky/Questionable Changes

For each risky or questionable update identified in Step 2, use AskUserQuestion with:
- Context: project name, branch, which doc file, what we're reviewing
- The specific documentation decision
- `RECOMMENDATION: Choose [X] because [one-line reason]`
- Options including C) Skip — leave as-is

Apply approved changes immediately after each answer.

---

## Step 5: CHANGELOG Voice Polish

**CRITICAL — NEVER CLOBBER CHANGELOG ENTRIES.**

This step polishes voice. It does NOT rewrite, replace, or regenerate CHANGELOG content.

A real incident occurred where an agent replaced existing CHANGELOG entries when it should have
preserved them. This skill must NEVER do that.

**Rules:**
1. Read the entire CHANGELOG.md first. Understand what is already there.
2. Only modify wording within existing entries. Never delete, reorder, or replace entries.
3. Never regenerate a CHANGELOG entry from scratch. The entry was written by `/ship` from the
   actual diff and commit history. It is the source of truth. You are polishing prose, not
   rewriting history.
4. If an entry looks wrong or incomplete, use AskUserQuestion — do NOT silently fix it.
5. Use Edit tool with exact `old_string` matches — never use Write to overwrite CHANGELOG.md.

**If CHANGELOG was not modified in this branch:** skip this step.

**If CHANGELOG was modified in this branch**, review the entry for voice:

- **Sell test:** Would a user reading each bullet think "oh nice, I want to try that"? If not,
  rewrite the wording (not the content).
- Lead with what the user can now **do** — not implementation details.
- "You can now..." not "Refactored the..."
- Flag and rewrite any entry that reads like a commit message.
- Internal/contributor changes belong in a separate "### For contributors" subsection.
- Auto-fix minor voice adjustments. Use AskUserQuestion if a rewrite would alter meaning.

---

## Step 6: Cross-Doc Consistency & Discoverability Check

After auditing each file individually, do a cross-doc consistency pass:

1. Does the README's feature/capability list match what CLAUDE.md (or project instructions) describes?
2. Does ARCHITECTURE's component list match CONTRIBUTING's project structure description?
3. Does CHANGELOG's latest version match the VERSION source (see Step 0.3)?
4. **Discoverability:** Is every documentation file reachable from README.md or CLAUDE.md? If
   ARCHITECTURE.md exists but neither README nor CLAUDE.md links to it, flag it. Every doc
   should be discoverable from one of the two entry-point files.
5. Flag any contradictions between documents. Auto-fix clear factual inconsistencies (e.g., a
   version mismatch). Use AskUserQuestion for narrative contradictions.

### 6.1: Optional UI/design-gate

**Only if `UI_PRESENT=true` (from Step 0.4):**

- If the project has visual artifacts (screenshots, demo GIFs, design tokens), check whether
  recent UI changes invalidate them.
- Suggest running `/plan-design-review` or `/qa-design-review` for visual regression check.
- If the diff touched only backend/CLI/bot code — skip.

For backend-only / CLI / bot / library projects, this sub-step is a no-op.

---

## Step 7: TODOS.md Cleanup

This is a second pass that complements `/ship`'s Step 5.5. Read `review/TODOS-format.md` (if
available) for the canonical TODO item format.

If TODOS.md does not exist, skip this step.

1. **Completed items not yet marked:** Cross-reference the diff against open TODO items. If a
   TODO is clearly completed by the changes in this branch, move it to the Completed section
   with `**Completed:** vX.Y.Z.W (YYYY-MM-DD)`. Be conservative — only mark items with clear
   evidence in the diff.

2. **Items needing description updates:** If a TODO references files or components that were
   significantly changed, its description may be stale. Use AskUserQuestion to confirm whether
   the TODO should be updated, completed, or left as-is.

3. **New deferred work:** Check the diff for `TODO`, `FIXME`, `HACK`, and `XXX` comments. For
   each one that represents meaningful deferred work (not a trivial inline note), use
   AskUserQuestion to ask whether it should be captured in TODOS.md.

---

## Step 8: VERSION Bump Question

**CRITICAL — NEVER BUMP VERSION WITHOUT ASKING.**

**Version follows SemVer:** `X.Y.Z` (MAJOR.MINOR.PATCH). Where to find the current version
depends on the stack — see Step 0.3 `Version source`:

| Stack | Location | Edit example |
|---|---|---|
| Python | `pyproject.toml` `[project] version = "X.Y.Z"` | `Edit` the line |
| Python alt | `avito_manager/__init__.py` `__version__ = "X.Y.Z"` | `Edit` the line |
| Node | `package.json` `"version": "X.Y.Z"` | `Edit` the line |
| Rust | `Cargo.toml` `[package] version = "X.Y.Z"` | `Edit` the line |
| Standalone | `VERSION` file (one line `X.Y.Z`) | `Edit` or `Write` |
| Go | Git tag `vX.Y.Z` | `git tag vX.Y.Z` (separately) |

1. **If no version source detected (Step 0.3 = none):** Skip silently with message
   "VERSION: no version source in this project — skipped."

2. Check if version was already modified on this branch:

```bash
# adapt to detected source
git diff <base>...HEAD -- pyproject.toml package.json Cargo.toml VERSION 2>/dev/null
```

3. **If version was NOT bumped:** Use AskUserQuestion:
   - RECOMMENDATION: Choose C (Skip) because docs-only changes rarely warrant a version bump
   - A) Bump PATCH (X.Y.**Z+1**) — bugfixes, doc tweaks shipping with small code changes
   - B) Bump MINOR (X.**Y+1**.0) — new features, backwards-compatible
   - C) Bump MAJOR (**X+1**.0.0) — breaking changes
   - D) Skip — no version bump needed

4. **If version was already bumped:** Do NOT skip silently. Instead, check whether the bump
   still covers the full scope of changes on this branch:

   a. Read the CHANGELOG entry for the current version. What features does it describe?
   b. Read the full diff (`git diff <base>...HEAD --stat` and `git diff <base>...HEAD --name-only`).
      Are there significant changes (new features, new commands, major refactors)
      that are NOT mentioned in the CHANGELOG entry for the current version?
   c. **If the CHANGELOG entry covers everything:** Skip — output "VERSION: Already bumped to
      vX.Y.Z, covers all changes."
   d. **If there are significant uncovered changes:** Use AskUserQuestion explaining what the
      current version covers vs what's new, and ask:
      - RECOMMENDATION: Choose A because the new changes warrant their own version
      - A) Bump to next patch — give the new changes their own version
      - B) Keep current version — add new changes to the existing CHANGELOG entry
      - C) Skip — leave version as-is, handle later

   The key insight: a version bump set for "feature A" should not silently absorb "feature B"
   if feature B is substantial enough to deserve its own version entry.

---

## Step 9: Commit & Output

**Empty check first:** Run `git status` (never use `-uall`). If no documentation files were
modified by any previous step, output "All documentation is up to date." and exit without
committing.

**Commit:**

1. Stage modified documentation files by name (never `git add -A` or `git add .`).
2. Create a single commit. Commit message format (SemVer, 3 segments):

```bash
git commit -m "$(cat <<'EOF'
docs: обновить документацию проекта для vX.Y.Z

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

(Сообщение на русском, повелительное наклонение — соответствует общим правилам коммитов
проекта. Если в проекте принят английский — `docs: update project documentation for vX.Y.Z`.)

3. Push to the current branch (only if remote exists):

```bash
git remote 2>/dev/null | grep -q . && git push || echo "No remote — skip push"
```

**Optional: PR body update (idempotent, race-safe)**

**Gate:** этот шаг выполняется только если:
- `gh` CLI установлен (`command -v gh`)
- PR для текущей ветки существует (`gh pr view 2>/dev/null`)

Если не выполнено — пропустить с сообщением "No gh CLI / no PR — skipping body update."

При выполненном gate:

1. Read the existing PR body into a PID-unique tempfile:

```bash
gh pr view --json body -q .body > /tmp/doc-release-pr-body-$$.md
```

2. If the tempfile already contains a `## Documentation` section, replace that section with the
   updated content. If it does not contain one, append a `## Documentation` section at the end.

3. The Documentation section should include a **doc diff preview** — for each file modified,
   describe what specifically changed (e.g., "README.md: added /new-cmd to commands table,
   updated count from 9 to 10").

4. Write the updated body back + cleanup:

```bash
gh pr edit --body-file /tmp/doc-release-pr-body-$$.md
rm -f /tmp/doc-release-pr-body-$$.md
```

5. If `gh pr edit` fails: warn "Could not update PR body — documentation changes are in the
   commit." and continue.

**Structured doc health summary (final output):**

Output a scannable summary showing every documentation file's status:

```
Documentation health:
  README.md       [status] ([details])
  ARCHITECTURE.md [status] ([details])
  CONTRIBUTING.md [status] ([details])
  CHANGELOG.md    [status] ([details])
  TODOS.md        [status] ([details])
  VERSION         [status] ([details])
```

Where status is one of:
- Updated — with description of what changed
- Current — no changes needed
- Voice polished — wording adjusted
- Not bumped — user chose to skip
- Already bumped — version was set by /ship
- Skipped — file does not exist

---

## Important Rules

- **Stack-agnostic.** Все шаги работают на любом стеке (Python/Node/Go/Rust/Generic).
  UI-зависимые проверки — за гейтом `UI_PRESENT` из Step 0.4.
- **Read before editing.** Always read the full content of a file before modifying it.
- **Never clobber CHANGELOG.** Polish wording only. Never delete, replace, or regenerate entries.
- **Never bump VERSION silently.** Always ask. Even if already bumped, check whether it covers the full scope of changes.
- **SemVer X.Y.Z** — 3 сегмента (не 4). MAJOR.MINOR.PATCH.
- **Be explicit about what changed.** Every edit gets a one-line summary.
- **Generic heuristics, not project-specific.** The audit checks work on any repo.
- **Discoverability matters.** Every doc file should be reachable from README or CLAUDE.md.
- **Voice: friendly, user-forward, not obscure.** Write like you're explaining to a smart person
  who hasn't seen the code.
- **No remote/PR — work locally.** Если нет git remote или gh CLI / PR — пропустить push и PR
  body update с предупреждением, не падать.

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
