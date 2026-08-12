# DexSato Solana Discovery Radar

**Status:** Canonical Product and Engineering Specification  
**Document type:** Single Source of Truth  
**Target release:** Founder Discovery Radar  
**Initial chain:** Solana only  
**Last updated:** 13 August 2026  

---

## 1. Purpose

This document is the single source of truth for the future construction of the DexSato Solana Discovery Radar.

All product, engineering, data, UI, Telegram, infrastructure, testing, and release decisions for this feature must follow this document unless the founder explicitly approves a revision.

This document does **not** authorize development. Development starts only after the founder explicitly approves a phase.

---

## 2. Product Thesis

DexScreener displays a broad market universe. Users must search, compare, interpret, and accept the risks themselves.

DexSato must not attempt to reproduce every token shown by DexScreener. DexSato must reduce noise by displaying only Solana tokens that pass defined eligibility, evidence, data-maturity, and risk checks.

The core value proposition is:

> **DexSato helps users determine which tokens are worth examining.**

DexSato is not:

- A trading terminal.
- A trade-execution system.
- A guaranteed token-safety service.
- A price-prediction service.
- A buy/sell signal provider.
- Financial advice.

The user remains responsible for every trading or investment decision.

---

## 3. Locked Product Principles

1. Solana is the only discovery chain for the initial version.
2. Core Market Radar remains operational and separate.
3. The existing decision engine is preserved and reused only after a candidate passes discovery gates.
4. Discovery Radar never sends orders or connects to a user wallet.
5. Tokens are identified by contract and pair identity, never by symbol alone.
6. A new listing is not automatically relevant, safe, or eligible.
7. Missing risk data never means low risk.
8. Multiple observations are required before a token may reach `WATCH` or `ALERT`.
9. Telegram is a curated digest, not a stream of every change.
10. AI may explain verified engine evidence later, but AI must not create the underlying decision.
11. The system must use official APIs or permitted data interfaces; it must not depend on scraping the DexScreener website UI.
12. No large all-at-once implementation. Every phase must be independently testable and reversible.

---

## 4. Product Separation

DexSato will contain two independent market products.

| Product | Purpose | Universe | Cadence |
|---|---|---|---|
| Core Market Radar | Stable market benchmark and current production intelligence | Registered markets such as BTC, ETH, SOL, XRP, and SUI | Existing scheduled scans |
| Solana Discovery Radar | Curated discovery of relevant new or emerging Solana tokens | Dynamically discovered Solana pairs | Separate discovery cadence |

Discovery Radar failure must not stop, delay, corrupt, or change Core Market Radar.

---

## 5. Existing Components and Their Roles

The following existing components should be preserved or extended carefully.

| Existing component | Decision | Future role |
|---|---|---|
| `scanner/dexscreener.py` | Preserve | Fetch market data after a candidate address or pair is known |
| `scanner/market_registry.py` | Preserve | Continue protecting the fixed Core Market Radar universe |
| `config/market_pairs.json` | Preserve | Must not become the discovery candidate registry |
| `scanner/normalizer.py` | Extend behind tests | Normalize additional discovery fields |
| `scanner/market_snapshot_builder.py` | Extend behind tests | Populate buyers, sellers, and transactions instead of `None` |
| `scanner/observation_builder.py` | Reuse conceptually | Build address-scoped, multi-window discovery observations |
| `scanner/signal_detector.py` | Do not reuse unchanged | Current direction-only signals are insufficient for microcaps |
| `scanner/decision_engine.py` | Preserve | Evaluate eligible, risk-cleared, sufficiently mature candidates |
| `scanner/runner.py` | Preserve | Remains the Core Market Radar orchestrator |
| `scanner/database.py` | Reuse connection | Persist discovery data in separate tables |
| `application/dto/token_detail_dto.py` | Extend | Base for the Discovery token-detail response |
| `application/services/token_query_service.py` | Refactor later | Query discovery tokens by address identity, not symbol |
| `app/main.py` | Extend later | Expose read-only Discovery pages and APIs |
| `application/telegram_notifier.py` | Extend separately | Send daily or weekly curated discovery digests |
| Health dashboard | Extend | Report discovery collector, API, freshness, and queue health |

