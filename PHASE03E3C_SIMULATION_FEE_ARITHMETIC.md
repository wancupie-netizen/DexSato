# 03-E.3C — Simulation Fee Arithmetic Alignment

Live Swap V2 evidence shows both quote and prepared order omit
`platformFee.amount` while retaining `feeBps` and `feeMint`. Therefore the
provider echo is not used as the amount authority.

The controlled expected gross fee is calculated from fixed evidence:
`1,000,000 * 50 / 10,000 = 5,000` raw WSOL. The reviewed 80% partner share is
`4,000` raw WSOL. Success still requires the same atomic simulation response to
show exactly that referral ATA balance delta. If Jupiter supplies an amount in
future, it must match the arithmetic or the harness fails closed.

The report records `provider_platform_fee_amount_present` and
`platform_fee_source`. No production formula, execution gate, signing,
broadcasting, endpoint, intent, or referral identity is changed.
