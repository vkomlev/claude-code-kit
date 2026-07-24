# API Contract Rules

Единые правила для публичных API-контрактов (HTTP/REST). Подключается из `tech-spec-composer`, `executor-pro`, `fastapi-api-developer`, `review-gate`, `techlead-code-reviewer`.

## 1. Frontend Route ≠ API Endpoint

В спецификациях, ADR и коде различать **два слоя** именования:

- **Frontend Route** — UX-имя страницы клиентского приложения (Next.js page, SPA route). Пример: `/auth/magic-link/request`, `/auth/magic-link/consume`. Человекочитаемое.
- **API Endpoint** — контракт между backend и frontend. Пример: `POST /api/v1/auth/magic-link/send`, `POST /api/v1/auth/magic-link/verify`. Глагольное, идиоматичное.

**Правило**: в любом spec/ADR/ТЗ обязаны быть **две отдельные таблицы**: «Frontend Routes» и «API Endpoints». Слияние в одно имя — дефект спеки.

## 2. Spec Backsync (обязателен в одном коммите)

**Любое** изменение публичного API (URL, метод, request schema, response schema, status code) обязано в **том же коммите** обновить:

1. OpenAPI / FastAPI route definition
2. spec/ТЗ-документ (`docs/spec/*.md`, `docs/tech-spec-*.md`)
3. ADR (`docs/ai/adr/*.md`), если это архитектурное решение
4. Документацию контрактов смежных модулей/репозиториев, если контракт читается из другого проекта (когда вы ведёте такую документацию)

PR без этой синхронизации — **автоматически FAIL** в `review-gate`.

## 3. Cross-Repo Drift Detector

Перед merge в main любого PR, меняющего публичный API:

```bash
# Найти все ссылки на старые пути в смежных репо
for path in OLD_PATH_1 OLD_PATH_2; do
  grep -r "$path" <корни смежных репозиториев> --include="*.{ts,tsx,py,md,yml,yaml}" \
    --exclude-dir={node_modules,.next,__pycache__,.venv}
done
```

Любое попадание ≥ 1 раз → **блокирующий FAIL** до синхронизации потребителей.

## 4. Hardcoded URL Guard

В сервисном слое (`app/services/`, `app/core/`, `lib/`, `services/`) — **запрещены** hardcoded production URLs.

Запретный grep (должен возвращать 0 строк):
```bash
grep -rE "https?://[a-z.]+\.example\.com|https?://localhost:[0-9]+" \
  app/services/ app/core/ lib/ services/ --include="*.{py,ts,tsx,js}"
```

Все публичные URL обязаны идти из `settings.public_base_url` (Pydantic Settings) или `process.env.NEXT_PUBLIC_*`. Email/notification сервисы — обязательно через env, с **dev-fallback** (логировать готовую ссылку в stdout, если внешний transport не сконфигурирован).

## 5. IDOR Sweep

Все endpoints, возвращающие или мутирующие user-data (содержат в URL `{user_id}`, `{attempt_id}`, `{session_id}`, `{course_id}`, `{material_id}` или возвращают объект с `user_id`/`owner_id`), обязаны:

1. Иметь `Depends(get_current_user)` (или эквивалент `Authorization: Bearer`).
2. Иметь явную IDOR-проверку: `if obj.user_id != current_user.id and not current_user.is_admin: raise HTTPException(403)`.
3. Иметь негативный тест на чужой ID → 403/404.

Команда проверки:
```bash
grep -nE "@router\.(get|post|put|patch|delete).*\{(user_id|attempt_id|session_id|course_id|material_id)\}" app/api/
# Для каждого попадания — проверить, что в сигнатуре есть get_current_user
```

## 6. Auth-Coverage Sweep

`review-gate` обязан собрать список всех `@router.*` декораторов в изменённых файлах и для каждого endpoint, возвращающего user-data, подтвердить наличие auth-зависимости. Endpoint без auth и без явного `# public: rationale` комментария — **блокирующий FAIL**.

## 7. Mock-Only Tests на External Write-Path

Если PR меняет HTTP client/SDK для внешнего API (LMS-client, VK-API, WP-REST, Telegram-API), 100% mock coverage **недостаточно** для PASS:

- Обязателен ≥ 1 live smoke-тест, gated по env (`<PROJECT>_<SERVICE>_TEST_*`).
- Тест может быть `@pytest.mark.skipif(not os.environ.get(...))`, но физически присутствовать в репо.
- При PR-review reviewer обязан запустить smoke хотя бы один раз и приложить raw output.

## 8. Mock vs Platform Reality

Моки в тестах не должны противоречить реальным платформенным ограничениям внешнего API. Конкретно:

- VK community-token vs user-token: разные наборы доступных методов (например, `wall.get` недоступен community-token).
- Telegram bot vs userbot: разные наборы методов.
- WP REST с `context=edit` vs `context=view`: разные поля в response.