### Canonical identity

The canonical identity for every discovered market is:

```text
chain_id + base_token_address + pair_address
```

The token symbol and name are display metadata only. They must never be used as the unique database key.

---

## 6. Target Architecture

```text
Solana discovery source
        |
        v
Discovery Collector
        |
        v
Identity Validation and Deduplication
        |
        v
Eligibility Gate
        |
        v
Risk Gate
        |
        v
Observation Queue
        |
        v
Discovery Intelligence Adapter
        |
        v
Existing Decision Engine
        |
        +------> Discovery Radar Dashboard
        |
        +------> Token Detail Page
        |
        +------> Daily or Weekly Telegram Digest
```

### Isolation rule

Discovery must have its own collector, scheduler, configuration, storage, logs, health state, and orchestration entry point.

It must not add arbitrary dynamic tokens to `config/market_pairs.json` or pass them directly into the existing production runner.

---

## 7. Required External Data Services

### 7.1 Discovery source

Purpose: obtain a dependable stream or list of newly listed Solana tokens or pairs.

Candidates for technical evaluation:

- Birdeye New Listing or filterable Token List API.
- Helius Solana WebSocket/RPC or webhooks.
- Another provider only if its coverage, terms, cost, and stability are documented.

The first implementation should prefer a structured listing API over a custom on-chain listener. A Helius listener should be considered only if the simpler source cannot provide sufficient coverage.

### 7.2 Market-data enrichment

DexScreener may enrich a known token or pair with:

- Pair creation time.
- DEX and quote token.
- Price.
- Liquidity.
- FDV and market cap.
- Volume by available time windows.
- Transaction counts.
- Buy and sell activity.
- Price changes.

DexScreener listing or trending status is metadata, not quality evidence.

### 7.3 Risk and on-chain verification

The initial risk-provider candidates are:

- RugCheck or another Solana-specific risk provider.
- Helius/Solana RPC for independently verifiable on-chain facts.

Minimum desired risk facts:

- Mint authority.
- Freeze authority.
- Holder concentration.
- Deployer or insider concentration when available.
- Liquidity status.
- Sell restriction or honeypot indication when available.
- Token metadata and impersonation warning.
- Known critical warnings.

Provider scores must not be copied blindly. DexSato must store the underlying risk facts and map them into its own explicit eligibility rules.

### 7.4 Provider-adapter requirement

Every external provider must sit behind a provider adapter. Business rules must not depend directly on one vendor response shape.

Each adapter must provide:

- Explicit timeouts.
- Rate-limit awareness.
- Retry with bounded backoff.
- Typed/validated output.
- Error classification.
- Provider name and retrieval timestamp.
- Test fixtures that do not call the live provider.

---

## 8. Discovery Funnel

Every candidate must pass through the following stages:

```text
RAW DISCOVERY
    -> IDENTITY VALIDATED
    -> ELIGIBILITY CHECKED
    -> RISK CHECKED
    -> OBSERVING
    -> DECISION ELIGIBLE
    -> DISPLAYED OR REJECTED
```

### 8.1 Identity validation

Validate:

- Chain is Solana.
- Pair address exists and is valid.
- Base token address exists and is valid.
- Quote token is recorded.
- Pair and token identities agree across providers where possible.
- The pair has not already been processed.

### 8.2 Eligibility gate

Eligibility categories:

- Pair age.
- Minimum liquidity.
- Minimum transaction activity.
- Minimum non-empty volume.
- Approved quote token.
- Data completeness.
- FDV/market-cap sanity.
- Pair persistence across observations.
- No immediately disqualifying market condition.

Exact numeric thresholds are **not locked** in this document. They must be derived from passive data collection and founder review.

### 8.3 Risk gate

Possible outcomes:

- `CLEAR_FOR_OBSERVATION`
- `RISK_NOT_VERIFIED`
- `HIGH_RISK`
- `REJECTED`

