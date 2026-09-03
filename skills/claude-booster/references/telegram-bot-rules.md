# Telegram Bot Rules (aiogram + aiogram-dialog + Redis FSM)

Единые правила для Telegram-ботов. Подключается из `executor-pro`, `executor-lite`, `techlead-code-reviewer`, `qa-fix`, `tech-spec-composer`, `telegram-ux-flow-designer`, `tg-bot-developer` (project-local).

Источник дефектов: tg-bot ERRORS 2026-03-03 (`~next_empty` aiogram-dialog), tg-bot чаты 30.04-01.05 (Y-4 Stage 3+4: FSM lock contention, zombie review states, legacy `/manual-check` escape-hatch).

## 1. aiogram-dialog: запрет «магических» условий

### Запрещены
- `when="~field_name"` как отрицание — **не работает** в aiogram-dialog. `~` не парсится как boolean NOT.
- `when="field_name"` для скрытия при truthy (логика инвертирована).
- Условия в строковом DSL, которые не покрыты unit-тестами на реальном render.

### Обязательно
- Lambda-форма: `when=lambda data, *_: not data.get("field_name", True)` — явное boolean выражение.
- Дефолт в `.get()` — обязателен (защита от `KeyError` при первом рендере).
- Unit-тест на каждое нетривиальное условие через `MockDialogManager`.

См. инцидент tg-bot 2026-03-03: `when="~next_empty"` скрывал кнопку всегда → `Phase 1 next` не работал в проде.

## 2. FSM lock contention и TTL

### Принцип
Любая claim-based операция (`/grade`, `/next`, `/lock`) использует Redis-lock с TTL. TTL должен покрывать **slowest realistic user path**, не средний.

### Запрещены
- TTL < 5 минут для пользовательских flow'ов (review, оценка, заполнение формы).
- Single-source TTL (только Redis) без fallback на DB-уровень claim record.
- Молчаливый release при таймауте — обязателен audit-log с reason.

### Обязательно
- TTL для review/grade flow: **300 сек минимум** (tg-bot Y-4 Stage 3 — поднятие с 180 до 300 после 409 contention).
- Конфиг TTL через env: `REVIEW_NEXT_TTL_SEC=300`, не hardcode.
- Negative тест: симулировать concurrent `/grade` от двух teacher'ов на одну review → один получает 200, второй 409 с `Retry-After`.
- Negative тест: симулировать lost-claim (process killed mid-review) → next `/next` через TTL+10s освобождает claim.

## 3. Zombie state recovery

### Что такое zombie state
Review/task запись в БД с inconsistent fields:
- `checked_at = NOT NULL, is_correct = NULL` (started but not graded)
- `claim_at = NOT NULL, claim_owner_id = NULL` (lock leaked)
- `status = 'pending_review'` навсегда после legacy endpoint

### Запрещены
- **Legacy escape-hatch endpoints** (`/manual-check`, `/admin-grade-bypass`) при наличии production grade flow → удалить полностью.
- Partial commit (audit row создан, но grade не применён) без savepoint обёртки.
- `UPDATE ... SET checked_at=now() WHERE id=...` без `is_correct` в одном statement.

### Обязательно
- Periodic cleanup job (raw SQL `WHERE checked_at IS NOT NULL AND is_correct IS NULL AND checked_at < now() - interval '1 hour'`) → reset to `pending`.
- Migration при удалении legacy endpoint — backfill всех текущих zombie rows (rid=10, rid=11 в tg-bot Y-4).
- Single transactional path для grade (`db.begin_nested()` для savepoint, rollback всё или commit всё).

## 4. callback_data discipline

### Лимит Telegram
`callback_data` ≤ **64 байта** (UTF-8). Превышение → silent fail / button broken.

### Запрещены
- JSON с длинными ключами в callback_data (`{"action":"grade","review_id":12345,"verdict":"accept"}` ~62 байта — на грани).
- UUID v4 (36 chars) + ещё что-то — превышает лимит.
- Хранение state в callback_data сверх ID — это работа FSM/Redis.