`tech-spec-composer` для VK/Telegram/Dzen/WP flows обязан **явно фиксировать** тип используемого токена/клиента и его ограничения. Mock, противоречащий ограничению, — дефект тестов.

## 9. Migration: Entrypoint vs Execution vs State/Storage

Для миграций (legacy → new system) различать **три слоя cutover**:

1. **Entrypoint migrated** — operator CLI/команда переехала на новый код.
2. **Execution migrated** — фактический runtime/subprocess больше не использует legacy исполнитель.
3. **State/Storage migrated** — данные, sessions, working dirs больше не пишутся в legacy путь.

`pipeline-orchestrator` / `executor-pro` обязаны различать эти слои в evidence. Operator handoff = entrypoint migrated **не означает** runtime migrated. Active legacy runtime, не помеченный явно как `legacy-required/frozen/read-only`, — блокирующий FAIL миграции.

## 10. Stage Handoff Continuity

Для multi-stage pipelines (`tg_export → vk_prepare_publish_metadata → vk_publish_ready`) acceptance требует доказать **business entity continuity** на одной и той же сущности:

- Один и тот же `channel_post_id`/`global_uid`/`uid` виден в parse result, в metadata candidate selection, в publish prep.
- Parse success **не подразумевает** publish-path reachability. Если downstream selector не выбирает upstream-produced entity, фаза не готова.
- Selector queries (`WHERE source_system = ...`) обязаны включать все upstream-produced источники.

## 12. DB Migration as Contract Change

Alembic-миграция (или эквивалент) — это **изменение публичного контракта** базы данных. Любая миграция (`upgrade`/`downgrade`) обязана в **том же коммите** обновлять:

1. `docs/db-schema-*.md` (или эквивалентный schema-mirror) — реальный список таблиц/колонок/FK после миграции
2. ADR, если миграция меняет smysl модели (added/removed/renamed entity)
3. Документацию контрактов смежных модулей, если затронутая таблица читается/пишется из другого проекта (когда вы ведёте такую документацию)

Команда проверки соответствия (выполнить в review-gate):
```bash
# Все Alembic-файлы в коммите имеют пару в schema-mirror
git diff --cached --name-only | grep -E "alembic/versions/.*\.py$"
git diff --cached --name-only | grep -E "docs/.*-schema-.*\.md$"
# Если первая команда не пуста, а вторая — пуста → блокирующий FAIL.
```

Класс: Alembic-миграции без spec backsync создают drift между кодом и документацией.

## 13. OAuth / Auth State Parameter Discipline

Для любого OAuth/auth-flow с параметром `state`/`linking-token`/`csrf-token` ТЗ и реализация обязаны явно фиксировать:

1. **Формат на входе** — что приходит от клиента (с префиксом `link:` / без, base64 / hex / UUID).
2. **Формат на выходе** — что backend возвращает в callback URL.
3. **Семантика префиксов** — если используется `state = "link:" + token`, явно описать парсинг.
4. **TTL и single-use** — short-lived, single-use, привязка к session.
5. **Защита от хайджека** — link_token выпускается только текущей сессией, проверяется при callback.

Mock в тестах должен покрывать:
- happy-path с правильным префиксом
- атаку с подменённым/чужим state → 403/400
- expired state → 410/400
- race condition: один state используется дважды

Класс: в OAuth/linking-flow параметр `state` легко недооценить в ходе ревью; правило закрывает класс.

## 14. SQL Formula Verification (window-functions, gap-detection, recursive CTE)

ТЗ или код, содержащие raw SQL с `ROW_NUMBER() OVER`, `LAG/LEAD`, gap-detection (`d - rn*1d`, `date - row_number * interval`), recursive CTE — обязаны проходить **mental trace на 3-input примере** перед фиксацией:

1. **Расписать вход** — 3-5 строк тестовых данных (например, `dates = [2026-04-25, 2026-04-26, 2026-04-28]`).
2. **Расписать промежуточные значения** — для каждой строки указать `row_number`, результат gap-формулы, к какой группе попадает.
3. **Расписать ожидаемый выход** — например, для streak: «25-26 — одна группа (gap=0), 28 — отдельная группа (gap=2), streak=2 для 25-26».
4. **Сравнить с реальным выводом SQL** — если расходится, формула ошибочна.

Антипаттерны:
- Копировать формулу из upstream-spec без trace.
- Полагаться на «выглядит правильно».
- Не различать `ORDER BY d ASC` и `ORDER BY d DESC` — для gap `d - rn*1d` работает только при ASC; для DESC нужна `d + rn*1d`.

Обязательно: код с такой SQL формулой обязан иметь **edge-case тест** минимум на:
- Single-day input (streak=1).
- Multi-day без gap (streak=N).
- Multi-day с gap=1 (streak обрывается).
- Today_active vs today_inactive.

Класс: формула streak `d - rn*1d` для DESC даёт streak=1 для всех multi-day users; баг ушёл бы на prod без edge-тестов.

## 15. Consumer Parity Check (cross-project новый тип/поле)