Rules:

- `HIGH_RISK` and `REJECTED` candidates must not become `ALERT`.
- `RISK_NOT_VERIFIED` must be clearly displayed and must not become `ALERT`.
- Provider failure must not be interpreted as a clean result.
- Critical risk discovered later must invalidate a previous candidate.

### 8.4 Observation requirement

A candidate must survive multiple observations before promotion.

Observation should evaluate:

- Liquidity stability or deterioration.
- Volume persistence rather than a single spike.
- Buy/sell activity.
- Transaction growth.
- Price movement magnitude.
- Market-cap and FDV changes.
- Data maturity.
- Risk-state changes.

The initial observation cadence and minimum count must be calibrated from collected data.

---

## 9. Discovery Lifecycle

| Status | Meaning | Public visibility |
|---|---|---|
| `DETECTED` | Pair found but not yet screened | No |
| `FILTERED` | Failed a non-critical eligibility rule | No |
| `OBSERVING` | Passed initial gates; collecting evidence | Optional founder-only |
| `WATCH` | Sufficient evidence to merit examination | Yes |
| `ALERT` | Strongest eligible evidence; immediate examination justified | Yes |
| `WEAKENING` | Previously qualified evidence is deteriorating | Yes, with warning |
| `INVALIDATED` | Critical risk or identity problem discovered | Warning/history only |
| `EXPIRED` | Candidate aged out without sufficient evidence | No or history only |

Lifecycle promotion and demotion must be deterministic and auditable.

---

## 10. Discovery Intelligence and Decision Engine

The existing engine must receive a normalized discovery observation only after the candidate passes the required gates.

### Required discovery evidence

- Magnitude-aware price change.
- Magnitude-aware liquidity change.
- Volume persistence.
- Buy/sell activity.
- Transaction activity.
- Pair age and data maturity.
- Risk status.
- Number and timing of observations.

### Required engine changes

The current direction-only signal logic (`UP`, `DOWN`, `STABLE`) is not sufficient for volatile new tokens. Discovery signals require calibrated thresholds and must distinguish noise, moderate movement, and material movement.

The existing Core Market Radar signal behaviour must not be changed as a side effect. Discovery-specific signal rules should be introduced behind a separate configuration or adapter.

### Confidence separation

The product must distinguish:

- **Market evidence strength** — strength of observed activity.
- **Risk clearance** — completeness and outcome of risk checks.
- **Data maturity** — amount and duration of observation.

One combined confidence label must not hide missing risk or immature data.

---

## 11. Database Design

Supabase remains the initial database. Discovery data should use separate tables.

### 11.1 `discovered_pairs`

Purpose: stable identity and first-seen record.

Suggested fields:

- `id`
- `chain_id`
- `pair_address`
- `base_token_address`
- `quote_token_address`
- `symbol`
- `name`
- `dex_id`
- `pair_created_at`
- `first_seen_at`
- `discovery_source`
- `source_payload_version`
- `created_at`

Required uniqueness:

```text
(chain_id, pair_address)
```

### 11.2 `discovery_observations`

Purpose: append-only time-series observations.

Suggested fields:

- `pair_id`
- `observed_at`
- `price_usd`
- `liquidity_usd`
- `fdv_usd`
- `market_cap_usd`
- `volume_5m`, `volume_1h`, `volume_6h`, `volume_24h`
- `buys_5m`, `buys_1h`, `buys_24h`
- `sells_5m`, `sells_1h`, `sells_24h`
- `transactions_5m`, `transactions_1h`, `transactions_24h`
- `price_change_5m`, `price_change_1h`, `price_change_6h`, `price_change_24h`
- `provider`
- `data_complete`

### 11.3 `discovery_screenings`

Purpose: eligibility and risk evaluation history.

Suggested fields:

- `pair_id`
- `screened_at`
- `eligibility_status`
- `failed_criteria`
- `risk_status`
- `risk_warnings`
- `risk_provider`
- `data_maturity`
- `ruleset_version`

