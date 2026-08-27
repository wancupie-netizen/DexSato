# Phase 02 P1-A — No-Store Responses & Rate-Limiter Lifecycle

## Response caching

DexSato overrides cache headers for these sensitive routes:

- `/api/discovery/solana/:token/jupiter-quote`
- `/api/discovery/solana/:token/jupiter-order`
- `/api/discovery/solana/:token/jupiter-execute`
- `/content-control/*`
- `/telegram/send`

Each response receives `Cache-Control: no-store, max-age=0`, `Pragma: no-cache`,
and `Expires: 0`. Existing cache headers from downstream handlers are removed first.

## Limiter lifecycle

The process-local limiter now:

- removes buckets inactive for 15 minutes during periodic sweeps;
- bounds active buckets with `DEXSATO_RATE_LIMIT_MAX_BUCKETS`;
- fails closed for a new client when capacity is full;
- preserves the existing per-route traffic limits.

The default maximum is 10,000 buckets. Allowed values are 1 through 100,000.

This remains a single-process control. A shared rate limiter is required before
horizontal scaling across multiple workers or replicas.
