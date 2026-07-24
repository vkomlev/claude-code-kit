# Observability Checks

## Logging
- Are important state transitions and failures logged?
- Are log levels appropriate (INFO/WARN/ERROR)?
- Is correlation/context included (request id, entity id, operation)?
- Are secrets/PII excluded from logs?

## Diagnostics
- Can on-call engineer identify root cause from logs?
- Are actionable messages present for expected failure modes?

## Metrics/Monitoring (if applicable)
- Are critical counters/latencies/error rates observable?
- Are alert-worthy conditions identifiable?

## Logging Presence Gate
- Does every new/changed pipeline module (>50 lines) have `import logging` and use a named logger?
- Absence of logging in pipeline modules is an automatic FAIL.
- Are key state transitions (fetch, parse, normalize, sync, publish) logged at INFO level?
- Are errors logged with sufficient context (entity id, step name, error message)?
