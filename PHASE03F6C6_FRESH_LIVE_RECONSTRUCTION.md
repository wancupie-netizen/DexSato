# Phase 03-F.6C.6 — Fresh Live Claim Reconstruction and Approval Preparation

## Purpose

F.6C.6 turns the F.6C.5 closure into an enforceable reconstruction workflow. It
first validates the exact immutable closure and boundary report. Its preparation
mode may then generate a new unsigned SDK capture, funded simulation closure and
unapproved one-shot gate, but it cannot sign, approve or submit the transaction.

## Anti-reuse contract

Preparation rejects reuse of the retired gate ID, prior message hash or prior
simulation closure. The new capture, simulation and gate must bind to one another,
retain the exact 5,000 raw claim with the 4,000/1,000 split, and report zero wallet
reviews, approvals and submission attempts.

The coordinator also produces an exact `claim_v2_gate_review.json` copy only after
the new gate passes all checks. This removes the manual review-copy omission seen
during the earlier operator rehearsal.

## Safety boundary

- fee execution remains disabled;
- live approval remains disabled;
- claim submission remains disabled;
- the transaction remains unsigned;
- no signed bytes, approval ID or provider submission is accepted;
- every output remains review-required and `execution_ready=false`.

`prepare` is intentionally reserved for a just-in-time operator window because the
Solana blockhash and one-shot gate expire. Tests and the read-only `plan` command
must pass before any operational preparation is attempted.
