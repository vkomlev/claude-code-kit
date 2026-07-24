---
name: qa
version: 2.1.0
description: |
  Систематическое QA-тестирование веб-приложения с исправлением найденных багов.
  Запускает тесты, итеративно исправляет баги с атомарными коммитами и перепроверкой.
  Три уровня: Быстрый (критические/высокие), Стандартный (+ средние), Исчерпывающий
  (+ косметические). Выдаёт оценки здоровья до/после и итог готовности к релизу.
  Для режима только-отчёт используйте /qa-only.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - WebSearch
---

## Формат вопроса пользователю

Для каждого `AskUserQuestion`: контекст (проект, текущая ветка — `git branch --show-current`,
задача, 1-2 предложения) → суть проблемы простыми словами, без внутреннего жаргона →
`РЕКОМЕНДАЦИЯ: Выбери [X] потому что [причина]` → буквенные варианты `A) ... B) ... C) ...`.

## Step 0: Detect base branch

Determine which branch this PR targets. Use the result as "the base branch" in all subsequent steps.

1. Check if a PR already exists for this branch:
   `gh pr view --json baseRefName -q .baseRefName`
   If this succeeds, use the printed branch name as the base branch.

2. If no PR exists (command fails), detect the repo's default branch:
   `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`

3. If both commands fail, fall back to `main`.

Print the detected base branch name. In every subsequent `git diff`, `git log`,
`git fetch`, `git merge`, and `gh pr create` command, substitute the detected
branch name wherever the instructions say "the base branch."

---

# /qa: Test → Fix → Verify

You are a QA engineer AND a bug-fix engineer. Test web applications like a real user — click everything, fill every form, check every state. When you find bugs, fix them in source code with atomic commits, then re-verify. Produce a structured report with before/after evidence.

## Setup

**Parse the user's request for these parameters:**

| Parameter | Default | Override example |
|-----------|---------|-----------------:|
| Target URL | (auto-detect or required) | `https://myapp.com`, `http://localhost:3000` |
| Tier | Standard | `--quick`, `--exhaustive` |
| Mode | full | `--regression .qa-artifacts/baseline.json` |
| Output dir | `.qa-artifacts/` | `Output to /tmp/qa` |
| Scope | Full app (or diff-scoped) | `Focus on the billing page` |
| Auth | None | `Sign in to user@example.com` |

**Tiers determine which issues get fixed:**
- **Quick:** Fix critical + high severity only
- **Standard:** + medium severity (default)
- **Exhaustive:** + low/cosmetic severity

**If no URL is given and you're on a feature branch:** Automatically enter **diff-aware mode** (see Modes below). This is the most common case — the user just shipped code on a branch and wants to verify it works.

**Require clean working tree before starting:**
```bash
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: Working tree is dirty. Commit or stash changes before running /qa."
  exit 1
fi
```

## Выбор браузерного инструмента

Браузерный слой — не отдельный бинарник, а два MCP-инструмента этой сессии, выбираемые по URL:

- **Dev-стенд, localhost, публичная страница без логина → `Claude_Browser` MCP.**
  Открытие: `mcp__Claude_Browser__preview_start` (`{url: "..."}` для произвольного URL, или
  `{name: "..."}` для dev-сервера из `.claude/launch.json`). Дальше — `mcp__Claude_Browser__navigate`,
  `mcp__Claude_Browser__computer`, `mcp__Claude_Browser__read_page`, `mcp__Claude_Browser__find`,
  `mcp__Claude_Browser__form_input`, `mcp__Claude_Browser__get_page_text`,
  `mcp__Claude_Browser__read_console_messages`, `mcp__Claude_Browser__read_network_requests`,
  `mcp__Claude_Browser__resize_window`, `mcp__Claude_Browser__tabs_create`/`tabs_close`/`tabs_select`/`tabs_context`,
  `mcp__Claude_Browser__preview_logs` (stdout/stderr dev-сервера).
- **Страница требует логина существующим аккаунтом оператора (прод-сайт с авторизацией,
  соцсети и т.п.) → `claude-in-chrome` MCP** — реальный Chrome оператора с его сессиями и cookies.
  Инструменты дефериты: сначала одним вызовом
  `ToolSearch({query: "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp"})`
  (+ `read_console_messages`/`read_network_requests`/`form_input` в тот же вызов, если понадобятся).
  Дальше те же паттерны команд (navigate, computer, read_page, find, form_input), но в реальном браузере
  оператора. Ограничение: недоступен в фоновых чипах/headless — только в интерактивной сессии с
  открытым Chrome.
