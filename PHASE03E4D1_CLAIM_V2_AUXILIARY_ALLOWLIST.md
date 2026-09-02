# Phase 03-E.4D.1 — ClaimV2 Auxiliary Instruction Decoder & Allowlist Audit

## Finding

The pinned SDK ClaimV2 transaction contains four top-level instructions:

1. Compute Budget `SetComputeUnitLimit`;
2. Compute Budget `SetComputeUnitPrice`;
3. Associated Token Program `Create` for the partner ATA;
4. the single final ClaimV2 call.

## Exact allowlist

The compute-unit limit must be positive and at most `1,400,000`. The price must
be at most `1,000,000` micro-lamports per CU. Both instructions must have zero
accounts and use their exact Compute Budget binary layouts.

The ATA instruction must use empty data (`Create`) and contain exactly six
accounts in this order:
  `payer, destination ATA, owner, mint, System Program, Token Program`;
- bind specifically to the independently derived partner ATA and partner owner;
- precede the single, final ClaimV2 instruction.

Arbitrary System/Token instructions, free transfers, additional signers, lookup
tables, extra destinations and instructions after ClaimV2 are not allowed.

## Commands

```powershell
python -m application.jupiter_claim_v2_auxiliary `
  --capture .\phase03e4c2_capture_001\unsigned_claim_v2_capture.json `
  --binding-report .\phase03e4c2_capture_001\claim_v2_compiled_binding_report.json `
  --output .\phase03e4c2_capture_001\claim_v2_auxiliary_report.json
```

After a successful auxiliary report, rerun E.4D with:

```powershell
python -m application.jupiter_claim_v2_simulation `
  --capture .\phase03e4c2_capture_001\unsigned_claim_v2_capture.json `
  --binding-report .\phase03e4c2_capture_001\claim_v2_compiled_binding_report.json `
  --auxiliary-report .\phase03e4c2_capture_001\claim_v2_auxiliary_report.json `
  --output-dir .\phase03e4d_simulation_002
```

Both results remain review-only. They do not sign or submit ClaimV2 and do not
enable production fee execution.
