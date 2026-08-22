# DexSato Solana Discovery - Product Roadmap and Canonical Specification

**Status:** Locked product direction  
**Document owner:** DexSato  
**Primary route:** `/discovery/solana`  
**Product category:** Evidence-led Solana token discovery and future non-custodial swap access  
**Trading status:** Deferred until discovery, data quality, and operational stability are validated

---

## 1. Document purpose

This document is the single source of truth for the DexSato Solana Discovery product experience, implementation boundaries, staged roadmap, and future Jupiter integration.

All product, design, engineering, data, risk, and monetization decisions for Solana Discovery should be checked against this specification before implementation.

Existing DexSato Market Workspace functionality remains a locked baseline. Solana Discovery must extend the platform without weakening existing market intelligence, data integrity, provider reliability, or user trust.

## 2. Locked product direction

DexSato Solana Discovery helps users discover and evaluate emerging Solana tokens through real market activity, verified pool information, transparent risk context, and auditable evidence.

The product is not a token-promotion feed, guaranteed-profit system, automated trading bot, or custodial exchange.

The intended long-term user journey is:

```text
Discover -> Review evidence -> Understand risk -> Connect wallet -> Swap via Jupiter
```

The initial prototype journey is deliberately narrower:

```text
Discover -> Review evidence -> Understand risk
```

Wallet connections, trade execution, and monetized swap routing remain disabled until their respective roadmap phases are approved.

## 3. Relationship to existing DexSato products

### 3.1 Existing Market Workspace

The existing DexSato Market Workspace supports established registered markets, exact-pool market information, charts, technical evidence, decision context, and data-health checks.

Its existing architecture, decision policies, and user experience must remain intact.

### 3.2 Existing Solana Discovery experiment

DexSato already has a Solana Discovery collector and a seven-day source-validation experiment.

That experiment currently measures operational proof points such as:

- Collector runs.
- Provider usage.
- Unique discovered tokens.
- Pair readiness.
- Tokens waiting for a pair.
- Time required for a token to obtain an observable pair.

These measurements validate collection infrastructure. They do not prove token safety, investment quality, or trade suitability.

The existing collector, scheduled tasks, experiment state, and local monitor must not be interrupted, replaced, or silently modified by prototype work.

### 3.3 Separate product surfaces

Keep internal operations and the public-facing discovery product separate:

| Surface | Intended audience | Primary purpose |
| --- | --- | --- |
| Solana Discovery experiment monitor | Admin and internal operations | Provider usage, collector status, run progress, pair readiness, diagnostics. |
| `/discovery/solana` | Users | Qualified token discovery, market evidence, risk context, and future swap access. |
| `/discovery/solana/{token_address}` | Users | Exact-token detail, live market data, evidence, risk checks, and future Jupiter swap panel. |

Internal metrics such as provider compute units, scheduler diagnostics, and raw collector throughput do not belong in the primary user experience unless explicitly approved.

## 4. Non-custodial operating model

DexSato must remain a non-custodial platform.

### 4.1 Prohibited behavior

DexSato must never:

- Request, receive, store, display, or transmit a user's seed phrase.
- Request or store a user's private key.
- Hold or custody user funds.
- Take custody of a user's wallet.
- Sign a transaction on a user's behalf using a user-controlled key.
- Automatically execute a trade without explicit user authorization.
- Represent an informational market price as a guaranteed executable swap price.

### 4.2 Division of responsibilities

| Component | Responsibility |
| --- | --- |
| DexSato | Discovery, evidence, market presentation, token validation, risk context, and integration experience. |
| User wallet | Key custody, user authorization, transaction signing, and wallet-based transaction approval. |
| Jupiter | Swap routing, executable quote generation, and transaction integration when enabled and supported. |
| Solana network | Transaction settlement and on-chain state. |
| User | Independent decision-making and explicit approval of any transaction. |

Backend provider API keys may be used for authorized data access where required. Provider API keys are operational credentials and must never be confused with user wallet private keys.

### 4.3 User-facing disclosure

Any future swap interface must clearly communicate:

> Trades are routed through Jupiter. DexSato does not hold your funds or private keys. Transactions must be approved in your connected wallet.

## 5. Revenue and Jupiter affiliate model

DexSato may pursue an integrator, referral, affiliate, or platform-fee model where supported by the selected Jupiter integration and applicable current terms.

No revenue assumption is valid until the exact implementation and requirements are confirmed.

Before enabling monetized execution, verify:

- The applicable Jupiter integration method.
- Whether the chosen method supports an integrator or referral fee.
- The required recipient account or destination.
- Supported fee assets.
- Supported fee configuration and limits.
- User-facing fee disclosure.
- The relationship between fees and executable quotes.
- Technical, jurisdictional, and compliance implications.

A fee-recipient account, if required, is a platform fee destination. It must not be represented as custody of user funds.

The prototype must not imply that Jupiter fees are already active, available, configured, or guaranteed.

## 6. Product routes and token identity

### 6.1 Discovery landing page

```text
/discovery/solana
```

### 6.2 Token detail route

```text
/discovery/solana/{token_address}
```

The token-address route is preferred over a symbol-only route because symbols can collide, be imitated, or refer to multiple assets.

Use the complete canonical token address internally. A shortened address may be displayed visually, but full-address copy and verification must remain possible once token detail is implemented.

Every displayed discovery candidate must eventually map to a validated Solana token identity and a specific observable pool.

## 7. Prototype scope: Discovery UI without live candidate data

The first approved build is a real, navigable prototype for `/discovery/solana` without connecting the discovery collector or inserting artificial market data.

### 7.1 Included

- Real application route.
- Responsive desktop and mobile layout.
- Existing DexSato visual identity.
- Support for existing dark and plain-white themes.
- Clear product heading and explanation.
- Experimental or preview-state labeling.
- Discovery summary metric placeholders.
- Search and filter interface shell.
- Honest empty state.
- Educational explanation of how discovery works.
- Risk and non-endorsement disclosures.
- Return navigation to the existing DexSato markets experience.
- Architectural space for a future token-detail route and future Jupiter section.

### 7.2 Excluded

- Collector modifications.
- Scheduled-task modifications.
- Live discovery-token ingestion.
- Invented token candidates.
- Fabricated prices, volume, liquidity, or charts.
- Active wallet connections.
- Swap execution.
- Automatic trading.
- Jupiter fee collection.
- User-fund custody.
- Changes to the established-market Decision Engine.

## 8. Prototype information architecture

### 8.1 Header

Suggested title:

```text
DexSato Solana Discovery
```

Suggested supporting text:

```text
Discover emerging Solana tokens through observable market activity,
verified pool data, and transparent risk context.
```

Suggested status indicators:

```text
Experimental
Solana network
Read-only preview
```

### 8.2 Summary metrics

Suggested metric cards:

- Tokens discovered.
- Qualified candidates.
- Recently active.
- Data updated.

Before a validated feed is connected, display unavailable values honestly:

```text
Tokens discovered       —
Qualified candidates    —
Recently active         —
Data updated            Not connected
```

Do not populate public-facing metrics from the existing internal monitor without confirming that the underlying definitions and candidate scope are appropriate.

### 8.3 Search and filters

Suggested search placeholder:

```text
Search token name, symbol, or contract address
```

Suggested category controls:

```text
All
Newly active
Volume rising
Liquidity improving
Higher risk
```

During the no-data prototype, these controls may appear as preview interface elements but must not pretend to return real results.

Future optional controls may include minimum liquidity, minimum volume, pair age, venue, data freshness, and risk state.

### 8.4 Empty state

Recommended copy:

```text
Solana Discovery is preparing its first live feed.

DexSato is validating token identity, pool liquidity,
market activity, and data freshness before showing candidates.

No discovery tokens are available yet.
```

Suggested actions:

```text
Back to Markets
Learn how discovery works
```

If illustrative skeleton cards are used, they must be visibly identified as placeholders and must not contain believable fabricated market values.

### 8.5 Educational section

Suggested progression:

```text
1. Discover observable token activity.
2. Review the exact pool and supporting evidence.
3. Understand liquidity and token-specific risks.
4. Make your own decision.
```

Future Jupiter execution can be acknowledged as planned only if clearly labeled as unavailable.

## 9. Future discovery candidate card

Once validated data is connected, each candidate card should include:

- Token name.
- Token symbol.
- Canonical Solana token address.
- Exact pool address.
- DEX or venue.
- Trading pair.
- Current informational market price.
- Liquidity.
- Available volume windows.
- Pair age.
- Transaction activity when verifiably available.
- Data freshness.
- Evidence explaining why the token appeared.
- Relevant risk context.
- A link to the token workspace.

Illustrative structure only:

```text
TOKEN NAME                                   Emerging Activity
SYMBOL / USDC

Contract: [verified token address]

Price                 [provider value]
Liquidity             [provider value]
Volume                [provider value]
Pool age              [calculated value]

WHY IT APPEARED

[Explanation derived from observed market evidence]

RISK CONTEXT

[Validated risk or explicit unavailable state]

[Review Token]
```