### Обязательно
- Pack-схема через `aiogram.filters.callback_data.CallbackData`: компактные имена (`g:12345:a` вместо JSON).
- Unit-тест на длину: `assert len(callback_data.pack().encode()) <= 64`.
- Если данные не лезут — хранить в FSM state, в callback передавать только short-id.

## 5. Multi-button UX (forbidden controls)

См. tg-bot ERRORS 2026-03-03 #2 + #3: next-mode `/grade` обнаруживал лишнюю кнопку `⬅️ К списку`, обходящую обязательный grade-flow и оставляющую lock.

### Запрещены в next/queue режиме
- Secondary navigation (`⬅️ К списку`, `🏠 Главное меню`) во время активного claim — обходит release.
- `/start` без прерывания текущего dialog'а — оставляет orphan FSM state.
- Inline back-button, ведущий не в expected target (`StudentsSG.LIST` вместо `MainMenuSG.MAIN` — амбигуальность ТЗ).

### Обязательно
- ТЗ обязано содержать раздел `Forbidden Controls` для каждого next/queue режима.
- `tech-spec-composer` для TG-bot задач — block ТЗ без явного списка forbidden controls.
- `techlead-code-reviewer` — `FAIL` если в next-mode UI render содержит forbidden controls.
- Release claim на **всех** путях выхода из dialog'а: `on_close`, `on_back`, `/start`, `/cancel`, timeout.

## 6. Cross-project API consumption (tg-bot → LMS)

tg-bot вызывает LMS API через `aiohttp`/`httpx`. Контракт меняется в LMS — tg-bot должен следовать.

### Запрещены
- Hardcoded LMS URL пути (`/api/v1/auth/magic-link/request`) — должны идти из `contracts/lms-api.md` mirror.
- Mock LMS client с устаревшим response shape — drift не ловится.
- Bot-token полномочия для cross-bot операций (teacher_bot отправляет от methodist_bot) — нарушает API design.

### Обязательно
- При обновлении LMS endpoint — tg-bot контракт-mirror в `contracts/tg-lms.md` обновляется в том же коммите (cross-project gate).
- Live smoke на критичный path (claim → grade → release) минимум раз в фазу — gated по env `TG_BOT_LIVE_SMOKE`.
- Mock LMS client синхронизируется с реальным `openapi.json` через автогенерацию (раз в неделю — см. §automation).

## 7. Encoding и русский язык

### Запрещены
- Mojibake в callback_data (`b'\xd1\x80\xd0\xb5\xd0\xb2'` вместо `'рев'`) — проверять кодировку при `.encode('utf-8')`.
- ASCII-only emoji-fallback (`>>` вместо `⚡`) без явного fallback rationale.

### Обязательно
- Все user-visible тексты — русские (`Принять / Отклонить`, не `Accept / Reject`).
- Кнопки `🔵 ⚡ ✅ ❌` UTF-8; в коде через unicode literals `"⚡"`, не raw bytes.
- `Console.OutputEncoding = UTF-8` в Windows-runner.

## 8. Контрольный чеклист перед PASS (TG-bot specific)

- [ ] aiogram-dialog conditions через lambda + .get() с дефолтом
- [ ] FSM lock TTL ≥ 300s + env-config + negative test на contention
- [ ] Zombie state cleanup job + savepoint pattern для grade/claim
- [ ] callback_data ≤ 64 байт (unit-тест на pack length)
- [ ] Forbidden Controls в ТЗ + release claim на всех путях выхода
- [ ] Cross-project contract-mirror обновлён в same commit (если LMS endpoint затронут)
- [ ] Live smoke critical path gated по env (раз в фазу)
- [ ] UTF-8 для всех user-visible текстов
- [ ] Multi-bot изоляция (teacher/methodist token не делегируются)
- [ ] Edit-prompt UX (§10): хелпер для редактирования полей с existing value

## 9. Связь с другими правилами

