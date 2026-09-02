# Phase 03-F.6A — Disabled Claim Submission Harness & Finalized Receipt Verifier

## Decision

The ClaimV2 submission path remains disabled by default. F.6A provides the
one-attempt transport and finalized-receipt verification contracts, but it does
not grant live-claim approval. A gate produced by F.5 therefore cannot submit:
both `submission_permitted` and `live_claim_approved` must be supplied by a
separate, future approval boundary.

## Submission contract

- `DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED` defaults to `false`.
- `DEXSATO_JUPITER_FEE_ENABLED` must remain `false`.
- The exact phrase `I APPROVE ONE CLAIM V2 SUBMISSION` is required.
- Only the wallet-signed bytes whose SHA-256 digest is bound to the gate are
  accepted.
- The persistent gate reserves its only attempt before the RPC call.
- RPC must use HTTPS; redirects are disabled; `skipPreflight` is false and
  `maxRetries` is zero.
- Provider prose is not persisted. Only fixed failure codes are stored.
- The harness never signs, stores a private key, or retries a submission.

## Receipt contract

Receipt verification is read-only and requires a finalized successful Solana
transaction. It binds the capture hashes and ClaimV2 identities to the consumed
gate, locates the referral, partner, and project-admin token accounts, and
requires the exact funded evidence split:

| Account | Required finalized delta (raw WSOL units) |
|---|---:|
| Referral source | -5000 |
| Partner destination | +4000 |
| Project-admin destination | +1000 |

A newly created destination ATA may have an implicit zero pre-balance. Missing,
ambiguous, wrong-owner, wrong-mint, failed, or non-finalized evidence is rejected.
Successful verification closes the gate as `FINALIZED_VERIFIED`, while
`execution_ready` and `claim_execution_ready` remain false.

## Operator state after installation

```dotenv
DEXSATO_JUPITER_CLAIM_GATE_ENABLED=false
DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED=false
DEXSATO_JUPITER_FEE_ENABLED=false
```

Do not enable claim submission in F.6A. The next phase must implement and audit
the separate live-approval transition before any controlled on-chain claim.
