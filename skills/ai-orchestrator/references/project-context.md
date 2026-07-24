# Project Context

## Registry Source
Ведите список своих проектов и путей в одном месте (например, `docs/project-registry.md`),
чтобы оркестратор знал границы и мог маршрутизировать задачи по нужным модулям.

## Shared Constraints
- Скиллы живут в `~/.claude/skills/` и доступны во всех проектах.
- Encoding guard обязателен для операций с текстом docs/reviews.
- Review-gate обязателен перед интеграцией в main/master.
- Ведите циклы обработки ошибок для кода (`ERRORS.md`) и качества ответов (`ANSWER_ERRORS.md`).
