# Phase 03-E.4D — ClaimV2 Read-Only Simulation & Balance-Delta Semantics

## Purpose

This phase simulates the E.4C.2 unsigned ClaimV2 transaction against Solana
mainnet RPC without signing or submitting it. The simulation verifies exact raw
token deltas for the referral source, partner destination, and project-admin
destination.

## Required semantics

For gross claim amount `G` and partner share `8000` basis points:

```text
partner = floor(G × 8000 / 10000)
project_admin = G - partner
G = partner + project_admin
```

The project-admin amount receives the integer remainder. Floating-point and UI
token amounts are never used.

## Gates

- Pinned SDK capture status and hashes must match its compiled binding report.
- The transaction is decoded and rebound before RPC access.
- Compiled account order remains `PINNED_SDK_COMPILED_IDL`.
- Solana mainnet genesis hash is required.
- `simulateTransaction` uses `sigVerify=false` and
  `replaceRecentBlockhash=true`.
- All three token balances must match mint, owner, Token Program, and message
  account index.
- Referral decrease must equal partner plus project-admin increases.
- Simulation errors, missing balances, ambiguous indexes, or mismatched deltas
  fail closed.

## Safety state

A successful result is `CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED`.
It is not an on-chain receipt and leaves every execution approval false.
`DEXSATO_JUPITER_FEE_ENABLED` must remain `false`.

## Command

```powershell
python -m application.jupiter_claim_v2_simulation `
  --capture .\phase03e4c2_capture_001\unsigned_claim_v2_capture.json `
  --binding-report .\phase03e4c2_capture_001\claim_v2_compiled_binding_report.json `
  --auxiliary-report .\phase03e4c2_capture_001\claim_v2_auxiliary_report.json `
  --output-dir .\phase03e4d_simulation_001
```

The output file is:

```text
phase03e4d_simulation_001\claim_v2_simulation_report.json
```
