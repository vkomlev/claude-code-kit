# Security Checks

## Input and Access Control
- Are inputs validated and normalized at boundaries?
- Is authorization enforced for sensitive operations?
- Are trust boundaries explicit across layers?

## Data Protection
- Are secrets never hardcoded or logged?
- Is sensitive data exposure prevented in API responses/errors?

## Abuse and Misuse
- Any injection, deserialization, SSRF, or traversal risk introduced?
- Are rate/abuse controls considered for public endpoints?

## Supply and Configuration
- Any unsafe defaults or debug settings left enabled?
- Are dependency updates introducing known risk patterns?

## Secret Rotation Completeness
- После ЛЮБОЙ ротации секрета (пароль БД, API-ключ, токен) — раскатка считается завершённой только после обязательного `grep -rn "<old-marker>"` по ВСЕМ директориям `~/projects/*` (все проекты из `project-registry.md`), включая untracked/gitignored файлы — не по субъективному списку «известных потребителей» из CHANGELOG/git log.
- Список потребителей секрета, названный оператором или найденный через `git log -S`, не считается exhaustive — он покрывает только задокументированные изменения, не более ранние недокументированные настройки того же паттерна подключения в других проектах.
