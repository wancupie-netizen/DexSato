# Phase 03-E Closure Audit

**Project:** DexSato / AlphaRadar
**Phase:** 03-E — Fee-Bearing Transaction Validation and Controlled Swap Test
**Closure date:** 2026-09-02 (UTC)
**Closure status:** `FINALIZED_VERIFIED`
**Production fee execution after closure:** Disabled

## 1. Executive summary

Phase 03-E successfully validated one tightly bounded, user-approved,
fee-bearing Jupiter swap on Solana Mainnet. The transaction finalized on-chain,
and the verified referral WSOL token account increased by exactly `5000` raw
units, matching a 50-bps fee on an input of `0.001 SOL`.

The successful test does **not** authorize unrestricted production fee
execution. Immediately after verification, the fee flag and one-shot mode were
disabled and the gate-path environment variable was removed. The consumed gate
cannot be reused.

## 2. Final on-chain evidence

| Evidence | Verified value |
| --- | --- |
| Transaction signature | `3PEdRJDZR8RAPYHvtRmkcKUV3BUKJergyAHUxaBD1PPWPWyXwmEYVgc9eJH6ha9HSbcDoMVkDqax9TRKpgNBEJCb` |
| Explorer | <https://solscan.io/tx/3PEdRJDZR8RAPYHvtRmkcKUV3BUKJergyAHUxaBD1PPWPWyXwmEYVgc9eJH6ha9HSbcDoMVkDqax9TRKpgNBEJCb> |
| Finalized slot | `443580807` |
| Gate ID | `27651ee2d00828c7ac47508ee4fac9d8` |
| Gate terminal state | `FINALIZED_VERIFIED` |
| Provider status | `Success` |
| Attempt count | `1` |
| Referral pre-balance | `0` raw WSOL |
| Referral post-balance | `5000` raw WSOL |
| Referral delta | `5000` raw WSOL |
| Fee receipt verified | `true` |

Arithmetic checked:

```text
Input                  = 0.001 SOL
Input raw              = 1,000,000 lamports
Integrator fee         = 50 bps = 0.50%
Expected gross accrual = 1,000,000 × 50 / 10,000
                       = 5,000 raw WSOL
Observed accrual       = 5,000 raw WSOL
```

This proves gross referral accrual for the tested transaction. It does not prove
that a later ClaimV2 operation has run or that the accrued amount has already
been distributed according to partner/Jupiter claim-share semantics.

## 3. Controlled execution contract

The live test was constrained to all of the following:

| Control | Bound value |
| --- | --- |
| Output token | TAP |
| Output mint | `ADcF26nFGKMuRZ7va5361H2PCHCDRi2FmeJBkX3Spump` |
| Input mint | Wrapped SOL |
| Input amount | Exactly `0.001 SOL` / `1,000,000` lamports |
| Fee | Exactly `50` bps |
| User wallet | `J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs` |
| Referral account | `5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ` |
| Referral WSOL ATA | `3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv` |
| Confirmation | Explicit one-shot confirmation phrase |
| Gate lifetime | Ten minutes |
| Retry policy | Only the identical signed transaction |
| Signing authority | Connected self-custody wallet only |

The gate lifecycle for the successful attempt was:

```text
ARMED → BOUND → CONSUMED → FINALIZATION_PENDING → FINALIZED_VERIFIED
```

## 4. Validation work completed

Phase 03-E covered the following controls:

1. Offline fee-transaction evidence harness.
2. Unsigned Jupiter order capture without signing or broadcasting.
3. Versioned-transaction and lookup-table account resolution.
4. Jupiter instruction and inner-instruction evidence decoding.
5. Program-identity and CPI review.
6. Typed pool/vault binding for reviewed routing programs.
7. Exact minimum-output boundary and floor/ceil hypothesis tests.
8. Minimum-output contract and unsigned message-byte binding.
9. Prepared-order identity and account-snapshot binding.
10. Live read-only account identity verification.
11. RouteV2 and in-transaction ATA lifecycle handling.
12. Fresh fee-bearing simulation and gross referral balance-delta validation.
13. ClaimV2 source/account and compiled-account investigations.
14. One-shot live approval gate and finalized receipt verification.
15. Safe failure diagnostics that retain only bounded codes and reviewed reason
    classifications.

## 5. Regression evidence

Final regression immediately before the successful controlled test:

```text
Python:     711 passed, 343 subtests passed
JavaScript: 7 passed, 0 failed
```

The JavaScript regression explicitly verified that:

- ordinary fee-enabled previews cannot prepare or sign;
- only the exact armed one-shot TAP contract can advance to review;
- the actual prepared order requires a separate review click;
- an amount change invalidates the prepared order;
- no signing occurs before explicit wallet confirmation.

