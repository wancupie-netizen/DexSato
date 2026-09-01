# 03-E.3B — Swap V2 Quote Fee-Shape Alignment

Live read-only diagnostics observed that Swap V2 quote preview returns
`platformFee.feeBps` and `platformFee.feeMint` before `taker`, while
`platformFee.amount` is absent. This hotfix distinguishes preview evidence from
prepared-order evidence.

- Quote preview must still provide the reviewed referral, fee rate and fee mint.
- An optional quote amount, if provided, must be exact.
- Prepared order must provide `platformFee.amount` and it must equal the fixed
  50 bps arithmetic for the controlled input.
- Missing, malformed or mismatched prepared-order amount remains fail-closed.

No fee formula, production execution gate, signing, broadcasting, endpoint,
trade amount, slippage or referral identity is changed.
