# Phase 03-F.6C.7 — Short-Lived Live Approval and Pre-Submission Inspection

This phase binds raw wallet-signed Solana bytes to the exact F.6C.6 preparation
before the existing 90-second approval transition. Submission remains disabled.
The approval must be followed by the separate read-only mainnet and exact funded
balance inspection; no submission attempt is consumed by either operation.

Fresh-approval and pre-execution CLIs now accept the browser `.bin` format without
ASCII conversion. The new coordinator imports no submission operation and always
returns `execution_ready=false`.
