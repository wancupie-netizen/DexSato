# Phase 03-A — Jupiter Fee Mechanism Audit

Date: 2026-08-28  
Scope: Read-only audit of the supplied DexSato Phase 03-A source bundle  
Baseline: Phase 02 closed; final regression reported as 331 passed

## Executive conclusion

DexSato currently charges no integrator/platform fee. The application intentionally enforces `0 bps` in the quote response, order response, execution response, browser client and automated tests.

The non-custodial model remains intact: DexSato requests an unsigned Jupiter transaction, the connected wallet signs it, and DexSato relays only the unchanged signed transaction. No private key, seed phrase or custody mechanism is present in the audited flow.

Phase 03 fee implementation is not ready to begin until the exact fee contract for Jupiter `/swap/v2/order` is verified against the current official Jupiter documentation and the DexSato public fee/referral account and fee rate are approved. Legacy Swap API fee parameters must not be copied into this endpoint by assumption.

## Current transaction flow

1. The browser requests a quote from DexSato.
2. DexSato calls `GET https://api.jup.ag/swap/v2/order` without a taker.
3. The browser displays the quote and confirmation summary.
4. The browser requests an order with amount, wallet and risk acknowledgement.
5. DexSato calls the same Jupiter order endpoint with the connected wallet as `taker`.
6. DexSato validates the returned unsigned Solana transaction.
7. The wallet signs the transaction locally.
8. DexSato verifies the signed message is unchanged.
9. DexSato relays it to `POST https://api.jup.ag/swap/v2/execute`.

## Verified findings from the supplied code

| Area | Current implementation | Audit result |
|---|---|---|
| Quote endpoint | `/swap/v2/order` without `taker` | Quote-only policy is explicit |
| Order endpoint | `/swap/v2/order` with `taker` | Unsigned wallet-bound order |
| Execute endpoint | `/swap/v2/execute` | Relays the wallet-signed transaction |
| DexSato fee request | No fee/referral parameter sent | No DexSato fee configured |
| Quote response | `dexsato_integrator_fee_bps: 0` | Explicit zero-fee contract |
| Order response | `dexsato_integrator_fee_bps: 0` | Explicit zero-fee contract |
| Execute response | `dexsato_integrator_fee_bps: 0` | Explicit zero-fee contract |
| Browser enforcement | Rejects quote/order unless fee equals zero | Fee addition requires coordinated UI change |
| Jupiter fee parsing | Reads provider `platformFee` when present | Informational only; not configured by DexSato |
| Fee disclosure UI | No DexSato fee row | Production transparency requirement not met yet |
| Client fee controls | None | Good: user cannot currently select or alter a fee |
| Private keys | Not requested, stored or transmitted | Non-custodial boundary preserved |

## Security strengths to preserve

- The server owns Jupiter API communication and does not expose the API key to the browser.
- The client cannot submit fee parameters through the public DexSato order route.
- The connected wallet must be the sole transaction signer.
- The returned transaction must contain an approved Jupiter program.
- The unsigned message digest is stored and compared with the wallet-signed message.
- Token, wallet, input amount, expiry and request identity are validated.
- Replayed, altered, expired and concurrent submissions are rejected.
- Pending orders are bounded globally and per wallet.

## Production blockers

### P03-A-01 — Official `/swap/v2/order` fee contract is not yet locked

The exact current Jupiter fields, account requirements, supported fee mint behaviour, response fields and limits for this endpoint must be verified from official Jupiter documentation before any code change.

Do not assume that Legacy Swap API fields such as `platformFeeBps` and `feeAccount` apply unchanged to `/swap/v2/order`. Likewise, do not assume a referral field name solely from an existing test assertion.

### P03-A-02 — DexSato fee policy has not been approved

The following decisions are still required:

- official fee rate in basis points;
- public DexSato fee/referral account;
- proof that DexSato controls that account;
- supported fee token or tokens;
- whether the provider deducts the fee from input or output;
- rounding and minimum-fee behaviour.

