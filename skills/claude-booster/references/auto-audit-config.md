# Auto-Audit Configuration (Режим E claude-booster)

Конфигурация автоматического запуска регулярного аудита skills. Применяется через scheduled task.

> **Заводишь или чинишь плановое задание — сперва `scheduled-tasks-windows.md`.** Там грабли,
> общие для всех заданий этой машины: планировщик стартует в `C:\Windows\System32` (падает
> всё, что работает с путями от cwd), `$ErrorActionPreference = "Stop"` убивает обёртку на
> stderr до логирования, History заданий выключена, `schtasks` из Git Bash требует
> `MSYS_NO_PATHCONV=1`. Стоили двух ложных диагнозов в внутренней задаче.

## Команда запуска

В чате Claude Code: `/claude-booster weekly-audit` (или `auto-audit`).

Запускает Режим E claude-booster:
1. Читает свежие JSONL-чаты за 7 дней по 4 проектам.
2. Читает ERRORS.md проектов на новые записи.
3. Параллельно анализирует через 4 Explore-агента.
4. Кластеризует находки, применяет автоправки (только Edit, ≥2 эпизода для триггера).
5. Записывает отчёт в improvement-log.md.

## Параметры окружения

- **Период:** 7 дней по умолчанию. Override: `/claude-booster auto-audit --since=2026-04-29 --until=2026-05-01`.
- **Проекты по умолчанию (8 активных):** content-service, LMS, SPW, tg-bot, content-project, CyberGuru-EGE, IT-Businessman, IDE-booster. Skip-rule: проект без JSONL в окне периода — пропускается (защита от шума single-session паттернов). Override: `--projects=LMS,SPW`.
- **Auto-fix threshold:** ≥2 эпизода одного класса в одном skill. Override: `--threshold=1` (агрессивный режим для onboarding новых проектов).

## TG-уведомления (через @plugin_telegram_telegram)

**Канал:** Telegram-плагин Claude Code (`mcp__plugin_telegram_telegram__reply`).
**Chat ID оператора:** `344276500` (из `~/.claude/channels/telegram/access.json`).
**Допущения:** оператор уже выполнил `/telegram:configure` и `/telegram:access` для allowlist.

**Что отправляется:**

| Событие | Маркер | Канал |
|---------|--------|-------|
| Каждый успешный прогон | 🤖 | Краткий summary (~600 символов): период, проектов, кластеров, автоправок, ссылка на improvement-log |
| Повтор паттерна 3+ раза | 🚨 ESCALATION | Отдельный reply со skill+проект+ERRORS-ссылка |
| Нужны новые reference/skill (S1/S2) | 🆘 Operator handoff | Отдельный reply с А/Б опциями для оператора |
| Skipped (rate-limit < 24h) | ⏭️ | Краткий reply «прогон пропущен, причина» |
| Ошибка прогона | ⚠️ | Reply с trace + путь логов |

**Антипаттерны (не делать):**
- Спам уведомлениями при каждом найденном кластере (только итоговый summary + escalations).
- Полный отчёт в TG (есть лимит 4096 символов, читать неудобно). Полный — в improvement-log.md, в TG только summary + ссылка.
- Креды/секреты в тексте reply (не светить chat_id, токены в исходящем).

**Fallback при недоступном TG-плагине** (e.g., headless-сессия не загружает MCP):
1. Зафиксировать в improvement-log.md: «TG notification skipped: plugin unavailable».
2. Использовать встроенный `notifyOnCompletion` Claude Code (in-app).
3. Опциональный workaround: bot token в env + `curl -X POST https://api.telegram.org/bot$TG_BOT_TOKEN/sendMessage -d chat_id=344276500 -d text=...` (но требует хранения токена, что нарушает правила безопасности).

## Способы планирования

> **ОСНОВНОЙ механизм (с 2026-06-01): проактивный самозапуск в живой сессии.** Разбор завязан на локальные чаты `~/.claude/projects/*.jsonl` и локальные файлы навыков — **облачный/удалённый агент (`/schedule`, RemoteTrigger) к ним доступа НЕ имеет**, headless-CLI ненадёжен. Поэтому правило в `~/.claude/CLAUDE.md` § Контур обратной связи: в любой сессии в понедельник+ проверить дату последнего weekly-аудита в improvement-log и предложить запуск, если прошло ≥7 дней. Способы A/B/C ниже — вспомогательные (A — облачный, для этого аудита непригоден; B — TG-напоминание, работает как толчок).

### Способ A: Anthropic SDK scheduled task (НЕ для этого аудита — нет доступа к локальным данным)

Использовать `mcp__scheduled-tasks__create_scheduled_task` — встроенный механизм Claude.

Параметры:
- **Name:** `weekly-skills-audit`
- **Cron:** `0 9 * * MON` — каждый понедельник 09:00
- **Action:** запустить chat session с командой `/claude-booster weekly-audit` в проекте `IDE_booster`
- **Notification:** уведомление пользователю о завершении (с резюме отчёта)

### Способ B: Windows Task Scheduler — TG-trigger (рекомендуется как primary после провала Способа A в headless)

