# Phase 03-E.2A — Full CPI Evidence & Referral Claim Semantics

## What changed

All returned inner instruction objects are preserved, including the seven previously
counted as other/unparsed. Each includes top-level index, ordinal, stack height,
format, original RPC object and canonical JSON hash. Full resolved message accounts
and lookup context accompany the report for compiled-index interpretation.
No instruction is declared safe merely because it is recorded.

The previous report does not contain those seven objects. They cannot be recovered
from a count. Rerun unsigned simulation to capture the new response. Current pool
state may change instructions/counts/results; this does not reconstruct the old slot.
Parsed RPC objects do not contain original instruction bytes; no bytes are invented.

## Install

From AlphaRadar, after E.2:

```powershell
python apply_dexsato_phase03e2a_inner_claim.py --check
python apply_dexsato_phase03e2a_inner_claim.py
python -m pytest
node --test tests/test_jupiter_fee_ui.js
```

Five changed/new files, normalized baseline guards, backups, CRLF/BOM preservation,
and idempotency. No .env changes. Fees remain disabled. Stop on a hash mismatch.

## Capture again (simulation only)

Use the same session with HTTPS SOLANA_RPC_URL and referral configuration. No automatic
.env loading. Input/minimum below apply only to the original supplied evidence.

```powershell
python -m application.jupiter_fee_simulation `
  --evidence ".\unsigned_evidence(1).json" `
  --output ".\fee_simulation_full_report.json" `
  --wallet "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs" `
  --input-raw 1000000 `
  --minimum-output-raw 102326 `
  --fee-bps 50
```

Exit 2 means a review report was produced, not execution approval. Output must not
already exist. If market conditions now cause simulation failure, return the report;
do not weaken slippage/minimum checks. No signing, sendTransaction, claim transaction,
or actual token movement is performed. No live simulation was run while packaging.

## Source-level claim verification

Reviewed source:
https://github.com/TeamRaccoons/referral/blob/6500f64ff004e78faa15d66446e175ede625260d/program/programs/referral/src/instructions/claim_v2.rs

At that revision, claim_v2 reads the ENTIRE referral token account balance at claim:

    partner_amount = floor(balance * referral_account.share_bps / 10000)
    project_amount = balance - partner_amount

The partner amount goes to the canonical ATA of referral_account.partner; the project
amount goes to the canonical ATA of project.admin, for the same mint/token program.
Account constraints bind project to admin, referral to project/partner, and enforce
the named referral PDA and referral ATA. The payer signs/pays; partner and admin are
SystemAccounts, not required Signers in this instruction. The referral PDA supplies
token-transfer authority. A payer cannot choose arbitrary recipients under these
constraints. Destination ATAs may be initialized at payer expense.

For WSOL the transfer remains WSOL token units; this instruction does not itself
unwrap SOL or close the referral account. UI/SDK wrappers may perform additional
instructions; those wrappers are not approved by this source-only review.

Example with share 8000 bps:

| Referral balance | Partner | Project |
| --- | --- | --- |
| 5000 raw WSOL | 4000 | 1000 |
| 5001 raw WSOL | 4000 | 1001 |
| 1 raw WSOL | 0 | 1 |

Integer rounding goes to the project remainder. Claim batching can affect rounding
relative to hypothetical per-trade splits. A swap deposits gross referral fees;
claim performs the division. A claim projection based on simulated post-balance is
not evidence of actual earnings, executable claim availability or prior balance zero.

The observed referral share was 8000. For the previously reported simulated balance
5000, this formula projects 4000 to DexSato's partner wallet ATA and 1000 to the project
admin ATA. We have NOT independently verified the current project's admin destination
address, deployed bytecode matching this revision, an actual claim, or fee receipt.
The report records these limits explicitly. No claim is built or simulated here.

## Review fields

- inner_instruction_evidence.groups: every returned inner object, including non-transfer CPIs.
- resolved_message_accounts / lookup_context: mapping and provenance.
- claim_projection: exact integer arithmetic using observed partner share and simulated
  total post-fee-account balance, with source and explicit non-verification flags.

Capture completeness does not close transaction security blockers. Return the full
report so the previously unknown instructions can be reviewed. Fee execution stays shut.

## Tests

Six new unittest cases cover complete synthetic seven-instruction retention, parsed/
compiled forms, unknown fields, missing data, invalid/duplicate indexes, bounds, claim
rounding and invalid inputs. Synthetic examples are NOT the missing real instructions.
Local compatibility regression passes; full pytest/SDK and live RPC require the user's
environment. Do not interpret local compatibility checks as full production approval.

## Commit after tests

```powershell
git add application/jupiter_fee_simulation.py application/jupiter_inner_evidence.py tests/test_jupiter_inner_evidence.py pytest.ini PHASE03E2A_INNER_CAPTURE_CLAIM.md
git commit -m "test: retain full CPI evidence and document referral claim split"
```
