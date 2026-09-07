# Phase 03-F.6C.4 — Operator Wallet-Signed Artifact and Independent Hash Verification

## Decision boundary

This phase proves that the wallet signed the exact fresh ClaimV2 message reviewed in
F.6C.3. It does not approve, broadcast, submit, or finalize a claim. The evidence file
contains hashes and public metadata only; serialized signed transaction bytes are never
copied into the report or gate.

Two checks must agree:

1. The existing ClaimV2 wallet-boundary decoder verifies the signer, account identity,
   message bytes, required signatures, closure, freshness, and gate binding.
2. A separate minimal Solana wire parser locates the message after the compact signature
   vector and independently calculates both message and full-transaction SHA-256 hashes.

## Safety configuration

Keep these values in the current PowerShell process:

```powershell
$env:DEXSATO_JUPITER_FEE_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_GATE_ENABLED = "true"
$env:SOLANA_RPC_URL = "https://YOUR_PRIVATE_MAINNET_RPC"
```

Never provide a seed phrase or private key to DexSato, Python, Node, the terminal, or
the evidence directory.

## Procedure

First run the F.6C.3 `generate` command using new capture and gate paths. Sign the exact
unsigned transaction in the trusted operator wallet, with broadcast disabled, and
export its serialized bytes temporarily.

Before binding, confirm that the gate is still `ARMED`, has zero approvals and zero
submission attempts. Then run:

```powershell
python -m application.jupiter_claim_v2_signed_evidence `
  --gate .\runtime\claim-v2-gate-f6c4-001.json `
  --closure .\phase03f6c4_capture_001\claim_v2_simulation_closure.json `
  --capture .\phase03f6c4_capture_001\unsigned_claim_v2_capture.json `
  --signed-transaction-file .\claim_v2_signed_not_submitted.bin `
  --wallet J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs `
  --output .\phase03f6c4_capture_001\wallet_signed_hash_evidence.json
```

The expected status is:

```text
CLAIM_V2_WALLET_SIGNED_HASH_INDEPENDENTLY_VERIFIED
```

Exit code `2` means review is required, not execution readiness. Verify in the report:

```text
independent_hash_verified = true
wallet_signature_verified = true
signed_transaction_persisted = false
gate_status = WALLET_APPROVAL_BOUND
live_claim_approved = false
approval_count = 0
submission_attempt_count = 0
transaction_submitted = false
execution_ready = false
```

Delete or move the temporary signed transaction into an approved offline evidence vault
after separately recording its SHA-256. Do not add it, the runtime gate, RPC URL, or any
capture directory to Git.

## Stop conditions

Stop on any mismatch, expired/stale capture, existing output path, changed message,
unexpected signer, approval count, or submission attempt. Do not retry against the same
gate after an uncertain mutation. F.6C.4 closes only the signing-and-hash boundary; a
future live claim still requires a new explicit operator decision.
