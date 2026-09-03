# Testing Checks

## Coverage Depth
- Do tests cover changed behavior and key regressions?
- Are both happy path and failure path tested?
- Are boundary/edge conditions included?

## Test Quality
- Are tests deterministic and isolated?
- Are assertions meaningful (not only status-code level)?
- Do tests validate contracts, not implementation trivia?

## Practical Sufficiency
- Is there at least one fast smoke path for changed endpoint/flow?
- Are required commands clearly listed and executable?
- Is there at least one runtime smoke on detail/list endpoint with date fields (where relevant)?

## Bugfix Discipline
- Is there a test that reproduces the bug before fix (failing before, passing after)?

## Mock-Only Coverage Gap
- If all tests for an external write-path (LMS, VK, WP API) are mock-only, flag as insufficient.
- At minimum one optional live smoke test (gated by env variable like CB_LMS_TEST_*) must exist.
- Mock-only coverage on external write-paths cannot justify PASS for acceptance; require evidence of at least one real API call or explicit waiver from user.
- Pattern: repeats ERRORS.md #74 class — watch for 100% mocked HTTP client phases.

## Spec-Mandated Test Files
- If the spec explicitly lists required test files (in §«Tests» / §«Test Coverage» / §«Тесты» section, e.g., `test_streak_logic.py with edge cases gap=1, gap=2, today_active`) and those files are missing in the repo — this is **S2 (likely functional defect risk)**, NOT S3 (medium).
- Rationale: spec author classified them as mandatory for acceptance; their absence indicates either (a) acceptance criteria not met, or (b) spec/impl drift. In LMS Y-3 the missing `test_streak_logic.py` hid a critical SQL formula bug that would have shipped to production.
- Verification: `grep -E "test_[a-z_]+\.py" docs/tech-spec-*.md` against repo `tests/` directory; for each match, confirm: (1) file exists, (2) contains the listed edge-cases, (3) status pass.
- Source: LMS ERRORS 2026-04-29 #1 (executor pattern repeat) + #3 (severity misclassification).