Never publish a candidate with ambiguous token identity, an unverified pool, or materially misleading market information.

## 10. Evidence labels and allowed language

Acceptable evidence labels, when supported by real data, include:

- Emerging Activity.
- Volume Increasing.
- Liquidity Improving.
- New Pool.
- Limited History.
- High Volatility.
- Data Incomplete.

A comparative label must require an appropriate prior observation. For example, `Volume Increasing` must not appear unless the system has enough valid observations to support the comparison.

Avoid unsupported promotional or certainty-based language, including:

- `100x potential`.
- `Guaranteed moonshot`.
- `Safe gem`.
- `Buy now`.
- `Verified profit`.
- Any implication that inclusion is an endorsement or trading instruction.

## 11. Candidate qualification policy

Before a discovery token is shown to users, the production pipeline should evaluate:

- Token-address validity.
- Solana network identity.
- Pair existence.
- Pool identity.
- Minimum liquidity.
- Minimum observable trading activity.
- Data freshness.
- Duplicate-token and duplicate-pool suppression.
- Sufficient source information to explain discovery eligibility.
- Appropriate risk-state disclosure.

Thresholds must be decided after reviewing actual collector output. This document intentionally does not lock unsupported numeric thresholds before evidence is available.

Suggested future states:

```text
QUALIFIED
REVIEW_REQUIRED
INSUFFICIENT_DATA
HIGH_RISK
STALE
UNSUPPORTED
```

Candidate qualification must never silently convert missing risk data into an implied safe status.

## 12. Token detail workspace

Future discovery-token workspaces should use the canonical address route:

```text
/discovery/solana/{token_address}
```

Recommended section order:

1. Token identity and contract verification.
2. Live informational price.
3. Exact-pool chart.
4. Market snapshot.
5. Discovery evidence.
6. Risk context and unavailable checks.
7. Pool and venue details.
8. Jupiter quote and swap panel, when explicitly enabled.

The workspace must distinguish between:

- Observed informational market price.
- Provider chart data.
- Executable Jupiter quote.
- Actual transaction result.

These values must never be treated as interchangeable.

## 13. Jupiter execution model

When the Jupiter phase is approved, the proposed interaction is:

```text
User selects a qualified token
        ↓
User connects a supported self-custody wallet
        ↓
DexSato requests a Jupiter quote for the verified token
        ↓
User reviews output, price impact, network fees, and applicable platform fees
        ↓
User approves and signs in the connected wallet
        ↓
Transaction is submitted and settled on Solana
```

Possible interface fields:

- Input asset.
- Output asset.
- Input amount.
- Estimated output.
- Price impact.
- Network fee.
- Route information when available.
- Platform fee when applicable.
- Quote age and expiry.
- Wallet approval state.

Supported wallets and implementation specifics must be confirmed during the integration phase.

No Jupiter execution feature may bypass token-address verification, user approval, or mandatory risk disclosures.

## 14. Risk disclosure requirements

Discovery tokens can have materially higher risk than established assets.

Suggested baseline disclosures:

```text
Liquidity can change quickly.
New tokens may have limited trading history.
Observed market activity does not prove token safety.
Discovery inclusion is not an endorsement.
Swap quotes can change before transaction confirmation.
```

Future risk checks may include, only when reliably supported:

- Holder concentration.
- Mint authority.
- Freeze authority.
- Liquidity changes.
- Token age.
- Pool age.
- Abnormal trading patterns.
- Token or execution restrictions.

Where a check is not available, report:

```text
Unavailable
Not verified
Insufficient data
```

No individual risk check or aggregate status may be described as a guarantee of token safety.

## 15. Data and operational safeguards

Discovery must preserve existing DexSato reliability principles:

- Registered or explicitly validated market identity.
- Exact-pool mapping.
- Bounded provider requests.
- Cache appropriate to provider limits.
- Controlled concurrency.
- Rate-limit awareness.
- Per-token failure isolation.
- Explicit freshness reporting.
- Safe unavailable states.
- No fabricated data during provider outages.
- No impact on established-market decision calculations.
- Monitoring that remains separated from the user experience.

The collector's existing scheduled tasks and seven-day experiment must not be stopped or modified as a side effect of building the prototype.

## 16. Responsive design requirements

The discovery experience must work on desktop and mobile.

Required behaviors:

