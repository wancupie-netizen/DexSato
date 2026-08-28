# Phase 02 P1-D — Clean Checkout & Collector Packaging Verification

## Audit result

`research/phase0_solana_discovery_probe_v2.py` is a required collector runtime
dependency. It contains no embedded API key, private key, seed phrase, wallet
credential, or non-standard Python dependency.

The provider module reads `BIRDEYE_API_KEY` only from the caller/environment.
Its upstream destinations are fixed HTTPS Birdeye and DexScreener endpoints.
Importing the module does not make a network request or write a file.

## Tracked runtime manifest

The collector requires these repository files:

- `application/discovery_storage.py`
- `research/__init__.py`
- `research/phase0_solana_discovery_probe_v2.py`
- `research/phase0_seven_day_collector.py`

Regression copies only these files into an isolated directory, removes provider
and storage environment variables, starts Python with isolated mode, and imports
the collector. No provider call, state file, status file, archive, `.env`, backup,
or local output is required.

The standalone probe remains read-only with respect to providers. Network calls
occur only when an explicit collection function or its CLI is executed.
