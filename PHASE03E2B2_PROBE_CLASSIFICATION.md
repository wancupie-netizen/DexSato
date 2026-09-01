# 03-E.2B.2 — Program-bound minimum probe classification

Requires installed 03-E.2B.1. Diagnostic harness only; no production fee, signing,
RPC call, probe byte mutation, .env or execution gate changes.

The supplied probe reached Jupiter instruction index 6 and returned Custom 6001;
all recorded downstream calls completed successfully. The previous classifier
additionally demanded an Anchor prose error line, which was not observed.

Error mapping: https://developers.jup.ag/docs/swap/v1/common-errors
JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4 code 6001 is SlippageToleranceExceeded.
The number by itself is NOT sufficient: different programs have different errors.

New criteria require ALL of:
- Strict numeric RPC error index/code equal expected route / 6001.
- Runtime invocation trace starting from instruction zero with consistent stack depth.
- Every child returns success before the outer Jupiter failure.
- Exactly the expected top-level Jupiter frame fails with custom error 0x1771.
- No unfinished stack, malformed lifecycle, downstream failure, truncation marker
  or additional lifecycle events after failure.

Anchor error prose is optional. Missing/partial traces remain inconclusive.
Logs are provider evidence, not a cryptographic proof. This observes a negative
simulation rejection, not exact rounding, threshold boundary, historical-state
equivalence, complete route safety, live fee receipt, or authorization to trade.
execution_ready and enforcement_verified remain false even for a matched probe.

## Install/test

```powershell
python .\apply_dexsato_phase03e2b2_probe_classification.py --check
python .\apply_dexsato_phase03e2b2_probe_classification.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Exact source hashes are checked before writes, backups retained, CRLF/BOM preserved.
Only the pool validation module, its test file and this document change. Do not
bypass a baseline mismatch. No additional dependencies.

Local verification: 25 pure tests passed, one SDK-vector skipped (solders absent),
two dependency-isolated production-parser byte tests passed. Reconstructing runtime
lifecycle lines from the uploaded filtered diagnostic events yielded the intended
classification, but is NOT a new RPC simulation or replay of the original raw logs.
Full application regression and fresh live simulation must run in your environment.

## Fresh report (same evidence parameters only)

Use existing RPC/referral process configuration and keep fees disabled.

```powershell
python -m application.jupiter_binding_audit `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\pool_minimum_classification_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

For a different capture, use that order's reviewed input/minimum/fee/wallet values.
Do not overwrite prior reports. Old evidence may fail as market state changes;
refresh unsigned evidence rather than relax validation if baseline simulation fails.
This CLI does not automatically load .env. Never share credentials.

Expected when the same failure pattern recurs:
negative_probe.status = NEGATIVE_MINIMUM_PROBE_OBSERVED.
Top-level status intentionally remains BINDING_REVIEW_REQUIRED (exit code 2).
Other pool bindings and precise minimum-output semantics remain open.

Upload pool_minimum_classification_report.json and regression output for review.
Do not treat a positive probe classification as permission to sign or send.

## Commit after tests pass (includes uncommitted E.2B.1 documentation)

```powershell
git add application/jupiter_pool_validation.py tests/test_jupiter_pool_validation.py PHASE03E2B2_PROBE_CLASSIFICATION.md PHASE03E2B2_PROBE_CLASSIFICATION.md
git diff --cached --check
git commit -m "test: classify minimum probe by Jupiter code and runtime trace"
```
