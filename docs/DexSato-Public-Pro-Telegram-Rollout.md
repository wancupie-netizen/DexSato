# Public / Pro and customer Telegram: rollout status

Status: implemented in local commits and verified by automated tests. Production activation is pending. This document describes the code state and activation checks; it does not confirm that the required migrations, bot webhook, or flags have been applied in production.

## Current access

| Surface | Public | Active Pro |
| --- | --- | --- |
| Trending and Top Traded | Up to 25 items per feed | Full permitted feed |
| Detected signals | Up to 5 unique signals in a rolling 24 hours | No Public quota |
| Recent 24H | Locked | Available |
| Full Discovery and Archive | Locked | Available |
| Customer Telegram alerts | Ineligible | Eligible only with a linked private Telegram account |

Authentication and Pro entitlement are separate. An authenticated account without an active Pro subscription has Public access. The server resolves the policy and enforces premium routes; the badge and lock messages reflect that result. The current lock message does not offer a checkout or claim that upgrades can be purchased in the app.

Customer Telegram delivery uses the founder automation's alert changes. Before each customer send, the server checks that the account still has a valid private Telegram link and current Pro alert entitlement. Founder notifications and customer alert fanout have separate paths. The customer flag defaults to disabled.

## Default flags and configuration

| Variable | Default in `.env.example` | Purpose |
| --- | --- | --- |
| `DEXSATO_PRODUCT_AUTH_ENABLED` | `false` | Product sign-in and server identity |
| `DEXSATO_TELEGRAM_LINK_ENABLED` | `false` | Customer Telegram link routes |
| `DEXSATO_CUSTOMER_TELEGRAM_ALERTS_ENABLED` | `false` | Customer alert fanout |
| `DEXSATO_TELEGRAM_BOT_USERNAME` | Empty | Bot username for the link URL |
| `DEXSATO_TELEGRAM_WEBHOOK_SECRET` | Empty | Secret checked on incoming Telegram webhook |

A disabled flag must remain disabled until its dependencies have been verified. Store actual keys and webhook secrets only in the server's secret configuration; never commit them. The existing founder bot token and founder chat ID are separate from customer account linking.

## Before any controlled activation

1. Confirm the deployment points to the intended commit and confirm its actual runtime flags. Do not infer live flag values from `.env.example`.
2. Verify the product identity migration `20260922203951_product_identity.sql`, subscription entitlement migration `20260927132824_product_subscription_entitlement.sql`, and Telegram link migration `20260928174059_telegram_account_link.sql` on the intended database. Review migration history and access controls before changing runtime flags.
3. Verify server-only product credentials, bot token, bot username, and webhook secret are present in the intended environment. Configure the bot webhook with the expected secret header. Test webhook reachability without publishing credentials.
4. Verify sign-in and entitlement behavior with guest, authenticated Public, active Pro, and lapsed Pro accounts. Check that direct requests to premium routes cannot return premium data for Public users.
5. Verify a private Telegram account can link to the intended DexSato account; test an expired or replayed link token and an invalid webhook secret. Confirm a Public or lapsed Pro account receives no customer alert.
6. Enable customer linking and customer alerts only in a controlled rollout after the preceding checks. Observe delivery results and keep founder Telegram notifications working independently. Disable the customer flag if customer delivery needs to stop.

## Local verification recorded

At commit `5b51531387fc836d1d902c73e6e91b395faf3791`, the A06 local regression run selected 32 test files and reported **256 passed, 2 deprecation warnings**. The run covered the product, Telegram, relevant Supabase adapters, Discovery presenter, and founder scheduler tests. It did not verify production migrations, live webhook configuration, real customer delivery, or production flag values.

No database migration, production flag activation, push, or deployment is part of this documentation change.
