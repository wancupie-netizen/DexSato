# 03-E.4A — ClaimV2 Source & Account Semantics Audit

## Outcome

This phase pins the official TeamRaccoons referral source at commit
`6500f64ff004e78faa15d66446e175ede625260d` and creates an offline, fail-closed
audit for the Ultra V2 `claimV2` instruction. It does not build, sign, simulate,
submit or claim a transaction.

The audit verifies the Anchor discriminator and exact `accountsStrict` order:

1. payer
2. project
3. admin
4. project admin token account
5. referral account
6. referral token account
7. partner
8. partner token account
9. mint
10. token program
11. system program
12. associated-token program

For Ultra V2, the referral token account is the canonical ATA whose authority
is the referral account. The partner and project-admin destinations are their
respective canonical ATAs for the same mint. Only the payer may sign the
normalized claim evidence, and all three token-flow accounts must be writable.

## Evidence boundary

Passing E.4A means only that supplied normalized account evidence matches the
pinned source contract. It does not prove that a transaction was produced by
the official SDK, that deployed bytecode matches the source, that a claim
simulation succeeded, or that the 80/20 split was paid on-chain.

Every successful report therefore keeps these fields false:

- `deployed_program_binary_verified`
- `claim_transaction_simulated`
- `claim_split_verified`
- `claim_submitted`
- `controlled_live_swap_approved`
- `production_fee_execution_enabled`
- `execution_ready`
- `fee_receipt_verified`

## Install and verify

```powershell
python .\apply_dexsato_phase03e4a_claim_v2_semantics.py --check
python .\apply_dexsato_phase03e4a_claim_v2_semantics.py
python -m pytest -q tests/test_jupiter_claim_v2_semantics.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Do not bypass a baseline mismatch. The installer does not read or write `.env`
and does not modify production swap, fee, wallet or execution code.

## Official source pins

- https://github.com/TeamRaccoons/referral/tree/6500f64ff004e78faa15d66446e175ede625260d
- `packages/sdk/src/referral.ts`
- `program/programs/referral/src/instructions/claim_v2.rs`
- https://dev.jup.ag/docs/tool-kits/referral-program
- https://dev.jup.ag/docs/ultra/add-fees-to-ultra

## Next approval boundary

E.4B may capture a fresh unsigned ClaimV2 transaction and bind its compiled
account metas to this contract. It must remain read-only and non-executable.
Only a later separately approved phase may simulate a claim. A controlled live
swap or claim requires explicit owner approval in a fresh step.

