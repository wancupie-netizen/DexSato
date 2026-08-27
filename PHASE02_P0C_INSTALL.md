# DexSato Phase 02 P0-C — Jupiter Pending-Order Isolation & Async Upstream Requests

Baseline: P0-B commit after `d216ec1`

## Changes

- Jupiter prepare and execute work runs through Starlette's bounded worker-thread path instead of blocking the FastAPI event loop.
- The quote endpoint remains a synchronous FastAPI route and is already dispatched through the framework thread pool.
- A wallet may hold at most four active swap reviews.
- Wallet quota is checked before the Jupiter order request and atomically rechecked when the prepared order is stored.
- Existing token, wallet, message-digest, signer-index, exact-retry, expiry, in-flight, and replay bindings remain intact.
- Reviewed insufficient-balance and wallet-quota messages remain actionable; unreviewed provider detail remains hidden.
- The Jupiter swap suite is now included in default pytest collection.

## Deliberate deployment constraint

Pending orders remain short-lived process memory and contain no private key, seed phrase, or wallet secret. Initial Railway deployment must therefore use exactly one application worker and one replica. A process restart safely invalidates pending reviews and requires the user to request a new quote.

Do not enable multiple workers or replicas until a shared atomic pending-order store is explicitly approved. This avoids adding a production database merely for a two-minute non-custodial review state.

## Regression

```powershell
python -m pytest `
 tests/test_jupiter_swap_service.py `
 tests/test_app_bootstrap.py `
 tests/test_production_security.py -v

python -m pytest -v
```
