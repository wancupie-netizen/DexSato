# Phase 03-F.6C.2 — Fresh Reconstruction, Wallet Signing & Approval

## Security decision

C.2 forbids reuse of the transaction, closure or gate from an earlier attempt.
The pinned SDK must construct a fresh unsigned ClaimV2 transaction, that exact
transaction must pass a fresh read-only simulation and closure, and a new gate
must bind the resulting message and transaction hashes.

C.2 can bind a wallet signature and create the 90-second F.6B approval. It has no
submission provider method and never calls `sendTransaction`.

## Required sequence

1. Keep fee execution, live approval and claim submission disabled.
2. Run the pinned SDK capture into a new, previously nonexistent output folder.
3. Re-run the auxiliary audit and funded read-only simulation for that capture.
4. Produce a new simulation closure containing the fresh capture hashes.
5. Arm a new F.5 gate from that exact closure.
6. Review and sign the unsigned transaction in the partner wallet without sending.
7. Enable only `DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED`.
8. Run the C.2 coordinator with the closure, capture, gate and signed bytes.
9. The coordinator verifies Solana mainnet and requires capture slot age 0–32.
10. It binds the unchanged signed message, then records one approval for 90 seconds.
11. Disable the live-approval flag immediately.
12. Run C.1 while both approval and submission flags are disabled.

If any step expires, fails or becomes ambiguous, stop. Reconstruct from step 2
with a new output folder; never edit a timestamp, hash, counter or gate status.

## C.2 coordinator template

```powershell
$env:DEXSATO_JUPITER_FEE_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED = "true"

python -m application.jupiter_claim_v2_fresh_approval `
  --gate ".\PRIVATE_RUNTIME\fresh-claim-gate.json" `
  --closure ".\PRIVATE_RUNTIME\fresh-simulation-closure.json" `
  --capture ".\PRIVATE_RUNTIME\unsigned_claim_v2_capture.json" `
  --signed-transaction-file ".\PRIVATE_RUNTIME\signed_claim_v2.txt" `
  --wallet "PARTNER_PUBLIC_ADDRESS" `
  --confirm "I APPROVE ONE LIVE CLAIM V2"

$env:DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED = "false"
```

Exit code `2` means the wallet signature and time-bounded approval require final
review. It does not mean that a claim was submitted or that execution is ready.

## Freshness boundary

The capture RPC slot must not be in the future and may be at most 32 finalized
slots behind the inspection RPC. This deliberately narrow window is separate
from Solana's broader blockhash lifetime. Passing it is necessary but never a
standalone submission approval.
