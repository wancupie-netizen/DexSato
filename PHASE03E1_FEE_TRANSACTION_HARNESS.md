# Phase 03-E.1 — Offline Fee Transaction Validation Harness

Baseline: 8642f95 (Phase 03-D.1). No production fee activation.

## Important finding and delivery boundary

The existing transaction policy checks signer/payer, selected top-level program
instructions and cumulative System transfers. It does NOT decode Jupiter route
instruction amounts, minimum output or fee destination/amount. Program allowlisting
and presence of the expected ATA cannot establish these semantics. Address lookup
table contents are not resolved by the current parser. Fee-enabled execution must
remain blocked. This harness is a diagnostic foundation, NOT a completed fee
transaction authorization validator or clearance for Phase 03-E.2.

This installment adds only an offline operator module, eight tests, test discovery
and these notes. No route/UI/service gate/production setting changes. It does not
request orders, fetch RPC, create accounts, sign, submit or claim tokens.

## Install and test

Run from the AlphaRadar repository root:

```powershell
python .\apply_dexsato_phase03e1_harness.py --check
python .\apply_dexsato_phase03e1_harness.py
python -m pytest tests/test_jupiter_fee_transaction_harness.py -v
python -m pytest -v
node --test tests/test_jupiter_fee_ui.js
```

Installer refuses target/source baseline mismatches. Backups are placed in
phase03e1_backups; do not commit backups or installer. Real .env is not touched.
The local build ran the documented stdlib compatibility runner and Node tests;
full pytest/FastAPI/solders execution must run on the user's installed environment.

## Offline input contract

A bounded JSON file contains exactly two top-level fields: `quote` and `order`.
These are untrusted raw provider response objects, not frontend display objects.
Quote must not include a transaction; order must be UNSIGNED (zero signatures).
Do not share API keys, headers, seed phrases, private keys or signed transactions.
Do not bypass the production fee-order gate to obtain an evidence file. Evidence
capture from the official API is a separate pending read-only workflow.

Operator arguments independently define wallet, output mint, input lamports,
minimum output in the output mint's raw units, referral and fee BPS. These values
are NOT taken from the untrusted response and do not change server fee policy.

Usage (replace placeholders with independently reviewed values):

```text
python -m application.jupiter_fee_transaction_harness evidence.json --wallet PUBLIC_WALLET --output-mint OUTPUT_MINT --input-raw INPUT_LAMPORTS --minimum-output-raw MINIMUM_RAW --referral PUBLIC_REFERRAL --fee-bps REVIEWED_BPS
```

No live input is required to run the synthetic tests. The earlier proposed 50bps
and 0.001 SOL are suggestions, not approved activation settings.

## Interpretation

- Exit 1 / REJECTED: invalid evidence, intent mismatch, structural failure,
  unresolved referenced lookup accounts or missing dependency.
- Exit 2 / REVIEW_REQUIRED: preliminary structural and provider metadata checks
  passed. This is deliberately NOT exit 0. No execution is authorized.
- `transaction_fee_verified`, `fee_receipt_verified`, `execution_ready` remain
  false in all reports. Never use report fields as authorization tokens.
- Expected ATA presence is diagnostic only; it may be unused by the instruction.
- Local files do not establish freshness, provider origin, simulation, account
  balances, minimum output enforcement or on-chain fee receipt.

## Required before controlled execution

1. Obtain sanitized unsigned fee-bearing order evidence through a reviewed capture
   flow without changing production flags or signing.
2. Pin the official IDL/decoder for the actual returned Jupiter route variant;
   resolve address lookup tables using bounded, validated RPC account reads.
3. Decode and bind route input/output, minimum output, fee mint, fee account and
   fee amount/rate to independently reviewed intent. Reject unsupported variants.
4. Validate all instruction roles including token-close destinations, ATA owners,
   compute budget costs, rent funding and any additional transfers. Existing
   structural policy alone does not prove these properties.
5. Reverify referral accounts, perform bounded simulation and inspect effects.
   Simulation is not a guarantee of execution or final fee receipt.
6. Require a separate review click for the actual prepared order, owner approval
   of fee/test amount and wallet signature. No automatic mainnet transactions.
7. Attribute fee receipt to the finalized transaction's actual instructions and
   pre/post token balances, not unrelated aggregate balance changes. 80/20 is the
   verified referral sharing contract; net wallet revenue may require claim checks.

No public fee execution or controlled real-money test is approved by this package.
