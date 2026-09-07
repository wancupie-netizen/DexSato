# Phase 03-F.6C.4B.2 — Raw Binary Decoder and Safe Diagnostics

## Finding

The browser sign-only boundary downloads raw Solana transaction bytes. The CLI
reads those bytes from disk, but the wallet-boundary decoder previously accepted
only a Base64 string. Real operator evidence therefore failed before gate binding,
while injected unit-test decoders masked the incompatible input contract.

## Correction

- Accept either bounded raw `bytes` or bounded SDK Base64 text.
- Apply the same 4,096-byte decoded transaction limit to both forms.
- Continue parsing with `solders.transaction.VersionedTransaction`.
- Preserve known fail-closed gate rejection codes at the CLI boundary.
- Redact unexpected exception messages to the existing generic reason.

## Safety invariants

- No transaction broadcast or RPC submission is added.
- No signed transaction bytes are persisted by the server.
- An expired or previously used gate remains rejected.
- A successful hash-only bind still leaves live approval and submission disabled.
- The failed gate `003` must not be reused; validation resumes with a fresh gate.

## Operator verification

Run focused tests, the full Python suite, and both Node suites before commit. Use
a newly generated gate only after all tests pass.
