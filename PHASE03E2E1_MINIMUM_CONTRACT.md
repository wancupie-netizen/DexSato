# 03-E.2E.1 — Minimum Contract & Mismatch Regression

## Scope

Offline harness only. No production formula, quote/swap service, frontend,
fee policy, environment or fee-execution gate changes.

The supplied ZIP contains all 16 requested files, flattened by Compress-Archive.
Quote, swap and frontend match the earlier audited copies after newline
normalization. No Git HEAD output was supplied, so the installer anchors to
the actual uploaded contents, not an assumed commit. Its BASELINE mapping
records normalized SHA-256 hashes for all 16 files.

## Install

Place `apply_dexsato_phase03e2e1_minimum_contract.py` in the project root.

```powershell
python .\apply_dexsato_phase03e2e1_minimum_contract.py --check
python .\apply_dexsato_phase03e2e1_minimum_contract.py
python -m pytest -q tests/test_jupiter_minimum_contract.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
git diff --check
git diff --stat
```

Installer accepts BOM/CRLF differences, checks every baseline before writing,
refuses conflicting new files, and backs up existing targets. Re-running after
installation is a no-op. Source mismatch means STOP: provide updated baseline;
do not bypass guards. Backups are in `phase03e2e1_backups/<timestamp>/`.

Changes are limited to:

- New `application/jupiter_minimum_contract.py` (offline only).
- New `tests/test_jupiter_minimum_contract.py`.
- New this document.
- Registration of the new test file in `pytest.ini`.

## Contract boundaries

`audit_minimum_contract(order, resolved, expected_message_sha256)` compares a
single prepared-order response with one supplied resolved V2 report. It checks
input/output raw amounts, slippage, decoded fields against the fixed instruction
header bytes, supported discriminator/name/program, and supplied message hash.
It requires strict canonical u64 decimal strings and integer slippage bps.

The report separates `provider_minimum_raw`, `floor_candidate_raw`,
`ceil_candidate_raw`, and `enforced_minimum_raw` (always null). Matching floor,
ceil, both, or neither is classified explicitly. Neither is review-required,
not silently corrected or assumed invalid under every possible program.

IMPORTANT: this is a HEADER CONSISTENCY comparator, not transaction validation.
It does not authenticate supplied JSON/hash, reconstruct the transaction,
resolve ALTs, decode the entire route tail, bind wallet/mints/vaults, prove
program semantics, or verify output/fees. Consistently forged JSON can pass
header checks. All results remain `execution_ready: false`,
`transaction_binding_verified: false`, `enforcement_verified: false`,
`fee_receipt_verified: false` and `production_formula_changed: false`.
Do not import this as an execution authorizer.

`format_raw_exact` is a proposed audit-only formatter with exact integer-string
decimal placement; it is NOT connected to the production browser. Existing UI
rounding and zero-slippage display findings are not fixed by this patch.

Malformed evidence raises `MinimumContractRejected` with a bounded reason code.
No network, signature, submission, environment access or live simulation exists
in this module. There is no command here that signs a trade.

## Verification

47 new tests passed locally with the uploaded resolved fixture. The fixture
test constructs a synthetic order response explicitly; it does not claim to
have the original captured provider response. Tests cover mismatching amounts,
slippage, decoded headers, program/variant, duplicate routes, message hash,
missing/bad raw values, u64 boundaries, decimals beyond eight, zero slippage,
unchanged input objects, and fresh orders differing legitimately from old quotes.

Full project regression must be run on the user's complete checkout. The
uploaded subset is not a complete runnable application. No full-suite total
or new on-chain verification is claimed by this package.

## Commit only after tests pass

```powershell
git add application/jupiter_minimum_contract.py tests/test_jupiter_minimum_contract.py pytest.ini PHASE03E2E1_MINIMUM_CONTRACT.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: separate minimum contract evidence and mismatch checks"
```

Do not stage backups, credentials, or unrelated untracked files.

## Next approval gate

This completes the offline comparison/regression step, not production minimum
alignment. Before production changes: authenticate the actual unsigned message
and bind its exact prepared-order disclosure; establish minimum semantics for
the supported instruction/deployment; then approve exact UI and production
validation changes separately. Fee execution remains disabled.
