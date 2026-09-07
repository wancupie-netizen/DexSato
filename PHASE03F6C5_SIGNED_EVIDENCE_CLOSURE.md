# Phase 03-F.6C.5 — Signed-Evidence Closure and Fresh Reconstruction Boundary

## Decision

The independently verified wallet-signed artifact is accepted as hash-only audit
evidence. It is not accepted as live-execution material because its RPC freshness
was intentionally not asserted and its recent blockhash is time-bound.

## Closure contract

The closure binds the source gate, simulation closure, message hash, signed
transaction hash, mint, referral account, operator identity and exact 5,000 raw
claim split. It accepts only a `WALLET_APPROVAL_BOUND` gate with one wallet review,
zero approvals, zero submission attempts, and every execution flag disabled.

The closure is written exclusively, receives a deterministic closure identifier,
does not persist transaction bytes, and explicitly retires the source gate and
signed transaction from reuse.

## Fresh reconstruction boundary

Any later live workflow must independently obtain and verify:

- current Solana mainnet identity and funded referral balance;
- a new recent blockhash;
- a fresh unsigned SDK capture and simulation closure;
- a new one-shot gate and wallet signature.

This phase does not construct or sign that transaction. It does not enable live
approval, submission, production fees, automatic retries, or execution readiness.

## Operator result

Successful commands return review-required status with exit code `2`. Runtime gate,
capture, signed binary, evidence, closure, and boundary reports remain operational
artifacts and must not be committed.
