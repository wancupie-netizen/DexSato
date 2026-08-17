# DexSato — Architecture, Product Roadmap & Security Baseline

**Status:** Working Baseline  
**Document Type:** Product architecture, technical boundaries, phased roadmap, and security baseline  
**Current Product Priority:** Intelligence Core  
**Future Protocol Chain:** Solana  
**Core Principle:** Intelligence-first, evidence-based, non-custodial, and security-by-design  
**Last Updated:** 17 August 2026

---

## 1. Purpose

This document defines the recommended product and technical direction for DexSato. It separates the current intelligence product from future execution and token-launch protocol capabilities.

It is intended to prevent three common architecture mistakes:

1. Treating the long-term protocol vision as the immediate V1 scope.
2. Mixing off-chain intelligence responsibilities with on-chain custody or execution responsibilities.
3. Building high-risk DeFi infrastructure before product demand, data quality, security capability, and legal position are validated.

This document is a baseline for product planning and architecture discussion. It is not a complete smart-contract specification, security audit, financial forecast, or legal opinion.

---

## 2. Executive Decision

DexSato should be developed in three distinct layers:

| Layer | Primary Function | Recommended Timing | Risk Level |
|---|---|---|---|
| DexSato Intelligence | Observe, interpret, explain, and track market conditions | Current priority | Low–Moderate |
| DexSato Execution | User-signed trading through existing external liquidity infrastructure | After Intelligence validation | Moderate–High |
| DexSato Launch Protocol | SPL token creation, bonding curve, reserves, fees, and graduation | Future phase only | Very High |

The approved development sequence is:

```text
Intelligence Core
      ↓
Reliable Data and Outcome Tracking
      ↓
Creator and Wallet Intelligence
      ↓
Read-only Trading Integration
      ↓
Non-custodial Execution
      ↓
Token Launch Protocol
```

**Current decision:** Do not treat the bonding curve, token launcher, native AMM, multi-chain support, or native DexSato token as V1 requirements.

---

## 3. Product Positioning

### 3.1 Current Positioning

DexSato is an evidence-based crypto market intelligence system that observes, interprets, and tracks market conditions without promising outcomes.

The current product lifecycle is:

> **Discover → Observe → Interpret → Track → Learn**

### 3.2 Future Positioning

After the intelligence product is validated, DexSato may expand into:

> **Discover → Analyze → Signal → Execute → Track**

The word **Signal** means a detected condition or meaningful change supported by evidence. It must not automatically mean a BUY or SELL instruction.

### 3.3 Long-Term Vision

The long-term protocol vision is:

> **DexSato = Market Intelligence + Non-custodial Execution + Optional Token Launch Infrastructure**

Token launch infrastructure is a future module, not the identity of the current product.

---

## 4. Product Principles

DexSato must remain:

- Intelligence-first.
- Evidence-based.
- Transparent about uncertainty.
- Non-custodial whenever execution is introduced.
- Clear about fees and transaction intent.
- Transparent about creator control and token authority.
- Explicit about data freshness and data limitations.
- Designed for traceable and explainable observations.
- Honest that trading newly launched tokens is highly risky.

DexSato must avoid:

- Guaranteed-return messaging.
- Unexplained BUY/SELL calls.
- Fake certainty or artificial confidence.
- Labels claiming that a token or wallet is “safe”.
- Hidden creator controls.
- Hidden fees or opaque transaction routing.
- Treating heuristics as proof of fraud.
- Custodial wallets in the initial product.
- Native token issuance before a genuine protocol need exists.
- Over-engineering before product-market fit.

---

## 5. Current Intelligence Architecture

### 5.1 Canonical Core Files

The current DexSato intelligence implementation should continue to treat the following files as the canonical core:

- `main.py`
- `runner.py`
- `decision_engine.py`
- `interpretation_engine.py`
- `signal_detector.py`
- `observation_builder.py`

Any future restructuring should preserve clear responsibility boundaries between these components.

### 5.2 Recommended Responsibility Boundaries

| Component | Responsibility | Must Not Do |
|---|---|---|
| Observation Builder | Convert normalized evidence into factual observations | Predict price or execute trades |
| Signal Detector | Detect meaningful conditions and changes | Present unsupported certainty |
| Interpretation Engine | Explain the relationship and context of observations | Modify raw market evidence |
| Decision Engine | Produce a supported status or suggested user response | Place trades or guarantee outcomes |
| Runner | Coordinate processing flow and dependencies | Contain core market logic |
| Main | Application entry point and configuration wiring | Become a monolithic business-logic file |