## 6. Failed attempt and diagnostic improvement

The first controlled gate (`002`) reached provider status `Failed`, produced no
signature, and was permanently closed after one attempt. The original gate format
did not retain a safe provider failure classification, so the precise upstream
failure could not be recovered after the browser/server session ended.

E.5C corrected this observability gap for future failures. Failed gates may now
retain only:

- `failure_reason`, selected from a fixed safe classification;
- `failure_code`, only when supplied as a bounded integer.

Raw Jupiter error text, API keys, credential-bearing RPC URLs, signed or unsigned
transaction bytes, and arbitrary provider content are not persisted. The
successful `003` attempt did not require these failure fields.

## 7. Security properties retained

- DexSato never receives a seed phrase or private key.
- The connected wallet is the sole transaction signer and payer.
- The unsigned transaction is bound by message digest before wallet approval.
- A signed retry cannot substitute a different transaction.
- Token, wallet, amount, fee policy, referral account and transaction identity
  are checked server-side.
- The one-shot gate is persisted and consumed before execution.
- Failed, consumed, expired or finalized gates cannot be re-armed or reused.
- Fee-bearing execution remains fail-closed without explicit one-shot mode and a
  valid ARMED gate.
- Fee receipt verification requires finalized RPC evidence and the exact expected
  referral balance delta.

## 8. Post-test safe state

The environment was returned to:

```text
DEXSATO_JUPITER_FEE_ENABLED=false
DEXSATO_JUPITER_ONE_SHOT_MODE=false
DEXSATO_JUPITER_ONE_SHOT_GATE_PATH=<absent>
```

Therefore the successful test is not an implicit production rollout. A normal
fee-bearing swap cannot be executed through the controlled path in this state.

## 9. Repository evidence

The E.5–E.5C controls were committed as:

```text
3566d25 test: gate one-shot Jupiter swap and retain safe failure diagnostics
```

Earlier Phase 03 evidence includes the server-side fee policy, on-chain referral
verification, Ultra V2 ATA correction, offline transaction harness, instruction
decoding, pool/minimum-output validation, identity binding and ClaimV2 research.
Refer to the corresponding `PHASE03*.md` documents and their Git commits for the
detailed installation and test history.

## 10. Evidence retention

Retain the following outside Git or in an approved secure evidence store:

- finalized gate file `tap-one-shot-gate-003.json`;
- failed gate file from attempt `002`;
- receipt verifier output;
- transaction signature and finalized slot;
- regression output showing 711 Python tests and 7 JavaScript tests;
- any read-only simulation/capture reports needed for the audit trail.

Do not commit:

- `runtime/`;
- gate files;
- `.env`;
- RPC URLs or provider API keys;
- installer backup directories;
- signed or unsigned live transaction captures unless separately reviewed and
  intentionally sanitized.

## 11. Residual risks and exclusions

The following remain outside this closure:

1. **ClaimV2 live execution:** no live referral claim was signed or submitted.
2. **Claim-share settlement:** gross accrual was proven; the eventual 80/20 claim
   distribution was not proven by this swap receipt.
3. **Unrestricted production monetization:** not enabled or approved.
4. **Multi-user/multi-worker fee execution:** the test covered one exact wallet,
   token, amount and persistent one-shot gate.
5. **Provider and program changes:** Jupiter, referral program, IDL, routing and
   dependency changes require re-review before production activation.
6. **Token investment risk:** transaction-safety validation is not token-security
   verification, endorsement or financial advice.
7. **Uncommitted ClaimV2 working tree:** ClaimV2-related files or modifications
   remaining outside commit `3566d25` must be reviewed and committed separately;
   they are not authorized by this closure.

## 12. Closure decision

Phase 03-E is closed with the following result:

```text
CONTROLLED FEE-BEARING SWAP       PASS
WALLET-SIGNED TRANSACTION         PASS
SOLANA FINALITY                   PASS
EXPECTED GROSS REFERRAL ACCRUAL   PASS (5000 raw WSOL)
FEE RECEIPT VERIFICATION          PASS
ONE-SHOT GATE CONSUMPTION         PASS
POST-TEST EXECUTION DISABLEMENT   PASS
LIVE CLAIMV2                      NOT PERFORMED
PRODUCTION MONETIZATION ROLLOUT   NOT APPROVED
```

**Final conclusion:** the exact one-shot fee-bearing swap contract is supported
by finalized on-chain evidence. Further monetization work must begin from a new,
separately approved phase and must not reuse the completed gate or treat this
controlled test as blanket production authorization.