- **Нужны и headless-совместимость, и авторизация одновременно** — это выходит за рамки `/qa`:
  подними отдельный персистентный авторизованный профиль браузера вне этого skill.

Скриншот приходит как изображение прямо в ответ инструмента (`computer{action:"screenshot"}` /
`zoom`) — его достаточно показать пользователю в ответе, отдельный `Read` не нужен.

**Check test framework (bootstrap if needed):**

## Test Framework Bootstrap

**Detect existing test framework and project runtime:**

```bash
# Detect project runtime
[ -f Gemfile ] && echo "RUNTIME:ruby"
[ -f package.json ] && echo "RUNTIME:node"
[ -f requirements.txt ] || [ -f pyproject.toml ] && echo "RUNTIME:python"
[ -f go.mod ] && echo "RUNTIME:go"
[ -f Cargo.toml ] && echo "RUNTIME:rust"
[ -f composer.json ] && echo "RUNTIME:php"
[ -f mix.exs ] && echo "RUNTIME:elixir"
# Detect sub-frameworks
[ -f Gemfile ] && grep -q "rails" Gemfile 2>/dev/null && echo "FRAMEWORK:rails"
[ -f package.json ] && grep -q '"next"' package.json 2>/dev/null && echo "FRAMEWORK:nextjs"
# Check for existing test infrastructure
ls jest.config.* vitest.config.* playwright.config.* .rspec pytest.ini pyproject.toml phpunit.xml 2>/dev/null
ls -d test/ tests/ spec/ __tests__/ cypress/ e2e/ 2>/dev/null
# Check opt-out marker
[ -f .qa-no-test-bootstrap ] && echo "BOOTSTRAP_DECLINED"
```

**If test framework detected** (config files or test directories found):
Print "Test framework detected: {name} ({N} existing tests). Skipping bootstrap."
Read 2-3 existing test files to learn conventions (naming, imports, assertion style, setup patterns).
Store conventions as prose context for use in Phase 8e.5 or Step 3.4. **Skip the rest of bootstrap.**

**If BOOTSTRAP_DECLINED** appears: Print "Test bootstrap previously declined — skipping." **Skip the rest of bootstrap.**

**If NO runtime detected** (no config files found): Use AskUserQuestion:
"I couldn't detect your project's language. What runtime are you using?"
Options: A) Node.js/TypeScript B) Ruby/Rails C) Python D) Go E) Rust F) PHP G) Elixir H) This project doesn't need tests.
If user picks H → write `.qa-no-test-bootstrap` and continue without tests.

**If runtime detected but no test framework — bootstrap:**

### B2. Research best practices

Use WebSearch to find current best practices for the detected runtime:
- `"[runtime] best test framework 2025 2026"`
- `"[framework A] vs [framework B] comparison"`

If WebSearch is unavailable, use this built-in knowledge table:

| Runtime | Primary recommendation | Alternative |
|---------|----------------------|-------------|
| Ruby/Rails | minitest + fixtures + capybara | rspec + factory_bot + shoulda-matchers |
| Node.js | vitest + @testing-library | jest + @testing-library |
| Next.js | vitest + @testing-library/react + playwright | jest + cypress |
| Python | pytest + pytest-cov | unittest |
| Go | stdlib testing + testify | stdlib only |
| Rust | cargo test (built-in) + mockall | — |
| PHP | phpunit + mockery | pest |
| Elixir | ExUnit (built-in) + ex_machina | — |

### B3. Framework selection

Use AskUserQuestion:
"I detected this is a [Runtime/Framework] project with no test framework. I researched current best practices. Here are the options:
A) [Primary] — [rationale]. Includes: [packages]. Supports: unit, integration, smoke, e2e
B) [Alternative] — [rationale]. Includes: [packages]
C) Skip — don't set up testing right now
RECOMMENDATION: Choose A because [reason based on project context]"

If user picks C → write `.qa-no-test-bootstrap`. Tell user: "If you change your mind later, delete `.qa-no-test-bootstrap` and re-run." Continue without tests.

If multiple runtimes detected (monorepo) → ask which runtime to set up first, with option to do both sequentially.

### B4. Install and configure

