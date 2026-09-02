# Phase 03-F.4 — ClaimV2 Simulation Closure and One-Shot Gate Design

## Closure result

The fresh funded ClaimV2 read-only simulation is closed as:

`FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED`

Observed and bound evidence:

| Field | Value |
|---|---:|
| Simulation slot | `443680900` |
| Referral pre-balance | `5000` raw WSOL |
| Referral post-balance | `0` |
| Gross simulated claim | `5000` |
| Partner simulated delta | `4000` |
| Project/admin simulated delta | `1000` |
| Partner pre-balance source | `CREATED_ATA_IMPLICIT_ZERO` |
| Balance conservation | Verified |
| Transaction signed | No |
| Transaction submitted | No |
| Claim submitted | No |

The closure ID is derived deterministically from the capture and transaction
hashes, slots, mint, identities and exact balance deltas. Capture, compiled
binding, auxiliary audit and simulation must all refer to the same evidence.

## Gate design result

`CLAIM_V2_ONE_SHOT_GATE_DESIGN_REVIEW_REQUIRED`

This phase produces a non-operational specification only:

- Mode: `DESIGN_ONLY`
- Exact and maximum claim: `5000` raw WSOL
- Expected split: `4000` partner / `1000` project
- Proposed expiry: 300 seconds
- Explicit confirmation phrase required by any future implementation
- One attempt; only identical status polling may be replayed
- A finalized on-chain receipt would be mandatory

## Proposed state model

```text
DESIGN_ONLY
APPROVAL_PENDING
ARMED
BOUND
CONSUMED
FINALIZATION_PENDING
FINALIZED_VERIFIED | FAILED | EXPIRED
```

These are design labels, not implemented transitions. This phase does not
provide persistence, arming, wallet signing, transaction submission, RPC calls
or a live-claim endpoint.

## Security invariants

- Exact transaction and message hashes are immutable gate inputs.
- Mint, referral account and partner identity are bound by closure evidence.
- Any balance other than `5000 = 4000 + 1000` is rejected.
- Any signed, submitted, claimed or execution-ready evidence is rejected.
- Simulation evidence cannot be promoted into execution approval.
- No private key, keypair or secret material is accepted or stored.
- Production fee execution remains disabled.

## Operator commands

Create the closure record:

```powershell
python -m application.jupiter_claim_v2_simulation_closure `
  --capture .\phase03f3_capture_002\unsigned_claim_v2_capture.json `
  --binding-report .\phase03f3_capture_002\claim_v2_compiled_binding_report.json `
  --auxiliary-report .\phase03f3_capture_002\claim_v2_auxiliary_report.json `
  --simulation-report .\phase03f3_sim_002\claim_v2_simulation_report.json `
  --output .\phase03f4_simulation_closure.json
```

Generate the design-only gate report:

```powershell
python -m application.jupiter_claim_v2_gate_design `
  --closure .\phase03f4_simulation_closure.json `
  --output .\phase03f4_claim_gate_design.json
```

Exit code `2` means review evidence was written. It never means that execution
is ready.

## Decision

ClaimV2 simulation is verified and may inform a future controlled approval
phase. Live claim execution remains unapproved and unimplemented.