No private key belongs in DexSato configuration. Only the public account address should be required by the application.

### P03-A-03 — Pending-order policy does not bind fee facts

The pending order currently binds token, wallet, expiry, message digest, signer index and last valid block height. It does not bind:

- configured fee bps;
- fee account;
- fee mint;
- quoted fee amount;
- expected output after fee.

These values must become part of the server-side order policy so configuration drift or a provider mismatch fails closed before signing or execution.

### P03-A-04 — Transaction validation is not fee-aware

The validator checks signers, programs, wallet authority and input transfer limits, but it does not validate the intended fee recipient or fee policy. Phase 03 must define the strongest validation that is possible for the exact transaction format returned by Jupiter.

At minimum, the server must validate the provider response against immutable server configuration and bind the exact returned transaction message. If the fee account and fee amount can be verified from transaction accounts/instructions, they should also be checked explicitly.

### P03-A-05 — User disclosure is incomplete

Before wallet approval the current UI shows the trade amount, expected output, minimum output, price impact, slippage and network fee, but no DexSato fee.

The confirmation must show, using provider-backed values:

- You pay;
- DexSato fee, including percentage and token amount;
- expected receive after fee;
- minimum receive;
- estimated network fee;
- fee recipient label or disclosure link where appropriate.

No invented fee amount may be displayed. If Jupiter cannot return an authoritative amount before signing, the UI must explain exactly what is known and how the fee is calculated.

## Required implementation contract for Phase 03-B

1. Fee configuration is server-only and immutable per process.
2. Production startup/readiness fails when fee mode is enabled but configuration is incomplete or invalid.
3. Public request models reject unknown client fee fields.
4. Quote and order use the same approved fee policy.
5. Provider fee response must match the configured policy.
6. Pending orders bind all authoritative fee facts.
7. The browser displays fee facts but never calculates, selects or submits the fee policy.
8. Wallet signing remains the only authorization to move user funds.
9. The execute route accepts only the exact signed transaction created for that pending order.
10. Logs may record fee bps, fee mint and public fee account, but never wallet secrets or signed transaction material.

## Recommended configuration shape

Names below are internal DexSato recommendations, not claims about Jupiter parameter names:

```text
DEXSATO_JUPITER_FEE_ENABLED=false
DEXSATO_JUPITER_FEE_BPS=<approved integer>
DEXSATO_JUPITER_FEE_ACCOUNT=<approved public Solana address>
```

Additional configuration should be introduced only if the verified Jupiter contract requires it. Production must not silently fall back to zero fee when fee mode is expected to be enabled.

## Required tests

- zero-fee mode remains explicit and backward compatible;
- enabled fee mode requires valid bps and public account;
- client-supplied fee fields are rejected;
- quote request contains the exact server fee policy;
- order request contains the same policy;
- provider fee mismatch fails closed;
- missing or changed fee response fails closed;
- pending order binds fee bps, account, mint and amount;
- altered signed transaction remains rejected;
- confirmation displays exact provider-backed fee details;
- readiness fails for incomplete production fee configuration;
- logs do not expose API keys or transaction material;
- successful small-value mainnet test proves fee receipt on-chain.

## Gate decision

**Phase 03-A status: CODE AUDIT COMPLETE — IMPLEMENTATION NOT YET APPROVED.**

Phase 03-B may start only after:

1. the current official Jupiter `/swap/v2/order` fee specification is recorded;
2. the DexSato fee rate is approved;
3. the public fee/referral account is supplied and ownership verified;
4. supported fee token behaviour is confirmed;
5. the user-facing disclosure format is approved.

## Important future reference

- Jupiter's own provider/platform fee and the DexSato integrator fee must not be conflated.
- A public fee account is not a secret; its private key must never enter the application.
- The frontend is a display and approval surface, not the fee-policy authority.
- A successful quote is not proof of on-chain fee receipt.
- Final acceptance requires a controlled small-value mainnet swap and independent on-chain verification.
