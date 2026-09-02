# Phase 03-E.4D.2 — Created-ATA Zero Pre-Balance & Delta Classification

## Finding

Solana simulation may omit a token account from `preTokenBalances` when that
account is created inside the same transaction. E.4D.1A proved that the pinned
ClaimV2 transaction creates the partner WSOL ATA before ClaimV2.

## Narrow classification rule

Only the partner token account may use an implicit zero pre-balance, and only
when all of these conditions hold:

- the E.4D.1A auxiliary report is bound to the same transaction hashes;
- `ata_create_destination` is `partnerTokenAccount`;
- no pre-token-balance entry exists at that exact message account index;
- the required partner post-token-balance exists and matches mint, owner and
  Token Program.

The report records:

```text
partner_pre_source: CREATED_ATA_IMPLICIT_ZERO
```

Referral and project-admin pre-balances remain mandatory. Every post-balance
remains mandatory. Multiple entries remain an error; they are never classified
as zero.

## Safety state

This is a simulation evidence classification only. It does not sign or submit
ClaimV2, verify an on-chain receipt, enable fees, or approve a controlled swap.
