# Phase 03-E.5C — Safe Jupiter Failure Diagnostics

Failed one-shot executions persist only `failure_reason`, selected from a fixed
classification, and `failure_code`, accepted only as a bounded integer. Raw
provider errors, API keys, credential-bearing RPC URLs, transaction bytes and
arbitrary provider text are never written to the gate. Unknown failures use
`JUPITER_EXECUTION_FAILED`.

This hotfix does not reopen a failed gate, arm a new gate, enable fees, sign or
broadcast. Run all regression tests with fee and one-shot flags disabled.
