# Operating Model

## Work Contours
1. Product delivery contour
- spec -> implementation -> review -> integration

2. Content/pipeline contour
- source intake -> parsing -> enrichment -> publishing/reporting

3. Improvement contour
- capture errors -> classify -> update rules/skills -> regression check

## Context Levels (Claude-only)
- minimal: routine deterministic execution (formatting, small edits, boilerplate, commits).
- standard: medium complexity integration and structured planning (specs, plans, reviews).
- full: architecture-level reasoning, complex debugging and final quality gate.

## Gates
- `spec-gate`: objective, scope, acceptance, constraints are explicit.
- `execution-gate`: implementation completed with relevant checks.
- `review-gate`: independent PASS/FAIL decision with findings.
- `merge/commit-gate`: integrate to main/master only after PASS.

## Branch Policy
- Default mode: direct work in main/master with stronger pre-commit controls.
- Separate branches: only for fully autonomous long-running agent work.

