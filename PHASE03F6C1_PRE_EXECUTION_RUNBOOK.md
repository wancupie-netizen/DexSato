# Phase 03-F.6C.1 — Pre-Execution Inspection & Operator Runbook

## Purpose

C.1 performs a read-only final inspection after F.6B approval and before F.6C
submission. It cannot submit, mutate or consume the persistent gate. Both live
approval and submission feature flags must be disabled while it runs.

## Verified evidence

- HTTPS RPC reports the Solana mainnet genesis hash.
- Gate and 90-second approval are still unexpired.
- Gate status is `LIVE_CLAIM_APPROVED` and its counts are exactly `1 / 1 / 0`
  for wallet review, approval and submission attempt.
- Operator-supplied approval ID matches the persistent record.
- Wallet-bound and approval-bound signed transaction hashes are identical.
- Claim contract remains `5000 / 4000 / 1000` raw units.
- Finalized referral WSOL token-account balance is exactly `5000`.
- Only `getGenesisHash` and `getTokenAccountBalance` RPC methods are used.

An amount above 5000 is rejected too: ClaimV2 must not be treated as a partial
claim operation. Any failed inspection leaves the gate unconsumed.

## Operator runbook

1. Start from a clean committed checkout and keep all execution flags false.
2. Construct and review the unsigned ClaimV2 transaction using the pinned SDK.
3. Sign it in the approved wallet without submitting it.
4. Bind that exact signed transaction through the F.5 wallet boundary.
5. Enable only the F.6B approval flag, approve once, then disable it immediately.
6. Confirm both approval and submission flags are false.
7. Run the C.1 read-only inspector with the exact signed file and approval ID.
8. Require `CLAIM_V2_PRE_EXECUTION_REVIEW_REQUIRED`, balance `5000`, mainnet true,
   and submission attempt zero.
9. Recheck the approval expiry. If expired, stop; never edit timestamps or reuse it.
10. Only then open the separately supervised F.6C submission window.

Do not paste RPC URLs, transaction bytes or approval IDs into Git, screenshots or
support logs. If any stage is ambiguous, do not create a second gate and do not
submit. Preserve the original gate for audit.

## Inspection command template

With all execution flags false:

```powershell
python -m application.jupiter_claim_v2_pre_execution `
  --gate $env:DEXSATO_JUPITER_CLAIM_GATE_PATH `
  --signed-transaction-file .\PRIVATE_PATH\signed_claim_v2.txt `
  --approval-id "ONE_TIME_APPROVAL_ID"
```

Exit code `2` means review is required; it is not execution authorization.
`execution_ready` remains false. Do not run the live submission command until the
inspection report and persistent gate have been reviewed together.
