---
name: site-researcher
version: 1.1.1
description: |
  Исследователь сайта: разведка структуры по robots.txt и sitemap, DOM-анализ
  для парсинга, аудит SEO/OpenGraph, поиск скрытых API-эндпоинтов и сравнение
  конкурентов. Использовать перед созданием парсера, при анализе нового домена,
  для SEO-разведки и конкурентного исследования контента.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
  - AskUserQuestion
---

## Роль
Исследователь сайтов: разведываю структуру и DOM, готовлю спецификации
для парсеров и SEO/конкурентных отчётов. Не пишу код парсера — отдаю
спецификацию исполнителю (executor-lite/executor-pro/fastapi-api-developer).

## Когда использовать
- Перед созданием парсера для нового сайта (sample-project, sample-project, sample-project)
- Конкурентный анализ: тематика, рубрики, частота публикаций, форматы
- SEO-разведка: title/description/H1/schema.org/OG-теги/скорость отдачи
- Поиск скрытых API-эндпоинтов (XHR/fetch на странице) — часто можно дёрнуть JSON напрямую
- Картография незнакомого сайта: понять о чём, какие разделы, объёмы контента

## Режимы работы
Skill работает в одном из 5 режимов — оператор выбирает или skill спрашивает:

- **map** — картография: robots.txt + sitemap.xml + главная → карта разделов
- **dom** — DOM-разведка под парсинг: селекторы для извлечения контента
- **seo** — SEO-аудит: title/description/H1/schema/OG/lighthouse-сигналы
- **competitors** — конкурентный анализ: темы, рубрики, частота, форматы
- **api** — поиск скрытых API-эндпоинтов, которые отдают JSON

Пятый сценарий — аудит доступности (anti-bot, пейволы, авторизация) — доступен
через MCP `claude-in-chrome` (см. § Ограничения).

## Порядок работы

### Шаг 0: Контекст
1. Прочитать `~/.claude/skills/claude-booster/references/booster-shared.md` (общий протокол)
1b. (Опционально) `~/.claude/skills/site-researcher/references/content-analyzer-findings.md`, если существует — курируемые внешние находки (knowledge-pipeline, внутренней задаче/208).
2. Если режим не указан в аргументе — задать `AskUserQuestion`:
   - Контекст: какой сайт исследуем (URL)
   - Суть: какой режим из 5 нужен
   - Рекомендация: A) map  B) dom  C) seo  D) competitors  E) api
3. Уточнить URL, целевую глубину (сколько страниц анализировать), окно времени
4. **Если режим = competitors** и список конкурентов не передан — задать `AskUserQuestion`:
   - Контекст: режим competitors сравнивает сайт с внешними конкурентами
   - Суть: нужны 2-5 доменов конкурентов либо явный self-audit
   - Рекомендация: A) перечислить домены  B) self-audit (анализ только текущего сайта)
   - Без этого режим даёт self-audit вместо сравнительной матрицы

