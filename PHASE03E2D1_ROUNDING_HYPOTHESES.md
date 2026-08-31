# 03-E.2D.1 — Independent Boundary & Floor/Ceil Hypotheses

Supersedes the E.2D four-probe classification and floor-only expectation.
Production arithmetic, quote/swap routes, fees, signing, .env and execution
gates are unchanged. This changes the read-only audit harness and its tests only.

## Six bounded parallel probes

- Boundary: below=N-1, equal=N, above=N+1, all at zero slippage.
- Rounding lower control: floor and ceil both predict success.
- Rounding split: floor predicts success, ceil predicts Jupiter 6001.
- Rounding upper control: floor and ceil both predict Jupiter 6001.

Predictions are independently reconstructed from integer arithmetic. Each
rounding probe reports floor_minimum, ceil_minimum and both expected outcomes.
At most six simulation requests run concurrently; no automatic retries.

Boundary classification uses only the first three probes, sharing the successful
equal-probe bank and pool trace. A failed rounding hypothesis does not invalidate
those boundary observations. Rounding conclusions additionally require a valid
boundary reference, matching bank/trace for all rounding probes and unchanged
output/fee on successful probes. Altered controls can contradict both hypotheses.

Top-level status is always BOUNDARY_ROUNDING_REVIEW_REQUIRED. Inspect:

- boundary.status: SAME_BANK_BOUNDARY_OBSERVED or BOUNDARY_INCONCLUSIVE.
- rounding.status: FLOOR_CONSISTENT_WITH_SAMPLES, CEIL_CONSISTENT_WITH_SAMPLES
  or ROUNDING_INCONCLUSIVE.
- rounding.hypotheses: separate CONSISTENT_WITH_SAMPLES,
  CONTRADICTED_BY_SAMPLES or INCONCLUSIVE outcomes, and mismatching probe names.
- probe_diagnostics: per-probe outcome and reasons.

Missing output/fee on a rejected probe is not a fee change. Those fields are
compared ONLY after SUCCESS. Unknown errors remain inconclusive, never treated
as Jupiter slippage. RPC or missing-trace failure of one probe is recorded with
a generic safe reason and does not erase other probes. Preflight/calibration
failure still stops the audit. No fabricated results or retry fallback.

This is finite unsigned simulation evidence, conditional on accurate RPC
bank/trace reporting. It does NOT prove the universal/deployed formula. Both
ceil(x) and quote-floor(quote*bps/10000) can be algebraically equivalent here;
these probes cannot identify the internal implementation. Do not update the
production formula merely because one hypothesis is consistent with samples.

execution_ready=false, fee_receipt_verified=false,
general_enforcement_proven=false, production_formula_changed=false always.

## Install and verify (AlphaRadar root)

Requires the E.2D installer baseline, regardless of whether it has been committed.
Exact hash checks, BOM/CRLF preservation, backups and idempotence are retained.
STOP means provide the named source file; never bypass the hash guard.

```powershell
python .\apply_dexsato_phase03e2d1_rounding.py --check
python .\apply_dexsato_phase03e2d1_rounding.py
python -m pytest -q
node --test tests/test_jupiter_fee_ui.js
```

Use the existing configured RPC/referral environment with fees disabled.
These parameters belong to the original unsigned evidence only:

```powershell
python -m application.jupiter_minimum_boundary `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\minimum_rounding_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

Upload the new report and regression results. The old four-probe report is not
silently upgraded: it lacks the two rounding controls. Keep it as prior evidence.
Report exit code 2 is intentional, never an execution approval. If source
evidence becomes stale, capture fresh unsigned evidence; do not weaken checks.

## Commit after review

```powershell
git add application/jupiter_minimum_boundary.py tests/test_jupiter_minimum_boundary.py PHASE03E2D1_ROUNDING_HYPOTHESES.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: separate boundary and floor ceil hypotheses"
```

If E.2D remains uncommitted, also review/stage its pytest.ini and
PHASE03E2D_MINIMUM_BOUNDARY.md explicitly. Never stage unrelated backups or .env.