### 11.4 `discovery_decisions`

Purpose: immutable output from Discovery Intelligence and the decision engine.

Suggested fields:

- `pair_id`
- `lifecycle_status`
- `recommended_action`
- `market_evidence_strength`
- `risk_clearance`
- `data_maturity`
- `evidence`
- `risk_note`
- `engine_version`
- `ruleset_version`
- `generated_at`

### 11.5 `discovery_alerts`

Purpose: deduplication and audit of Telegram messages.

Suggested fields:

- `pair_id`
- `digest_type`
- `decision_id`
- `delivery_status`
- `sent_at`
- `telegram_message_id`
- `error`

### Retention requirement

Raw rejected candidates should have a shorter retention period than observations and decisions for qualified candidates. Retention periods must be approved after measuring real data volume.

---

## 12. Application APIs

Initial read-only endpoints:

```text
GET /api/discovery
GET /api/discovery/{pair_address}
GET /api/discovery/{pair_address}/history
GET /api/discovery/status
```

### `GET /api/discovery`

Returns only publicly eligible candidates. Suggested filters:

- lifecycle status
- age
- DEX
- liquidity range
- risk status
- sort by latest, evidence strength, liquidity, or activity

### `GET /api/discovery/{pair_address}`

Returns:

- Identity and contract details.
- Current market facts.
- Current lifecycle status.
- Decision evidence.
- Risk facts and warnings.
- Data maturity.
- First and latest observation times.
- External links.

### Security requirements

- Public endpoints are read-only.
- No provider secret may reach browser HTML or JSON.
- Internal collection/admin endpoints, if later required, must be authenticated.
- Responses must be rate-limited or cached before public launch.

---

## 13. User Interface

### 13.1 Discovery Radar page

Display only qualified candidates. It must not imitate a complete exchange or DexScreener directory.

Each card or row should show:

- Official token image when reliably available.
- Symbol, name, and shortened contract address.
- Pair age.
- DEX and pair.
- Current lifecycle status.
- Market evidence strength.
- Risk clearance.
- Data maturity.
- Liquidity, volume, transactions, and buy/sell activity.
- Short, deterministic reason for inclusion.
- `View Analysis` action.

### 13.2 Token detail page

The page must answer:

1. What is this token?
2. Why did DexSato display it?
3. What is changing?
4. What risks are known or unverified?

Required sections:

- Token identity and contract.
- Current market information.
- Transaction and buy/sell activity.
- Evidence timeline.
- Decision-engine output in plain language.
- Risk checks and warnings.
- Data maturity.
- Links to DexScreener and a Solana explorer.
- Clear non-advisory disclaimer.

### Wording standard

Allowed:

> This token remains under observation because liquidity and buyer activity increased across multiple observations.

Not allowed:

> Buy this token now.

---

## 14. Telegram Strategy

Telegram is not part of raw discovery. It is the final distribution layer.

Permitted digest types:

- **Daily Radar:** maximum 3–5 strongest qualified candidates.
- **Weekly Discovery:** most persistent and best-supported candidates of the week.
- **Critical Update:** a previously qualified candidate becomes `WEAKENING` or `INVALIDATED`, or a critical risk appears.

Telegram should be triggered by meaningful lifecycle transitions, not every database change.

Eligible transitions include:

- `OBSERVING -> WATCH`
- `WATCH -> ALERT`
- `WATCH/ALERT -> WEAKENING`
- `ANY -> INVALIDATED`
- A new critical risk warning

Every digest must link back to the dashboard for full evidence.

---

## 15. Runtime and Infrastructure

### 15.1 Founder data-validation stage

Permitted initial environment:

- Existing Windows PC.
- Separate Windows Scheduled Task for discovery.
- Supabase database.
- Existing FastAPI dashboard.
- Existing Cloudflare Tunnel and Access.
- Separate discovery logs and health state.

Suggested experimental collection interval: 5–10 minutes. This is provisional and must respect provider limits.

PC downtime and missed listings are acceptable during private proof-of-concept collection, but must be documented in the results.