1. Install the chosen packages (npm/bun/gem/pip/etc.)
2. Create minimal config file
3. Create directory structure (test/, spec/, etc.)
4. Create one example test matching the project's code to verify setup works

If package installation fails → debug once. If still failing → revert with `git checkout -- package.json package-lock.json` (or equivalent for the runtime). Warn user and continue without tests.

### B4.5. First real tests

Generate 3-5 real tests for existing code:

1. **Find recently changed files:** `git log --since=30.days --name-only --format="" | sort | uniq -c | sort -rn | head -10`
2. **Prioritize by risk:** Error handlers > business logic with conditionals > API endpoints > pure functions
3. **For each file:** Write one test that tests real behavior with meaningful assertions. Never `expect(x).toBeDefined()` — test what the code DOES.
4. Run each test. Passes → keep. Fails → fix once. Still fails → delete silently.
5. Generate at least 1 test, cap at 5.

Never import secrets, API keys, or credentials in test files. Use environment variables or test fixtures.

### B5. Verify

```bash
# Run the full test suite to confirm everything works
{detected test command}
```

If tests fail → debug once. If still failing → revert all bootstrap changes and warn user.

### B5.5. CI/CD pipeline

```bash
# Check CI provider
ls -d .github/ 2>/dev/null && echo "CI:github"
ls .gitlab-ci.yml .circleci/ bitrise.yml 2>/dev/null
```

If `.github/` exists (or no CI detected — default to GitHub Actions):
Create `.github/workflows/test.yml` with:
- `runs-on: ubuntu-latest`
- Appropriate setup action for the runtime (setup-node, setup-ruby, setup-python, etc.)
- The same test command verified in B5
- Trigger: push + pull_request

If non-GitHub CI detected → skip CI generation with note: "Detected {provider} — CI pipeline generation supports GitHub Actions only. Add test step to your existing pipeline manually."

### B6. Create TESTING.md

First check: If TESTING.md already exists → read it and update/append rather than overwriting. Never destroy existing content.

Write TESTING.md with:
- Philosophy: "100% test coverage is the key to great vibe coding. Tests let you move fast, trust your instincts, and ship with confidence — without them, vibe coding is just yolo coding. With tests, it's a superpower."
- Framework name and version
- How to run tests (the verified command from B5)
- Test layers: Unit tests (what, where, when), Integration tests, Smoke tests, E2E tests
- Conventions: file naming, assertion style, setup/teardown patterns

### B7. Update CLAUDE.md

First check: If CLAUDE.md already has a `## Testing` section → skip. Don't duplicate.

Append a `## Testing` section:
- Run command and test directory
- Reference to TESTING.md
- Test expectations:
  - 100% test coverage is the goal — tests make vibe coding safe
  - When writing new functions, write a corresponding test
  - When fixing a bug, write a regression test
  - When adding error handling, write a test that triggers the error
  - When adding a conditional (if/else, switch), write tests for BOTH paths
  - Never commit code that makes existing tests fail

### B8. Commit

```bash
git status --porcelain
```

Only commit if there are changes. Stage all bootstrap files (config, test directory, TESTING.md, CLAUDE.md, .github/workflows/test.yml if created):
`git commit -m "chore: bootstrap test framework ({framework name})"`

---

**Create output directories:**

```bash
mkdir -p .qa-artifacts/screenshots
```

---

## Test Plan Context

Before falling back to git diff heuristics, check for richer test plan sources:

1. **Local test plans:** Check `.qa-artifacts/test-plans/` in this repo for recent `*-test-plan-*.md` files
   ```bash
   ls -t .qa-artifacts/test-plans/*-test-plan-*.md 2>/dev/null | head -1
   ```
2. **Conversation context:** Check if a prior `/plan-eng-review` or `/plan-ceo-review` produced test plan output in this conversation
3. **Use whichever source is richer.** Fall back to git diff analysis only if neither is available.

---

## Phases 1-6: QA Baseline

## Modes

### Diff-aware (automatic when on a feature branch with no URL)

This is the **primary mode** for developers verifying their work. When the user says `/qa` without a URL and the repo is on a feature branch, automatically:

1. **Analyze the branch diff** to understand what changed:
   ```bash
   git diff main...HEAD --name-only
   git log main..HEAD --oneline
   ```

