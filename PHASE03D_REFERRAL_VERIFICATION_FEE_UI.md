# Phase 03-D — On-Chain Referral Account Verification & Fee Disclosure UI

Date: 2026-08-31. Target baseline: Phase03C commit 9d6c045 as represented by the
supplied Phase03A files plus the installed Phase03C changes.

## Status and scope

Implementation is ready for local regression and a read-only mainnet check.
The user's referral accounts have NOT yet been verified live in this workspace.
No swap, account creation, signature, fee activation or fee collection occurred.
The installer never edits the real .env, commits files, or changes wallet keys.
It refuses unknown file versions and backs up replaced files.

Keep DEXSATO_JUPITER_FEE_ENABLED=false. Existing zero-DexSato-fee trading stays
available. Historical discovery qualification is not a trading restriction.
The server's hard fee-order activation gate remains in place. Removing it requires
owner approval, an actual successful referral report, an agreed fee rate, and
transaction-level fee destination/amount verification for controlled testing.
Account verification alone does not prove that a given swap paid the fee.

## Implemented verification

- Use solders Pubkey/PDA APIs, not custom elliptic-curve code.
- Verify the FULL mainnet genesis hash (not truncated CAIP-2 network ID).
- Fetch project, referral and token accounts in one finalized getMultipleAccounts
  snapshot; report its slot and observation timestamp.
- Verify referral program ownership and Anchor account discriminators.
- Verify the fixed Ultra project and its project/base PDA relationship.
- Compare referral partner with the full public address configured by the owner.
- Check named referral PDA when a name exists; unnamed accounts are supported.
- Require the reviewed 8000-bps partner share (80% partner / 20% Jupiter).
- Derive each referral_ata PDA and validate the SPL account's token program,
  mint, project authority, initialized state, delegate, close authority and native flag.
- Current automated SOL-input quote verification requires WSOL. The operator
  CLI checks BOTH WSOL and USDC, including when the fee flag is false.
- HTTPS RPC only, redirects disabled, bounded response size and connection/read
  timeouts. Read methods only; fixed safe errors without RPC URL or credentials.
- No cached report is accepted as authorization to trade or collect fees.

RPC_ACCOUNT_VERIFIED means account state observed through the configured trusted
RPC. It is neither proof of possession of the partner wallet's key, an independent
cryptographic state proof, a token-safety label, nor proof of fee receipt.

## Fee disclosure and order review

Both quote and order responses include fee_disclosure. Disabled mode explicitly
shows zero DexSato fee without claiming Jupiter route fees are zero.
Enabled preview requires live WSOL referral verification. It displays the server
fee rate and an ESTIMATE calculated as approved SOL input multiplied by rate.
This is not a confirmed debit; raw fee receipt amount remains unknown.
The Jupiter share is described as INCLUDED, never added a second time.
Network fees and account rent are separate. Gasless fee previews fail closed
until their additional cost contract is reviewed.

The UI checks matching policy IDs/account/mint, rejects malformed disclosure,
and blocks fee-enabled execution previews. Text is rendered using textContent.
Actual prepared order amounts replace the initial quote summary, and another
explicit click is required before wallet signing. Changing the amount or
withdrawing acknowledgement discards the unsigned order. The hard-coded 0-bps
footer is replaced by a reference to the quote/order review.
Existing theme styles are reused; no redesign, login or new payment system.

## Installation and regression

Run the installer from the project root with --check, then without it.
Backups are under phase03d_backups; do not commit that directory.

```powershell
python -m pip install -r requirements.txt
python -m pip check
python -m pytest -v
node --test tests/test_jupiter_fee_ui.js
git diff --check
git diff --stat
```

New dependency: solders==0.29.0 (published Windows x86-64 CPython 3.10+ ABI3 wheel).
Only its public-key/PDA API is used. No keypair/signing API is imported.
Dependency pin is not a vulnerability-clearance claim; include it in the next
deployment dependency scan. Node is needed only for the additional mocked UI tests.

## Run the real read-only account check

Use the full PUBLIC wallet address controlling your Ultra referral, not the
referralAccount, token mint, or a shortened J2PV...bVTs label. SOLANA_RPC_URL must
already be set privately in this PowerShell session to your trusted HTTPS mainnet
endpoint. Do not paste a credential-bearing RPC URL into chat. The CLI uses process
environment variables; it does not automatically load a .env file.

```powershell
$env:DEXSATO_JUPITER_FEE_ENABLED = "false"
$env:DEXSATO_JUPITER_REFERRAL_ACCOUNT = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
$env:DEXSATO_JUPITER_REFERRAL_PARTNER = "PASTE_FULL_PUBLIC_OWNER_WALLET_ADDRESS"
python -m application.jupiter_referral_verification
```

Successful output has status RPC_ACCOUNT_VERIFIED, the observed partner/project,
partner_share_bps, slot, checked_at and both derived token_accounts. These are
public values and can be shared for review. fee_receipt_verified remains false.
Failure exits nonzero with a safe reason. Missing or mismatched accounts must be
reviewed; do not bypass the verifier or change the expected authority to force a pass.
This command does not create missing token accounts or require wallet approval.

## Verification performed here

- 32 unittest checks for policy, provider flow, account parser and disclosure,
  using synthetic accounts and injected/mock upstream calls.
- 23 existing quote/swap function checks, 9 readiness function checks and 14
  request-field rejection cases through the stdlib compatibility runner.
- 59 presenter/client source checks.
- 6 Node mocked-DOM tests, including order review before signing and stale-order reset.
- Installer dry-run, backup, baseline mismatch, repeat installation, syntax and
  Windows BOM/CRLF preservation checks.

Full pytest/FastAPI regression and the actual solders PDA test were NOT run here:
the runtime lacks these dependencies. The user must install requirements and run
the commands above. No live mainnet result is implied by mock test success.

## Primary sources

- https://developers.jup.ag/docs/swap/order-and-execute
- https://developers.jup.ag/docs/api-reference/swap/order
- https://github.com/TeamRaccoons/referral/tree/6500f64ff004e78faa15d66446e175ede625260d
  - program/programs/referral/src/lib.rs: Borsh layouts and seed constants.
  - instructions/initialize_referral_token_account.rs: token PDA and project authority.
  - instructions/initialize_referral_account_with_name.rs: named referral PDA.
  - instructions/claim.rs: partner/project claim split.
- https://pypi.org/project/solders/0.29.0/
- https://namespaces.chainagnostic.org/solana/caip2

Recheck official contract changes before activation. Program upgradeability and
RPC trust remain operational considerations; the pinned source is documentation
for the parser, not an attestation of deployed program bytecode.
