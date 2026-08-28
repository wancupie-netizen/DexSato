# Phase 02 P1-C — Readiness Integrity & Production Configuration Validation

## Liveness and readiness

- `/health/live` confirms only that the process can respond.
- `/health/ready` performs local checks only and never calls Jupiter, Birdeye,
  Solana RPC, or another upstream provider.

Readiness requires:

- the static asset directory;
- valid `state.json` with a `candidates` object;
- valid `status.json` with a `metrics` object;
- a readable SQLite archive that passes `PRAGMA quick_check`;
- the required `discoveries` table;
- valid production configuration.

The public response contains only `ready` or `unavailable` component states. It
does not contain paths, credentials, provider responses, or exception details.

## Production configuration

Production startup requires:

- `JUPITER_API_KEY`;
- `BIRDEYE_API_KEY`;
- `SOLANA_RPC_URL` using HTTPS without embedded credentials;
- the P1-B persistent-storage and single-worker contract;
- a 32+ character `DEXSATO_OPERATOR_TOKEN` only when internal endpoints are
  explicitly enabled.

Development remains unchanged and does not require production provider keys.
Placeholders from `.env.example` are rejected in production.

These checks validate configuration presence and local integrity. They do not
claim that an external provider is currently available; provider failures remain
handled by the relevant application service.