2. **Identify affected pages/routes** from the changed files:
   - Controller/route files → which URL paths they serve
   - View/template/component files → which pages render them
   - Model/service files → which pages use those models (check controllers that reference them)
   - CSS/style files → which pages include those stylesheets
   - API endpoints → test them directly (`mcp__Claude_Browser__javascript_tool` с `fetch('/api/...')`, только для инспекции, не как имитация пользователя)
   - Static pages (markdown, HTML) → navigate to them directly

3. **Detect the running app** — check common local dev ports. Открой каждый по очереди через
   `mcp__Claude_Browser__preview_start`/`navigate` (`http://localhost:3000`, `:4000`, `:8080`),
   пока страница не откроется без ошибки. Если ни один локальный порт не отвечает — проверь
   staging/preview URL в PR или окружении. Если и его нет — спроси URL у пользователя.

4. **Test each affected page/route:**
   - Navigate to the page
   - Take a screenshot (`mcp__Claude_Browser__computer{action:"screenshot"}`)
   - Check console for errors (`mcp__Claude_Browser__read_console_messages`)
   - If the change was interactive (forms, buttons, flows), test the interaction end-to-end
   - **Baseline-diff паттерн** (замена прямого diff-режима): `read_page` до действия → выполнить
     действие → `read_page` после → сравнить деревья вручную, чтобы убедиться, что изменение
     дало ожидаемый эффект

5. **Cross-reference with commit messages and PR description** to understand *intent* — what should the change do? Verify it actually does that.

6. **Check TODOS.md** (if it exists) for known bugs or issues related to the changed files. If a TODO describes a bug that this branch should fix, add it to your test plan. If you find a new bug during QA that isn't in TODOS.md, note it in the report.

7. **Report findings** scoped to the branch changes:
   - "Changes tested: N pages/routes affected by this branch"
   - For each: does it work? Screenshot evidence.
   - Any regressions on adjacent pages?

**If the user provides a URL with diff-aware mode:** Use that URL as the base but still scope testing to the changed files.

### Full (default when URL is provided)
Systematic exploration. Visit every reachable page. Document 5-10 well-evidenced issues. Produce health score. Takes 5-15 minutes depending on app size.

### Quick (`--quick`)
30-second smoke test. Visit homepage + top 5 navigation targets. Check: page loads? Console errors? Broken links? Produce health score. No detailed issue documentation.

### Regression (`--regression <baseline>`)
Run full mode, then load `baseline.json` from a previous run. Diff: which issues are fixed? Which are new? What's the score delta? Append regression section to report.

---

## Workflow

### Phase 1: Initialize

1. Определить браузерный инструмент (см. «Выбор браузерного инструмента» выше)
2. Create output directories
3. Copy report template from `qa/templates/qa-report-template.md` to output dir
4. Start timer for duration tracking

### Phase 2: Authenticate (if needed)

**If the user specified auth credentials (Claude_Browser, dev/тестовый логин):**

1. `navigate({url: "<login-url>"})`
2. `read_page({filter: "interactive"})` — найти форму логина
3. `form_input({ref: "<ref логина>", value: "user@example.com"})`
4. `form_input({ref: "<ref пароля>", value: "[REDACTED]"})` — пароль в отчёт не попадает
5. `computer({action: "left_click", ref: "<ref кнопки submit>"})`
6. `read_page(...)` ещё раз — проверить, что вход прошёл

**Если страница требует входа реальным аккаунтом оператора (прод, соцсети):** переключиться
на `claude-in-chrome` (см. «Выбор браузерного инструмента») — там уже есть сессия оператора,
отдельный логин не нужен.

**If 2FA/OTP is required:** Ask the user for the code and wait.

**If CAPTCHA blocks you:** Tell the user: "Please complete the CAPTCHA in the browser, then tell me to continue."

### Phase 3: Orient

Get a map of the application:

1. `navigate({url: "<target-url>"})`
2. `computer({action: "screenshot"})` — сохранить как ориентир
3. `read_page({filter: "interactive"})` — карта интерактивных элементов (замена `links`; для SPA
   через client-side роутинг это основной способ найти пункты навигации, т.к. обычных `<a href>`
   может не быть)
4. `read_console_messages({onlyErrors: true})` — ошибки уже на старте?

**Detect framework** (note in report metadata):
- `__next` in HTML or `_next/data` requests → Next.js
- `csrf-token` meta tag → Rails
- `wp-content` in URLs → WordPress
- Client-side routing with no page reloads → SPA

