# 03-E.2E.4.2 — In-Transaction ATA Creation & Lifecycle Binding

## Finding resolved

The E2E4 live report at finalized slot `443351004` could not find the WSOL and
USDC token accounts. This was an expected pre-transaction state, not an RPC or
mint mismatch. Both addresses reproduce exactly as canonical associated token
accounts for the approved wallet and their respective mints.

The bound unsigned message contains this lifecycle:

1. `CreateIdempotent` canonical WSOL ATA.
2. System transfer of exactly `1,000,000` lamports from the sole wallet signer.
3. SPL Token `SyncNative` on that WSOL ATA.
4. `CreateIdempotent` canonical USDC ATA.
5. One Jupiter `routeV2` instruction using those accounts and mints.
6. SPL Token `CloseAccount` for WSOL, returning lamports to the wallet.

Because the unsigned transaction was never submitted, neither account had to
exist at the snapshot. The WSOL ATA is also designed to be closed in the same
transaction.

## Security contract

Missing token accounts are accepted for identity review only when all checks
below pass against the exact message hash:

- addresses equal the canonical ATA PDA derived from wallet, Tokenkeg and mint;
- both ATA instructions are exactly `CreateIdempotent` with six reviewed roles;
- wallet is payer, ATA owner and sole signer;
- System and SPL Token program IDs are exact;
- WSOL funding equals the order/header input amount;
- create → transfer → sync → route → close ordering is exact;
- destination ATA is created before the route;
- source close destination and authority are the wallet;
- each lifecycle instruction occurs exactly once;
- no other instruction may reference either missing ATA except the reviewed
  lifecycle and Jupiter route.

Non-token accounts missing from the same snapshot remain an immediate failure.
Existing token accounts continue through the original raw account owner, mint,
authority, state and option checks.

## Non-goals

This is read-only audit tooling. It does not sign, simulate, submit, create or
close an account. It does not change production endpoints, UI, fee policy,
minimum formula, program allow-list or wallet permissions. It does not prove
route-tail semantics, inner CPI effects, fee receipt or snapshot authenticity.

All successful reports retain:

- `status: LIVE_IDENTITY_REVIEW_REQUIRED`
- `execution_ready: false`
- `fee_receipt_verified: false`
- `transaction_submitted: false`
- `production_formula_changed: false`

## Install and regression

E2E4.1 must already be installed. Stop on any baseline mismatch.

```powershell
python .\apply_dexsato_phase03e2e42_ata_lifecycle.py --check
python .\apply_dexsato_phase03e2e42_ata_lifecycle.py
python -m pytest -q tests/test_jupiter_ata_lifecycle_binding.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

## Repeat the live read-only snapshot

Reuse the same evidence and independently reviewed intent. Every run needs a
new output directory:

```powershell
python -m application.jupiter_live_identity_snapshot `
  --evidence ".\phase03e2e4_capture_001\unsigned_evidence.json" `
  --intent ".\phase03e2e4_capture_001\live_identity_intent.json" `
  --output-dir ".\phase03e2e4_live_005"
```

Expected console result:

```json
{"status":"LIVE_IDENTITY_REVIEW_REQUIRED","execution_ready":false,"fee_receipt_verified":false}
```

Review and upload `phase03e2e4_live_005/live_identity_report.json`. The report
must contain `ata_lifecycle.canonical_ata_derivation_verified: true`, exact
instruction indices, `wsol_transfer_lamports: 1000000`, and
`lifecycle_instruction_order_verified: true`.

## Regression coverage

Deterministic tests cover successful lifecycle and live orchestration plus
failures for wrong ATA derivation, transfer amount, ordering, duplicate create,
missing close and unsupported missing-account references. Existing-account,
RouteV2, byte-hash and identity regression suites remain in scope.

Do not commit until full Python and JavaScript tests pass and the new live
report is reviewed. Never stage evidence, snapshots, `.env`, backup directories
or unrelated files.
