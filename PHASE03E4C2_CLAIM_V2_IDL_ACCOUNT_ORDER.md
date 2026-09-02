# Phase 03-E.4C.2 — ClaimV2 IDL Account-Order Reconciliation

## Outcome

DexSato now validates ClaimV2 accounts using the compiled account order from
the pinned `@jup-ag/referral-sdk` version `0.3.0` artifact:

| Position | Role | Required address |
|---:|---|---|
| 9 | `systemProgram` | `11111111111111111111111111111111` |
| 10 | `tokenProgram` | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` |
| 11 | `associatedTokenProgram` | `ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL` |

The previous audit inferred the final account order from an SDK object literal.
Anchor compiles account positions from its IDL, so object-property order is not
the correct authority for transaction account indexes.

## Evidence

The read-only pinned-SDK capture produced exactly 12 ClaimV2 accounts. Ten
positions matched the existing identity contract. Positions 9 and 10 contained
the correct immutable program addresses in the reverse order from the old role
map. Position 11 matched the Associated Token Program.

This result identifies a validator schema-order defect. It does not indicate a
malicious replacement address, identity mismatch, or permission expansion.

## Changes

- Position 9 is mapped to `systemProgram`.
- Position 10 is mapped to `tokenProgram`.
- The report records SDK version `0.3.0` and authority
  `PINNED_SDK_COMPILED_IDL`.
- A regression test rejects the obsolete source-literal tail order.
- Existing exact-address, signer, writable, mint, project, and ATA checks remain.

## Safety state

This reconciliation does not submit or simulate a claim and does not approve a
controlled live swap. The following values remain false:

- `claim_submitted`
- `controlled_live_swap_approved`
- `production_fee_execution_enabled`
- `execution_ready`
- `fee_receipt_verified`

Keep `DEXSATO_JUPITER_FEE_ENABLED=false` until later approval gates are complete.

## Verification

Run:

```powershell
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Then repeat the isolated read-only SDK capture using the same reviewed identity.
The expected next status is `PINNED_SDK_CLAIM_V2_REVIEW_REQUIRED`; it remains a
review result and is not permission to submit a claim or execute a live swap.
