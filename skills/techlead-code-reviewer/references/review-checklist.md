# Core Review Checklist

## Correctness
- Does code implement intended behavior exactly?
- Are edge cases and failure paths handled?
- Any hidden state/ordering assumptions?
- Any likely regression in neighboring flows?

## SOLID / DRY / Clean Code
- Single responsibility preserved at class/function level?
- Open/closed preserved without fragile condition chains?
- Dependency inversion respected at boundaries?
- Duplicated logic introduced instead of reuse?
- Naming, abstraction, and function size support maintainability?

## Production Reliability
- Timeouts/retries/error handling are explicit and bounded?
- Resource handling (DB sessions, files, network) is safe?
- Concurrency/idempotency considerations covered where relevant?

## Operational Readiness
- Logs provide enough context for incident diagnosis?
- Sensitive data excluded from logs?
- Validation commands are reproducible?

## Phase Integrity Check
- Is there a source-of-truth document for stage names and boundaries?
- Does the review separate `microstep implemented`, `current repository integration-safe`, and `phase complete`?
- Are all mandatory subparts/source kinds of the current phase explicitly accounted for?
- Is any recommendation to move forward blocked until unfinished current-phase work is called out?
- Is the live repository/runtime judged as it exists now, not as it may look after future planned steps?

## Goal-Level Data Completeness Check
- If the business goal is migration/backfill/import, was actual target data presence checked, not only code/tests?
- Is there a source-of-truth for expected counts or reconciliation?
- Are smoke fixtures clearly separated from real historical data?
- If media transfer matters, was actual media presence checked?
- Does the review separate `code complete`, `smoke complete`, and `historical data loaded`?

## Domain Model Completeness Check
- If commands or operator flows are being migrated, what domain model stands behind them?
- Are classification fields, policy state, generator keys, mappings, and similar prerequisites present in the target system as usable data?
- Is any command being treated as implemented even though only its shell exists?

## Operator-Critical Chain Check
- If the phase gate includes a manual/control run, was the real chain checked end-to-end?
- For conditional chains, was reachability of the recovery/interactive branch proven from the preceding step?
- If component tests are green but the real control run contradicts them, does the review keep the phase at `FAIL`?
- Is live source-side or operator-side evidence treated as stronger than mocked/component-level evidence for final acceptance?

## Closure Check
- Is the phase blocked only by one last acceptance step?
- If yes, is it safe, authorized by the user, and targetable through a disposable object?
- If yes, has the execution plan shifted from "manual later" to "run now and capture evidence"?

## Date/Time Critical Check
- For any `raw SQL -> date field -> now comparison` path, are types normalized and guarded before comparison?

## Live API / External Write-Path Check
- If a pipeline writes to an external API (e.g. a third-party API/CMS), is there at least one live smoke test (gated by env)?
- Is 100% mock-only coverage on external write-paths flagged as insufficient for PASS?
- Does the config contain real values (not placeholders) with enabled: true?
- Are runtime dependencies actually installed in target env (not just in requirements.txt)?

## Spec-to-Code Identifier Consistency
- Are key identifiers (global_uid, source_key) in code consistent with the canonical spec definition?
- If format diverged, is there an explicit justification and spec update?

## Fetch/Normalize/Parse Mode Consistency
- For pipeline parse-paths, do fetch and normalize use the same mode (edit vs rendered)?
- Does the mode match the plan/spec decision?

## Config Silent-Failure Check (registration gaps + fallback defaults)
Two shapes of the same root cause — config going quietly wrong instead of failing loudly:
- **Whitelist gap:** new env/config key registered only in `.env`/`.env.example`, not in the project's
  config loader. A whitelist-style loader (e.g. `config.py::load_config()`) silently drops
  unregistered keys — the handler runs in a "quiet empty" mode instead of failing. Smoke assertion:
  `assert "NEW_KEY" in load_config()`. Recurred repeatedly across projects.
- **Silent dev-fallback:** `os.environ.get(KEY) or "<dev-looking default>"` (localhost URL, hardcoded
  test API key/token) — a missing/unset env var in a real run falls back to a dev value instead of
  failing. Caught only by an *independent* review of scripts that hit a real/prod target,
  not by this checklist — treat as a gap this checklist must close.
  Correct shape: `os.environ[KEY]` (raises if unset) for any value used against a real/prod target.
- Either shape on a key outside the whitelist or with a dev-looking fallback — automatic FAIL, not a style note.
