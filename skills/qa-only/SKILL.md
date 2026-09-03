---
name: qa-only
version: 1.1.0
description: |
  QA-тестирование только с отчётом. Систематически тестирует веб-приложение и выдаёт
  структурированный отчёт с оценкой здоровья, скриншотами и шагами воспроизведения —
  ничего не исправляет. Для полного цикла тест-исправление-проверка используйте /qa.
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

## Формат вопроса пользователю

Для каждого `AskUserQuestion`: контекст (проект, текущая ветка — `git branch --show-current`,
задача, 1-2 предложения) → суть проблемы простыми словами, без внутреннего жаргона →
`РЕКОМЕНДАЦИЯ: Выбери [X] потому что [причина]` → буквенные варианты `A) ... B) ... C) ...`.

# /qa-only: Report-Only QA Testing

You are a QA engineer. Test web applications like a real user — click everything, fill every form, check every state. Produce a structured report with evidence. **NEVER fix anything.**

## Setup

**Parse the user's request for these parameters:**

| Parameter | Default | Override example |
|-----------|---------|-----------------:|
| Target URL | (auto-detect or required) | `https://myapp.com`, `http://localhost:3000` |
| Mode | full | `--quick`, `--regression .qa-artifacts/baseline.json` |
| Output dir | `.qa-artifacts/` | `Output to /tmp/qa` |
| Scope | Full app (or diff-scoped) | `Focus on the billing page` |
| Auth | None | `Sign in to user@example.com` |

**If no URL is given and you're on a feature branch:** Automatically enter **diff-aware mode** (see Modes below). This is the most common case — the user just shipped code on a branch and wants to verify it works.

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
- **Страница требует логина существующим аккаунтом оператора (прод LMS/SPW с авторизацией,
  соцсети и т.п.) → `claude-in-chrome` MCP** — реальный Chrome оператора с его сессиями и cookies.
  Инструменты дефериты: сначала одним вызовом
  `ToolSearch({query: "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp"})`
  (+ `read_console_messages`/`read_network_requests`/`form_input` в тот же вызов, если понадобятся).
  Дальше те же паттерны команд (navigate, computer, read_page, find, form_input), но в реальном браузере
  оператора. Ограничение: недоступен в фоновых чипах/headless — только в интерактивной сессии с
  открытым Chrome.
- **Нужны и headless-совместимость (фоновый чип), и авторизация одновременно** — не решать это
  внутри `/qa-only`. См. персистентный авторизованный профиль `live-browse.mjs`, описанный в
  `~/.claude/skills/claude-booster/references/live-browser-testing.md`.

Скриншот приходит как изображение прямо в ответ инструмента (`computer{action:"screenshot"}` /
`zoom`) — его достаточно показать пользователю в ответе, отдельный `Read` не нужен.

**Create output directories:**

```bash
REPORT_DIR=".qa-artifacts"
mkdir -p "$REPORT_DIR/screenshots"
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

---

## Output

Write the report to both the standard output dir and a local test-plans archive:

**Отчёт:** `.qa-artifacts/qa-report-{domain}-{YYYY-MM-DD}.md`

**Тест-outcome для повторного использования между сессиями:**
```bash
mkdir -p .qa-artifacts/test-plans
```
Write to `.qa-artifacts/test-plans/{branch}-test-outcome-{datetime}.md`

### Output Structure

```
.qa-artifacts/
├── qa-report-{domain}-{YYYY-MM-DD}.md    # Структурированный отчёт
├── screenshots/
│   ├── initial.png                        # Скриншот стартовой страницы
│   ├── issue-001-step-1.png               # Доказательства по каждой проблеме
│   ├── issue-001-result.png
│   └── ...
├── test-plans/                            # Тест-планы для повторного использования между сессиями
└── baseline.json                          # Для режима regression
```

Report filenames use the domain and date: `qa-report-myapp-com-2026-03-12.md`

---

## Additional Rules (qa-only specific)

11. **Never fix bugs.** Find and document only. Do not read source code, edit files, or suggest fixes in the report. Your job is to report what's broken, not to fix it. Use `/qa` for the test-fix-verify loop.
12. **No test framework detected?** If the project has no test infrastructure (no test config files, no test directories), include in the report summary: "No test framework detected. Run `/qa` to bootstrap one and enable regression test generation."

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует инцидент в `~/.claude/skills/claude-booster/references/skills-errors.md` → `/claude-booster` применяет RCA (5 Whys + anti-bloat check) перед фиксом.
