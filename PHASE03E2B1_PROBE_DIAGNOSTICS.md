# 03-E.2B.1 — Filtered Minimum Probe Diagnostics

Diagnostic-only update on top of 48ed567 / the corrected E.2B installer.
No .env, fee policy, wallet UI, transaction mutation, RPC method or execution gate changes.

The existing audit command automatically includes negative_probe.diagnostics:

- Safe instruction index, numeric custom code, allowlisted built-in/transaction error.
- Filtered program invoke/success/failure records with original log line indices.
- Allowlisted Anchor error names and numeric error numbers; no free-form messages.
- Missing-log, omitted-line and bounded-event indicators.
- Maximum 128 saved events. Raw logs, error prose, RPC URL and probe transaction are not saved.

Existing pass criteria are unchanged. Missing logs now produce an explicit inconclusive
diagnostic instead of preventing the report. Diagnostic fields never authorize execution.
An unrecognized error is not converted into success. Execution remains disabled.

## Install and test

```powershell
python .\apply_dexsato_phase03e2b11_probe_diagnostics.py --check
python .\apply_dexsato_phase03e2b11_probe_diagnostics.py
python -m pytest tests/test_jupiter_pool_validation.py -v
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

The installer checks the exact previously delivered file contents (BOM/CRLF normalized),
backs up modified files and stops before writing if any baseline differs. It changes
only the pool-validation module, its tests and this new document. Do not bypass a STOP.

Local checks: 17 pure tests passed; one solders vector skipped (dependency unavailable).
Two byte-mutation checks passed with dependency-isolated exact production parsers.
Full application/SDK regression and live RPC execution have not been run locally.

## Regenerate report — do not overwrite the original

With the existing process RPC/referral configuration and fees disabled, for the SAME
previously captured 0.001 SOL, 50 bps, minimum 102326 raw USDC unsigned evidence:

```powershell
python -m application.jupiter_binding_audit `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\pool_minimum_diagnostic_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

Use the actual evidence path if different. Never reuse these example amounts for a
different order without checking its fields. Old orders can fail as market state moves;
if the baseline fails, obtain fresh unsigned evidence and use its reviewed parameters.
The CLI does not automatically load .env. No new API key is required by this patch.

Review output uses exit code 2 and BINDING_REVIEW_REQUIRED deliberately. This is not
transaction approval. Upload pool_minimum_diagnostic_report.json for analysis. If no
report is generated, share the fixed error code printed by the command, not secrets.

## Commit after regression passes

```powershell
git add application/jupiter_pool_validation.py tests/test_jupiter_pool_validation.py PHASE03E2B1_PROBE_DIAGNOSTICS.md
git diff --cached --check
git commit -m "test: retain filtered Jupiter minimum probe diagnostics"
```