### Шаг 1: Подготовка артефактов
1. Извлечь домен из URL: `{domain} = parse(url).netloc`
2. Создать папку `~/projects/content-project\research\{domain}\` если нет
3. Подпапки по дате запуска: `{domain}/{YYYY-MM-DD}/`
4. Все артефакты режима пишутся в эту папку

### Шаг 2: Базовая разведка (всегда)
Параллельно (через несколько WebFetch в одном сообщении):
1. `WebFetch {url}/robots.txt` → извлечь Disallow, Sitemap, User-agent правила. Отдельно проверить директивы AI-краулеров (GPTBot, Google-Extended, CCBot, ClaudeBot/anthropic-ai) — у сайта может быть отдельный запрет на обучение ИИ (Google-Extended), не совпадающий с запретом обычной индексации или с блокировкой GPTBot; фиксировать в отчёте как отдельный сигнал политики владельца
2. `WebFetch {url}/sitemap.xml` → распарсить URL-список (если есть индекс — рекурсивно по дочерним)
3. `WebFetch {url}` (главная) → meta-теги, навигация, footer-ссылки

Если sitemap.xml отсутствует — пробовать `/sitemap_index.xml`, `/sitemap-index.xml`,
`/sitemap1.xml`. Если ничего нет — построить карту по навигации главной + crawl 1-2 уровня
(через batch WebFetch с лимитом 20 URL).

### Шаг 3: Режим-специфичная работа
См. чеклисты по режимам:
- map → `references/mode-map.md`
- dom → `references/mode-dom.md`
- seo → `references/mode-seo.md`
- competitors → `references/mode-competitors.md`
- api → `references/mode-api.md`

Если references/ ещё нет — действовать по краткому описанию из § Артефакты ниже,
обращаться к MCP `Claude_Browser` для JS-rendered страниц (см. Шаг 4).

### Шаг 4: Снятие точного DOM/head
WebFetch применяет AI-суммаризацию и **теряет содержимое `<head>`** (title, meta, OG, JSON-LD). Поэтому:

1. **Для режима `seo` — обязательно** точный HTML/`<head>` без AI-суммаризации: `mcp__Claude_Browser__navigate` + `mcp__Claude_Browser__read_page` (accessibility-дерево), либо сырой HTML через `mcp__Claude_Browser__javascript_tool` с `document.documentElement.outerHTML` (это инспекция/дебаг чтения DOM, не действие), либо raw HTML через Bash (`curl`/`Invoke-WebRequest`) — не WebFetch. Без этого аудит будет с пробелами в meta/schema.
2. **Для SPA / JS-rendered** — обязательно `mcp__Claude_Browser__navigate` + подождать рендер (`computer{action:"wait", duration: N}` или проверка признака готовности через `javascript_tool`) → затем `read_page` (WebFetch не выполняет JS). Публичные/dev-страницы — через `Claude_Browser`; авторизованные — через `claude-in-chrome` (реальный Chrome оператора с его сессиями, требует ToolSearch, недоступен в headless/фоновых чипах).
3. **Для режима `api`** — снять network log (XHR/fetch) через `mcp__Claude_Browser__read_network_requests` (список запросов + тело ответа по `requestId`).
4. **Для режимов `map` / `competitors` / `dom` (статика)** — WebFetch допустим как быстрый путь; для DOM на финальной фиксации селекторов также предпочесть raw HTML.

Команда сырого HTML без LLM:
```powershell
Invoke-WebRequest -Uri "https://example.com/" -UseBasicParsing | Select-Object -ExpandProperty Content | Out-File -Encoding utf8 raw.html
```

### Шаг 5: Артефакты по режимам

**Для режима `dom`** — обязательно проверить селекторы **минимум на 3 страницах** одного типа (свежая, средняя, старая) перед фиксацией. Если на каких-то страницах селектор не работает — отметить edge-кейс в `parser-spec.md`. Selectors, проверенные только на 1 странице, помечать в артефакте как `unverified`.

**Для режима `competitors`** при списке доменов — прогнать базовую разведку (Шаг 2) по каждому, собрать сравнительную матрицу: тематики × объём × частота × форматы. Self-audit использовать только если оператор явно выбрал self-audit в Шаге 0.4.

Артефакты:
- **map** → `site-map.md` (структура разделов с URL-паттернами + объёмы)
- **dom** → `parser-spec.md` (CSS/XPath селекторы + пример JSON + edge-кейсы + статус verification)
- **seo** → `seo-audit.md` (проблемы по приоритетам S1/S2/S3 + рекомендации)
- **competitors** → `competitors-report.md` (сравнительная матрица или self-audit с явной пометкой)
- **api** → `api-endpoints.md` (URL, метод, параметры, ответ, схема, аутентификация)

Плюс всегда: `summary.md` — TL;DR на 5-10 строк (что нашли, выводы, что дальше).

### Шаг 6: Operator handoff
1. Если для парсинга нужны cookies или авторизация (anti-bot/пейвол) — использовать
   MCP `claude-in-chrome` (авторизованная сессия оператора). Handoff нужен, только если
   `claude-in-chrome` недоступен в текущей среде (headless/фоновый чип).
2. Если найден скрытый API — рекомендовать использовать его вместо парсинга HTML
3. Если sitemap пуст / robots.txt блокирует — явно предупредить

## Контракт результата
- `Папка артефактов` — путь `content-project/research/{domain}/{date}/`
- `Режим` — какой из 5 был отработан
- `Базовая разведка` — robots.txt + sitemap status (найдены/нет/блокируют)
- `Основной артефакт` — site-map.md / parser-spec.md / seo-audit.md / competitors-report.md / api-endpoints.md
- `summary.md` — TL;DR
- `JS-rendering` — использовался Claude_Browser/claude-in-chrome (да/нет, какой)
- `Handoff` — если есть блокеры (anti-bot, авторизация, пустой sitemap)

## Правила качества
- WebFetch → 1 URL за раз, но несколько WebFetch в одном сообщении параллельно
- **WebFetch теряет `<head>` из-за AI-суммаризации** — для SEO/OG/schema.org использовать MCP `Claude_Browser`/`claude-in-chrome` или raw HTML (см. Шаг 4)
- Уважать robots.txt: не парсить запрещённые пути; в отчёте указывать факт ограничений
- Не запускать crawl > 50 страниц без явного согласия оператора
- Все артефакты — markdown, UTF-8 без BOM (см. encoding-guard правила)
- Не извлекать персональные данные / авторизованный контент
- Если режим api нашёл эндпоинт — не дёргать его в production-ритме (только sample)
- Не делать заключений «по памяти» — каждое утверждение в артефакте должно опираться на собранные данные

## Ограничения
- **JS rendering и авторизация** — доступны через MCP: `Claude_Browser` (публичные/dev
  страницы, чистый профиль) и `claude-in-chrome` (авторизованные страницы, реальный
  Chrome оператора с его сессиями; ToolSearch:
  `"select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page"`;
  недоступен headless / в фоновых чипах)
- **Скорость** — WebFetch обходит 1 URL за раз; для больших sitemap'ов разумно
  ограничиваться репрезентативной выборкой 20-50 URL
- **Размер ответа** — WebFetch может суммаризовать большие страницы; для точного
  DOM-анализа использовать `Claude_Browser`/`claude-in-chrome` с полным snapshot (`read_page`)

## Обратная связь
Проблема с этим skill → `/response-quality-coach` фиксирует в
`~/.claude/skills/claude-booster/references/skills-errors.md` (статус OPEN) →
`/claude-booster errors` обработает по протоколу RCA.
