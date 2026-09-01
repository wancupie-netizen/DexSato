# 03-E.4B — Unsigned ClaimV2 Capture & Compiled Account Binding

## Outcome

E.4B accepts an externally exported, unsigned Solana transaction and binds the
compiled ClaimV2 instruction to the exact 12-role contract audited in E.4A.
It performs no network request and cannot build, sign, simulate, submit or
claim a transaction.

The capture requires exactly one default signature slot, exactly one ClaimV2
instruction, a canonical transaction encoding, a bounded transaction size and
a supplied lookup-table snapshot. Every compiled account index is resolved to
its public address, signer flag and writable flag before E.4A semantics are
applied.

## E.4A compatibility correction

The permissionless ClaimV2 payer may legitimately be the referral partner.
E.4B therefore corrects the earlier over-strict alias check to allow
`payer == partner`. Project, admin, referral account, partner and mint must
remain distinct. No signer or destination-account control is weakened.

## Evidence boundary

A successful result is:

`UNSIGNED_CLAIM_V2_ACCOUNT_BINDING_REVIEW_REQUIRED`

It proves only byte-to-account binding for the supplied unsigned transaction.
ALT snapshot authenticity/freshness, auxiliary instruction semantics, deployed
program bytecode, simulation, 80/20 balance deltas and an on-chain receipt are
not proved. `execution_ready`, `fee_receipt_verified`, `claim_split_verified`
and production fee execution remain false.

## Install and verify

```powershell
python .\apply_dexsato_phase03e4b_unsigned_claim_binding.py --check
python .\apply_dexsato_phase03e4b_unsigned_claim_binding.py
python -m pytest -q tests/test_jupiter_claim_v2_semantics.py tests/test_jupiter_claim_v2_capture.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Do not bypass a baseline mismatch. The installer does not read or write `.env`
and does not modify the production swap, fee, wallet or execution path.

## Capture input contract

The operator-supplied JSON contains only:

- `transaction`: canonical base64 unsigned versioned transaction
- `identity`: independently reviewed payer/project/admin/referral/partner/mint
- `lookup_snapshot`: one slot plus raw ALT accounts, if the message uses ALTs

Run without overwriting an existing report:

```powershell
python -m application.jupiter_claim_v2_capture `
  --input .\claim_v2_unsigned_input.json `
  --output .\claim_v2_compiled_binding_report.json
```

This phase deliberately does not supply a ClaimV2 transaction builder. A later
phase may add a pinned official-SDK, capture-only workflow after separate
review. No live claim or controlled swap is approved here.

