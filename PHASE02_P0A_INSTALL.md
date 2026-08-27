# DexSato Phase 02 P0-A — Application Boundary Hardening

Baseline: `8ae2113`

## Files

- `application/production_security.py` — production bind settings, body limits, route throttling, and operator access dependency.
- `app/main.py` — installs the boundary middleware and protects internal routes.
- `.env.example` — documents production boundary settings without secrets.
- `pytest.ini` — includes the security-boundary suite in default collection.
- `tests/test_production_security.py` — regression coverage for production host, internal access, body limits, and throttling.

## Production defaults

- `HOST=0.0.0.0` when `DEXSATO_ENV=production`; local development remains `127.0.0.1`.
- Internal endpoints are hidden in production unless explicitly enabled.
- Enabling internal endpoints requires a 32+ character bearer token.
- Request bodies default to a 16 KiB maximum.
- Login, Telegram, Jupiter quote/order/execute, Solana API, and general API routes have separate rate buckets.
- Client identity comes from the direct socket address; forwarded headers are not trusted in P0-A.

## Required Railway configuration later

```text
DEXSATO_ENV=production
HOST=0.0.0.0
PORT=<Railway injected PORT>
DEXSATO_MAX_REQUEST_BYTES=16384
DEXSATO_INTERNAL_ENDPOINTS_ENABLED=false
```

Do not set `DEXSATO_OPERATOR_TOKEN` unless internal endpoints are deliberately enabled. Never commit its real value.

## Regression

```powershell
python -m pytest tests/test_production_security.py tests/test_app_bootstrap.py -v
```

Then run the complete project regression before commit.