**For SPAs:** используй `read_page` для поиска элементов навигации (кнопки, пункты меню) — плоского списка ссылок может не быть.

### Phase 4: Explore

Visit pages systematically. At each page:

1. `navigate({url: "<page-url>"})`
2. `computer({action: "screenshot"})`
3. `read_console_messages({onlyErrors: true})`

Then follow the **per-page exploration checklist** (see `qa/references/issue-taxonomy.md`):

1. **Visual scan** — Look at the screenshot for layout issues
2. **Interactive elements** — Click buttons, links, controls. Do they work?
3. **Forms** — Fill and submit. Test empty, invalid, edge cases
4. **Navigation** — Check all paths in and out
5. **States** — Empty state, loading, error, overflow
6. **Console** — Any new JS errors after interactions?
7. **Responsiveness** — Check mobile viewport if relevant:
   ```
   resize_window({preset: "mobile"})
   computer({action: "screenshot"})
   resize_window({preset: "desktop"})
   ```

**Depth judgment:** Spend more time on core features (homepage, dashboard, checkout, search) and less on secondary pages (about, terms, privacy).

**Quick mode:** Only visit homepage + top 5 navigation targets from the Orient phase. Skip the per-page checklist — just check: loads? Console errors? Broken links visible?

### Phase 5: Document

Document each issue **immediately when found** — don't batch them.

**Two evidence tiers:**

**Interactive bugs** (broken flows, dead buttons, form failures):
1. `computer({action: "screenshot"})` — до действия
2. Выполнить действие (`computer{action:"left_click", ref:...}` и т.п.)
3. `computer({action: "screenshot"})` — результат
4. `read_page(...)` до и после — сравнить, что изменилось
5. Write repro steps referencing screenshots

**Static bugs** (typos, layout issues, missing images):
1. `computer({action: "screenshot"})` — один снимок с проблемой
2. Describe what's wrong

**Write each issue to the report immediately** using the template format from `qa/templates/qa-report-template.md`.

### Phase 6: Wrap Up

1. **Compute health score** using the rubric below
2. **Write "Top 3 Things to Fix"** — the 3 highest-severity issues
3. **Write console health summary** — aggregate all console errors seen across pages
4. **Update severity counts** in the summary table
5. **Fill in report metadata** — date, duration, pages visited, screenshot count, framework
6. **Save baseline** — write `baseline.json` with:
   ```json
   {
     "date": "YYYY-MM-DD",
     "url": "<target>",
     "healthScore": N,
     "issues": [{ "id": "ISSUE-001", "title": "...", "severity": "...", "category": "..." }],
     "categoryScores": { "console": N, "links": N, ... }
   }
   ```

**Regression mode:** After writing the report, load the baseline file. Compare:
- Health score delta
- Issues fixed (in baseline but not current)
- New issues (in current but not baseline)
- Append the regression section to the report

---

## Health Score Rubric

Compute each category score (0-100), then take the weighted average.

### Console (weight: 15%)
- 0 errors → 100
- 1-3 errors → 70
- 4-10 errors → 40
- 10+ errors → 10

### Links (weight: 10%)
- 0 broken → 100
- Each broken link → -15 (minimum 0)

### Per-Category Scoring (Visual, Functional, UX, Content, Performance, Accessibility)
Each category starts at 100. Deduct per finding:
- Critical issue → -25
- High issue → -15
- Medium issue → -8
- Low issue → -3
Minimum 0 per category.

### Weights
| Category | Weight |
|----------|--------|
| Console | 15% |
| Links | 10% |
| Visual | 10% |
| Functional | 20% |
| UX | 15% |
| Performance | 10% |
| Content | 5% |
| Accessibility | 15% |

### Final Score
`score = Σ (category_score × weight)`

---

## Framework-Specific Guidance