### 15.2 Founder beta or public stage

Before relying on the feature for users, move the discovery workload to an always-on environment with:

- Web service for FastAPI.
- Background discovery worker.
- Scheduler or cron.
- Supabase.
- Managed environment secrets.
- Structured logs.
- Health checks.
- Retry and dead-letter handling.
- Monitoring and alerting.

Railway is an eligible future host, subject to the separate Railway migration KIV document. Do not migrate solely to build the initial data proof.

### 15.3 Avoided architecture

Do not permanently split the production system with the collector on a server and the authoritative dashboard snapshot on a founder PC. A temporary experiment may do so only with an explicit expiry and reconciliation plan.

---

## 16. Operational Health

Discovery health must report separately:

- Collector state.
- Last successful discovery poll.
- Last successful enrichment.
- Discovery API status.
- Risk API status.
- Queue depth.
- Oldest pending candidate.
- Last observation timestamp.
- Database write status.
- Rate-limit state.
- Error count.
- Last successful digest.

Core Market Radar health must remain independent.

---

## 17. Primary Risks and Controls

| Risk | Consequence | Required control |
|---|---|---|
| Excessive candidate volume | API cost and database growth | Early deduplication, cheap prefilter, and retention policy |
| Duplicate symbols | Mixed or incorrect data | Address-based canonical identity |
| Rug pull or honeypot | User loss and reputational harm | Risk gate, explicit warnings, no safety guarantee |
| False momentum | Noisy shortlist | Multiple observations and magnitude thresholds |
| Paid boost mistaken as quality | Biased output | Treat boost/ads as metadata only |
| Provider outage | Missing or stale discovery | Timeout, bounded retry, health degradation, no false clearance |
| Rate limiting | Partial data | Queue, caching, batching, and backoff |
| API contract change | Collector failure | Provider adapters and contract tests |
| PC downtime | Missed candidates | Accept only during proof; always-on worker before beta |
| Changes damage Core Radar | Production regression | Separate runner, config, tables, tests, and health |
| Users interpret display as advice | Legal and trust risk | Neutral wording and prominent disclaimer |
| Secrets exposed publicly | Account compromise | Server-side secrets only and environment controls |

---

## 18. Testing Requirements

Each phase requires automated tests before merge.

Minimum suites:

- Provider response validation.
- Identity and deduplication.
- Eligibility rules.
- Risk outcome mapping.
- Observation calculations.
- Lifecycle promotion and demotion.
- Discovery-specific signal thresholds.
- Decision-engine integration.
- Database uniqueness and idempotency.
- API response contracts.
- Telegram digest deduplication.
- Health degradation and recovery.
- Regression tests proving Core Market Radar output remains unchanged.

Live provider tests must not be required for the normal unit-test suite.

---

## 19. Development Phases and Gates

### Phase 0 — Data-source proof

**Objective:** prove that a source can supply sufficiently complete, stable, and affordable new Solana token data.

Deliverables:

- Provider comparison.
- Small read-only proof script or isolated adapter.
- Measured candidates per hour/day.
- Coverage sample.
- Rate limits and cost.
- Missing-field report.
- Provider terms review.

No dashboard, engine decision, or Telegram.

**Go criteria:** one source provides a usable stream with stable identifiers and acceptable cost.  
**No-go criteria:** incomplete coverage, unstable identifiers, prohibited use, or unacceptable cost.

### Phase 1 — Passive collector

**Objective:** collect without influencing users or the engine.

Deliverables:

- Separate discovery runner.
- Identity validation and deduplication.
- Discovery tables.
- DexScreener enrichment.
- Structured logs and health.
- 7–14 days of silent data.

### Phase 2 — Eligibility and risk gates

**Objective:** remove obvious noise and unsafe/unverified candidates.

Deliverables:

- Versioned eligibility rules.
- Risk-provider adapter.
- Explicit gate outcomes.
- Founder report of rejection reasons.

### Phase 3 — Observation lifecycle

**Objective:** identify persistent evidence rather than one-time spikes.