При **разблокировке нового типа задачи / нового поля в response schema** в одном проекте — обязательная **сверка ВСЕХ потребителей** перед merge:

1. **Идентифицировать всех consumers** контракта через grep по схеме во всех связанных проектах:
   ```bash
   for project in <корни связанных проектов>; do
     grep -rn "<schema-name>\|<field-name>" "$project/" --include="*.{py,ts,tsx,md}"
   done
   ```
2. **Для каждого consumer** проверить:
   - используется ли новое поле / тип
   - совпадает ли имя поля с openapi (не drift `value` vs `text`)
   - mock-client синхронизирован с реальным openapi (`pnpm gen:api-types` / autogen)
3. **Live smoke раз в фазу** на критичный path для каждого consumer (gated env: `<PROJECT>_LIVE_SMOKE=1`).
4. **tech-spec-composer** обязан включать `Consumer Parity Check` в §«Критерии приёмки» при разблокировке нового типа.

Класс: consumer читает старое имя поля из mock (`value` вместо `text` из openapi), пока новый тип задачи заблокирован — drift не проявляется, пока тип не разблокируют. Consumer Parity Check ловит drift на review-gate, а не в production smoke.

## 16. Тест/проверка валидирует наблюдаемую истину, а не прокси

Зелёные тесты + «рендерится» + 200 ≠ работает у пользователя. Тест обязан проверять
то, что увидит пользователь/потребитель, а не суррогат («мок вернул», «поле есть»,
«функция вызвана»). Класс дал 6 багов на прод за одну сессию (2026-07-19).

- **Мок повторяет РЕАЛЬНУЮ форму ответа.** Enveloped/пагинированный эндпоинт (`Page[T]`
  = `{items,total,...}`, `{data:...}`) — мок и тип клиента обязаны быть этой формы, НЕ
  голым массивом/объектом «как удобно». Типы клиента — из `openapi` (`gen:api-types` /
  autogen), не выдуманные. (Баг: хук типизировал `by-user` как `MessageRead[]`, а эндпоинт
  отдаёт `Page` → `.map is not a function` на проде; тест мокал массив и не поймал.)
- **Assert ЗНАЧЕНИЯ, не присутствие.** Проверять, что поле содержит ОЖИДАЕМУЮ сущность
  (`student_name == "Иванов Иван"`), а не только «поле есть». (Баг: off-by-one в маппинге
  dict подставлял в `student_name` external_uid задания; тест проверял наличие ключа.)
- **List/inbox/aggregate — тест на НЕПУСТЫХ реалистичных данных.** Пустой ответ не
  исполняет ветку сборки строк. (Баг: inbox падал `KeyError 'last_message'` только на
  непустом диалоге — на проде, т.к. эндпоинт был сервис-only и с данными не гонялся.)
- **Кросс-view/кросс-эндпоинт инвариант.** Счётчик обязан совпадать со списком, который он
  суммирует (тот же предикат) — проверить равенство. Action-flow проверять по КОНЕЧНОМУ
  состоянию (заявка ушла из очереди, счётчик уменьшился), а не по «мутация вызвана». (Баги:
  «На проверке» считал по одному предикату, очередь — по другому; override продлевал лимит,
  но не закрывал заявку → очередь не сокращалась.)
- **Живая проверка в браузере валидирует то же на проде:** реальные значения,
  консистентность счётчик↔список, завершённость потока — не «страница отрисовалась + 200».

Класс (все прошли зелёные тесты, но упали на проде): Page-vs-array, inbox KeyError,
off-by-one в маппинге имени, счётчик≠очередь, override не закрывает заявку.

## 11. Контрольный чеклист перед PASS

Перед `review-gate PASS` вручную пройти:

- [ ] Public API изменён → spec/ADR обновлены в том же commit
- [ ] Cross-repo grep на старые пути выполнен и вернул 0 строк
- [ ] Hardcoded URL grep пуст
- [ ] IDOR sweep по новым endpoints выполнен, негативные тесты есть
- [ ] Если PR меняет external client — есть live smoke (хотя бы как `skipif`)
- [ ] Mocks не противоречат платформенным ограничениям
- [ ] Migration cutover: явное состояние всех трёх слоёв задокументировано
- [ ] Stage handoff: business entity видна end-to-end в pipeline evidence
- [ ] DB migration в коммите → schema-mirror обновлён в том же коммите (§12)
- [ ] OAuth `state`/linking-token явно специфицирован (§13)
- [ ] SQL window/gap-detection/recursive CTE прошёл mental trace на 3-input + edge-case тесты (§14)
- [ ] Consumer Parity Check выполнен при разблокировке нового типа/поля (§15)
- [ ] Тесты валидируют наблюдаемую истину, не прокси: мок = реальная форма ответа (envelope/Page), assert значений (не «поле есть»), непустые данные для list/inbox, кросс-view инвариант (счётчик=список) и конечное состояние потока (§16)

Любой невыполненный пункт без явного обоснования (`# rationale: ...`) — блокирующий FAIL.