### 5.3 Recommended Intelligence Flow

```text
Data Sources
     ↓
Normalization and Validation
     ↓
Observation Builder
     ↓
Signal Detector
     ↓
Interpretation Engine
     ↓
Decision Support
     ↓
Outcome Tracking
```

Each stage should produce traceable output that can be inspected independently.

---

## 6. Intelligence Output Contract

Every DexSato analysis should distinguish facts, computed metrics, heuristics, interpretation, and suggested action.

Recommended output structure:

```text
Market State:
Momentum increasing

Verified Observations:
- Five-minute volume increased relative to the 30-minute baseline.
- Unique buyer count increased.
- Sell pressure remains below the recent baseline.

Risk Observations:
- Top-holder concentration is elevated.
- Several early wallets share a funding relationship.

Interpretation:
Short-term activity is strengthening, but holder concentration and
early-wallet relationships increase risk.

Suggested Status:
Worth Monitoring — evidence is not yet sufficient to confirm sustained momentum.

Data Status:
Indexer current as of <timestamp>; no known lag.
```

Suggested qualitative statuses include:

- **Worth Monitoring**
- **Developing Condition**
- **Evidence Strengthening**
- **Risk Elevated**
- **Insufficient Data**
- **Condition Invalidated**

Numeric scores should not replace supporting evidence.

---

## 7. Evidence and Explainability Requirements

Every significant observation should be able to answer:

1. What changed?
2. Compared with which baseline?
3. Over what time window?
4. Which data source supports it?
5. How fresh is the data?
6. What limitations apply?
7. What would invalidate the observation?

DexSato should explicitly classify displayed information as:

| Classification | Meaning |
|---|---|
| Verified On-chain Fact | Directly verifiable from blockchain state |
| Computed Metric | Derived deterministically from defined inputs |
| Heuristic Observation | Pattern detected using defined but non-conclusive rules |
| Interpretation | Contextual explanation of one or more observations |
| Unavailable / Stale | Data is missing, delayed, inconsistent, or outside freshness limits |

---

## 8. Data Integrity Architecture

### 8.1 Source-of-Truth Rules

When execution is introduced, the blockchain remains the source of truth for:

- Token balances.
- SOL balances.
- Mint state.
- Token authority state.
- Transaction status.
- Program state.
- Bonding-curve reserves.
- Graduation state.

The DexSato database may be the source of truth for:

- User preferences.
- Watchlists.
- Alert configuration.
- Subscription records.
- Cached and indexed analytics.
- Observation history.
- Outcome evaluation.

The database must never define ownership of user crypto assets.

### 8.2 Freshness and Degradation

Every real-time view should define:

- Data timestamp.
- Maximum acceptable age.
- Indexer lag threshold.
- RPC failure behaviour.
- Fallback provider behaviour.
- UI state when data is stale.

If critical data is stale or inconsistent, DexSato should degrade safely by disabling affected analysis or execution rather than presenting old data as current.

### 8.3 Outcome Tracking

DexSato should maintain a learning loop:

```text
Observation
    ↓
State at Time of Observation
    ↓
Subsequent State at Defined Intervals
    ↓
Outcome Evaluation
    ↓
Rule and Product Improvement
```

Recommended evaluation windows may include 5 minutes, 30 minutes, 4 hours, and 24 hours, depending on the observation type.

Outcome tracking must evaluate whether observations were useful and correctly described—not claim guaranteed predictive accuracy.

---

## 9. Creator and Wallet Intelligence

### 9.1 Creator Intelligence

Potential creator observations include:

- Number of tokens launched.
- Number of launches that reached meaningful liquidity.
- Token survival duration.
- Time until creator first sold.
- Creator allocation and current holdings.
- Repeated launch behaviour.
- Historical sell behaviour.
- Repeated funding patterns.
- Known wallet relationships.

Example:

> Creator sold within the first ten minutes in several previous launches.

This is preferable to an unexplained creator score.

### 9.2 Wallet Intelligence

Potential wallet observations include:

- Entry timing across launches.
- Holding duration.
- Repeated co-occurrence with other wallets.
- Funding source.
- Connected-wallet patterns.
- Buy/sell aggressiveness.
- Historical interaction patterns.

DexSato must not claim that a wallet is profitable, trustworthy, fraudulent, or controlled by a specific person without sufficient evidence.

### 9.3 Coordinated-Wallet Detection

Possible indicators include:

- Same upstream funding source.
- Similar wallet funding time.
- Rapid sequential purchases.
- Repeated co-occurrence across launches.
- Similar trade timing and size.
- Shared intermediary wallets.

The output should use wording such as:

> Potential coordinated early-buying cluster detected.

Each warning should include reasons, evidence, time window, confidence limitations, and alternative explanations. It is risk intelligence, not proof of fraud.

---

## 10. Product Roadmap

## Phase 0 — Intelligence Core Stabilization

**Objective:** Produce reliable, explainable, and testable market observations.

Scope:

- Data normalization and validation.
- Observation engine.
- Signal detection.
- Interpretation engine.
- Decision-support status.
- Market-state classification.
- Evidence traceability.
- Data freshness handling.
- Observation logging.
- Outcome tracking.
- Unit and integration tests.

Exit criteria:

- Core outputs are deterministic for identical inputs.
- Every important output can display supporting evidence.
- Missing or stale data fails safely.
- Observation outcomes can be evaluated historically.
- The product is useful without transaction execution.

## Phase 1 — Intelligence Product MVP

**Objective:** Validate that users repeatedly use DexSato to discover and understand market conditions.

Scope:

- Token discovery feed.
- Token detail page.
- Watchlists.
- Observation timeline.
- Basic token-risk indicators.
- Holder concentration.
- Volume and trading-velocity observations.
- Alerts.
- Clear risk disclaimers.

Exit criteria:

- Users return to review observations and watchlists.
- Data quality and alert latency meet defined targets.
- Usage shows which observations affect user decisions.
- No custody or on-chain protocol is required.

## Phase 1.5 — Creator and Wallet Intelligence

**Objective:** Build differentiated intelligence from historical creator and wallet behaviour.

Scope:

- Creator history.
- Early-wallet behaviour.
- Holder growth.
- Funding relationships.
- Basic wallet clustering.
- Historical token outcomes.
- Evidence-backed risk observations.

Exit criteria:

- Cluster warnings include evidence and limitations.
- False-positive rates are monitored.
- Creator and wallet histories add measurable user value.
- Data coverage is sufficient to avoid misleading empty profiles.

## Phase 2 — Read-only Trading Integration

**Objective:** Validate user interest in moving from intelligence to action without DexSato executing trades.

Scope:

- External route and market links.
- Indicative quote display.
- Transaction education.
- Execution-intent analytics.
- Clear distinction between DexSato data and third-party route data.

Exit criteria:

- Users demonstrate demand for execution from analysis pages.
- Quote freshness and route-data reliability are understood.
- Legal and compliance assessment supports the next phase.

## Phase 2.5 — Non-custodial Execution

**Objective:** Enable user-signed trades through existing Solana liquidity infrastructure.

Scope:

- Solana wallet integration.
- Transaction preview.
- Slippage protection.
- User-signed execution.
- Existing external liquidity route.
- Transaction result and failure handling.
- Execution monitoring.

Exit criteria:

- DexSato never receives private keys or seed phrases.
- On-chain constraints protect minimum output.
- Transaction preview exposes route, mint, program, fee, and slippage.
- Security review and operational monitoring are complete.
- Execution volume demonstrates genuine product demand.

## Phase 3 — Token Launch Protocol Research

**Objective:** Determine whether a DexSato launch protocol is commercially, technically, legally, and operationally justified.

Research scope:

- Creator demand.
- Bonding-curve economics.
- Graduation venue.
- Liquidity protection.
- Fee model.
- Audit budget.
- Solana engineering capability.
- Legal position and operating jurisdiction.
- Mainnet exposure limits.

This phase is research and specification work, not automatic approval to deploy.

## Phase 4 — Limited Launch Protocol

Proceed only if Phase 3 is approved.

Potential scope:

- Standard SPL token creation.
- Fixed supply.
- Mint and freeze authority policy.
- Program-controlled reserve.
- Audited bonding curve.
- Buy and sell instructions.
- Transparent fees.
- Programmatic graduation.
- Existing Solana liquidity venue.
- Limited mainnet exposure.
- Continuous security monitoring.

---

## 11. Solana Recommendation for Future Protocol Work

If DexSato proceeds to execution or token launch, the recommended initial chain is Solana.

Recommended baseline:

| Decision | Recommendation |
|---|---|
| Blockchain | Solana only |
| Token standard | Standard SPL Token |
| Smart-contract language | Rust |
| Framework | Anchor |
| User custody | Non-custodial |
| Quote asset | SOL initially |
| Token supply | Fixed by default |
| Mint authority | Revoked by default after supply creation |
| Freeze authority | Revoked by default |
| Initial liquidity | Bonding curve only if Phase 3 is approved |
| Reserve control | Program-controlled PDA/vault |
| Post-graduation liquidity | Existing Solana venue |
| Treasury | Multisig |
| Upgrade authority | Multisig |
| Native DexSato token | Not approved for initial phases |
| Native AMM | Not approved for initial phases |
| Multi-chain | Not approved for initial phases |

Solana is preferred for future protocol work because of its transaction cost, speed, SPL tooling, wallet ecosystem, and active token-trading environment. This choice must be revalidated when implementation begins.

---

## 12. Future Token Launch Architecture

This section describes a future architecture boundary. It is not part of the current Intelligence V1.

### 12.1 Creator Flow

A future creator flow may include:

1. Connect a supported Solana wallet.
2. Enter token name, symbol, description, image, links, supply, and allocation.
3. Review authority, allocation, fees, and launch configuration.
4. Sign token-creation and initialization transactions.
5. Create the SPL mint and metadata.
6. Mint the fixed supply.
7. Revoke the required authorities.
8. Initialize program state and bonding-curve reserve.
9. Publish the token page.
10. Open trading only after all state checks pass.

### 12.2 Authority Policy

Default community-token policy:

- Fixed supply.
- Mint authority revoked.
- Freeze authority revoked.
- Creator allocation publicly visible.
- Top-holder concentration publicly visible.
- Active authorities clearly labelled.

Special-token modes with active authority should not be included initially.

### 12.3 Reserve Model

Before graduation, trader funds must flow into a program-controlled PDA/vault, not a creator wallet.

```text
Trader
   │
   │ SOL
   ▼
Bonding-Curve PDA / Vault
   │
   ├── Buy and sell accounting
   ├── Fee accounting
   └── Programmatic graduation
```

No employee or founder wallet should be able to directly drain bonding-curve reserves.

### 12.4 Graduation State Machine

Recommended conceptual state machine:

```text
ACTIVE
  ↓
GRADUATION_READY
  ↓
MIGRATING
  ↓
GRADUATED
```

Backward transitions must be impossible. Graduation must be idempotent and must prevent repeated migration, reused reserves, fake destination pools, incorrect mint or quote assets, and unauthorized CPI targets.

---

## 13. Protocol Specification Required Before Coding

No bonding-curve smart contract should be implemented for mainnet until the following items are mathematically and operationally specified.

### 13.1 Economic Specification

- Exact curve formula.
- Initial virtual token reserve.
- Initial virtual SOL reserve.
- Pricing and rounding direction.
- Minimum and maximum trade size.
- Fee calculation order.
- Fee rounding.
- Creator allocation limit.
- Graduation condition.
- Reserve target.
- Treatment of unsold tokens.
- Treatment of failed or abandoned launches.
- Sell behaviour near reserve limits.

### 13.2 Instruction Specification

For every instruction, define:

- Required signer.
- Required accounts.
- Account owner validation.
- PDA derivation.
- Mint validation.
- Allowed protocol states.
- Preconditions.
- State mutation.
- Events emitted.
- Failure behaviour.
- Idempotency requirements.

### 13.3 Invariants

At minimum:

- Reserve cannot become negative.
- Output cannot exceed available reserve.
- Output cannot be received without valid input.
- Fee components must reconcile with total fees.
- Supply accounting must reconcile.
- Graduation can happen at most once.
- Reserve ownership remains program-controlled.
- Invalid state transitions are impossible.
- User minimum-output constraints are enforced on-chain.

---

## 14. Trust Boundaries

