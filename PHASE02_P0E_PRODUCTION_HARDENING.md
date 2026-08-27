# DexSato Phase 02 P0-E — Production Logging, Dependency Review & Final Regression

Baseline: `c5c1188`

## Production logging

DexSato emits one JSON event per HTTP response and one bounded event for an uncaught exception. Events contain only request ID, method, sanitized route class, response status, duration, event name, and exception class when applicable.

Logs deliberately exclude request/response bodies, query strings, headers, client IP, wallet addresses, token mints, Jupiter provider request IDs, API keys, transaction bytes, exception messages, private keys, and seed phrases.

Use `DEXSATO_LOG_LEVEL=INFO`. `DEBUG` fails closed when `DEXSATO_ENV=production`. The built-in launcher disables Uvicorn access logs in production because raw URL access logging would bypass route sanitization.

For an external production command, use:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log
```

## Dependency review

The five direct production dependencies are pinned to the exact versions installed during P0-E and covered by the full DexSato regression:

- `supabase==2.31.0`
- `python-dotenv==1.2.2`
- `requests==2.34.2`
- `fastapi==0.139.0`
- `uvicorn==0.51.0`

The supplied environment report recorded `No broken requirements found` from `python -m pip check`.

This is an integrity and reproducibility result, not a claim that a live vulnerability database found zero CVEs. A network-backed `pip-audit -r requirements.txt` must run in CI or the Railway private-deployment phase, and any finding must be reviewed before public launch.

## Final verification

```powershell
python -m pip check
python -m pytest -v
```

No production deployment or public launch is authorized by this phase alone.
