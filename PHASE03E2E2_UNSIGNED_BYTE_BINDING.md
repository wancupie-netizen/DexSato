# 03-E.2E.2 — Unsigned Transaction Byte Binding

Offline harness only. Baseline is the supplied E2E1 ZIP plus the exact E2E1
installer outputs reported committed as 145d449. Hash guards stop on differences.
No production, UI, environment, minimum formula or fee-execution change.

## Install and verify

```powershell
python .\apply_dexsato_phase03e2e2_unsigned_binding.py --check
python .\apply_dexsato_phase03e2e2_unsigned_binding.py
python -m pytest -q tests/test_jupiter_minimum_contract.py tests/test_jupiter_unsigned_minimum_binding.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Uses the existing solders dependency; no dependency version changes. Installer
creates the new module, test and this note, plus test registration in pytest.ini.
It checks baseline before writing, backs up existing targets, refuses conflicts
and supports BOM/CRLF. Re-running is a no-op. Do not bypass STOP errors.

## What is bound

`audit_unsigned_minimum(encoded, order, expected_message_sha256, resolved=None)`
accepts canonical base64 of an unsigned version-0 transaction (maximum 1232 bytes).
Solders parses/sanitizes the transaction; serialization must round-trip exactly.
Only a single unsigned writable payer and static program IDs are supported.
Nonzero signatures are rejected; this function never creates signatures.

SHA-256 is recomputed from the serialized versioned message and compared with
the expected hash. Exactly one static Jupiter instruction is selected. The
pinned V2 header fields are extracted directly from its bytes and fed into E2E1.
Optional resolved-report instruction bytes and index must match the actual
instruction, not merely echo the same hash. Input/output amounts and slippage
must agree with the supplied prepared order.

## What is NOT verified

`minimum_header_bytes_bound: true` means the minimum-header comparison was tied
to actual supplied bytes. It does NOT mean `transaction_binding_verified`:
that broader flag remains false. Hashes do not authenticate provider provenance
if bytes and expected hash are supplied together by an untrusted party.

Full route-tail interpretation, ALT contents, expected wallet identity, mint
ownership, pool/vault state, fee behavior, program deployment semantics,
freshness and actual minimum enforcement remain outside this step. Optional
report account metadata is not trusted or certified. The exact original
instruction tail is compared when a report is supplied, not semantically decoded.

`enforced_minimum_raw` stays null. `execution_ready`, `enforcement_verified`,
`transaction_binding_verified`, `fee_receipt_verified`, and
`production_formula_changed` stay false. This module must not authorize trades.
There is no RPC access, simulation, signing, broadcasting or claim operation.
Legacy messages and lookup-loaded program IDs are deliberately unsupported in
this audit harness; this does not change production trading behavior.

## Evidence and testing

The supplied real unsigned fixture and resolved fixture are used with a clearly
synthetic order response matching its header; this is not a new captured quote.
Tests cover signed input, invalid/oversized base64, truncation/trailing bytes,
wrong hashes, header mutation with old and recomputed hashes, report tail/index
forgery and duplicate Jupiter instructions. E2E1's 47 tests remain unchanged.
Full regression must still run in the complete user checkout.

This closes the narrow supplied-bytes/header binding gap only. Production
minimum semantics and fee receipt still need separate verification/approval.

## Commit after all tests pass

```powershell
git add application/jupiter_unsigned_minimum_binding.py tests/test_jupiter_unsigned_minimum_binding.py pytest.ini PHASE03E2E2_UNSIGNED_BYTE_BINDING.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: bind minimum contract to unsigned transaction bytes"
```