- **api-contract-rules.md §1-6**: tg-bot как cross-project consumer LMS — все правила backsync применяются.
- **operator-handoff-rules.md**: smoke в TG App требует operator (нельзя автоматизировать через playwright); классификация А (mock TG WebApp) vs Б (operator runs bot in real chat).
- **frontend-stack-rules.md §4**: TG App context — один из трёх для SPW; правила multi-context smoke matrix распространяются.

## 10. Edit-prompt UX (редактирование текстовых полей)

Источник: tg-bot внутренней задаче (2026-05-20) — разрозненная реализация
редактирования полей: где-то prompt был с tap-to-copy старого значения, где-то
plain-text «Текущее имя: …», где-то ничего. Пользователь не мог скопировать
старое значение чтобы поменять только фрагмент.

### Принцип

Для **любого** редактирования поля, у которого есть существующее значение
(имя, email, название, URL, описание, причина, комментарий…) — обязательно
показать старое значение **в tap-to-copy формате** (HTML `<code>`) ОТДЕЛЬНЫМ
сообщением, а в приглашении использовать `ForceReply` с placeholder из старого
значения.

Это позволяет:
- Видеть текущее значение поля прямо рядом с приглашением.
- Скопировать его одним тапом (Telegram-клиенты делают tap-to-copy на `<code>`).
- Вставить и поменять только фрагмент — частый кейс при правке email домена,
  суффикса названия, фрагмента описания.

### Запрещены

- Plain-text «Текущее значение: ABC» в Window prompt вместо хелпера —
  пользователь не может скопировать.
- Дублировать «текущее значение» plain-text'ом в getter Window'а, если хелпер
  уже отправил его (двойной рендер, путаница).
- Свой код auto-delete / ForceReply / `<code>`-форматирования для edit-prompt'ов —
  только через хелпер (DRY).

### Обязательно

- **Общий хелпер**: `send_edit_prompt_with_copy(event, prompt, current_value, manager, next_state)`
  — отправляет ForceReply + `<code>{escaped current_value}</code>`, выполняет switch_to.
- **Специализированные обёртки** для типовых полей: `start_user_name_edit`,
  `start_user_email_edit`, `start_material_field_edit` — внутри проекта.
- **HTML-экранирование** `current_value` через `html.escape(text, quote=True)` —
  иначе TG отвергнет сообщение из-за невалидного HTML или будет XSS-инъекция
  тегов.
- **Лимит длины** ≤ 4080 символов в `<code>` (защита от MESSAGE_TOO_LONG); при
  превышении — обрезать и пометить «… (обрезано)».
- **placeholder** в ForceReply ≤ 64 символа (лимит Telegram); хелпер
  обрезает автоматически.

### Когда хелпер НЕ нужен

- Новый ввод без существующего значения (создание курса, отправка нового
  сообщения, причина отказа на заявку) — обычный TextInput/MessageInput.
- Поиск/фильтр по списку (нет «старого значения»).
- Выбор кнопкой (access_level, role, флаги) — InlineKeyboard, не текст.

### Скрипт обнаружения нарушений (cross-project grep)

```bash
# Найти getter'ы, которые рендерят plain "Текущее ..." text:
grep -rE "Текущ(ее|ий|ая).*\{.*\}" src/bots/ --include="*.py" | \
  grep -v "edit_prompt\|send_edit_prompt_with_copy"

# Найти Window edit-* без вызова хелпера:
grep -rB5 "EDIT_TITLE\|EDIT_NAME\|EDIT_EMAIL\|EDIT_DESCRIPTION" src/bots/ \
  --include="*.py" | grep -E "switch_to.*EDIT" | grep -v "send_edit_prompt"
```

`techlead-code-reviewer` и `pr-review` обязаны помечать любое новое
редактирование поля без `send_edit_prompt_with_copy` как **S2 UX-блокер**.

См. `tg-bot/.claude/CLAUDE.md §Edit-Prompt UX Guard` для project-local
инструкции и ссылок на хелперы.
