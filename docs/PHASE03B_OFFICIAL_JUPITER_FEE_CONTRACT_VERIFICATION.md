# Phase 03-B — Official Jupiter Fee Contract Verification

Date verified: 2026-08-28

Scope: Jupiter Swap V2 Meta-Aggregator `/swap/v2/order` and `/swap/v2/execute`

Status: Contract verified; no DexSato application code modified

## Decision

DexSato should use the Jupiter Referral Program through these `/swap/v2/order` query parameters:

```text
referralAccount=<DEXSATO_REFERRAL_ACCOUNT>
referralFee=50
```

The minimum supported referral fee is **50 bps (0.50%)**. The previously proposed 20 bps is not accepted by the official Swap V2 contract and must not be implemented.

Recommended initial policy:

```text
DexSato user-facing fee: 50 bps (0.50%)
Jupiter share: 20% of the integrator fee
DexSato effective share: 40 bps (0.40%), subject to successful collection
```

Jupiter states that there is no separate Jupiter platform fee when referral fees are active. The order response remains authoritative and must be validated for every quote and order.

## Authoritative sources

1. Swap V2 Order API reference

   https://developers.jup.ag/docs/api-reference/swap/order

2. Swap V2 Order and Execute guide

   https://developers.jup.ag/docs/swap/order-and-execute

3. Swap API overview

   https://developers.jup.ag/docs/swap

4. Legacy Ultra fee guide, used only to identify migration warnings

   https://developers.jup.ag/docs/ultra/add-fees-to-ultra

The Ultra guide explicitly states that Ultra is no longer actively maintained and has been superseded by Swap V2. Its routing statements must not override the current Swap V2 documentation.

## Verified request contract

### Quote-only request

`taker` is omitted. Jupiter returns a quote without transaction material.

```text
GET /swap/v2/order
  ?inputMint=<INPUT_MINT>
  &outputMint=<OUTPUT_MINT>
  &amount=<RAW_INPUT_AMOUNT>
  &referralAccount=<DEXSATO_REFERRAL_ACCOUNT>
  &referralFee=50
```

### Wallet-bound order request

The same referral policy must be sent with the connected wallet as `taker`.

```text
GET /swap/v2/order
  ?inputMint=<INPUT_MINT>
  &outputMint=<OUTPUT_MINT>
  &amount=<RAW_INPUT_AMOUNT>
  &taker=<CONNECTED_WALLET>
  &referralAccount=<DEXSATO_REFERRAL_ACCOUNT>
  &referralFee=50
```

### Execute request

No separate fee parameters are added to `/swap/v2/execute`.

```json
{
  "signedTransaction": "<UNCHANGED_WALLET_SIGNED_TRANSACTION>",
  "requestId": "<ORDER_REQUEST_ID>"
}
```

The fee is already represented by the Jupiter order and its assembled transaction.

## Parameter rules

| Field | Rule |
|---|---|
| `referralAccount` | Jupiter Referral Program account address |
| `referralFee` | Number in basis points |
| Valid fee range | 50–255 bps |
| Pairing | Both fields must be supplied together |
| `taker` omitted | Quote only; `transaction` is null |
| `taker` supplied | Assembled transaction may be returned |
| Swap mode | Referral parameters cause `mode: manual` |
| Execute | Uses the `requestId` from the order |

## Verified response fields

DexSato must treat these fields as separate facts:

| Response field | Meaning |
|---|---|
| `referralAccount` | Referral account applied to the order |
| `feeMint` | Token mint selected by Jupiter for fee collection |
| `feeBps` | Total fee rate charged for the swap |
| `platformFee.amount` | Jupiter platform-fee raw amount |
| `platformFee.feeBps` | Jupiter's own platform fee rate |
| `platformFee.feeMint` | Mint used for Jupiter platform fee |
| `mode` | `ultra` or `manual` based on optional parameters |
| `transaction` | Null without taker; base64 transaction with taker |
| `requestId` | Identifier required by `/execute` |

`feeBps` and `platformFee.feeBps` are not interchangeable. The top-level value is the total fee rate, while `platformFee.feeBps` represents the Jupiter platform portion.

## Fee collection model

- Jupiter takes 20% of the configured integrator fee.
- No separate Jupiter platform fee is added when referral mode is active.
- Jupiter selects `feeMint` using its priority order:
  1. SOL;
  2. stablecoins;
  3. liquid-staked tokens;
  4. blue-chip tokens;
  5. other tokens.