| Boundary | Controls | Responsibilities |
|---|---|---|
| User-controlled | User wallet and signature | Private keys, asset ownership, transaction approval |
| On-chain program-controlled | Program logic and PDA/vault | Reserves, state transitions, fees, graduation |
| Backend-controlled | Auth, APIs, database, indexer | Preferences, alerts, analytics, subscriptions |
| Multisig-controlled | Multiple authorized signers | Treasury, upgrade authority, emergency controls |
| Third-party infrastructure | RPC, indexer, liquidity route | Data availability and external execution dependencies |

Compromise of a DexSato backend or admin account must not automatically result in loss of user funds.

---

## 15. Authority Matrix

| Authority | Recommended Controller | May Do | Must Not Do |
|---|---|---|---|
| Program Upgrade | Multisig | Approve reviewed program upgrades | Directly withdraw user reserves |
| Emergency Pause | Multisig | Pause narrowly defined high-risk actions | Seize user assets or redirect reserves |
| Treasury | Multisig | Manage collected protocol fees | Access bonding-curve reserves |
| Protocol Configuration | Multisig with change controls | Change approved configurable parameters | Bypass immutable safety limits |
| Metadata Moderator | Restricted backend role | Hide malicious links or images | Change on-chain ownership or balances |
| Subscription Admin | Restricted backend role | Manage plans and billing configuration | Modify protocol state or user assets |

Material configuration and upgrade changes should be logged, reviewed, and publicly announced where appropriate.

---

## 16. Non-custodial Execution Requirements

DexSato must never:

- Ask for a seed phrase.
- Store user private keys.
- Require users to transfer trading funds to a staff wallet.
- Treat a database balance as ownership of blockchain assets.
- Allow an administrator to arbitrarily move user funds.

Every trade must be explicitly signed by the user wallet.

### 16.1 Transaction Preview

Before signing, the interface should display:

- Asset and amount paid.
- Estimated asset and amount received.
- Minimum output.
- Slippage limit.
- Protocol, creator, and referral fees where applicable.
- Token mint.
- Program address.
- Expected route.
- Material warnings.

### 16.2 Slippage Protection

Every buy must enforce a user-defined `minimum_tokens_out` on-chain.

Every sell must enforce a user-defined `minimum_quote_out` on-chain.

Frontend calculations alone are insufficient.

---

## 17. Security Architecture

### 17.1 Threat Model

DexSato should assume attacks against:

- Smart contracts and curve mathematics.
- Account and PDA validation.
- Treasury and upgrade authority.
- Frontend and transaction construction.
- DNS, domains, CI/CD, and dependencies.
- Backend APIs and admin accounts.
- RPC and indexer infrastructure.
- Creator abuse, wash trading, and Sybil activity.
- Malicious token metadata.
- Fake mint, token, program, and destination accounts.
- Fee routing and liquidity migration.

### 17.2 Smart-Contract Controls

Future Solana programs should use:

- Rust and Anchor.
- Explicit signer validation.
- Explicit account-owner validation.
- Strong account constraints.
- PDA derivation checks.
- Mint and token-account checks.
- Program ID and CPI target checks.
- State-transition validation.
- Checked arithmetic.
- Defined rounding policy.
- On-chain slippage checks.
- Idempotent graduation logic.

Anchor reduces implementation errors but does not replace protocol design, adversarial testing, or independent audit.

### 17.3 Treasury and Upgrade Authority

Protocol treasury, upgrade authority, and emergency authority should use multisig control rather than a founder hot wallet.

Illustrative operational baseline:

- 3-of-5 multisig.
- Hardware-wallet signers.
- Personnel and location separation.
- Key rotation and recovery plans.
- Transaction review process.
- Audit trail.
- Limited emergency authority.

The final threshold must reflect the actual team structure and operational risk.

### 17.4 Program Verification

Production releases should publish:

- Program ID.
- Source commit or release tag.
- Reproducible build instructions.
- Verified build result.
- Audit report.
- Release notes.

### 17.5 Frontend Security

Controls should include:

- Strict Content Security Policy.
- Locked and reviewed dependencies.
- Protected branches.
- Mandatory code review.
- Secure CI/CD.
- Security-key or strong 2FA enforcement.
- Protected environment variables.
- Domain and DNS protection.
- Release approval controls.
- Monitoring for unauthorized changes.

