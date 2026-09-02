# 03-E.4C.1 — Dependency Advisory Attestation & Isolated Capture Gate

## Outcome

E.4C.1 converts the reviewed npm findings into a runtime fail-closed gate. A
ClaimV2 SDK capture cannot start until the local lockfile, current npm advisory
profile and approved read-only scope all match the reviewed evidence.

Reviewed lock SHA-256:

`f174f8bdaa2ea9096060e3714a39a4b486fafb082ec4ae1e7fa484af9b6908f4`

Reviewed root advisories:

- `GHSA-3gc7-fjrx-p6mg` / source `1103747` / `bigint-buffer` / high
- `GHSA-w5hq-g745-h8pq` / source `1119441` / `uuid` / moderate

The nine npm vulnerability nodes are propagation of those reviewed dependency
chains. Their canonical semantic profile is pinned, including package names,
severity, direct/transitive status, affected ranges, propagation paths and the
exact 0/0/5/4/0 count.

## Runtime gate

Before the official SDK process is invoked, E.4C.1:

1. hashes and validates the npm v3 lockfile;
2. validates the signed-off attestation scope;
3. launches `npm audit --json --omit=dev --ignore-scripts` separately;
4. accepts npm exit code 1 only when the exact reviewed profile is returned;
5. rejects a new package, advisory source, range, severity or count;
6. rejects registry/audit unavailability rather than using stale evidence;
7. starts the SDK builder only after all checks pass.

The npm audit subprocess receives only `PATH` plus npm safety controls. The SDK
subprocess remains one-shot, receives only the HTTPS RPC URL and has a 45-second
timeout. Neither process receives unrelated application secrets.

## Approval boundary

This is a narrow risk acceptance for one-shot, unsigned, read-only ClaimV2
capture only. It does not approve these packages for the production server,
wallet signing, live claim, transaction submission or long-running operation.

Every successful report retains:

- `production_runtime_approved: false`
- `live_claim_approved: false`
- `execution_ready: false`
- `fee_receipt_verified: false`

## Install and verify

The exact reviewed `tools/claim_v2_capture/package-lock.json` must be present.
Do not regenerate it before installation.

```powershell
python .\apply_dexsato_phase03e4c1_dependency_advisory_gate.py --check
python .\apply_dexsato_phase03e4c1_dependency_advisory_gate.py

python -m pytest -q `
  tests/test_jupiter_claim_v2_semantics.py `
  tests/test_jupiter_claim_v2_capture.py `
  tests/test_jupiter_claim_v2_sdk_capture.py

python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Never run `npm audit fix`, `npm audit fix --force`, `npm update` or dependency
overrides within this pinned tool.

## Capture

After full regression passes, use the same E.4C command:

```powershell
python -m application.jupiter_claim_v2_sdk_capture `
  --identity .\claim_v2_identity.json `
  --output-dir .\phase03e4c_capture_001
```

Expected success remains `PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED`. Upload
both generated JSON files for independent review before any later phase.

## Advisory references

- https://github.com/advisories/GHSA-3gc7-fjrx-p6mg
- https://github.com/advisories/GHSA-w5hq-g745-h8pq

