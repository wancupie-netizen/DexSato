# Phase 03-E.1A — Unsigned Order Evidence Capture & Jupiter Instruction Decoder

Baseline: e5f3f98. No execution or activation approval.

## Scope

Two operator-only modules, pinned IDL subset, two test files and test discovery.
No production endpoint, UI, fee-policy, signing, execute or pending-order changes.
The existing fee-enabled execution gate remains unchanged.

Capture is hardcoded to GET https://api.jup.ag/swap/v2/order, WSOL -> USDC,
ExactIn, excluding JupiterZ/DFlow/OKX. First request omits taker (quote); second
includes public taker (unsigned order). It does NOT call /execute or sendTransaction.
RPC checks use the existing finalized, mainnet-only read-only referral verifier.
API requests may count against the operator's API quota, but no funds are moved.

Capture requires production fee flag false, explicit test amount/fee/slippage,
existing HTTPS RPC and API key. No automatic .env loading. No keys in CLI arguments.
The capture test policy is isolated from production; no environment mutation.
SOL input range for this diagnostic is 0.001–1 SOL, slippage 0–100bps, fee 50–255bps.
These bounds are NOT changes to normal user trading controls.

## Install

Copy installer into AlphaRadar, then run:

```powershell
python .\apply_dexsato_phase03e1a_capture_decoder.py --check
python .\apply_dexsato_phase03e1a_capture_decoder.py
python -m pytest tests/test_jupiter_unsigned_capture.py tests/test_jupiter_instruction_decoder.py -v
python -m pytest -v
node --test tests/test_jupiter_fee_ui.js
```

STOP on baseline mismatch; do not force overwrite. Backups are under
phase03e1a_backups. Do not commit backups, installer or captured evidence.

## Read-only capture example

Use the same PowerShell session with JUPITER_API_KEY, SOLANA_RPC_URL,
DEXSATO_JUPITER_REFERRAL_ACCOUNT and DEXSATO_JUPITER_REFERRAL_PARTNER configured.
Keep DEXSATO_JUPITER_FEE_ENABLED=false. Never provide wallet private keys or seeds.

This sample requests 0.001 SOL, 50bps referral fee and 50bps slippage for inspection
only. It does not approve those values for live execution. The output directory
must NOT already exist, and its parent must exist. A failure may leave an empty
directory; choose a new name for the next attempt.

```powershell
python -m application.jupiter_unsigned_capture `
  --wallet J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs `
  --input-raw 1000000 `
  --fee-bps 50 `
  --slippage-bps 50 `
  --output-dir ..\dexsato_unsigned_evidence_01
```

Successful capture deliberately exits 2, printing CAPTURED_REVIEW_REQUIRED.
Errors exit 1 with fixed reason codes; full URLs, headers and raw provider errors
are not printed. Partial I/O failures do not claim success. Files are never
overwritten. The provider may decline to build an order if the wallet has
insufficient balance; capture does not fund accounts or suggest depositing funds.

Files created outside the repository:

- unsigned_evidence.json: allowlisted quote/order fields, unsigned transaction.
  Request IDs and unknown fields are removed; format can be read by the E.1 harness.
- decoder_report.json: source-pinned instruction layouts, public account roles,
  message digest, capture timestamp and finalized referral observation.

Share decoder_report.json first. It contains public wallet/account information,
not private keys. Never sign the captured transaction; it is audit evidence and
will expire. The quote and order are sequential independent provider observations,
not guaranteed identical pricing. A saved report does not establish future freshness.

## Decoder contract and limitations

Supports only Jupiter V6 `route` and `sharedAccountsRoute` from the pinned IDL.
Parses the complete Borsh route vector (including variable enum fields), then
inAmount, quotedOutAmount, slippageBps and platformFeeBps; rejects unknown enum
values, invalid bools, truncation and trailing bytes. Never guesses fee fields by
reading the tail of an unknown instruction. IDL subset hash is verified locally.

Maps each declared account role, including platformFeeAccount, to static keys.
Address-lookup references are reported with index and null address, not guessed.
Other programs and unknown Jupiter discriminators are explicitly NOT decoded.
Additional remaining accounts and CPI behavior are not certified by this decoder.

Important: the pinned public CPI IDL is from 2024 and is not a claim of current
deployed program equivalence. It may not describe a current order, newer swap
enum, routeV2, routing wrapper or RFQ instruction. The real capture report decides
the next decoder/lookup work; no fallback to a different API or weaker validator.

All reports keep execution_ready, transaction_fee_verified, fee_receipt_verified
false. LAYOUT_DECODED only means bytes match this IDL layout. It does NOT prove
fees, balances, mint ownership, route semantics, safe close destinations, rent,
compute fees, minimum output enforcement, simulation or settlement. Account and
message digests are diagnostic bindings, not authentication or authorization.

## Next evidence-driven step

Review the actual program IDs/discriminators in decoder_report.json. Resolve
lookup tables from validated RPC state and bind decoded amounts and fee account
roles to intent and verified mint/authority before considering simulation or
activation. Unknown variants require their own reviewed official schema.
No controlled real-money swap is authorized by this installment.

## Sources and local verification

- https://developers.jup.ag/docs/api-reference/swap/order (reviewed 2026-08-31):
  fixed order endpoint, taker behavior, fee parameters, excluded routers and payer.
- https://github.com/jup-ag/jupiter-cpi/blob/12bc5f67b94a2c3edc74d6e721a19442124a0bad/idl.json
  route/sharedAccountsRoute arguments, account order and Swap/Side/RoutePlanStep.

15 new tests pass locally through the stdlib compatibility runner with mocked
HTTP/RPC plus the prior local checks. Six Node UI tests and installer checks also
run locally. Full pytest/FastAPI/solders regression and actual capture must run
in the user's environment; no live quote, capture, simulation or transaction was
performed by the assistant. No claim is made that the on-chain fee has been received.
