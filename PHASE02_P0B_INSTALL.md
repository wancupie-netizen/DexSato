# DexSato Phase 02 P0-B — Safe Errors, Security Headers & Readiness

Baseline: `d216ec1`

## Security behaviour

- Public 5xx responses no longer expose filesystem, provider, scheduler, AI, Telegram, or snapshot exception text.
- The reviewed insufficient-SOL message remains public so the wallet UI can guide the user; unreviewed Jupiter/provider details remain hidden.
- Every normal HTTP response receives CSP, frame denial, MIME-sniffing protection, referrer policy, permissions policy, and a server-generated request ID.
- Production responses receive HSTS.
- Production startup requires an explicit trusted-host allowlist and rejects `*`.
- `X-Forwarded-Proto` affects secure-cookie decisions only when trusted proxy headers are explicitly enabled.

## Health endpoints

- `/health` remains backward-compatible.
- `/health/live` confirms that the process can serve requests.
- `/health/ready` checks static assets, collector telemetry files, and the discovery archive without contacting external providers.
- Readiness returns HTTP 503 when a required local component is unavailable.

## Environment

Local development:

```text
DEXSATO_ALLOWED_HOSTS=127.0.0.1,localhost
DEXSATO_TRUST_PROXY_HEADERS=false
```

Railway later requires its exact generated hostname in `DEXSATO_ALLOWED_HOSTS`. Set `DEXSATO_TRUST_PROXY_HEADERS=true` only after confirming Railway's trusted proxy boundary.

## Regression

```powershell
python -m pytest tests/test_production_security.py tests/test_app_bootstrap.py -v
python -m pytest -v
```
