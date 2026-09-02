# 03-E.4C — Pinned SDK ClaimV2 Construction & Read-Only Capture

## Outcome

E.4C isolates official SDK construction in a small Node process and immediately
passes the resulting unsigned bytes through the E.4B compiled-account auditor.
It cannot accept private keys, keypairs, seed phrases or signatures, and does
not expose signing, simulation, submission or claim execution APIs.

The direct dependency contract is fixed to:

- `@jup-ag/referral-sdk` `0.3.0`
- `@solana/web3.js` `1.98.4`
- audited referral source commit
  `6500f64ff004e78faa15d66446e175ede625260d`

Before construction, the Python boundary requires npm lockfile version 3,
exact direct versions, registry-only resolved URLs and SHA-512 integrity for
every transitive package. The complete lockfile SHA-256 is recorded in the
report.

## Read-only RPC boundary

The official `claimV2` SDK method reads mint, referral and project accounts,
recent blockhash, lookup/compute-budget information and a finalized slot.
E.4C therefore permits only an HTTPS RPC endpoint supplied through the child
process environment. The endpoint is never written to evidence. No unrelated
environment variables are forwarded.

This is network read-only construction, not Solana simulation. The builder
verifies that every transaction signature is still all-zero before returning
the bytes.

## Install and prepare dependencies

```powershell
python .\apply_dexsato_phase03e4c_pinned_sdk_capture.py --check
python .\apply_dexsato_phase03e4c_pinned_sdk_capture.py

Push-Location .\tools\claim_v2_capture
npm install --package-lock-only --ignore-scripts
npm ci --ignore-scripts
Pop-Location
```

Review and commit `package-lock.json` only after confirming that both direct
versions remain exact. Never use `npm update`, version ranges or install
scripts for this capture tool.

## Tests

```powershell
python -m pytest -q `
  tests/test_jupiter_claim_v2_semantics.py `
  tests/test_jupiter_claim_v2_capture.py `
  tests/test_jupiter_claim_v2_sdk_capture.py

python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

## Identity input

Create an operator-reviewed JSON containing public fields only:

```json
{
  "payer": "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs",
  "project": "DkiqsTrw1u1bYFumumC7sCG2S8K25qc2vemJFHyW2wJc",
  "admin": "CONFIRMED_ULTRA_PROJECT_ADMIN",
  "referral_account": "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ",
  "partner": "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs",
  "mint": "So11111111111111111111111111111111111111112",
  "token_program": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
  "referral_share_bps": 8000
}
```

Do not guess the Ultra project admin. Copy it from the previously verified
finalized referral/project snapshot.

## Run capture

Keep `DEXSATO_JUPITER_FEE_ENABLED=false`, then run:

```powershell
python -m application.jupiter_claim_v2_sdk_capture `
  --identity .\claim_v2_identity.json `
  --output-dir .\phase03e4c_capture_001
```

Expected status:

`PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED`

Upload both generated files for review:

- `unsigned_claim_v2_capture.json`
- `claim_v2_compiled_binding_report.json`

The report remains `execution_ready=false` and `fee_receipt_verified=false`.
No controlled live swap or claim is approved by E.4C.

## Source references

- https://dev.jup.ag/docs/ultra/add-fees-to-ultra
- https://github.com/TeamRaccoons/referral/tree/6500f64ff004e78faa15d66446e175ede625260d

