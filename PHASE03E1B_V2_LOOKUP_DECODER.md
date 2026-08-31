# Phase 03-E.1B — V2 Decoder & Lookup Account Resolution

## Scope and safety boundary

This operator-only diagnostic extends the offline decoder with `shared_accounts_route_v2`
and resolves version-0 address lookup tables through read-only mainnet RPC.
No wallet signing, swap execution, fee activation, pending-order changes or `.env` edits.
The fee execution gate remains closed. Resolution is NOT transaction authorization.

## Install

Run from the AlphaRadar project root after the E.1A import hotfix (393 tests reported).

```powershell
python apply_dexsato_phase03e1b_v2_lookup.py --check
python apply_dexsato_phase03e1b_v2_lookup.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Installer checks normalized source hashes, preserves CRLF/BOM, refuses unexpected
changes before writing, saves backups to `phase03e1b_backups`, and is idempotent.
It installs six files. Existing application runtime and trade validation are unchanged.
If a hash check fails, stop and supply the current relevant files; do not force it.

## Resolve captured evidence (no new Jupiter order needed)

Use the SAME PowerShell session with your configured HTTPS `SOLANA_RPC_URL`.
This CLI reads process environment variables; it does not automatically load `.env`.
Keep `DEXSATO_JUPITER_FEE_ENABLED=false`. No Jupiter API key is needed for lookup reads.

```powershell
python -m application.jupiter_lookup_decoder `
  --evidence "unsigned_evidence.json" `
  --output "decoder_v2_resolved.json"
```

Replace the evidence path with the actual file location/name, including `(1)` if present.
Output uses exclusive creation: an existing report is never overwritten. Choose a new
output filename on a repeat run. No signed transaction is accepted.

Success summary:

```json
{"status":"RESOLVED_REVIEW_REQUIRED","execution_ready":false,"fee_receipt_verified":false}
```

Send the resolved report and test results for review before any controlled swap.
The old captured transaction must NOT be signed: its blockhash/quote may have expired.

## What is decoded

- Exact V2 discriminator `d19853937cfed8e9`.
- Header: id u8, input u64, quoted output u64, slippage u16, platform fee u16,
  positive slippage u16, vector length u32.
- Route steps: reviewed Swap ordinals 0–38, allocation bps u16, input/output index u8.
  Unsupported enums, invalid booleans, bad bounds and trailing/truncated bytes reject.
- Twelve fixed account roles; all other positions are explicitly remaining accounts.
  V2 has NO named platformFeeAccount among these twelve roles. Its semantics cannot
  be inferred by reusing the V1 account position.

The uploaded fixture decodes input 1,000,000 lamports, quoted output 102,841 raw USDC,
slippage 50 bps, platform fee 50 bps and four route steps. This is byte interpretation,
not a proof of how much was charged or received.

## Lookup validation

- Allowlisted RPC methods only: getGenesisHash, getMultipleAccounts.
- HTTPS, no redirects, timeouts, bounded responses, fixed public errors.
- Solana mainnet genesis and one finalized RPC account snapshot.
- ALT program owner, non-executable flag, canonical base64, metadata type, 56-byte
  header, 32-byte address alignment, maximum 256 addresses, index bounds.
- Conservative rejection of deactivating/deactivated tables and same-slot extensions.
  Some of these may still be usable by Solana; this audit intentionally requires an
  unambiguous mature snapshot instead of emulating SlotHashes cooldown rules.
- Maximum eight lookup tables per diagnostic snapshot (bounded response size).
- Message order: static keys, ALL loaded writable keys, ALL loaded readonly keys.
- Message hash, current snapshot slot/time, per-table data hashes, account indexes,
  signer/writable message flags, every instruction's resolved accounts and raw bytes.

Flags are message-declared privileges, not a simulation of runtime privilege demotion.
RPC state is provider evidence at resolution time, not capture-time proof. No simulation,
deployed bytecode verification, token ownership validation or CPI-effect verification
is performed by this module. Non-Jupiter instructions remain explicitly not decoded.
`RESOLVED_REVIEW_REQUIRED` means address resolution completed; inspect each instruction's
status because unsupported Jupiter layouts may still be present.

## Sources and verification limits

V2 layout (secondary source, pinned):
https://github.com/sevenlabs-hq/carbon/blob/af70b199b39e60a1a33306e5411f8040374f8d9a/decoders/jupiter-swap-decoder/src/instructions/shared_accounts_route_v2.rs

Same commit: `types/route_plan_step_v2.rs` and `types/swap.rs`.
This is Carbon-generated schema evidence, NOT official Jupiter program attestation.
The first 39 enum variants reuse the integrity-pinned legacy schema after layout comparison.

Solana ALT serialization/reference:
https://github.com/solana-labs/solana/blob/v1.18.26/sdk/program/src/address_lookup_table/state.rs

## Tests and handoff

New regression tests use actual unsigned transaction bytes, plus explicitly synthetic
ALT snapshots. Synthetic addresses must never be presented as resolved mainnet state.
Local compatibility tests pass; this build environment lacks pytest/FastAPI/solders,
so the full regression and live HTTPS RPC lookup must be run in your environment.
The user previously reported 393 tests passing; that is not this build's full-suite result.

Remaining fee approval requirements: independently validate recipient roles and mint/
authority, instruction semantics and amounts, then obtain explicit controlled-test
approval and verify actual fee receipt on-chain. This patch does not open that gate.

## Commit only these files after tests pass

```powershell
git add application/jupiter_instruction_decoder.py application/jupiter_lookup_decoder.py tests/test_jupiter_lookup_decoder.py tests/fixtures/jupiter_v2_unsigned.json pytest.ini PHASE03E1B_V2_LOOKUP_DECODER.md
git commit -m "test: decode Jupiter V2 routes and resolve lookup evidence"
```

Ensure prior E.1A changes/import hotfix are committed separately if still uncommitted.
Do not use `git add .` with unrelated backups and research files present.
