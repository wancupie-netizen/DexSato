# Phase 03-F.6C.4B — Local Wallet Sign-Only Boundary

## Security boundary

This operator tool signs an exact, fresh ClaimV2 transaction in an injected Solana
wallet and downloads the serialized bytes locally. It cannot broadcast, approve, bind,
or submit anything. The Python process serves only three allowlisted static assets on
IPv4 loopback and rejects POST, PUT, DELETE, unknown paths, and non-loopback Host
headers. The page has `connect-src 'none'` and cannot make network requests.

No private key or seed phrase is accepted. The wallet extension owns the signing
operation. The server never receives the selected capture, gate, or signed bytes.

## Preparation

Install the pinned browser dependency if its bundle is absent:

```powershell
cd C:\Users\Sufi\Documents\Projects\AlphaRadar\tools\claim_v2_capture
npm ci --ignore-scripts
cd C:\Users\Sufi\Documents\Projects\AlphaRadar
```

Generate a new F.6C.3 capture and gate immediately before signing. Never reuse an
expired or previously reviewed gate. Keep fee, live approval, and submission flags
`false`; only the gate feature remains `true`.

Copy the ARMED gate to a temporary review file because the browser file picker cannot
read it directly through the server:

```powershell
Copy-Item `
  .\runtime\claim-v2-gate-f6c4-002.json `
  .\phase03f6c4_capture_002\claim_v2_gate_review.json
```

## Start and sign

```powershell
python .\tools\claim_v2_sign_only\server.py --port 8765
```

Open `http://127.0.0.1:8765/` in the browser containing the trusted wallet extension.
Select:

1. `phase03f6c4_capture_002\unsigned_claim_v2_capture.json`
2. `phase03f6c4_capture_002\claim_v2_gate_review.json`

Confirm the warning and click the sign-only button. Check the wallet shows the expected
operator address. Reject the prompt if the wallet offers broadcast/submission or shows
unexpected accounts or amounts. The expected browser status is
`WALLET_SIGNED_BINARY_DOWNLOADED_NO_SUBMISSION`.

Stop the local server with `Ctrl+C`. Do not open the `.bin`, upload it, commit it, or
send it to another person. Move directly to the F.6C.4 independent Python verifier while
the same gate is still fresh.

## Invariants

- exact claim: 5,000 raw WSOL;
- partner expectation: 4,000 raw;
- project expectation: 1,000 raw;
- gate before signing: `ARMED`, zero reviews/approvals/submissions;
- server persistence: none;
- browser network access: none;
- live approval: false;
- submission attempts: zero;
- execution ready: false.
