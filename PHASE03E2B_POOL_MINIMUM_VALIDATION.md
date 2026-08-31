# 03-E.2B — Pool/Vault Binding & Minimum Output Validation

## Scope and status

This is an operator-only evidence harness, NOT a production execution validator.
No routes, wallet UI, fee policy, signing code, .env, or execution gates change.
The full stage is NOT closed by installing this harness or by passing its tests.

Implemented:

- Reparse the original unsigned transaction and resolve its lookups again.
- Reuse referral validation and the reviewed WSOL -> USDC simulation profile.
- Check exact integer minimum-output arithmetic against the ORDER, not only the quote.
- Require baseline simulation output to meet both the order minimum and operator minimum;
  require gross referral fee inflow to match policy arithmetic with no fee outflow.
- Identify the actual Pancake program ID, bind its CPI accounts to the Jupiter message,
  and fetch pool/input-vault/output-vault in one finalized RPC snapshot.
- Check pool owner, candidate PoolState header, config, observation address, mint order,
  WSOL/USDC direction, pool and vault PDAs, SPL vault mint/authority/native state,
  initialized state, absence of delegate/close-authority, and snapshot minimum slot.
- Make an IN-MEMORY unsigned negative probe: change only Jupiter V2 quotedOutAmount
  and slippageBps, demanding a much larger output with zero slippage. Simulate only.
- Recognize route-level Custom 6001 together with SlippageToleranceExceeded logs and
  a Jupiter-only failure line. Other errors, downstream failures or missing logs are
  inconclusive, NOT a passing minimum-output enforcement check.

## Important limits

The Pancake identity is supported by the pinned official Pancake repository:
https://github.com/pancakeswap/pancakeswap-ai/blob/f8d2f9da32b9a12404e921fab900648d056853a8/packages/plugins/pancakeswap-driver/skills/collect-fees/references/fetch-solana.cjs

PoolState/PDA interpretation uses the Raydium-family source pinned in the module.
It is explicitly CANDIDATE_LAYOUT_BINDING_MATCHED, not proof of Pancake bytecode.
Unknown/changed layouts fail the checks and require review; never patch offsets just
to make a report pass. Tick arrays and config/observation account contents are NOT
fully validated by this version (only their references in PoolState/CPI are checked).

Meteora, Saber and Orca pool-state adapters are NOT implemented here. Their actual
program IDs are listed under unsupported_pool_programs. all_pool_bindings_verified
always remains false. Thus this package is groundwork, not complete route validation.

The negative probe is a separate simulation at a potentially different slot. It does
not prove exact boundary/rounding behavior or that the original transaction can safely
execute later. Its mutation is not exposed as a signable order or saved in the report.
enforcement_verified stays false, even when the negative probe is observed.

Snapshots are current provider observations, not cryptographic/historical proofs.
No simulation is an actual fee receipt or claim. execution_ready and
fee_receipt_verified remain false in every outcome.

## Install and test (PowerShell, project root)

```powershell
python .\apply_dexsato_phase03e2b_pool_minimum.py --check
python .\apply_dexsato_phase03e2b_pool_minimum.py
python -m pytest tests/test_jupiter_pool_validation.py -v
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Installer checks exact normalized baselines before writing, preserves existing newline
style/BOM, backs up changed files, and refuses unexpected existing files. Do not bypass
a baseline mismatch. It does not install dependencies or alter .env.

Local builder verification: 9 pure unit tests passed, 1 SDK-vector test skipped because
solders was unavailable; 2 wire-mutation checks passed using the exact production parser
functions in a dependency-isolated harness. Full pytest, real SDK vector, live CLI/RPC,
and frontend regression still need running in the project environment. No claim of a
complete passing regression suite is made for this package.

## Run read-only audit

Use an existing unsigned evidence file, NOT decoder_report.json or simulation report.
Use the wallet/input/minimum/fee values belonging to THAT evidence. The example below
matches the previously discussed 0.001 SOL / 50bps / 102326 raw USDC capture; do not use
these values with a different capture without reviewing its order fields.
SOLANA_RPC_URL and the existing referral account/partner environment settings must
already be configured in this process. Never paste RPC credentials into an audit report.
Keep DEXSATO_JUPITER_FEE_ENABLED=false. A local .env is not automatically loaded by this CLI.

```powershell
$evidencePath = Read-Host 'Full path to the unsigned evidence JSON'
if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) { throw 'Evidence file not found' }
python -m application.jupiter_binding_audit `
  --evidence "$evidencePath" `
  --output ".\pool_minimum_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

Expected review status: BINDING_REVIEW_REQUIRED, exit code 2 (deliberately not approval).
Failed validation/unavailable RPC: BINDING_AUDIT_INCOMPLETE, exit code 1. Existing output
files are never overwritten. Preserve old reports and choose a new output name.
If baseline simulation fails, capture a fresh unsigned order; do not relax checks.

Share pool_minimum_report.json for review. Public addresses are included; wallet secrets,
RPC URL and mutated transaction are not included. The next review must resolve remaining
pool families, full CPI effects and exact minimum enforcement before any controlled swap.

## Commit only after tests pass

```powershell
git add application/jupiter_pool_validation.py application/jupiter_binding_audit.py tests/test_jupiter_pool_validation.py pytest.ini PHASE03E2B_POOL_MINIMUM_VALIDATION.md
git commit -m "test: add pool binding evidence and unsigned minimum-output probe"
```
