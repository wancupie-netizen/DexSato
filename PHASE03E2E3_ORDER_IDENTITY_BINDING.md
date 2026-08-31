# 03-E.2E.3 — Prepared-Order Identity & Account Binding

## Scope and baseline

Offline harness only. Baseline is the uploaded E2E1 ZIP plus exact E2E1/E2E2
installer outputs, most recently reported committed as 69ff3d2. The installer
checks normalized source hashes, not an assumed Git branch. Production quote,
swap, UI, minimum formula, environment and fee-execution gates are unchanged.

## Install

```powershell
python .\apply_dexsato_phase03e2e3_order_identity.py --check
python .\apply_dexsato_phase03e2e3_order_identity.py
python -m pytest -q tests/test_jupiter_minimum_contract.py tests/test_jupiter_unsigned_minimum_binding.py tests/test_jupiter_order_identity_binding.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Four targets only: new application/jupiter_order_identity_binding.py, new test,
this note, and registration in pytest.ini. No dependency changes. Existing
solders is reused. Installer supports BOM/CRLF, backups and repeat no-op; all
baseline checks precede writes. On STOP, provide updated files, never bypass.

## Checks implemented

1. Reuse E2E2: canonical unsigned message, recomputed message hash and minimum
   header comparison against the prepared-order amounts/slippage.
2. Require independent expected wallet, input mint, output mint, source token
   account and destination token account. Match order taker/inputMint/outputMint.
3. Reconstruct loaded account keys from raw ALT state, in Solana order: static,
   all writable lookups, all readonly lookups. Validate ALT owner, executable
   flag, state/layout, activation/warmup, table/index bounds and duplication.
4. Match payer and V2 userTransferAuthority to the expected writable signer.
5. Match writable source/destination account roles and input/output mint roles.
6. Require classic SPL Token program IDs for source/destination and the correct
   Jupiter program self-role. Token-2022 is unsupported in this initial harness.
7. Decode raw 165-byte token account state: mint, wallet authority, initialized
   (not frozen), no delegate/alternate close authority. Require distinct source
   and destination. Decode existing 82-byte mint state: classic program owner,
   initialized flag, supported decimals and authority option tags.
8. Record hashes of raw account data and supplied snapshot slot for traceability.

These are narrow fail-closed audit constraints, not new user trading rules.

## API and input contract

```python
audit_order_identity(
    encoded,                  # canonical base64 unsigned VersionedTransaction
    order,                    # inAmount/outAmount/otherAmountThreshold strings;
                              # slippageBps integer; taker/inputMint/outputMint
    expected,                 # independently supplied intent, see below
    snapshot,                 # raw account state, see below
    expected_message_sha256,  # message hash, not whole transaction hash
    expected_snapshot_slot,
)
```

Expected identity keys:

```json
{
  "wallet": "PUBLIC_WALLET_ADDRESS",
  "input_mint": "PUBLIC_INPUT_MINT",
  "output_mint": "PUBLIC_OUTPUT_MINT",
  "source_token_account": "PUBLIC_SOURCE_TOKEN_ACCOUNT",
  "destination_token_account": "PUBLIC_DESTINATION_TOKEN_ACCOUNT"
}
```

Snapshot structure (placeholders, not a runnable evidence file):

```json
{
  "context": {"slot": 123},
  "accounts": {
    "PUBLIC_ACCOUNT_ADDRESS": {
      "owner": "ACCOUNT_PROGRAM_OWNER",
      "executable": false,
      "data": ["BASE64_RAW_ACCOUNT_BYTES", "base64"]
    }
  }
}
```

Caller must provide all referenced ALTs plus the two existing token accounts and
two mint accounts from one identified RPC snapshot. The module does not collect
RPC data. Do not merge different-bank snapshots while retaining one slot label.
Do not derive expected identity solely from the same untrusted order/report.

Existing accounts only: an account missing before transaction execution is
rejected, not silently inferred from an ATA creation instruction. Newly-created
accounts, delegated accounts and Token-2022 need separately reviewed support.
No such support is added or enabled here.

## Honest result flags

`identity_snapshot_consistent: true` means supplied raw snapshot state agrees
with expected identity and transaction role indexes. `lookup_bytes_resolved`
means raw lookup addresses were decoded, NOT that their on-chain provenance was
authenticated. `minimum_header_bytes_bound` is inherited from E2E2.

Still false: snapshot_authenticity_verified, snapshot_freshness_verified,
lookup_state_verified, transaction_binding_verified, enforcement_verified,
execution_ready, fee_receipt_verified, production_formula_changed.
`enforced_minimum_raw` remains null.

No network requests, signing, broadcast, simulation, claim or runtime execution
authorization exists. Full route/CPI effects, other transaction instructions,
program behavior, freshness and fee receipt are not proven by these checks.
A consistently forged snapshot can pass offline consistency checks. Snapshot
hashes provide reproducibility, not independent authentication.

## Tests and evidence limits

42 new deterministic tests use synthetic transaction and raw account state,
including two ALTs to test writable/readonly ordering. They exercise order,
wallet, instruction mint/account roles, token authority/mint/frozen/delegate,
account owner/encoding/size, ALT state, slot and mint-state mismatches.
With E2E1/E2E2, 104 targeted tests passed locally. Full regression must run on
the complete user checkout. No live referral/swap account snapshot was newly
captured or verified in this step; passing synthetic tests is not a live audit.

## Commit after full regression passes

```powershell
git add application/jupiter_order_identity_binding.py tests/test_jupiter_order_identity_binding.py pytest.ini PHASE03E2E3_ORDER_IDENTITY_BINDING.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: bind prepared order identity to account snapshots"
```

Next evidence requirement: apply the harness to an actual unsigned prepared
order with independently recorded intent and a coherent raw RPC account
snapshot. Review unsupported pre-create accounts before expanding the scope.
Production activation and fee execution still require separate approval.
