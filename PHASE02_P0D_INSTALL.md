# DexSato Phase 02 P0-D — Transaction, Signer, Program & Trade-Universe Validation

Baseline: `eae438f`

## Enforced trade universe

Quote, order, and execute require the mint to exist in the persistent Solana Discovery observations. `currently_qualified`, liquidity, volume, freshness, ranking, and rotating-scan selection are analysis signals and do not block a user-directed swap.

Archive observations retain the complete Jupiter flow with an explicit context notice. Users still review the live quote, acknowledge risk, inspect the wallet transaction, and decide whether to sign.

Exact-mint lookup reads the persistent archive directly, so observations beyond the 100-row front-feed window are not excluded from their token workspace or user-directed Jupiter flow.

## Qualification reason transparency

Every bounded scan records whether a token was evaluated and the actual outcome. Public archive records distinguish `Qualified now`, a specific failed check, provider/verification unavailability, stale collector data, absence from the current collector set, and `Not evaluated in this scan`. Historical evidence is labelled `Last confirmed checks`; it is not presented as a current result.

P0-D.4.2 presents `Last qualified` and `Current scan` as readable relative times. The Jupiter notice is concise: `Previously discovered`, followed by a reminder to check the latest market data and quote.

## Transaction policy

Before a transaction is returned for wallet approval, the server now verifies:

- Solana message structure, instruction vectors, and version-0 address lookup structure;
- the connected wallet is the sole required signer and transaction payer;
- the payer is writable;
- all instruction account indexes are within the combined static/lookup account range;
- every top-level program resolves from a static account and is server-allowed;
- an approved Jupiter v6 instruction exists and includes the connected wallet;
- direct System Program instructions are wallet-sourced transfers only;
- cumulative direct System transfers do not exceed the approved SOL input;
- top-level token instructions are limited to CloseAccount and SyncNative;
- CloseAccount requires the connected wallet;
- associated-token creation uses the connected wallet as payer.

The reviewed built-in top-level program allowlist contains System, Compute Budget, SPL Token, Token-2022, Associated Token Account, and Jupiter v6 programs. `DEXSATO_ALLOWED_SWAP_PROGRAMS` can replace this list only through server configuration; it is never accepted from a client request.

## Deliberate limits

- DexSato integrator fee remains zero. Fee-account validation belongs to Phase 03 after an official account and rate exist.
- A program ID referenced only through an address lookup table is rejected because it cannot be independently resolved by this checkpoint.
- Any real Jupiter transaction outside this policy fails closed. Do not broaden the policy until the exact rejected transaction shape and official program are verified.

## Regression

```powershell
python -m pytest `
 tests/test_jupiter_quote_service.py `
 tests/test_jupiter_swap_service.py `
 tests/test_app_bootstrap.py `
 tests/test_production_security.py -v

python -m pytest -v
```
