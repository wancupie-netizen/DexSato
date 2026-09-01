# 03-E.3 — Fresh Fee-Bearing Order Simulation & Referral Balance-Delta Verification

## Outcome and boundary

This operator-only harness captures a fresh Swap V2 order for exactly
`0.001 SOL`, validates the server-selected `50 bps` policy and `platformFee`,
performs the E2E4 identity/ATA lifecycle checks, then calls Solana
`simulateTransaction`. It never signs, broadcasts, calls Jupiter `/execute`,
changes `.env`, enables the production fee gate or writes on-chain state.

The one-shot command keeps capture, finalized identity snapshot and simulation
inside a five-minute evidence window. The output directory is new-only and all
reports omit API keys, RPC URLs, request IDs, raw upstream errors and headers.

## Reviewed fee contract

For the controlled WSOL → USDC case:

- input: `1,000,000` lamports (`0.001 SOL`);
- provider fee: `50 bps`;
- expected total platform fee: `5,000` raw WSOL;
- reviewed referral share: `8,000 bps` (80%);
- expected referral ATA simulation delta: `4,000` raw WSOL;
- Jupiter share implied by the reviewed contract: 20%.

The expected WSOL referral ATA is derived canonically from the configured public
referral account and WSOL mint. It must occur once as a writable, non-signer
message account. The harness derives the delta from `preTokenBalances` and
`postTokenBalances` returned by the same simulation result, not from two
separate live reads.

## Simulation contract

The RPC request is fixed to:

- HTTPS Solana mainnet verified by genesis hash;
- `simulateTransaction` only;
- `sigVerify: false`;
- `replaceRecentBlockhash: true`;
- `innerInstructions: true`;
- `commitment: confirmed`;
- `minContextSlot` equal to the finalized identity snapshot slot;
- one requested post-simulation account: referral WSOL ATA.

Solana documents that an unsigned transaction may be simulated when signature
verification is disabled, and that the node can replace an expired blockhash.
No `sendTransaction` method is available in this module.

## Important Jupiter lifecycle note

Jupiter's official integrator-fee guide currently states that Ultra Swap is no
longer actively maintained and has been superseded by Swap V2. DexSato already
uses `/swap/v2/order`; this harness does not fall back to the deprecated
`/ultra/v1/order`. The guide remains the reviewed source for the referral
account, fee-mint priority and 80/20 fee split, while the actual Swap V2 order
and simulated bytes are treated as the decisive evidence.

References reviewed 2026-09-01:

- https://developers.jup.ag/docs/ultra/add-fees-to-ultra
- https://solana.com/docs/rpc/http/simulatetransaction

## Install and regression

Baseline requires committed E2E4.2 (`a8fc9d3`) and the existing E1A capture
files. Stop on any mismatch.

```powershell
python .\apply_dexsato_phase03e3_fee_simulation.py --check
python .\apply_dexsato_phase03e3_fee_simulation.py
python -m pytest -q tests/test_jupiter_fee_balance_simulation.py tests/test_jupiter_fresh_fee_simulation.py tests/test_jupiter_unsigned_capture.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

## Required environment

Keep production fee execution disabled:

```text
DEXSATO_JUPITER_FEE_ENABLED=false
```

The existing public/referral configuration and task credentials must be present
in the current shell/process environment:

- `JUPITER_API_KEY`
- `SOLANA_RPC_URL` (HTTPS mainnet)
- `DEXSATO_JUPITER_REFERRAL_ACCOUNT`
- `DEXSATO_JUPITER_REFERRAL_PARTNER`

Never paste credential-bearing values into reports or chat.

## Run the one-shot simulation

Use the approved public wallet. This does not access the wallet extension and
does not require a signature:

```powershell
python -m application.jupiter_fresh_fee_simulation `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --output-dir ".\phase03e3_sim_001"
```

A successful evidence capture deliberately exits with code 2:

```json
{"status":"SIMULATED_FEE_DELTA_REVIEW_REQUIRED","execution_ready":false,"fee_receipt_verified":false}
```

Upload `phase03e3_sim_001/fee_balance_simulation_report.json` first. Do not
upload the companion account snapshot unless byte-level diagnosis is requested.

## Success criteria

The report must show:

- `simulation_partner_delta_verified: true`;
- `platform_fee_raw: "5000"`;
- `expected_partner_delta_raw: "4000"`;
- `referral_delta_raw: "4000"`;
- `transaction_submitted: false`;
- `on_chain_receipt_verified: false`;
- `execution_ready: false`;
- `fee_receipt_verified: false`.

Any simulation error, stale evidence, wrong delta, mismatching referral ATA,
missing platform-fee evidence, production fee flag, identity failure or RPC
network mismatch stops with a fixed reason code.

## Limitations and next gate

Simulation uses a trusted RPC provider and replacement blockhash. It proves
neither that the wallet will sign nor that the identical transaction will land.
It does not create an on-chain receipt, guarantee future liquidity, authenticate
the RPC snapshot, or activate production. Even a perfect `4,000` raw delta
remains simulation evidence only.

Controlled live execution requires a separate owner-approved phase, a newly
captured order, wallet review and post-confirmation on-chain balance/transaction
metadata verification. Do not remove the production execution gate in E3.
