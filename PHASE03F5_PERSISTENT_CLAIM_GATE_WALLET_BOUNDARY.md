# Phase 03-F.5 — Persistent One-Shot Claim Gate and Wallet Boundary

## Result

The persistent ClaimV2 gate and wallet-signature validation boundary are
implemented but disabled by default. This phase does not submit a claim.

## Gate contract

- Requires `DEXSATO_JUPITER_CLAIM_GATE_ENABLED=true` for an explicit window.
- Requires production fee execution to remain disabled.
- Requires the exact phrase `I APPROVE ONE CONTROLLED CLAIM V2`.
- Expires after 300 seconds.
- Binds the F.4 closure ID, message hash and unsigned transaction hash.
- Binds the mint, referral account, partner and exact `5000` raw claim.
- Persists atomically and rejects re-arming the same path.
- Accepts one wallet-reviewed signed-transaction digest.
- Allows only an identical status poll after wallet binding.

## Wallet boundary

The boundary parses the unsigned capture and wallet-signed Solana versioned
transaction. It verifies that:

1. The unsigned transaction and message hashes match the gate.
2. Signed and unsigned message bytes are identical.
3. The required signer set is unchanged.
4. The connected wallet is both payer and bound partner.
5. The wallet signature is present.

Only the SHA-256 digest of the signed transaction is written to the gate. Full
signed transaction bytes are not persisted or returned.

## Deliberate stop boundary

After successful wallet validation the state is:

`WALLET_APPROVAL_BOUND`

The following remain false:

- `submission_permitted`
- `claim_submitted`
- `live_claim_approved`
- `claim_execution_ready`
- `execution_ready`
- `fee_receipt_verified`

There is no RPC client, submission function, signing key, keypair, private key
or seed phrase handling in either new module.

## Environment defaults

```text
DEXSATO_JUPITER_CLAIM_GATE_ENABLED=false
DEXSATO_JUPITER_CLAIM_GATE_PATH=
```

Do not permanently enable the feature flag. Any later controlled submission
requires a separately audited phase, a new explicit approval and finalized
on-chain receipt verification.