Deliverables:

- Multi-observation queue.
- Lifecycle state machine.
- Discovery-specific signal thresholds.
- Existing decision-engine adapter.
- Outcome tracking.

### Phase 4 — Founder-only dashboard

**Objective:** allow the founder to evaluate quality manually.

Deliverables:

- Discovery list.
- Token detail page.
- Risk and data-maturity display.
- Filters and external links.

No general public access until quality is reviewed.

### Phase 5 — Founder Telegram digest

**Objective:** test whether the shortlist is useful without dashboard monitoring.

Deliverables:

- Daily and/or weekly digest.
- Transition-based critical updates.
- Deduplication and delivery history.

### Phase 6 — Calibration

**Objective:** measure whether DexSato genuinely reduces search time and noise.

Minimum duration: 2–4 weeks.

Measure:

- Candidates discovered.
- Candidates rejected by each gate.
- Candidates reaching `WATCH` and `ALERT`.
- False positives.
- Invalidations after qualification.
- Median time from discovery to display.
- Founder-rated relevance.
- Outcome after selected observation windows.

### Phase 7 — Limited founder beta

Start only after calibration confirms acceptable quality and infrastructure is always-on.

---

## 20. Release Acceptance Criteria

Discovery Radar is ready for limited users only when:

- Core Market Radar regression tests pass unchanged.
- Canonical address identity is enforced.
- Duplicate processing is idempotent.
- Risk status is visible for every displayed token.
- Unverified risk cannot become `ALERT`.
- Multiple observations are required.
- Stale data is clearly marked.
- Provider outages degrade safely.
- Telegram cannot repeatedly send the same decision.
- Public APIs expose no secrets.
- The dashboard contains neutral language and disclaimers.
- Founder calibration demonstrates meaningful noise reduction.
- Collector and dashboard run in an always-on supported environment.

---

## 21. Explicitly Out of Scope for Initial Version

- Additional chains.
- Wallet connection.
- Trade execution.
- Copy trading.
- Automated portfolio actions.
- User-generated token submissions.
- AI-generated trade recommendations.
- Social sentiment as a primary decision source.
- Full historical charting platform.
- Reproducing the entire DexScreener catalog.
- Real-time Telegram messages for every new pair.
- Paid promotion influencing eligibility or ranking.

---

## 22. Open Decisions Requiring Evidence

The following must remain open until Phase 0 or passive collection provides evidence:

- Primary discovery provider.
- Risk provider.
- Provider plan and budget.
- Polling cadence.
- Pair age limits.
- Minimum liquidity.
- Minimum volume and transactions.
- Approved quote tokens.
- Required observation count and duration.
- Magnitude thresholds.
- Candidate retention periods.
- Daily versus weekly default Telegram cadence.
- Exact public ranking method.

These values must not be selected merely because they appear reasonable.

---

## 23. Change-Control Rules

1. This file is the canonical specification.
2. Any scope or architectural change must update this file in the same pull request.
3. Implementation PRs must cite the relevant phase and section.
4. A PR must not combine multiple major phases without founder approval.
5. Core Market Radar changes require separate justification and regression evidence.
6. Provider credentials, secrets, and paid-plan details must never be committed.
7. Threshold changes must be versioned and supported by calibration evidence.
8. An implementation detail may change without founder approval only when it does not alter product behaviour, risk policy, scope, or operating cost materially.

---

## 24. Recommended First Authorized Task

When the founder authorizes development, begin with **Phase 0 — Data-source proof only**.

The first task must answer:

> Can DexSato obtain a reliable, sufficiently complete, stable, and affordable stream of newly listed Solana pairs with canonical token and pair identities?

Do not build the dashboard, Telegram digest, AI summary, lifecycle engine, or production worker before this question is answered.

---

## 25. Final Product Statement

> DexSato is a curated decision-intelligence layer for discovering Solana tokens worth examining. It reduces market noise by combining eligibility screening, repeated observation, explicit risk information, and deterministic decision evidence. It informs the user without executing or directing a trade.

