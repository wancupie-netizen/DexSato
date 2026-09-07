# Phase 03-F.6C.4A — Dependency Advisory Re-attestation

## Decision

The package lock is unchanged at SHA-256
`f174f8bdaa2ea9096060e3714a39a4b486fafb082ec4ae1e7fa484af9b6908f4`, but the
registry advisory profile changed on 7 September 2026 from 9 to 11 findings. This
re-attestation accepts the current profile **only for the isolated, one-shot, read-only
unsigned ClaimV2 capture child process**. It does not approve these dependencies for
the production runtime, wallet signing, live approval, or submission.

Evidence hashes:

```text
npm audit:      bc23015ed0d89edd11b884b622fc48ec5f1f84a9419b5702da695179095bddec
dependency tree:e58ad16c64e4bec3513de4fabdd417b9fbe6f87dbbc4a950eec87e18af6f6322
profile:        a1be05d1b8d121f2c056bd07f57cc6ec1a3318fd563c0b39f44277898506910e
```

## New findings

- `stream-json` / `GHSA-528h-pc64-c93x`: affected path-filter APIs can exhibit
  quadratic CPU use on deeply nested untrusted JSON. The fixed ClaimV2 builder does not
  call those filter APIs, runs in an isolated child process, and is bounded by a
  45-second parent timeout.
- `toml` / `GHSA-82x6-q7mm-w9cf`: deeply nested untrusted TOML can exhaust recursion.
  The fixed builder accepts a strict JSON object and does not parse user-supplied TOML.
- `toml` / `GHSA-v5mp-jgw5-2x6j`: crafted TOML may cause prototype pollution. The
  capture path does not accept or parse TOML.

The advisories remain material outside this narrow path. No automatic upgrade or
`npm audit fix` is authorized because npm proposes semver-major dependency changes that
would invalidate the pinned SDK construction and its account-order audit.

## Preserved controls

- exact package-lock hash and registry-integrity checks;
- exact advisory-profile and evidence hashes;
- exact five-advisory source/GHSA allowlist;
- `npm audit --omit=dev --ignore-scripts` before every capture;
- isolated Node child with restricted environment and 45-second timeout;
- strict bounded JSON input and output;
- production fee, live approval, and submission remain disabled;
- `production_runtime_approved`, `live_claim_approved`, `execution_ready`, and
  `fee_receipt_verified` remain `false`.

Any subsequent profile, severity, source, GHSA, dependency-tree, or lockfile change
must fail closed and receive a new review.
