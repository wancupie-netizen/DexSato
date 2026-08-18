# DexSato Revenue Model — Canonical

**Status:** Canonical product decision  
**Version:** 1.0  
**Decision date:** 18 August 2026  
**Current execution scope:** Subscription model definition only  

---

## 1. Purpose

This document is the single source of truth for DexSato's revenue model.

DexSato will use a hybrid business model:

1. Subscription revenue from discovery, filtering, intelligence, monitoring,
   and alerts.
2. Transaction-fee revenue from optional non-custodial execution in a future
   phase.

Only the subscription model is in the current product-planning scope.
Transaction execution, transaction fees, global operating structure, and
jurisdictional implementation are explicitly deferred until DexSato has real
usage evidence.

This decision does not authorize implementation of payments, wallet
connections, swaps, transaction fees, or additional production services.

---

## 2. Product Positioning

DexSato is not merely a market-data terminal and must not become a generic AI
trading-opinion product.

DexSato's core value is:

> Help users identify which Solana tokens are worth investigating, understand
> the supporting evidence and risks, and save time in a market with excessive
> noise.

Major-market coverage such as BTC, ETH, SOL, XRP, and other established assets
remains useful as market context. Solana Discovery is intended to become the
primary subscription trigger because it addresses a stronger user problem:
finding relevant opportunities early without manually reviewing every token.

Users pay for reduced noise, earlier discovery, structured evidence,
continuous monitoring, and useful alerts—not merely for raw data.

---

## 3. Revenue Architecture

### 3.1 Current revenue track: Subscription

Subscription provides access to deeper and faster:

- Solana token discovery;
- qualification and filtering;
- decision evidence;
- risk visibility;
- lifecycle monitoring;
- change detection;
- watchlists;
- historical outcomes; and
- alerts.

### 3.2 Future revenue track: Transaction fee

Optional non-custodial execution may later allow users to connect their own
wallet, review a quote, and sign their own transaction. DexSato may receive a
clearly disclosed integrator or transaction fee.

This track is **KIV** and is not part of current development.

Future execution principles, if authorized:

- DexSato must not hold user funds.
- DexSato must not store user private keys.
- The user must approve and sign every transaction.
- Fees, price impact, slippage, and material risks must be visible before
  signing.
- DexSato must not guarantee returns or represent `READY` as safe to buy.
- Legal, security, operational, and jurisdictional feasibility must be
  reviewed before public implementation.

### 3.3 Global operations

Global operating structure, allowed or restricted markets, legal entity,
geofencing, sanctions controls, and jurisdiction-specific requirements are
also **KIV**.

They will be assessed only when there is sufficient product usage to justify
the work. Global availability must never be interpreted as an absence of
regulatory responsibilities.

---

## 4. Subscription Plans

DexSato will begin with only two customer-facing plans: **Free** and **Pro**.
Unnecessary tier complexity is prohibited during early validation.

| Capability | Free | Pro |
|---|---|---|
| Major-market context | Included | Included |
| Solana Discovery | Selected candidates | All candidates passing DexSato filters |
| Full token analyses | Up to 3 per day | No restrictive daily limit under fair use |
| Discovery timing | Curated summary or digest | Latest qualified feed |
| Token and pair identity | Basic | Complete available evidence |
| Liquidity, volume, and transactions | Current values | Trends and meaningful changes |
| Essential risk flags | Included | Included with deeper evidence |
| Why It Surfaced | Short explanation | Full supporting evidence |
| What Changed | Not included | Included |
| Intelligence Summary | Basic | Complete evidence-led summary |
| Token lifecycle | Current state | State history and transitions |
| Historical outcome | General summary | Candidate-level history |
| Watchlist | Up to 3 tokens | Up to 50 tokens |
| Telegram | Daily or weekly digest | Priority alerts |
| Custom filters | Not included | Included |
| Token comparison | Not included | Included |
| Decision history | Up to 24 hours | Target range of 30–90 days |
| Advertising | May be considered later | No advertising |

Exact limits may be refined through user testing, but changes must preserve a
clear distinction:

> Free demonstrates trust and usefulness. Pro delivers speed, depth,
> monitoring, and material time savings.

---

## 5. Safety Must Not Be Paywalled

DexSato must not hide essential safety information solely to force an upgrade.

Where data is available, Free users must still be shown critical warnings such
as:

