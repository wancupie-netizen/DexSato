# 03-E.3A — Safe Stage Diagnostics

This hotfix replaces the one generic orchestration error with fixed stage codes:

- `FRESH_ORDER_CAPTURE_UPSTREAM_UNAVAILABLE`
- `FRESH_INTENT_DERIVATION_FAILED`
- `FRESH_IDENTITY_SNAPSHOT_UPSTREAM_UNAVAILABLE`
- `FRESH_BALANCE_SIMULATION_UPSTREAM_UNAVAILABLE`

The original reviewed validation errors remain unchanged. Upstream exception
text, API keys, RPC URLs, request data and headers are never returned. The
hotfix does not enable fees, sign, broadcast, call `/execute`, or weaken any
transaction/referral/identity validation.

Run with a new output directory after installation. A failed attempt may leave
its newly-created directory empty by design; it never overwrites evidence.
