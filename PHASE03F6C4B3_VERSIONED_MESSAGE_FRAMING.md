# Phase 03-F.6C.4B.3 — Versioned Message Framing Reconciliation

## Finding

Raw wallet-signed bytes passed the independent wire hash check, proving that the
browser output and SDK capture contained the same message. The wallet boundary
then hashed `bytes(transaction.message)`, which does not provide the authoritative
versioned wire framing required for a Solana V0 transaction.

## Correction

The decoder now uses `solders.message.to_bytes_versioned` and bounds its output
before comparing the unsigned, signed, capture, and gate message identities.

## Safety invariants

- No transaction broadcast, approval, or submission is added.
- Unknown parser errors remain redacted.
- Empty or oversized encoded messages fail closed.
- Gate `005` is not reusable after the failed review attempt.
