# Phase 03-F.6B — Explicit Live Claim Approval & Gate Consumption

## Security decision

F.6B adds the missing explicit approval transition but does not submit a
transaction. Approval and submission are deliberately separate operating
windows. The approval transition refuses to run while claim submission is
enabled.

## Approval requirements

- `DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED=true` only for the approval step.
- `DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED=false` during that step.
- `DEXSATO_JUPITER_FEE_ENABLED=false` remains mandatory.
- Exact confirmation: `I APPROVE ONE LIVE CLAIM V2`.
- Exact persistent gate ID and wallet-signed transaction SHA-256.
- Gate status must be `WALLET_APPROVAL_BOUND`, unexpired and unused.
- Wallet review count must be one; approval and submission counts must be zero.

The transition creates a random approval ID, records one approval, and expires
it after 90 seconds or at the original gate expiry, whichever occurs first. It
stores no transaction bytes, signature material, key or provider response.

## Consumption contract

The F.6A submission harness now requires the exact approval ID. Reservation is
atomic and precedes the provider call. On reservation it immediately clears
`submission_permitted`, records `approval_consumed_at`, and increments the
submission attempt count to one. Wrong IDs, expiry, replay and modified signed
transaction hashes fail without consuming an attempt.

The audit recognizes only these states:

| State | Approval | Attempt | Submission permitted |
|---|---:|---:|---:|
| `LIVE_CLAIM_APPROVED` | 1 | 0 | true |
| `SUBMISSION_PENDING` | 1 | 1 | false |
| `FINALIZATION_PENDING` | 1 | 1 | false |
| `FAILED` | 1 | 1 | false |
| `FINALIZED_VERIFIED` | 1 | 1 | false |

All reports retain `execution_ready=false`. F.6B does not turn on either feature
flag and does not authorize automatic or repeated ClaimV2 execution.

## Safe operating sequence

1. Keep both approval and submission flags false by default.
2. Enable only the approval flag, execute the explicit transition, then disable it.
3. Inspect the persistent record and copy the one-time approval ID.
4. A separately controlled submission window may enable only the submission flag.
5. Submit the exact wallet-signed bytes with that approval ID once.
6. Disable submission immediately and verify the finalized receipt.