- SPL and Token2022 fee tokens are supported.
- A referral token account must already exist for the selected `feeMint`.
- If that token account is missing, Jupiter can still return and execute the order without collecting the DexSato fee.

Therefore, a successful swap is not evidence that DexSato received its fee.

## Required Jupiter accounts

DexSato needs:

1. one Referral Program `referralAccount`;
2. one `referralTokenAccount` for each expected fee mint;
3. a wallet under DexSato control to initialize and later claim the referral fees.

Start with referral token accounts for:

- wrapped SOL mint: `So11111111111111111111111111111111111111112`;
- USDC mint, after verifying the canonical mainnet mint during setup.

More token accounts can be added after observing actual `feeMint` values.

The setup/claim wallet private key is needed only for the separate administrative account-creation and fee-claiming operation. It must never be placed in the DexSato web application, repository or Railway environment.

## Routing impact

Current Swap V2 documentation states that `referralAccount` plus `referralFee` is supported across Metis, JupiterZ, Dflow and OKX. Referral parameters change the order to `mode: manual`, which signals that optional parameters affected swap behaviour.

Do not carry forward the superseded Ultra statement that integrator fees necessarily restrict all orders to Metis. Phase 03 implementation should still record `mode` and `router` so beta testing can measure real execution impact.

## Fail-closed requirements for DexSato

For both the quote-only response and wallet-bound order response, reject the response if:

- `referralAccount` does not equal the server-configured DexSato account;
- `feeBps` does not equal the configured `50` bps in referral mode;
- `feeMint` is absent or invalid;
- the required DexSato referral token account for `feeMint` is unavailable;
- the quote and order return different fee policies;
- input mint, output mint, amount or taker differs from the approved request;
- the order transaction fails the existing signer/program/message validation.

Jupiter's documented behaviour is to allow the swap without the integrator fee when the required referral token account is missing. That availability-first behaviour conflicts with DexSato monetization integrity. DexSato should detect the mismatch and stop before wallet approval rather than silently execute at zero DexSato fee.

## Server configuration contract

Recommended DexSato configuration names:

```text
DEXSATO_JUPITER_FEE_ENABLED=false
DEXSATO_JUPITER_REFERRAL_ACCOUNT=<PUBLIC_REFERRAL_ACCOUNT>
DEXSATO_JUPITER_REFERRAL_FEE_BPS=50
```

Rules:

- production accepts `50–255` only when enabled;
- initial approved value is exactly `50`;
- the browser never sends or overrides these values;
- readiness fails if fee mode is enabled but configuration is missing;
- zero-fee fallback is forbidden when production fee mode is enabled;
- only public addresses belong in runtime configuration.

## User disclosure contract

Before opening the wallet, display:

```text
You pay                  0.1 SOL
DexSato fee              0.50%
Fee token                SOL
Expected receive         <provider-backed output>
Minimum receive          <provider-backed minimum>
Network fee              Confirmed by wallet
```

Recommended copy:

> DexSato charges a 0.50% fee on swaps completed through this interface. The fee token and final amounts are supplied by Jupiter. Your wallet must approve the transaction.

The frontend may format authoritative server values but must not independently invent or calculate the fee policy.

## Required Phase 03-C tests

- configuration accepts 50 and 255 bps;
- configuration rejects 0–49 and values above 255 when enabled;
- client fee fields remain rejected;
- quote request includes the configured referral pair;
- order request includes the identical referral pair;
- execute request contains no client-controlled fee fields;
- quote response validates `referralAccount`, `feeBps` and `feeMint`;
- order response validates the same values;
- missing referral token account or fee mismatch fails closed;
- pending order binds referral account, fee bps and fee mint;
- confirmation summary uses server-authoritative fee data;
- logs exclude API keys, signed transactions and private material;
- zero-fee mode remains explicit while the feature flag is disabled.

## Phase gate

**Phase 03-B status: OFFICIAL CONTRACT VERIFIED.**

Phase 03-C can begin after the user supplies or approves creation of:

1. the DexSato public `referralAccount`;
2. the WSOL referral token account;
3. the initial `50 bps` fee policy.

No production fee should be enabled until a small-value mainnet transaction proves that:

```text
User signs the expected transaction
→ swap settles
→ user receives the expected token
→ DexSato referral balance increases
→ Jupiter receives its documented share
```
