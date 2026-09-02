# Phase 03-F.3A — Dependency Advisory Re-attestation

## Decision

`READ_ONLY_CAPTURE_REATTESTED`

The npm advisory profile changed after the original E4C review. The installed
dependency graph and lockfile did not change. Review identified one metadata
difference: the affected range reported for direct dependency
`@solana/web3.js` expanded from an upper bound of `1.98.4` to
`1.99.0-beta.0`.

## Exact evidence

| Evidence | SHA-256 |
|---|---|
| `package-lock.json` | `f174f8bdaa2ea9096060e3714a39a4b486fafb082ec4ae1e7fa484af9b6908f4` |
| Advisory profile | `f948fc71f79aed1ac0b699a073fe76c5a1c574389fe55b9c5b52f29e1c47bcd1` |
| Reviewed npm audit | `d9469e8bd2dc8686a0c0b75f6bb4cc39978b7dc8a3cc0a07947cca2926686cee` |
| Reviewed dependency tree | `de268ab351a5fa34af654b0edd7ef69b26f46636547b142b24652044f1ef6e64` |

The old and new dependency trees are byte-identical. Advisory counts remain
zero critical, four high, five moderate and nine total. No dependency was
installed, removed or upgraded by this phase.

## Accepted boundary

The advisory risk is accepted only for:

`ONE_SHOT_READ_ONLY_UNSIGNED_CLAIM_V2_CAPTURE_ONLY`

The Node process receives a bounded identity request and HTTPS RPC endpoint,
constructs an unsigned transaction, and returns bounded JSON. The Python
boundary independently re-decodes and re-binds that transaction.

## Explicit non-approvals

- `production_runtime_approved=false`
- `live_claim_approved=false`
- `execution_ready=false`
- `fee_receipt_verified=false`
- No signing or transaction submission
- No automatic `npm audit fix`

Any change to the lockfile, advisory profile, reviewed audit hash, reviewed
dependency-tree hash, root advisory set or safety flags blocks capture again.

## Next operation

After focused and full regression tests pass, repeat the fresh funded ClaimV2
unsigned capture. A successful capture remains review evidence and proceeds
only to read-only simulation.
