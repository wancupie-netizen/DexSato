# Phase 03-E.4D.1A — Actual Auxiliary Program Semantics Reconciliation

The real pinned-SDK capture replaced the provisional auxiliary hypothesis with
transaction-byte evidence. Its exact sequence is:

| Index | Program semantics | Bound value |
|---:|---|---:|
| 0 | Set compute-unit limit | 50,472 CU |
| 1 | Set compute-unit price | 145,930 micro-lamports/CU |
| 2 | Create partner ATA | partner WSOL ATA |
| 3 | ClaimV2 | final instruction |

The validator accepts the binary instruction families with explicit upper
bounds rather than hard-coding only the observed numeric values. The estimated
maximum priority fee is reported in lamports. The ATA is bound to the same
partner, mint, System Program and Token Program independently required by the
ClaimV2 account contract.

No execution permission changes. The diagnostic and auxiliary report remain
review evidence only; transaction signing, submission and fee execution remain
disabled.
