# Phase 02 P1-B — Persistent Storage & Single-Worker Runtime Contract

## Development compatibility

When `DEXSATO_DISCOVERY_STORAGE_DIR` is empty in development, DexSato continues
to use:

`output/research/solana-discovery-phase0-seven-day`

No existing local archive is moved or deleted.

## Production storage contract

Production requires `DEXSATO_DISCOVERY_STORAGE_DIR` to be an absolute path to an
existing writable persistent-volume directory. Startup fails if it is missing,
relative, absent, or not writable. The temporary write probe is removed
immediately.

The web application, discovery feed, SQLite archive, Python collector, and
PowerShell collector runner all resolve the same directory.

Railway example:

1. Attach a Railway Volume, mounted at `/data`.
2. Set `DEXSATO_DISCOVERY_STORAGE_DIR=/data`.
3. Ensure the collector and web process use that same mounted directory.

Do not point the variable at the repository `output/` directory in production.

## Runtime topology contract

Jupiter pending orders and request rate limits remain process-local. Until they
move to a shared store, production must use exactly:

- one web worker;
- one Railway replica.

Set `DEXSATO_WEB_WORKERS=1`. `WEB_CONCURRENCY` and `UVICORN_WORKERS`, when set,
must also equal `1`; unsafe values stop startup.

Official production start command:

`python -m application.production_server`

The launcher hardcodes one Uvicorn worker and disables raw access logging.
Horizontal scaling is not authorized by this phase.
