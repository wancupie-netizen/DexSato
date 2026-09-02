# Phase 03-E.5B — One-Shot TAP UI Activation

The browser may advance from a fee-bearing quote to transaction review only for
the existing controlled one-shot contract: TAP output, 0.001 SOL input, 50 bps,
explicit one-shot mode, and a valid unexpired ARMED gate. All ordinary
fee-bearing previews remain locked. The browser validates the server's
`ONE_SHOT_TAP` scope and exact token/amount before enabling Review transaction.

Install and test first. Then configure one-shot mode and a new gate path, restart
the server, arm immediately before the approved test, hard-refresh, and request a
fresh quote. The UI must say `Armed · one controlled TAP swap`.

This change does not arm, sign, broadcast, or verify a fee receipt.