- pair not yet available;
- extremely low liquidity;
- active mint authority;
- active freeze authority;
- concentrated holders;
- Token-2022 transfer fees;
- suspicious market behavior;
- material data unavailable; and
- other high-severity risk conditions.

Pro may provide deeper evidence, history, monitoring, and interpretation, but
the existence of a known critical warning must remain visible to Free users.

---

## 6. Intended Free Output

Example structure:

```text
Token: EXAMPLE
Status: WATCH
Age: 42 minutes
Liquidity: USD38,000
Volume: USD91,000
Risk: HIGH

Why it surfaced
• Buyer activity increased
• Liquidity passed the basic threshold

Important warning
• Holder concentration unavailable

Full analysis limit: 1 of 3 used today
```

The Free experience must provide genuine value and demonstrate that DexSato's
filtering is useful. It must not provide the complete monitoring workflow.

---

## 7. Intended Pro Output

Example structure:

```text
Token: EXAMPLE
Lifecycle: DISCOVERED → TRADEABLE → WATCH
Evidence strength: DEVELOPING
Risk level: HIGH

Why it surfaced
• Liquidity increased from USD14k to USD38k
• Unique buyers increased across three scans
• Buy volume remained stronger than sell volume
• Pair remained active for 45 minutes

What changed
• Liquidity +46%
• Buyers +31%
• Sell pressure increased slightly
• Top-holder concentration improved

Risk evidence
• Mint authority disabled
• Freeze authority disabled
• Liquidity condition requires monitoring
• Top holders remain concentrated

DexSato view
Continue monitoring. Evidence is improving, but holder concentration remains
a material risk.

Next checkpoint: 15 minutes
```

The summary must remain evidence-led. AI may improve clarity, but must not
invent evidence, override deterministic risk rules, or act as the foundation
of a decision.

---

## 8. Initial Pricing Direction

The initial pricing direction is:

| Plan | Price | Purpose |
|---|---:|---|
| Free | USD0 | Build trust, demonstrate product value, and support acquisition |
| Founder Pro | USD9/month | First 100 paying users during validation |
| Pro standard | USD19/month | Intended standard price after early validation |

Founder Pro pricing may remain available while the original subscription stays
active. Final billing terms, taxes, refunds, annual pricing, and payment
provider selection require a separate implementation decision.

No payment system should be built merely because pricing is documented.

---

## 9. Subscription Activation Gates

Paid subscriptions must not be activated until DexSato can demonstrate:

1. Reliable discovery-source operation.
2. Consistent candidate identity and pair resolution.
3. Filtering that materially reduces market noise.
4. Evidence fields that are understandable and reproducible.
5. Useful alert quality without excessive notifications.
6. Historical tracking sufficient to evaluate discovery outcomes.
7. Stable access control and basic account management.
8. Real feedback showing that target users value the output.

Phase 0 proves only the data-source layer. It does not, by itself, satisfy all
subscription activation gates.

---

## 10. Core Product and Commercial Metrics

Early validation should measure:

- qualified candidates per day;
- percentage of discovered tokens that become tradeable;
- time from discovery to pair availability;
- percentage rejected as noise or risk;
- alert open and click-through rates;
- watchlist additions;
- return visits;
- Free-to-Pro conversion;
- Pro retention and cancellation;
- user-reported time saved; and
- historical outcomes of surfaced candidates.

Raw token count is not a success metric. DexSato succeeds when fewer, more
relevant candidates help users reach informed decisions faster.

---

## 11. Explicit Non-Goals for the Current Phase

The following are not authorized by this document:

- wallet connection;
- token swap execution;
- transaction-fee collection;
- custody or deposit balances;
- payment gateway implementation;
- subscription billing implementation;
- global entity or jurisdiction setup;
- KYC or sanctions-system implementation;
- changes to the stable Market Radar engine;
- public integration of Phase 0 research data; or
- AI-generated trade instructions.

---

## 12. Locked Decision Summary

```text
Business model         : Hybrid
Current revenue focus  : Subscription
Plans                  : Free + Pro
Founder Pro direction  : USD9/month, first 100 users
Standard Pro direction : USD19/month
Transaction fees       : KIV
Global operations      : KIV
Current build scope    : Phase 0 data-source proof only
Phase 1                : Not authorized
```

Any later proposal that conflicts with this document must explicitly identify
the proposed change, supporting evidence, risks, and founder approval.
