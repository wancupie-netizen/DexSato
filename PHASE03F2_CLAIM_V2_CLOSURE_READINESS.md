# Phase 03-F.2 — ClaimV2 Closure Audit and Monetization Readiness

## Decision

`ACCRUAL_READY_CLAIM_NOT_READY`

DexSato has finalized on-chain evidence that a controlled fee-bearing swap
credited exactly `5000` raw WSOL to the verified referral token account. This
closes the fee-accrual question. It does not approve ClaimV2 execution.

## Evidence boundary

| Control | Result |
|---|---|
| Fee-bearing swap receipt | `FINALIZED_VERIFIED` |
| Referral accrual | `5000` raw WSOL |
| ClaimV2 source semantics | Pinned and verified read-only |
| SDK | `@jup-ag/referral-sdk` `0.3.0` |
| Source commit | `6500f64ff004e78faa15d66446e175ede625260d` |
| Compiled account order | `PINNED_SDK_COMPILED_IDL` |
| Auxiliary instructions | Allowlist-reviewed |
| Successful balance-delta simulation | Not yet verified |
| Live ClaimV2 approval | Not granted |
| Claim execution readiness | `false` |

The prior simulation rejection `REFERRAL_SOURCE_DELTA_INVALID` remains a real
blocker. A finalized swap receipt proves accrual but cannot substitute for a
fresh read-only ClaimV2 simulation against the funded referral account.

## Readiness states

`ACCRUAL_READY_CLAIM_NOT_READY` means monetization accrual is proven while the
claim path remains disabled.

`ACCRUAL_AND_READ_ONLY_CLAIM_SIMULATION_VERIFIED` may be emitted after exact
80/20 simulated balance deltas and conservation pass. Even this state keeps
`claim_execution_ready=false`; a separate one-shot live-claim approval gate is
still mandatory.

## Fail-closed invariants

- The evaluator performs no RPC, signing, submission, swap or claim.
- The finalized referral delta must equal the recorded `5000` raw WSOL.
- SDK version, source commit and compiled account order must match the pin.
- Capture and auxiliary message/transaction hashes must match.
- Dependency tooling remains isolated and is not approved for production.
- Evidence carrying any execution-ready or submitted claim flag is rejected.
- Simulation arithmetic must conserve gross = partner + project.
- A successful simulation never becomes live-claim approval.

## Operator usage

Create a bounded normalized JSON document containing these top-level objects:

```text
fee_receipt
claim_semantics
unsigned_capture
auxiliary_audit
claim_simulation
dependency_attestation
```

Then run:

```powershell
python -m application.jupiter_claim_v2_readiness `
  --evidence .\claim_v2_closure_evidence.json `
  --output .\claim_v2_readiness_report.json
```

Exit code `2` means a review report was generated. It is deliberately not an
execution-ready signal. Exit code `1` means evidence was rejected or output was
unavailable.

## Conditions before a future live claim review

1. Capture a fresh unsigned ClaimV2 transaction after referral funding.
2. Re-bind all compiled accounts and auxiliary instructions.
3. Run read-only mainnet simulation with exact source and destination balances.
4. Verify the 80/20 split and exact balance conservation.
5. Reassess dependency advisories; do not run an automatic dependency fix.
6. Design a separate expiring, one-shot claim approval gate.
7. Require wallet review and retain finalized on-chain claim receipt evidence.

Claim execution and production fee execution remain disabled by this phase.
