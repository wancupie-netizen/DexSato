# 03-E.2D — Exact Minimum Output Boundary Validation

## Safety contract

Separate operator-only, read-only audit CLI. No production routes, UI, .env,
fee policy, signing, submission or claim behavior is changed. Requires fees
disabled. Uses existing bounded simulateTransaction RPC only; never sends a
transaction. All reports retain execution_ready=false and fee_receipt_verified=false.
No mutated transaction payload is persisted. Only a transaction hash is saved.

## Experiment

1. Run fresh E.2C binding preflight. Require all three typed bindings, linked
   route, Pancake candidate match and no unsupported program for this profile.
2. Re-read unsigned evidence, resolve accounts and require unchanged message hash.
3. Simulate original order again to select observed net output N; require normal
   output minimum and fee checks. This calibration may precede the comparison bank.
4. In parallel (maximum four workers, no automatic retries), simulate mutations
   changing ONLY quotedOutAmount and slippageBps of the original Jupiter V2 route.

| Probe | Requested threshold | Expected |
|---|---|---|
| below | N-1 at 0 bps | Success, same output N |
| equal | N at 0 bps | Success, same output N |
| above | N+1 at 0 bps | Jupiter 6001 at original route, validated runtime trace |
| rounding_floor | Nonintegral quote*(10000-bps)/10000 with floor N | Success, same output N |

For rounding, use the order's nonzero slippage, or an explicitly synthetic 50
bps if original slippage is zero. This is not a user slippage setting change.
The probe N success is the counterfactual reference bank. Every comparison
probe must report the SAME finalized context slot, identical pool CPI trace,
and the expected outcome. Successful probes must preserve net output and fee.
Pool fingerprints include all four pool calls and their returned child CPIs,
including transfers/events, not just program names. Failed transactions are
not treated as balance changes: their pre-rejection CPI evidence is compared.

minContextSlot is only a lower bound, NOT an RPC slot pin. Returned slots are
checked explicitly. A shared slot/trace relies on trustworthy RPC reporting;
this is not a cryptographic proof or independent replay of a frozen bank.

## Results

- SAME_BANK_BOUNDARY_OBSERVED: adjacent N/N+1 behavior observed in one reported
  bank, with the negative Jupiter classification and matching pool traces.
- rounding_sample_observed=true: the tested nonintegral example is consistent
  with floor rather than ceil. Not proof for every possible amount/bps/route.
- BOUNDARY_INCONCLUSIVE: changed slot, pool trace, output, fee or unexpected
  outcome. Review reasons; NEVER treat an inconclusive result as passing.
- BOUNDARY_AUDIT_INCOMPLETE: bad input/preflight, missing trace, upstream error,
  existing output file or dependency failure. No successful report is claimed.

Even a positive result is finite evidence, not universal minimum enforcement,
complete CPI/DEX math or deployed-source equivalence. Pancake/source proof,
remaining CPI semantics and real on-chain fee receipt are still outstanding.
This does not activate controlled swaps or fee execution. All audit runs return
exit code 2 on report creation, intentionally not an execution approval.

## Install and test (AlphaRadar root)

```powershell
python .\apply_dexsato_phase03e2d_minimum_boundary.py --check
python .\apply_dexsato_phase03e2d_minimum_boundary.py
python -m pytest -q
node --test tests/test_jupiter_fee_ui.js
```

Baseline is E.2C ac9b87c plus the E.2B.2 classifier. Installer preflights hashes,
preserves BOM/CRLF, backs up changed files and supports repeat installation.
If STOP appears, supply the named source; do not remove hash guards.

## Generate report

Use the previously configured HTTPS RPC/referral environment. Do not enable fees.
These parameters belong to the existing unsigned evidence only.

```powershell
python -m application.jupiter_minimum_boundary `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\minimum_boundary_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

Full preflight runs before four bounded parallel probes; allow RPC processing
time. No transactions are signed or broadcast and no tokens are spent by this
audit (RPC provider usage charges can still apply). Provider throttling is not
a reason to weaken checks. If slots differ, retain the inconclusive report;
a new run may use an unused output filename. Repeated instability requires a
frozen-bank replay environment, not repeated unbounded RPC retries.

Upload minimum_boundary_report.json and regression output for review. If old
evidence no longer simulates, capture fresh unsigned evidence with matching
parameters rather than weakening the original minimum or fee checks.

## Commit after validation

```powershell
git add application/jupiter_minimum_boundary.py tests/test_jupiter_minimum_boundary.py pytest.ini PHASE03E2D_MINIMUM_BOUNDARY.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: probe exact Jupiter minimum output boundaries"
```

Do not stage unrelated backups, .env or evidence files automatically.
