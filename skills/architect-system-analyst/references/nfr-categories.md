# NFR — Non-Functional Requirements

Явно проработать минимум 4 категории: **Performance, Reliability, Security, Maintainability**. Остальные — по применимости.

Для каждой NFR — формат: **Цель → Метрика → Текущее значение → Допустимая деградация**.

## Обязательные

### Performance
- **Latency** ключевых операций (p50/p95/p99)
- **Throughput** (RPS / задач в минуту)
- **Resource budget** (CPU/RAM/диск на процесс)
- Пример: «p95 /api/publications < 500ms, throughput 100 req/s»

### Reliability
- **Availability target** (99.x% или «best effort»)
- **MTTR** (mean time to recovery)
- **Backup / restore** стратегия и проверенность
- **Graceful degradation** — что происходит при недоступности зависимости
- Пример: «Pipeline выдерживает отказ VK API — retry 3x, затем skip с логом»

### Security
- **Threat model** — от кого защищаемся (внешний злоумышленник, внутренняя ошибка, LLM-инъекция)
- **Secrets management** — где хранятся, кто имеет доступ
- **Input validation** — на каких границах
- **Audit trail** — для каких операций
- **Dependency hygiene** — lock-файлы, CVE-мониторинг

### Maintainability
- **Readability target** — новый разработчик находит нужный код за X минут
- **Test coverage** — % для критических модулей
- **Deployment simplicity** — сколько шагов от clone до running
- **Documentation freshness** — README / ARCHITECTURE обновляются вместе с кодом

## По применимости

### Scalability
- **Growth assumptions** — во сколько раз вырастут данные / пользователи за год
- **Horizontal scaling** — какие компоненты stateless
- **Data partitioning** — когда понадобится и по какому ключу

### Observability
- **Logs**: structured, уровни, retention
- **Metrics**: что меряем, где смотрим (dashboard URL)
- **Traces**: для распределённых систем
- **Alerting**: кто получает и по каким условиям

### Compliance / Legal
- **Data residency** — где хранятся данные
- **PII handling** — как изолированы персональные данные
- **Retention policies** — сколько храним и как удаляем

### Operability
- **Runbook** — типичные инциденты и рецепты
- **On-call readiness** — есть ли дежурство, какие escalation paths
- **Environment parity** — dev/staging/prod различия

### Portability
- **Platform lock-in** — где мы завязаны на конкретного вендора
- **Data export** — как вытащить всё в переносимом формате

### Usability (для CLI / admin-tools)
- **Discoverability** команд (`--help`, subcommands)
- **Error messages** — ясные, с actionable подсказками
- **Idempotency** — повторный запуск безопасен

## Форма вывода NFR-секции

```markdown
## NFR

### Performance
| Метрика | Цель | Текущее | Допустимо |
|---------|------|---------|-----------|
| p95 API | <500ms | 380ms | 700ms |
| Pipeline full run | <10min | 7min | 15min |

### Reliability
- Availability: best-effort (single-operator project), MTTR <1ч
- Backup: ежедневный pg_dump в `backups/`, тестируется еженедельно

### Security
- Secrets: `.env` + `CB_CONTENT_HUB_DSN`, не в git
- Input validation: pydantic на границе CLI, SQL параметризован
- Threat: LLM output не выполняется как код, валидируется против schema

### Maintainability
- Test coverage: core pipeline 80%+
- Setup from scratch: <15 минут по README
- ARCHITECTURE.md обновляется вместе с изменениями границ
```

## Правила

- NFR без метрики = пожелание, не требование
- NFR без owner = ничьё, не выполнится
- NFR без regular check = через квартал уже не актуальны
- Для small project не городить 10 категорий — брать 4 обязательные + 1-2 по рискам