### 17.6 Backend and API Security

Controls should include:

- Authentication and authorization.
- Role-based access control.
- Rate limits and quotas.
- Request validation.
- Parameterized queries.
- Secret and API-key rotation.
- Audit logs.
- Abuse detection.
- Isolation of high-risk admin routes.
- Backup and recovery testing.

---

## 18. Emergency Controls

Future protocol emergency controls may allow a multisig to:

- Pause new launches.
- Pause new bonding-curve trades.
- Disable a compromised protocol action.
- Disable frontend transaction construction.
- Display an emergency warning.

Emergency controls must be:

- Narrowly scoped.
- Logged.
- Multisig-controlled.
- Tested.
- Unable to arbitrarily seize user funds.
- Documented with activation and recovery procedures.

A pause mechanism must not become a hidden custody backdoor.

---

## 19. Monitoring and Incident Response

Monitor:

- Program errors and failed transactions.
- Reserve and treasury movements.
- Fee reconciliation.
- Upgrade and configuration attempts.
- Graduation events.
- RPC instability and indexer lag.
- Unexpected account or reserve deltas.
- Backend and admin actions.
- Dependency and deployment changes.
- Abnormal buy/sell patterns.

An incident-response plan should define:

1. Detection.
2. Severity classification.
3. Containment authority.
4. User communication.
5. Investigation and evidence preservation.
6. Recovery.
7. Post-incident review.

Automated protective actions must be constrained to avoid creating new abuse or denial-of-service paths.

---

## 20. Testing and Audit Strategy

### 20.1 Intelligence Testing

- Unit tests for each rule.
- Deterministic fixture tests.
- Data-quality tests.
- Missing and stale-data tests.
- Historical replay tests.
- Outcome-evaluation tests.
- False-positive monitoring.

### 20.2 Protocol Testing

Before meaningful mainnet funds:

- Unit tests for every instruction and calculation.
- Integration tests for full launch, buy, sell, fee, and graduation flows.
- Property-based testing.
- Fuzz testing.
- Invariant testing.
- Adversarial account-substitution testing.
- Extreme and boundary-value testing.
- Independent Solana smart-contract audit.
- Remediation and critical-fix review.
- Limited mainnet beta.
- Bug bounty.

### 20.3 Example Critical Findings

- Drain of bonding-curve reserves.
- Unauthorized treasury withdrawal.
- Arbitrary minting.
- Unauthorized liquidity removal.
- Upgrade-authority compromise path.
- Pricing or rounding exploit causing material reserve loss.
- Repeated graduation or reserve reuse.

---

## 21. Mainnet Readiness Gates

A token-launch protocol must not proceed to meaningful mainnet exposure until all applicable gates are complete:

- [ ] Product demand validated.
- [ ] Protocol specification complete.
- [ ] Curve mathematics independently reviewed.
- [ ] Legal and compliance position documented.
- [ ] Non-custodial wallet model verified.
- [ ] No seed/private-key storage.
- [ ] Program-controlled reserves.
- [ ] Mint/freeze authority policy implemented.
- [ ] On-chain slippage enforcement.
- [ ] Graduation and migration state protection.
- [ ] Liquidity-protection model implemented.
- [ ] Multisig treasury.
- [ ] Multisig upgrade authority.
- [ ] Emergency controls tested.
- [ ] Reproducible and verified build.
- [ ] Unit and integration tests complete.
- [ ] Fuzz and invariant tests complete.
- [ ] Independent audit complete.
- [ ] Critical findings remediated.
- [ ] Monitoring and alerts operational.
- [ ] Incident-response procedure tested.
- [ ] Secure frontend, DNS, and deployment controls.
- [ ] Admin RBAC and audit logs.
- [ ] Limited-beta exposure cap defined.
- [ ] Bug-bounty plan prepared.

---

## 22. Business Model Boundaries

Potential long-term revenue sources include:

- Intelligence subscription.
- Premium alerts.
- Historical analytics.
- API and data access.
- Non-custodial execution or referral fees.
- Token launch fees.
- Bonding-curve protocol fees.
- Transparent creator fee sharing.

DexSato revenue should depend on useful platform activity, not on DexSato taking directional market risk.

Referral and creator fee systems should be delayed until DexSato can address:

- Self-referral.
- Sybil farming.
- Wash trading.
- Circular referral structures.
- Fraudulent volume generation.
- Applicable legal and consumer-protection requirements.

Illustrative revenue calculations must not be treated as forecasts without validated volume, retention, cost, and jurisdiction assumptions.

---

## 23. Explicitly Deferred Features

The following are not approved for the initial product phases:

- Native DexSato AMM.
- Native DexSato token.
- Multi-chain support.
- Margin or leverage.
- Derivatives.
- Custodial wallets.
- Fully autonomous profit bots.
- Unrestricted automated execution.
- Complex on-chain referral economy.
- Special tokens with hidden or active authorities.

Deferred features may only be reconsidered after a documented product, security, operational, and legal review.

---

## 24. Key Architecture Questions

### Intelligence Core

1. What normalized event and observation schemas should DexSato adopt?
2. Which observations are deterministic metrics versus heuristics?
3. What freshness thresholds apply to each data type?
4. How will historical replay and outcome evaluation work?
5. How will false positives and rule changes be measured?
6. Which data sources are required for reliable creator and wallet analysis?

### Execution Layer

7. Which Solana wallet and transaction standards will be supported?
8. Which external route or liquidity infrastructure is appropriate?
9. What transaction data must be independently verified before signing?
10. What execution limits apply during beta?

### Launch Protocol

11. Is there validated creator demand for a DexSato launchpad?
12. What exact bonding-curve formula and virtual reserves are appropriate?
13. What graduation condition will be used?
14. Which venue will receive graduated liquidity?
15. How will LP ownership or liquidity locking work?
16. What fee split is sustainable and compliant?
17. What creator allocation is permitted?
18. Which emergency and upgrade controls are required?
19. What audit budget and process are realistic?
20. Which operating and user jurisdictions will be supported?

---

## 25. Architecture Decision Record Summary

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Intelligence Core is the current product priority | Approved |
| ADR-002 | Observations must be evidence-based and explainable | Approved |
| ADR-003 | Signal does not automatically mean BUY or SELL | Approved |
| ADR-004 | Intelligence, execution, and launch protocol are separate layers | Approved |
| ADR-005 | Current Intelligence V1 has no custody requirement | Approved |
| ADR-006 | Outcome tracking is part of the intelligence architecture | Approved |
| ADR-007 | Solana is the preferred future execution/protocol chain | Provisional |
| ADR-008 | Future execution must be user-signed and non-custodial | Approved |
| ADR-009 | Bonding curve is deferred pending specification and validation | Deferred |
| ADR-010 | Existing liquidity infrastructure is preferred over a native AMM | Approved |
| ADR-011 | Native DexSato token is not required | Deferred |
| ADR-012 | Multi-chain support is not required | Deferred |
| ADR-013 | Mainnet protocol requires independent audit | Approved |
| ADR-014 | Treasury, upgrade, and emergency authority use multisig | Approved for future protocol |

---

## 26. Final Architecture Principle

The strongest immediate version of DexSato is not a website that launches tokens or generates unexplained trade calls.

It is:

> **An evidence-based crypto intelligence system that helps users discover market activity, understand on-chain conditions, recognize risks, and evaluate how those conditions develop over time.**

If validated, DexSato may later add non-custodial execution and, only after deeper commercial and security validation, token-launch infrastructure.

The long-term data moat is:

```text
Market Data
    ↓
Observations
    ↓
Creator and Wallet History
    ↓
Outcome Tracking
    ↓
Better Intelligence
    ↓
More Useful User Actions
    ↓
More High-Quality Data
```

Security, explainability, and data integrity are product features. If users cannot trust DexSato's data, transaction intent, or protocol controls, the rest of the platform has limited value.

---

## 27. Disclaimer

DexSato intelligence should not be presented as financial advice or a guarantee of future market performance. Crypto assets, especially newly launched tokens, may experience extreme volatility, manipulation, illiquidity, and total loss.

Any future launchpad, execution, referral, or fee-sharing capability may trigger regulatory, licensing, AML/KYC, securities, payments, consumer-protection, tax, or digital-asset obligations depending on operating jurisdiction, user jurisdiction, custody model, marketing, and token structure.

Jurisdiction-specific professional advice is required before production deployment.
