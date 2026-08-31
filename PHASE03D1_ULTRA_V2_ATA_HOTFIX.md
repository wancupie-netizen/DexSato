# Phase 03-D.1 — Ultra V2 Referral ATA Verification

Baseline: Phase 03-D, user commit `9dbd0cb`.

## Correction

The original verifier used the V1 referral-token PDA and project authority.
The Ultra dashboard uses V2 canonical Associated Token Accounts owned by the
referral account. Existing synthetic tests repeated the V1 assumption. Therefore
`MISSING_REFERRAL_TOKEN_ACCOUNT_WSOL` did not establish that the user's V2 account
was absent. Do not create replacement accounts merely to satisfy that old check.

| Property | Correct Ultra V2 contract |
| --- | --- |
| ATA seeds | referral-account bytes, Tokenkeg-program bytes, mint bytes |
| Derivation program | Associated Token Program, `ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL` |
| SPL authority | referralAccount, not the Ultra project or partner wallet |
| Referral | named PDA derived from `referral`, Ultra project and stored name |
| Supported fee mints | canonical WSOL and USDC, both Tokenkeg |

No V1 fallback. Frozen/uninitialized accounts, unexpected delegate/close authority,
wrong mint, wrong owner/program, wrong project/partner/share and wrong network
remain rejected. Off-curve referral PDAs are supported through solders.

## Scope and safety

Only verifier, its tests and two documentation files change. No dependency,
frontend, fee-rate, quote/order policy, wallet, signing or transaction changes.
No account creation, claim, transfer or fee activation. Existing fee-enabled
execution gate remains. The real `.env` is never modified.

## Installation (PowerShell, repository root)

Copy the installer into `C:\Users\Sufi\Documents\Projects\AlphaRadar`.

```powershell
python .\apply_dexsato_phase03d1_ultra_v2_ata.py --check
python .\apply_dexsato_phase03d1_ultra_v2_ata.py
python -m pytest tests/test_jupiter_referral_verification.py -v
python -m pytest -v
node --test tests/test_jupiter_fee_ui.js
```

Installer checks every target before writing. If it reports a baseline mismatch,
stop and review the changed file; do not force overwrite. Existing files are backed
up under `phase03d1_backups/`. BOM/CRLF are preserved. Installation is idempotent.
Do not commit backups or the installer.

## Read-only mainnet verification

In the same PowerShell session where your HTTPS `SOLANA_RPC_URL`,
`DEXSATO_JUPITER_REFERRAL_ACCOUNT` and full public
`DEXSATO_JUPITER_REFERRAL_PARTNER` are configured, run:

```powershell
python -m application.jupiter_referral_verification
```

Keep fees disabled. This command does not load `.env` automatically. It uses only
`getGenesisHash` and a finalized `getMultipleAccounts` request. Do not share RPC
credentials or wallet secrets. No private key or seed phrase is needed.

Success must report `RPC_ACCOUNT_VERIFIED`, `token_account_model: ULTRA_V2_ATA`,
the expected referral account as `token_authority`, and WSOL/USDC token-account
addresses. Review the full public partner address against your owner wallet.
`fee_receipt_verified: false` is intentional: account verification is not proof of
fee collection, transaction correctness or successful execution. An RPC provider
is trusted to report state; this is not a cryptographic state proof.

If verification fails, preserve the fixed reason code and investigate; do not
disable validation or create/fund accounts blindly.

## Evidence and tests

Official SDK/program source pinned to TeamRaccoons/referral commit
`6500f64ff004e78faa15d66446e175ede625260d`:

- https://github.com/TeamRaccoons/referral/blob/6500f64ff004e78faa15d66446e175ede625260d/packages/sdk/src/referral.ts
- https://github.com/TeamRaccoons/referral/blob/6500f64ff004e78faa15d66446e175ede625260d/program/programs/referral/src/instructions/claim_v2.rs

Regression coverage includes exact V2 seeds/program, distinction from V1 PDA,
named referral requirement, project/partner authority rejection, missing V2 account
without fallback, finalized read-only RPC and existing malformed-account cases.

Local verification uses synthetic layouts/mocked RPC and a stdlib compatibility
runner, plus the unchanged six Node UI tests and installer checks. This runtime
does not have solders, pytest or FastAPI: full pytest and the real solders derivation
test must run in the user's environment. No live mainnet verification or transaction
was performed while building this hotfix.
