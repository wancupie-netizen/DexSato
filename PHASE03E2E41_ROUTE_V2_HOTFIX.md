# 03-E.2E.4.1 — RouteV2 Decoder & Identity Binding

## Outcome

The read-only E2E4 evidence path now recognizes Jupiter's `routeV2`
instruction discriminator `bb64facc31c4af14` as a separate variant from
`sharedAccountsRouteV2`. The captured message
`20f61c6b84131b1167837eb7f6d48803c495ddcbc2c6646414c3717f1e2e13f8`
can therefore proceed to identity review without treating the newer route-tail
enum as understood.

This is audit tooling only. It does not change the production swap endpoint,
fee policy, fee formula, wallet flow, transaction allow-list or execution gate.
`execution_ready` and `fee_receipt_verified` remain false.

## Evidence boundary

The hotfix decodes only the bounded RouteV2 fixed header:

- `inAmount`
- `quotedOutAmount`
- `slippageBps`
- `platformFeeBps`
- `positiveSlippageBps`
- `routePlanCount`

The route-plan tail is retained only through a SHA-256 digest. It is not decoded
because the captured first enum ordinal is newer than the pinned legacy swap
schema. Reports therefore state `route_plan_decoded: false` and
`schema_authority: SECONDARY_SCHEMA_HEADER_ONLY`.

RouteV2 identity binding uses only fixed positions 0–6 and 9: wallet authority,
source/destination token accounts, source/destination mints, both token
programs and the Jupiter program. Position 7 is intentionally named
`unverifiedFixedAccount`; its semantic role is not used as evidence. Position 8
is also not used by identity binding. No fee-account role is inferred.

The Anchor discriminator is deterministic (`sha256("global:route_v2")[:8]`).
Jupiter's official swap-instructions interface remains the authoritative source
for transaction construction; the detailed fixed-header/account schema is
cross-checked against secondary V6 schema mirrors and the captured bytes. This
does not constitute deployed-program verification.

References:

- https://dev.jup.ag/docs/api-reference/swap/v1/swap-instructions
- https://dev.jup.ag/docs/swap/v1/common-errors
- https://github.com/solana-foundation/surfpool/blob/main/crates/core/src/scenarios/protocols/jupiter/v6/idl.json

## Install and verify

E2E4 must already be installed. On baseline mismatch, stop and review; do not
bypass the guard.

```powershell
python .\apply_dexsato_phase03e2e41_route_v2.py --check
python .\apply_dexsato_phase03e2e41_route_v2.py
python -m pytest -q tests/test_jupiter_route_v2_hotfix.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

The installer changes seven audit/test/documentation targets plus `pytest.ini`.
It never reads or writes `.env` and never alters production UI or service code.

## Re-run the captured decoder

Use a new output filename because evidence tools do not overwrite reports:

```powershell
python -m application.jupiter_lookup_decoder `
  --evidence ".\phase03e2e4_capture_001\unsigned_evidence.json" `
  --output ".\phase03e2e4_capture_001\decoder_route_v2_resolved.json"
```

Expected state is `RESOLVED_REVIEW_REQUIRED`, not execution approval. Confirm
that exactly one Jupiter instruction has:

- `name: routeV2`
- `route_plan_decoded: false`
- `fee_account_role_verified: false`
- the expected message hash

Generate the E2E4 intent only after independently checking the wallet and mint
addresses. For `routeV2`, source and destination token accounts are fixed
instruction positions 1 and 2. Do not reuse the older shared-route positions 2
and 5.

Then run the E2E4 live read-only snapshot with a new output directory and upload
`live_identity_report.json` for review. A successful identity snapshot remains
`LIVE_IDENTITY_REVIEW_REQUIRED`; it does not authorize signing or submission.

## Regression coverage

Tests cover the captured header, exact discriminator, amount/BPS bounds,
route-plan count bounds, non-decoding of the new route tail, explicit
non-reliance on the unverified fixed account, RouteV2 identity positions and
continued support for `sharedAccountsRouteV2`.

## Commit boundary

Do not commit until the full Python and JavaScript regressions pass and the new
live report is reviewed. Stage only E2E4/E2E4.1 files; never stage evidence,
snapshots, `.env`, backups or unrelated files.
