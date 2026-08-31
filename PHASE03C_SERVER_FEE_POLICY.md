# Phase 03-C — Server-Side Fee Policy & Referral Validation

Date: 2026-08-31. Baseline: supplied phase03a audit package.

## Scope and activation boundary

Server-side referral policy and provider-response validation are implemented.
This is NOT on-chain referral ownership verification or proof of fee receipt.
Fee-enabled swap orders remain hard-blocked until reviewed fee disclosure and
on-chain validation are implemented in the next phase. There is no environment
switch that bypasses that execution gate. Existing fee-disabled trading remains
available, including previously discovered tokens; discovery qualification is
not reintroduced as a trading restriction.

## Configuration

Keep DEXSATO_JUPITER_FEE_ENABLED=false. The installer only changes .env.example,
never your real .env or Railway settings. Example public Ultra referral account:
5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ.
This address was supplied by the owner and has NOT been independently verified
on-chain. Public-key format validation is not ownership validation.

Proposed example rate: 50 bps (0.50%), not an approved or activated charge.
Supported configured range: 50–255 bps, per reviewed Swap V2 documentation.
Configuration is immutable for the process lifetime; changes require restart.
Readiness rejects malformed configuration and changes after policy loading.
Configuration-ready does not mean fee-execution-ready.

## Controls

- Quote and dormant order paths generate referralAccount/referralFee on server.
- Client fee overrides remain rejected by existing strict request schemas.
- Provider account, feeBps and feeMint must match policy; missing fields fail closed.
- Current SOL-input flow requires WSOL fee mint. USDC is recognized for future
  compatible pairs, not enabled as a new input trading feature.
- Pending orders bind immutable fee evidence and policy fingerprint.
- Execute rejects changed policy and retains existing signer, message integrity,
  expiry, replay, concurrency and program checks.
- Execute sends no fee override parameters to Jupiter.
- PROVIDER_VALIDATED means response checks only. No fee-received claim is made.
- dexsato_fee_amount_raw remains null: platformFee.amount is not substituted as
  DexSato revenue. Jupiter base fees may exist while DexSato fees are disabled.

An echoed referral account and matching 50 bps can coincide with default fees;
they cannot establish that a referral token account exists or received funds.
Next phase must validate the correct Ultra project/program and referral account,
derive and read WSOL/USDC referral token accounts using verified official layouts,
check mint/authority, display actual fee economics, and verify an explicitly
approved small-value transaction on-chain. Never provide private keys or seeds.

## Official references reviewed

- https://developers.jup.ag/docs/swap/order-and-execute
- https://developers.jup.ag/docs/api-reference/swap/order

The docs describe a 20% Jupiter share of integrator fees; 50 bps charged is not
50 bps net revenue to DexSato. Reverify contract and share before activation.

## Installation and tests

Run the installer from the AlphaRadar project root, first with --check, then
without it. It validates all target baselines, backs up replaced files, preserves
existing encoding/line endings, and refuses unknown edits. Re-running is safe.
It neither commits changes nor enables fees. Restart your development server.

```powershell
python -m pytest tests/test_jupiter_fee_policy.py tests/test_jupiter_quote_service.py tests/test_jupiter_swap_service.py tests/test_production_readiness.py tests/test_app_bootstrap.py -v
python -m pytest -v
git diff --stat
git diff --check
```

Local verification: 21 new unittest checks, 23 existing quote/swap function
assertions, 9 readiness function assertions and 14 route request rejection cases
passed using a stdlib compatibility runner with mocked upstream calls. Full
pytest/FastAPI integration was NOT run here because dependencies were unavailable.
The dormant fee order path is tested by explicitly mocking the activation gate;
separate tests confirm the real gate rejects fee-enabled orders before network.
No live RPC verification, wallet signing, swap or fee collection was performed.
User-side full regression remains required before commit.
