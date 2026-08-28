# DexSato Phase 02 — Final Security Audit Record

**Project:** DexSato Solana Discovery Terminal  
**Audit closure date:** 28 August 2026  
**Final audited baseline:** `8be19ff`  
**Final regression:** `331 passed`  
**Dependency audit:** No known vulnerabilities reported by `pip-audit` at the time of review

## 1. Purpose

This document records the security and production-hardening work completed in
Phase 02. It is intended as a future reference before monetization, deployment,
private beta, public launch, or any significant architecture change.

This record is not a permanent guarantee that the application has no
vulnerabilities. It describes the code, configuration rules, tests, and known
constraints verified at the baseline above. The deployed environment must be
audited again during Phase 05.

## 2. Product and trust boundary

The audited product scope is:

- Solana Discovery Terminal;
- user-connected Solana wallet;
- Jupiter quote, order, wallet signing, and execution flow;
- persistent Solana discovery archive;
- non-custodial transaction architecture;
- no public login, subscription, or payment system.

DexSato must never request, receive, log, store, or transmit a wallet seed phrase
or private key. The user signs every transaction in their wallet. DexSato only
relays the wallet-signed transaction that matches the reviewed server-side order.

## 3. Phase 02 execution record

| Workstream | Commit | Result |
|---|---|---|
| P0-A — Application Boundary Hardening | `d216ec1` | Complete |
| P0-B — Safe Errors, Security Headers & Readiness | `74cde5f` | Complete |
| P0-C — Jupiter Pending-Order Isolation & Async Requests | `eae438f` | Complete |
| P0-D — Transaction, Signer, Program & Trade Validation | `c5c1188` | Complete |
| P0-E — Logging, Dependency Review & Regression | `f40b038` | Complete |
| P1-A — No-Store Responses & Limiter Lifecycle | `3d27614` | Complete |
| P1-B — Persistent Storage & Single-Worker Contract | `b0dec17` | Complete |
| P1-C — Readiness Integrity & Configuration Validation | `5979f31` | Complete |
| P1-D — Clean Checkout & Collector Packaging | `8be19ff` | Complete |

## 4. Security controls implemented

### 4.1 HTTP application boundary

- Production trusted hosts must be explicitly configured.
- Wildcard trusted hosts are rejected in production.
- Request bodies are bounded before and during body consumption.
- Sensitive endpoints have route-specific rate limits.
- Rate-limit buckets are bounded and inactive buckets are removed.
- New rate-limit buckets fail closed when process capacity is reached.
- Internal routes are hidden by default in production.
- Enabled internal routes require a constant-time checked operator bearer token.
- Development/debug documentation endpoints remain disabled by the application.

### 4.2 Browser and response security

- Content Security Policy is attached to responses.
- Framing is denied.
- MIME sniffing is disabled.
- Referrer information is suppressed.
- Camera, microphone, and geolocation permissions are disabled.
- HSTS is enabled in production.
- Server-generated request IDs are used; client-provided IDs are not trusted.
- Jupiter and operator responses override downstream caching with:

  ```text
  Cache-Control: no-store, max-age=0
  Pragma: no-cache
  Expires: 0
  ```

### 4.3 Safe errors and logging

- Provider exception details are not returned to users.
- Only reviewed, actionable Jupiter messages may be shown publicly.
- Production logs use structured JSON metadata.
- Logged routes replace token mints with a safe route template.
- Logs exclude request bodies, signed transactions, wallets, token mints, query
  values, authorization headers, API keys, upstream request IDs, and exception
  messages.
- Production `DEBUG` logging is rejected.
- Raw Uvicorn access logging is disabled by the official production launcher.

### 4.4 Wallet and Jupiter transaction controls

- Wallet and mint addresses are validated.
- Swap amounts are bounded and validated server-side.
- Explicit risk acknowledgement is required before order construction.
- Pending orders are bound to token, wallet, amount, message digest, expiration,
  and wallet signer position.
- Extra transaction signers are rejected.
- The connected wallet must be the authorized signer.
- Unapproved top-level programs are rejected.
- Cumulative system transfers above the approved SOL amount are rejected.
- Provider token, wallet, amount, and transaction mismatches are rejected.
- Modified, unsigned, expired, replayed, or concurrent duplicate submissions are
  rejected.
- A retry must use exactly the same wallet-signed transaction.
- Blocking Jupiter work is moved outside the asynchronous event-loop thread.
- Users may request a trade for a previously discovered token; qualification is
  analysis context and not a trading prohibition.

### 4.5 User isolation

- Pending Jupiter orders are bound to the originating wallet and request.
- Per-wallet pending-order limits prevent one wallet from filling the global
  pending-order store.
- One wallet cannot execute another wallet's pending order.
- No wallet private material is accepted by the API schema.

### 4.6 Persistent discovery storage

- Web app, feed, SQLite archive, Python collector, and PowerShell collector resolve
  the same storage directory.
- Development preserves the existing local storage path.
- Production requires an absolute, existing, writable persistent-volume path.
- Production startup fails closed when the storage contract is invalid.
- Temporary storage write probes are removed immediately.
- No existing archive is automatically moved or deleted.

### 4.7 Readiness integrity

`/health/live` confirms process availability only.

`/health/ready` performs local checks without calling external providers. It
requires:

- static assets;
- valid `state.json` with a `candidates` object;
- valid `status.json` with a `metrics` object;
- readable SQLite storage;
- successful `PRAGMA quick_check`;
- the required `discoveries` table;
- valid production configuration.

The readiness response exposes only component states. It does not expose paths,
credentials, provider payloads, or exception details.

### 4.8 Dependencies and clean packaging

- Direct production dependencies are exactly pinned.
- `pip check` reported no broken requirements.
- `pip-audit -r requirements.txt` reported no known vulnerabilities at audit time.
- The collector's runtime import graph was verified in an isolated clean tree.
- `research/phase0_solana_discovery_probe_v2.py` contains no embedded credentials.
- Collector import performs no network call and writes no state.
- `.env`, backup files, old output, and other untracked files are not required by
  the clean collector runtime.

## 5. Required production configuration

Secrets must be provided through the deployment environment and never committed.

```text
DEXSATO_ENV=production
HOST=0.0.0.0
PORT=<platform supplied port>
DEXSATO_ALLOWED_HOSTS=<exact production hostnames>
DEXSATO_DISCOVERY_STORAGE_DIR=/data
DEXSATO_WEB_WORKERS=1
DEXSATO_LOG_LEVEL=INFO
JUPITER_API_KEY=<server-side secret>
BIRDEYE_API_KEY=<server-side secret>
SOLANA_RPC_URL=https://<reviewed RPC endpoint>
```

Internal endpoints should remain disabled:

```text
DEXSATO_INTERNAL_ENDPOINTS_ENABLED=false
```

If they are explicitly enabled, `DEXSATO_OPERATOR_TOKEN` must be a random value
of at least 32 characters.

The official production start command is:

```text
python -m application.production_server
```

## 6. Verified results

| Verification | Result |
|---|---|
| Final full regression | `331 passed` |
| Readiness — static | `ready` |
| Readiness — collector | `ready` |
| Readiness — archive | `ready` |
| Readiness — configuration | `ready` |
| Direct dependencies installed as reviewed | Passed |
| `pip check` | No broken requirements |
| `pip-audit` | No known vulnerabilities at audit time |
| Clean collector import | Passed |
| Embedded collector secret scan | None found |

## 7. Accepted constraints and residual risks

These items are documented constraints, not completed protections:

1. **Single process and replica**  
   Pending Jupiter orders and rate limits remain process-local. Production must
   use exactly one web worker and one replica until a shared store is introduced.

2. **Restart behaviour**  
   A process restart intentionally removes pending orders. Users must request a
   fresh Jupiter order after restart.

3. **CSP inline allowances**  
   The current UI still requires `'unsafe-inline'` for scripts/styles. Migrating
   inline assets to static files or CSP nonces remains future hardening.

4. **External-provider availability**  
   Readiness does not contact Jupiter, Birdeye, DexScreener, or Solana RPC. A
   `ready` response does not guarantee that an upstream provider is available.

5. **Dependency audit timing**  
   “No known vulnerabilities” reflects the advisory database at audit time.
   Dependencies must be audited again before deployment and public launch.

6. **Deployment not yet audited**  
   Railway, HTTPS termination, proxy behaviour, volume durability, exposed routes,
   domain configuration, and live logs have not yet been verified. These belong
   to Phases 04 and 05.

7. **Jupiter fee not yet implemented**  
   Phase 02 validates the existing transaction boundary. Fee account ownership,
   fee calculation, fee transparency, and on-chain fee receipt belong to Phase 03.

## 8. Required re-audit triggers

Repeat the relevant security review whenever any of these changes:

- Jupiter API version, order format, transaction structure, or program allowlist;
- fee account, fee token, or fee calculation;
- wallet connection or signing library;
- supported chain or RPC provider;
- number of workers or replicas;
- persistent storage technology or mount path;
- reverse proxy, domain, CORS, CSP, or CDN configuration;
- authentication, login, subscription, or user database;
- public/internal endpoint exposure;
- direct or transitive dependency versions;
- collector provider or discovery qualification logic.

## 9. Pre-deployment verification checklist

Before Railway private deployment:

- [ ] Deploy only committed files from a clean checkout.
- [ ] Confirm no `.env`, backup, patch, or local output file is committed.
- [ ] Attach a persistent volume and set its absolute path.
- [ ] Use one worker and one replica.
- [ ] Configure exact allowed hosts.
- [ ] Add server-side Jupiter and Birdeye keys.
- [ ] Configure a reviewed HTTPS Solana RPC endpoint.
- [ ] Keep internal endpoints disabled unless operationally required.
- [ ] Run `python -m pip check`.
- [ ] Run `python -m pip_audit -r requirements.txt`.
- [ ] Run `python -m pytest -v`.
- [ ] Verify `/health/live` and `/health/ready`.
- [ ] Inspect production logs for metadata only.
- [ ] Confirm sensitive Jupiter responses contain `Cache-Control: no-store`.
- [ ] Perform the deployed security and transaction audit in Phase 05.

## 10. Closure decision

At baseline `8be19ff`, Phase 02 P0-A through P1-D is complete. No known critical
or P0 security issue remains in the reviewed code. DexSato may proceed to Phase
03 design and implementation, subject to the accepted constraints in this record.

Phase 03 must preserve the non-custodial boundary and must not weaken signer,
program, amount, replay, logging, caching, storage, or readiness controls recorded
here.