- No horizontal page overflow.
- Readable typography and contrast in both themes.
- Summary cards adapt to narrower screens.
- Search and filters remain usable on mobile.
- Token addresses can be truncated visually without losing full-address access.
- Risk notices remain visible and legible.
- Primary actions remain accessible without implying unsupported trade availability.
- Existing DexSato branding and theme preferences are respected.

## 17. Staged implementation roadmap

### D1 - Real discovery prototype without live data

Deliver:

- `/discovery/solana` route.
- Responsive public-facing discovery interface.
- Honest no-data empty state.
- Search and filter shell.
- Experimental/read-only labeling.
- Existing DexSato themes.
- Risk and non-custodial product messaging.

Do not deliver wallet connectivity, token ingestion, Jupiter execution, or artificial market data.

Exit criteria:

- Desktop and mobile layouts are approved.
- The route loads successfully.
- Existing market pages continue to work.
- Existing tests remain green.
- The current collector and scheduled tasks are unaffected.

### D2 - Collector audit and validated feed connection

Deliver:

- Audit of the existing collector output and data contracts.
- Controlled read-only ingestion from validated discovery data.
- Token/pool deduplication.
- Source and freshness display.
- Safe unavailable states.

Exit criteria:

- Displayed tokens correspond to verified Solana token and pool identities.
- Feed failures do not affect existing markets.
- No fabricated or stale candidate is presented as fresh.

### D3 - Candidate qualification and evidence

Deliver:

- Minimum qualification policies based on observed collector data.
- Liquidity and activity checks.
- Pair-age handling.
- Evidence-based inclusion explanations.
- Clear risk and insufficient-data labels.

Exit criteria:

- Every displayed candidate has an auditable reason for inclusion.
- Missing checks are disclosed explicitly.
- Duplicate or ambiguous candidates are excluded.

### D4 - Discovery-token detail workspace

Deliver:

- Canonical token-address route.
- Exact-pool token details.
- Live informational price.
- Validated market chart where available.
- Discovery evidence and risk context.
- Market-source attribution.

Exit criteria:

- The selected token, pool, chart, and displayed price agree on asset identity.
- Unsupported data fails safely.
- Mobile and desktop experiences are approved.

### D5 - Jupiter integration sandbox

Deliver:

- Supported self-custody wallet connection.
- Read-only executable quote retrieval.
- Token-address and route validation.
- Price-impact and fee presentation.
- Assessment of the supported affiliate/integrator-fee model.

Exit criteria:

- No user private keys or seed phrases are accessed or stored.
- Quotes are clearly differentiated from market observation prices.
- Fee behavior and platform disclosures are verified.

### D6 - Controlled non-custodial trading pilot

Deliver:

- Explicit wallet-approved swaps for eligible tokens.
- Visible risk, output, fee, and price-impact information.
- Controlled user rollout.
- Product-event measurement without sensitive wallet secrets.

Exit criteria:

- Transactions require explicit user approval.
- DexSato never takes custody of user funds.
- Swap behavior, provider availability, and user comprehension are validated.
- Any platform fee matches the verified integration and disclosed terms.

## 18. Public-user testing principles

The broader product goal is to validate DexSato with real users rather than extending development indefinitely.

Discovery rollout should therefore prioritize:

- A small, understandable initial experience.
- Real evidence over feature volume.
- Honest empty and unavailable states.
- Stable market data.
- Reliable scan operations.
- Clear user understanding of risk.
- Controlled iteration based on observed usage.

Initial discovery validation may begin with a limited number of qualified candidates after the feed is connected. The exact number should be selected based on available data and operational capacity.

## 19. Out-of-scope items until explicitly approved

The following are not part of the initial prototype:

- Trading across the top 100 established markets.
- Automatic token purchasing.
- Copy trading.
- Custodial balances.
- Seed-phrase or private-key workflows.
- Profit guarantees.
- AI-generated token endorsements.
- Unverified token safety scores.
- Simulated live market values.
- Replacing or redesigning the established Market Workspace.
- Interrupting the existing Solana collector experiment.

## 20. Change-control rule

This document is the canonical product baseline for DexSato Solana Discovery.

Changes to custody boundaries, trading behavior, data-quality rules, discovery qualification, collector integration, Jupiter fee assumptions, or roadmap sequencing require explicit product approval and an update to this document before implementation.

---

**Canonical product statement**

> DexSato Solana Discovery is an evidence-led Solana token discovery experience that may later provide non-custodial Jupiter swap access. DexSato does not store user private keys, seed phrases, or funds, and does not present token discovery as a guarantee of safety or profit.
