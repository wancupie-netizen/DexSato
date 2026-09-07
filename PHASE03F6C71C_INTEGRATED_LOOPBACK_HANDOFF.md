# Phase 03-F.6C.7.1C — Integrated Loopback JIT Sign-Only Handoff

The trusted wallet connects before generation begins. A one-shot, random-token
loopback request then constructs fresh artifacts and returns only unsigned JSON
to the same-origin browser. The wallet signs immediately and the browser downloads
the binary. Signed bytes are never posted back to Python.

The endpoint binds only to IPv4 loopback, requires the exact Origin and session
token, accepts an empty body, and can run once. It has no approval, RPC submission,
or broadcast endpoint. Production fee, live approval, and claim submission flags
remain disabled during generation.

Loopback failures are classified by fixed stage and an uppercase domain-code
whitelist. Exception prose, paths, RPC endpoints, provider bodies, and transaction
material are never copied into the HTTP diagnostic response.