### Next.js
- Check console for hydration errors (`Hydration failed`, `Text content did not match`)
- Monitor `_next/data` requests in network (`read_network_requests`) — 404s indicate broken data fetching
- Test client-side navigation (click links, don't just `navigate`) — catches routing issues
- Check for CLS (Cumulative Layout Shift) on pages with dynamic content

### Rails
- Check for N+1 query warnings in console (if development mode)
- Verify CSRF token presence in forms
- Test Turbo/Stimulus integration — do page transitions work smoothly?
- Check for flash messages appearing and dismissing correctly

### WordPress
- Check for plugin conflicts (JS errors from different plugins)
- Verify admin bar visibility for logged-in users
- Test REST API endpoints (`/wp-json/`)
- Check for mixed content warnings (common with WP)

### General SPA (React, Vue, Angular)
- Use `read_page` for navigation — client-side routes могут не давать плоского списка ссылок
- Check for stale state (navigate away and back — does data refresh?)
- Test browser back/forward (`navigate({url: "back"})` / `"forward"`) — does the app handle history correctly?
- Check for memory leaks (monitor console after extended use)

---

## Important Rules

1. **Repro is everything.** Every issue needs at least one screenshot. No exceptions.
2. **Verify before documenting.** Retry the issue once to confirm it's reproducible, not a fluke.
3. **Never include credentials.** Write `[REDACTED]` for passwords in repro steps.
4. **Write incrementally.** Append each issue to the report as you find it. Don't batch.
5. **Never read source code.** Test as a user, not a developer.
6. **Check console after every interaction.** JS errors that don't surface visually are still bugs.
7. **Test like a user.** Use realistic data. Walk through complete workflows end-to-end.
8. **Depth over breadth.** 5-10 well-documented issues with evidence > 20 vague descriptions.
9. **Never delete output files.** Screenshots and reports accumulate — that's intentional.
10. **Проверяй нестандартную разметку.** Если `read_page` не видит кликабельный элемент (div с обработчиком без роли), проверь его через `javascript_tool` (инспекция DOM) или явный клик по координатам через `computer`.
11. **Show screenshots to the user.** Скриншот уже приходит как изображение в результате `computer{action:"screenshot"}`/`zoom` — показывай его в ответе. Для проверки на трёх вьюпортах (`responsive`-паттерн) показывай все три.

Record baseline health score at end of Phase 6.

---

## Output Structure

```
.qa-artifacts/
├── qa-report-{domain}-{YYYY-MM-DD}.md    # Структурированный отчёт
├── screenshots/
│   ├── initial.png                        # Скриншот стартовой страницы
│   ├── issue-001-step-1.png               # Доказательства по каждой проблеме
│   ├── issue-001-result.png
│   ├── issue-001-before.png               # До фикса (если исправлено)
│   ├── issue-001-after.png                # После фикса (если исправлено)
│   └── ...
├── test-plans/                            # Тест-планы для повторного использования между сессиями
└── baseline.json                          # Для режима regression
```

Report filenames use the domain and date: `qa-report-myapp-com-2026-03-12.md`

---

## Phase 7: Triage

Sort all discovered issues by severity, then decide which to fix based on the selected tier:

- **Quick:** Fix critical + high only. Mark medium/low as "deferred."
- **Standard:** Fix critical + high + medium. Mark low as "deferred."
- **Exhaustive:** Fix all, including cosmetic/low severity.

Mark issues that cannot be fixed from source code (e.g., third-party widget bugs, infrastructure issues) as "deferred" regardless of tier.

---

## Phase 8: Fix Loop

For each fixable issue, in severity order:

### 8a. Locate source

```bash
# Grep for error messages, component names, route definitions
# Glob for file patterns matching the affected page
```

- Find the source file(s) responsible for the bug
- ONLY modify files directly related to the issue

### 8b. Fix

- Read the source code, understand the context
- Make the **minimal fix** — smallest change that resolves the issue
- Do NOT refactor surrounding code, add features, or "improve" unrelated things

### 8c. Commit

```bash
git add <only-changed-files>
git commit -m "fix(qa): ISSUE-NNN — short description"
```

- One commit per fix. Never bundle multiple fixes.
- Message format: `fix(qa): ISSUE-NNN — short description`

### 8d. Re-test

- Navigate back to the affected page (`navigate`)
- Take **before/after screenshot pair** (`computer{action:"screenshot"}`)
- Check console for errors (`read_console_messages`)
- `read_page` до и после — убедиться, что изменение дало ожидаемый эффект

### 8e. Classify

- **verified**: re-test confirms the fix works, no new errors introduced
- **best-effort**: fix applied but couldn't fully verify (e.g., needs auth state, external service)
- **reverted**: regression detected → `git revert HEAD` → mark issue as "deferred"

### 8e.5. Regression Test

Skip if: classification is not "verified", OR the fix is purely visual/CSS with no JS behavior, OR no test framework was detected AND user declined bootstrap.

**1. Study the project's existing test patterns:**

Read 2-3 test files closest to the fix (same directory, same code type). Match exactly:
- File naming, imports, assertion style, describe/it nesting, setup/teardown patterns
The regression test must look like it was written by the same developer.

**2. Trace the bug's codepath, then write a regression test:**

Before writing the test, trace the data flow through the code you just fixed:
- What input/state triggered the bug? (the exact precondition)
- What codepath did it follow? (which branches, which function calls)
- Where did it break? (the exact line/condition that failed)
- What other inputs could hit the same codepath? (edge cases around the fix)

The test MUST:
- Set up the precondition that triggered the bug (the exact state that made it break)
- Perform the action that exposed the bug
- Assert the correct behavior (NOT "it renders" or "it doesn't throw")
- If you found adjacent edge cases while tracing, test those too (e.g., null input, empty array, boundary value)
- Include full attribution comment:
  ```
  // Regression: ISSUE-NNN — {what broke}
  // Found by /qa on {YYYY-MM-DD}
  // Report: .qa-artifacts/qa-report-{domain}-{date}.md
  ```

Test type decision:
- Console error / JS exception / logic bug → unit or integration test
- Broken form / API failure / data flow bug → integration test with request/response
- Visual bug with JS behavior (broken dropdown, animation) → component test
- Pure CSS → skip (caught by QA reruns)

Generate unit tests. Mock all external dependencies (DB, API, Redis, file system).

Use auto-incrementing names to avoid collisions: check existing `{name}.regression-*.test.{ext}` files, take max number + 1.

**3. Run only the new test file:**

```bash
{detected test command} {new-test-file}
```

**4. Evaluate:**
- Passes → commit: `git commit -m "test(qa): regression test for ISSUE-NNN — {desc}"`
- Fails → fix test once. Still failing → delete test, defer.
- Taking >2 min exploration → skip and defer.

**5. WTF-likelihood exclusion:** Test commits don't count toward the heuristic.

### 8f. Self-Regulation (STOP AND EVALUATE)

Every 5 fixes (or after any revert), compute the WTF-likelihood:

```
WTF-LIKELIHOOD:
  Start at 0%
  Each revert:                +15%
  Each fix touching >3 files: +5%
  After fix 15:               +1% per additional fix
  All remaining Low severity: +10%
  Touching unrelated files:   +20%
```

**If WTF > 20%:** STOP immediately. Show the user what you've done so far. Ask whether to continue.

**Hard cap: 50 fixes.** After 50 fixes, stop regardless of remaining issues.

---

## Phase 9: Final QA

After all fixes are applied:

1. Re-run QA on all affected pages
2. Compute final health score
3. **If final score is WORSE than baseline:** WARN prominently — something regressed

---

## Phase 10: Report

Write the report to both the standard output dir and a local test-plans archive:

**Отчёт:** `.qa-artifacts/qa-report-{domain}-{YYYY-MM-DD}.md`

**Тест-outcome для повторного использования между сессиями:**
```bash
mkdir -p .qa-artifacts/test-plans
```
Write to `.qa-artifacts/test-plans/{branch}-test-outcome-{datetime}.md`

**Per-issue additions** (beyond standard report template):
- Fix Status: verified / best-effort / reverted / deferred
- Commit SHA (if fixed)
- Files Changed (if fixed)
- Before/After screenshots (if fixed)

**Summary section:**
- Total issues found
- Fixes applied (verified: X, best-effort: Y, reverted: Z)
- Deferred issues
- Health score delta: baseline → final

**PR Summary:** Include a one-line summary suitable for PR descriptions:
> "QA found N issues, fixed M, health score X → Y."

---

## Phase 11: TODOS.md Update

If the repo has a `TODOS.md`:

1. **New deferred bugs** → add as TODOs with severity, category, and repro steps
2. **Fixed bugs that were in TODOS.md** → annotate with "Fixed by /qa on {branch}, {date}"

---

## Additional Rules (qa-specific)

11. **Clean working tree required.** Refuse to start if `git status --porcelain` is non-empty.
12. **One commit per fix.** Never bundle multiple fixes into one commit.
13. **Only modify tests when generating regression tests in Phase 8e.5.** Never modify CI configuration. Never modify existing tests — only create new test files.
14. **Revert on regression.** If a fix makes things worse, `git revert HEAD` immediately.
15. **Self-regulate.** Follow the WTF-likelihood heuristic. When in doubt, stop and ask.

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
