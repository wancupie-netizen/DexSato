# 03-E.2C — Meteora, Saber & Orca Pool/Vault Binding

## Scope and safety contract

Read-only audit extension. Production swap/quote services, fee policy, wallet
signing, UI, .env and transaction restrictions are unchanged. Fee execution
must remain disabled. No sendTransaction, execute, sign, claim or transfer API
is added. Reports always retain execution_ready=false and fee_receipt_verified=false.

Supported instructions: Meteora DLMM legacy swap, Saber stable-swap swap,
Orca Whirlpool legacy exact-input swap, using the legacy SPL Token program.
Other instruction versions and Token-2022 require separate review. The WSOL,
USDT and USDC restriction is only this evidence audit profile, NOT a trading
qualification rule or change to user-directed trading.

## Checks implemented

- Strict discriminator/tag, byte length, account roles, amount and CPI depth.
- All CPI keys and program IDs must occur in the resolved original message.
- Jupiter program authority must match every leg's transfer authority.
- One finalized getMultipleAccounts snapshot per leg, with minContextSlot at
  least the baseline simulation slot; exact response count and address order.
- Program executable and upgradeable-loader ownership; pool owner and layout.
- DLMM LbPair mint/reserve fields, reserve PDAs, oracle field/PDA and event PDA.
- Saber SwapInfo reserve/mint fields, stored nonce authority PDA, destination
  admin-fee account, initialized/unpaused state.
- Whirlpool mint/vault fields, pool PDA (fee-tier seed), oracle PDA, direction.
- Legacy token account owner, mint, authority, initialization, native flag,
  absence of delegate/close authority and nonzero delegated allowance.
- Every returned child token transfer must follow the expected source/vault/
  destination/authority edges, amount and sequence. Checked transfers also
  require the expected mint and decimals. Unexpected children fail the binding.
- Meteora self-CPI event envelopes are recorded separately, not treated as
  additional swaps. Event payload semantics are explicitly NOT verified.
- Captured route linkage: WSOL->USDT (Meteora) -> USDC (Saber), and WSOL->USDC
  (Orca). Intermediate account, amount and call ordering must match. A different
  topology reports review required; it is not automatically accepted.

## Important limits

These are typed pool/vault bindings, NOT complete DEX execution proofs.
Tick arrays, bin arrays, bitmap contents, oracle price math, fee math and
deployed-bytecode/source equivalence are not proven by this patch. DLMM has
multiple pool creation seed schemes; pool origin PDA is not claimed, while
pool ownership, discriminator, stored reserves and reserve PDAs are checked.
Snapshots occur after simulation and do not prove identical historical state.
Source-pinned layouts do not prove that an upgradeable deployment is immutable.
Pancake's existing candidate-layout caveat remains. Exact minimum-output
boundary proof and on-chain fee receipt remain outstanding.

## Install (project root)

Save apply_dexsato_phase03e2c_typed_pools.py in the AlphaRadar project root.

```powershell
python .\apply_dexsato_phase03e2c_typed_pools.py --check
python .\apply_dexsato_phase03e2c_typed_pools.py
python -m pytest -q
node --test tests/test_jupiter_fee_ui.js
```

Installer requires the E.2B.2 classification baseline. It preflights all targets,
backs up replaced files, preserves BOM/CRLF, and supports repeat installation.
If it reports STOP, do not remove its hash guards: provide the named current
source file for review. Do not use git add . because unrelated backups exist.

## Generate a fresh report

Use the same configured HTTPS RPC/referral environment as your previous audit.
Do not enable fees. Keep the output filename unused.

```powershell
python -m application.jupiter_binding_audit `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\typed_pool_binding_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw "1000000" `
  --minimum-output-raw "102326" `
  --fee-bps "50"
```

The amounts above belong to the existing captured evidence. If the baseline
simulation no longer succeeds, capture fresh unsigned evidence and use its
matching parameters; do not weaken validation to accept stale evidence.

For this route, inspect typed_pool_binding_count (expected 3 if snapshots and
children match), each typed_pool_bindings entry, typed_route_links, and
unsupported_pool_programs. A recognized but invalid leg remains uncovered and
explicitly rejected, never silently removed. Top-level BINDING_REVIEW_REQUIRED
and exit code 2 are intentional even when all three new bindings match.
all_pool_bindings_verified remains false because broader proof gaps remain.

Upload typed_pool_binding_report.json plus test results before proceeding.
No mainnet snapshot success or fee receipt is claimed by local fixture tests.

## Sources pinned during implementation

- Meteora IDL (layout, account roles, program ID):
  https://github.com/MeteoraAg/dlmm-sdk/blob/fb02e51ae677bbd18e76543f702dae40632426db/idls/dlmm.json
- Meteora PDA derivations:
  https://github.com/MeteoraAg/dlmm-sdk/blob/fb02e51ae677bbd18e76543f702dae40632426db/ts-client/src/dlmm/helpers/derive.ts
- Saber packed SwapInfo (395 bytes):
  https://github.com/saber-hq/stable-swap/blob/39d5d4e0e844a009c83d37a3ce63d219fdba0bff/stable-swap-client/src/state.rs
- Saber instruction roles/tag:
  https://github.com/saber-hq/stable-swap/blob/39d5d4e0e844a009c83d37a3ce63d219fdba0bff/stable-swap-client/src/instruction.rs
- Orca Whirlpool (653 bytes) and pool seeds:
  https://github.com/orca-so/whirlpools/blob/3b47341e16110ba015ca0acf06a53c0fa12e49f3/programs/whirlpool/src/state/whirlpool.rs
- Orca swap roles and direction:
  https://github.com/orca-so/whirlpools/blob/3b47341e16110ba015ca0acf06a53c0fa12e49f3/programs/whirlpool/src/instructions/swap.rs

## Commit only after regression and report review

```powershell
git add application/jupiter_typed_pool_binding.py application/jupiter_binding_audit.py tests/test_jupiter_typed_pool_binding.py tests/fixtures/typed_pool_cpi.json pytest.ini PHASE03E2C_TYPED_POOL_BINDINGS.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: bind Meteora Saber and Orca pools and vaults"
```

If the earlier E.2B.1/E.2B.2 changes remain uncommitted, review and commit them
separately or explicitly include their intended paths. This patch does not
silently stage or discard those changes.
