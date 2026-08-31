# Phase 03-E.2 — Fee Instruction Semantics & Simulation Validation

## Boundary

Operator-only diagnostic. No signTransaction, sendTransaction, swap execution, key
files, activation flags, new routes or changes to production transaction validation.
Fees must stay disabled. Every report keeps execution_ready, transaction_fee_verified
and fee_receipt_verified false. Exit code 2 means a report was produced for review,
not execution approval. Exit code 1 means validation/input/transport was incomplete.

## Install and tests

Save the installer in AlphaRadar, then:

```powershell
python apply_dexsato_phase03e2_simulation.py --check
python apply_dexsato_phase03e2_simulation.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Five files are installed. The installer preserves existing newline/BOM style, checks
baseline hashes, refuses conflicting edits, and backs up replaced files into
phase03e2_backups. It never edits .env. Stop on a hash mismatch; do not force it.

## Run against the previously captured evidence

Same PowerShell session must have SOLANA_RPC_URL (HTTPS),
DEXSATO_JUPITER_REFERRAL_ACCOUNT and DEXSATO_JUPITER_REFERRAL_PARTNER configured.
The CLI reads process environment only; it does not auto-load .env. No Jupiter API
key is needed for simulation. Never share private keys, seed phrases or RPC secrets.

```powershell
python -m application.jupiter_fee_simulation `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\fee_simulation_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw 1000000 `
  --minimum-output-raw 102326 `
  --fee-bps 50
```

These intent values apply ONLY to the supplied WSOL->USDC capture (0.001 SOL input,
0.102326 USDC minimum). Changing intent requires a separately reviewed capture.
Output is created exclusively; choose a new output filename if it already exists.

The tool replaces the recent blockhash in the RPC simulation, not in the saved
transaction. Signature verification is off because all signatures must be zero.
The transaction is never broadcast. Original quote/route/amount/slippage remain
unchanged. Expired market conditions can cause a simulation error despite blockhash
replacement. Failure is evidence, not a reason to weaken checks. Send the report.
If a fresh capture is needed, use the existing unsigned-capture command with a NEW
output directory; review its new minimum output before rerunning this command.

## Implemented checks

- Reparse original unsigned bytes and re-resolve lookup tables live; never trust an
  uploaded decoder report as an authorization token.
- Independently supplied wallet, amount, minimum output and fee rate matched to quote,
  order and V2 header. WSOL->USDC / ExactIn / metis only.
- One signer, wallet payer, non-gasless, canonical wallet WSOL and USDC ATAs.
- Current Ultra referral/partner/WSOL account verification using the existing module.
- Observed V2 remaining position 12 must contain the verified writable referral ATA.
  This positional profile is NOT an official recipient-semantics proof.
- Only reviewed Compute Budget settings, idempotent wallet ATA creation, exact total
  SOL wrapping transfer, SyncNative and wallet-directed CloseAccount around one V2
  Jupiter route. Unknown top-level instructions reject before simulation.
- Fixed simulateTransaction RPC method, HTTPS, timeout, no redirects, 1 MiB response
  cap, duplicate JSON key rejection, finalized commitment and minContextSlot.
- Successful simulation must return requested referral and user destination accounts
  with correct token program, mint, authority, initialized state, no delegate/close
  authority. No inference from balances fetched at different slots.
- Collect RPC-parsed SPL transfer/transferChecked CPI amounts under the Jupiter route.
  Unparsed/other instructions are counted as incomplete, never guessed. This is
  provider interpretation; full independent byte-level CPI validation is still pending.

## Report interpretation

SIMULATION_FAILED: RPC hypothetical execution returned an error; numeric instruction
index/custom code are retained when available, raw logs/errors are not exposed.

SIMULATION_REVIEW_REQUIRED: RPC execution succeeded and required post-state was
available, but this is still not security approval. Inspect parsed_token_transfers,
observed_fee_in_raw, observed_fee_out_raw, observed_destination_net_raw and
other_or_unparsed_inner_count. Missing CPI evidence does not mean zero actual fee.

fee_credit_observed_in_simulation means the RPC-parsed CPI list includes an inbound
transfer to the verified fee ATA without an observed outbound transfer. It does NOT
prove complete net balance change, correct fee split, real receipt, deployed-code
correctness, general safety or wallet approval. Existing fee account balance alone
never establishes collection. Gross arithmetic is input*feeBps/10000, a comparison
reference only; do not assume how Ultra splits or rounds until evidence is reconciled.

## Sources / limits

RPC semantics: https://solana.com/docs/rpc/http/simulatetransaction
V2 secondary schema provenance remains pinned in the E.1B decoder documentation.
This patch does not independently attest Jupiter deployed bytecode or fully validate
DEX inner programs. All such checks remain review items before a controlled test.

No live simulation was run during packaging: this build runtime lacks configured
RPC credentials and solders/FastAPI/pytest. Fifteen new unittest cases pass locally
with compatibility stubs; the additional real SDK ATA test and full regression must
run in AlphaRadar. Fixtures include user-supplied resolved evidence and synthetic
simulation responses. Synthetic fee amounts are NOT mainnet receipts.

## Commit after regression passes

```powershell
git add application/jupiter_fee_simulation.py tests/test_jupiter_fee_simulation.py tests/fixtures/jupiter_v2_resolved_audit.json pytest.ini PHASE03E2_FEE_SEMANTICS_SIMULATION.md
git commit -m "test: validate fee profile and capture unsigned simulation evidence"
```

Do not add unrelated backups or generated reports with git add .