**Контекст:** SDK scheduled task (Способ A) запускался 2026-05-04, но упал тихо без session log и TG-уведомления. Гипотеза: Agent (Explore) и MCP-плагин telegram недоступны в headless-сессии Claude Code. Способ B полностью обходит это — отправляет **TG-reminder через Telegram Bot API напрямую** (curl/Invoke-RestMethod), а сам анализ остаётся ручным запуском `/claude-booster auto-audit` в interactive-сессии.

**Готовый скрипт:** `~/.claude/scripts/weekly-audit-trigger.ps1`

Что делает:
1. Собирает stat за 7 дней по 8 проектам: размер JSONL-чатов, кол-во записей ERRORS.md за период.
2. Формирует summary без LLM (factual, не интерпретация).
3. Отправляет в Telegram через `https://api.telegram.org/bot<TOKEN>/sendMessage`.
4. Логирует в `~/.claude/logs/weekly-audit-trigger-YYYY-MM-DD.log`.
5. Reminder призывает оператора запустить `/claude-booster auto-audit` вручную.

**Pre-requisites (один раз):**

1. **Создать Telegram-бота** (если ещё нет): чат с `@BotFather` → `/newbot` → получить `<token>`.
2. **Установить env-переменную пользователя:**
   ```powershell
   [Environment]::SetEnvironmentVariable('TG_BOT_TOKEN', '<token>', 'User')
   # Опционально:
   [Environment]::SetEnvironmentVariable('TG_CHAT_ID', '344276500', 'User')
   ```
3. **Перезагрузить терминал** (чтобы env подхватилась).
4. **Проверить отправку вручную:**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.claude\scripts\weekly-audit-trigger.ps1"
   ```
   Если в Telegram пришло сообщение — всё ок.

**Регистрация в Windows Task Scheduler:**
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File ~/.claude\scripts\weekly-audit-trigger.ps1"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "Claude-WeeklyAuditTrigger" `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "Weekly skills audit reminder via Telegram"
```

**Проверка регистрации:**
```powershell
Get-ScheduledTask -TaskName "Claude-WeeklyAuditTrigger" | Format-List
Get-ScheduledTaskInfo -TaskName "Claude-WeeklyAuditTrigger"  # last/next run, exit codes
```

**Тестовый запуск без ожидания понедельника:**
```powershell
Start-ScheduledTask -TaskName "Claude-WeeklyAuditTrigger"
```

**Откат:**
```powershell
Unregister-ScheduledTask -TaskName "Claude-WeeklyAuditTrigger" -Confirm:$false
```

**Hybrid-режим:**
- MCP scheduled task `weekly-skills-audit` оставлен enabled — может однажды заработать (если Anthropic починит headless plugin loading).
- Native Windows Task Scheduler `Claude-WeeklyAuditTrigger` — гарантированный fallback.
- Оба запускаются по понедельникам в 09:00. Если оба сработают — оператор увидит 2 сообщения (это OK, лучше чем 0).
- Через 4 недели по метрикам решить: оставить hybrid или отключить MCP-вариант.

### Способ B-OLD: Windows Task Scheduler с headless Claude CLI (не работает стабильно)

~Не рекомендуется~ — попытка запустить `claude --headless --prompt="..."` через Windows Task Scheduler требует Anthropic API-ключа в env, не использует MCP-плагины (тот же блок, что у SDK scheduled task), и truncate'ит длинные prompt'ы. Сохранён здесь как историческая заметка.

### Способ C: Loop skill (полу-автоматический)

Использовать встроенный `loop` skill для interactive прогонов:
```
/loop 7d /claude-booster weekly-audit
```
Запускает каждые 7 дней внутри активной сессии. Минус: требует открытой сессии.

## Безопасность auto-режима

- **Edit-only:** Режим E не создаёт новых файлов автоматически. Только правки существующих.
- **Backup перед каждой правкой** обязателен.
- **Anti-bloat check** обязателен (как в Режим D).
- **Operator handoff** для S1/S2 кластеров требующих новых файлов — через `AskUserQuestion`.
- **Эскалация** при повторе паттерна 3+ раза — явный маркер `**ESCALATION:**` в отчёте.
- **Rate limit:** не запускать чаще 1 раза в 24 часа во избежание ложных срабатываний на single-session паттерны.

## Метрики эффективности (review-after-N-runs)

После каждого прогона записываются метрики в `references/auto-audit-metrics.md`:
- Кластеров обнаружено
- Автоправок применено
- OPEN записей создано
- Эскалаций
- Skills затронуто (уникальных)
- Время прогона

Ежемесячно — операторский review метрик. Если автоправки имеют high false-positive rate (>30%) — повысить threshold до 3 эпизодов или отключить auto-mode для конкретного skill.

## Проверка установки расписания

```powershell
# Способ A (SDK):
# через mcp__scheduled-tasks__list_scheduled_tasks

# Способ B (Windows):
Get-ScheduledTask -TaskName "Claude-WeeklyAudit" | Format-List

# Способ C (loop):
# проверить вывод /loop list
```

## Откат

Способ A: `mcp__scheduled-tasks__update_scheduled_task` (disable) или delete.
Способ B: `Unregister-ScheduledTask -TaskName "Claude-WeeklyAudit" -Confirm:$false`.
Способ C: остановить loop через UI Claude Code.
