# Phase 03-E.5 — One-Shot Controlled Fee-Bearing Swap & Receipt

Pins exactly one TAP purchase to wallet `J2PV...bVTs`, input `0.001 SOL`, fee
`50 bps`, and referral account `5q9...NQQ`. The persistent state machine is
`ARMED -> BOUND -> CONSUMED -> FINALIZATION_PENDING -> FINALIZED_VERIFIED`.

The gate is consumed before the first execute request. Only an identical signed
transaction may be retried for Jupiter status polling. Failure also closes the
gate. A finalized Solana receipt must show exactly `5000` raw WSOL added to the
verified referral ATA.

Arm only immediately before the controlled test:

```powershell
python -m application.jupiter_one_shot_swap_gate `
  --output .\runtime\tap-one-shot-gate.json `
  --confirm "I APPROVE ONE CONTROLLED TAP FEE SWAP"
```

Configure the server process with the absolute gate path and the reviewed fee
policy, restart it, request exactly `0.001 SOL` for TAP, review the wallet
transaction, and sign once. Do not expose the gate file through static routes.
The controlled path additionally requires
`DEXSATO_JUPITER_ONE_SHOT_MODE=true`; without that explicit opt-in, the
historical fee-execution blocker remains authoritative.

After Jupiter returns success, verify finalized receipt:

```powershell
python -m application.jupiter_one_shot_receipt `
  --gate .\runtime\tap-one-shot-gate.json
```

This gate is deliberately token-, wallet-, amount-, fee- and transaction-bound.
