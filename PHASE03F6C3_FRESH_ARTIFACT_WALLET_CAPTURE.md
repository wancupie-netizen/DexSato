# Phase 03-F.6C.3 — Fresh Artifact and Wallet-Signed Evidence Capture

## Security decision

This phase is **capture-only**. It reconstructs a fresh unsigned ClaimV2 transaction,
verifies a funded read-only simulation, closes that evidence, and creates an unapproved
one-shot gate. A separate command verifies wallet-signed bytes and stores only their
SHA-256 digest in the gate. It never approves or submits the claim.

The intended claim remains exactly 5,000 raw WSOL units: 4,000 to the partner and
1,000 to the project administrator. Production fees, live claim approval, and claim
submission must remain disabled throughout this phase.

## Required environment

```powershell
$env:DEXSATO_JUPITER_FEE_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED = "false"
$env:DEXSATO_JUPITER_CLAIM_GATE_ENABLED = "true"
$env:SOLANA_RPC_URL = "https://YOUR_PRIVATE_MAINNET_RPC"
```

## 1. Generate fresh artifacts

Use new paths. The command refuses an existing output directory or gate file.

```powershell
python -m application.jupiter_claim_v2_artifact_workflow generate `
  --identity .\claim_v2_identity.json `
  --output-dir .\phase03f6c3_capture_001 `
  --gate .\runtime\claim-v2-gate-f6c3-001.json `
  --confirm "I APPROVE ONE CONTROLLED CLAIM V2"
```

Expected status: `FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED`, exit code `2`.
At this point the gate is `ARMED`, with zero approvals and zero submission attempts.

## 2. Wallet signing boundary

Import the unsigned transaction into the trusted wallet workflow and sign the exact
message. Do not broadcast it. Export the signed serialized transaction to a temporary
file, then run:

```powershell
python -m application.jupiter_claim_v2_artifact_workflow bind `
  --gate .\runtime\claim-v2-gate-f6c3-001.json `
  --closure .\phase03f6c3_capture_001\claim_v2_simulation_closure.json `
  --capture .\phase03f6c3_capture_001\unsigned_claim_v2_capture.json `
  --signed-transaction-file .\claim_v2_signed_not_submitted.bin `
  --wallet J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs `
  --output .\phase03f6c3_capture_001\wallet_signed_evidence.json
```

Expected status: `CLAIM_V2_WALLET_SIGNED_EVIDENCE_CAPTURED_NO_SUBMISSION`, exit code
`2`. The signed bytes are not copied into any report or gate; only their digest is
retained. Securely remove the temporary signed file after independently recording its
hash, subject to the operator's evidence-retention policy.

## Stop conditions

Stop if any status differs, a path already exists, the capture exceeds the freshness
window, the wallet/message/account identity changes, or any safety flag is enabled.
Do not enable live approval or submission in this phase. F.6C.4 requires a separate,
explicit decision and a new time-bounded approval.
