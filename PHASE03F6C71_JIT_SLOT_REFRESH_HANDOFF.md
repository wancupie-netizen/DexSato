# Phase 03-F.6C.7.1 — Just-in-Time Slot Refresh and Approval Handoff

This phase retains the existing maximum capture age of 32 finalized slots. It
does not refresh metadata on an old transaction. Instead, explicit operator
readiness triggers a new blockhash, unsigned capture, funded simulation closure,
and one-shot gate. A second read-only RPC check must find a slot age of at most
four before the artifacts are released to the sign-only browser.

The handoff imports no submission operation. During generation, production fees,
live approval, and claim submission must all remain disabled. A failed slot-budget
check atomically marks the generated gate `JIT_HANDOFF_RETIRED`; it cannot be
used by an approval path requiring `ARMED`.

The browser must already be open at the loopback sign-only page before starting
the handoff. The operator selects the newly created unsigned capture and exact
gate-review copy, signs immediately, and uses an already-running PowerShell
watcher to invoke the separate F.6C.7 short-lived approval. No `.bin` is uploaded
or persisted by the server.

The F.6C.7 approval boundary accepts this JIT report only when its sign-now
action, unchanged 32-slot maximum, at-most-four-slot handoff age, exact remaining
budget, unconsumed gate, and disabled submission fields are all present. Merely
renaming another report to the JIT status cannot authorize approval.
