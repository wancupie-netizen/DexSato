# Phase 03-F.6C — Controlled One-Shot ClaimV2 Execution

## Scope and decision

F.6C supplies a supervised mainnet submission boundary for the wallet-signed
ClaimV2 transaction already approved by F.6B. It does not sign transactions,
hold keys, enable configuration, retry a provider call, or approve subsequent
claims. Installation performs no network request and no live claim.

## Locked contract

The execution boundary requires all of the following before submission:

- approval feature disabled and submission feature enabled;
- production fee execution disabled;
- HTTPS RPC whose genesis hash is Solana mainnet;
- status `LIVE_CLAIM_APPROVED` with an unexpired gate and 90-second approval;
- exact one-time approval ID;
- identical wallet-bound and approval-bound signed transaction SHA-256;
- one wallet review, one approval and zero submission attempts;
- exact gross claim `5000` raw WSOL;
- exact expected partner share `4000` and project share `1000`;
- exact phrase `I AUTHORIZE THIS ONE CLAIM V2 ON SOLANA MAINNET`.

Only after the mainnet check passes does the F.6A harness atomically reserve the
single attempt and call `sendTransaction`. Preflight is enabled and automatic
retries are zero. The result remains `FINALIZATION_PENDING` until the independent
F.6A finalized-receipt verifier proves the ClaimV2 instruction, account order and
balance deltas `-5000 / +4000 / +1000`.

## Operational warnings

This phase moves real assets when its CLI is deliberately invoked with both a
wallet-signed transaction and the one-time approval ID. Review the wallet display
and gate file immediately before execution. Never place transaction material,
approval IDs, RPC credentials or environment contents in Git or chat logs.

After any success, rejection, timeout or ambiguous provider result, disable the
submission flag. Do not create another gate or resend. Inspect the persistent
gate and query the recorded signature before deciding anything further.

## Default configuration

```dotenv
DEXSATO_JUPITER_CLAIM_GATE_ENABLED=false
DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED=false
DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED=false
DEXSATO_JUPITER_FEE_ENABLED=false
```

`execution_ready` remains false in every returned report; this is a one-time
operator authorization boundary, not a general production execution switch.
