# 03-E.3D — Gross Referral Accrual vs Claim Semantics

Fresh read-only simulation observed the referral WSOL ATA move from `0` to
`5,000` raw units for the controlled 0.001 SOL, 50 bps order. This is the gross
referral accrual. It is not a direct 80% partner payout.

The harness now requires exactly `5,000` raw WSOL as the atomic swap-simulation
delta. It separately records the reviewed 80% partner claim estimate (`4,000`)
and explicitly marks `partner_claim_delta_observed` and `claim_split_verified`
false. Claim was not called, simulated or submitted.

This corrects evidence labels only. Referral identity, fee rate/mint, fixed
input, transaction identity, ATA lifecycle, RPC mainnet, simulation safety,
production execution gate, signing and broadcast restrictions remain intact.
