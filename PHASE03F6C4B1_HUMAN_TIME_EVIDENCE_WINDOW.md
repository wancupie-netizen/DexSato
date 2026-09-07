# Phase 03-F.6C.4B.1 — Human-Time Sign-Only Evidence Window Separation

## Finding

The existing `MAX_CAPTURE_SLOT_AGE = 32` boundary is appropriate immediately before a
live approval, but is too short for an operator to select evidence files, review a
wallet prompt, download signed bytes, and invoke the independent verifier. Applying
that live-execution freshness rule to a no-submission evidence exercise creates an
unsafe incentive to rush wallet review.

## Hotfix decision

The 32-slot rule and all live approval/submission code remain unchanged. The independent
hash-evidence path now uses only the existing time-bounded gate TTL when binding the
wallet signature. `validate_wallet_signed_claim` still verifies the exact closure,
unsigned transaction, message, signer set, wallet signature, and gate state.

This evidence can never be promoted directly to live execution. Its report states:

```text
rpc_freshness_verified = false
capture_freshness_policy = GATE_TTL_ONLY_NO_SUBMISSION
live_reconstruction_required = true
live_claim_approved = false
submission_attempt_count = 0
execution_ready = false
```

Any future live claim must reconstruct and simulate a fresh unsigned transaction and
pass the original strict slot-freshness boundary immediately before a separate explicit
approval. A wallet-signed F.6C.4 evidence artifact is therefore proof of identity and
message integrity only, never reusable execution authorization.

## Preserved stop conditions

- expired, used, mismatched, or unsafe gate;
- changed message or serialized transaction;
- unexpected wallet, signer set, account identity, closure, mint, or amount;
- enabled production fee, live approval, or submission flag;
- existing evidence output;
- any nonzero approval or submission count.
