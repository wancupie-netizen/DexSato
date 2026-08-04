# ADR-004: Request Contract Rules

**Status:** Accepted  
**Decision Date:** Sprint E9.5  
**Architecture Version:** 1.0  
**Supersedes:** None  

**Related Documents:**

- `docs/architecture/DexSato_Architecture.md`
- `docs/architecture/ADR/ADR-001_Artifact_Ownership.md`
- `docs/architecture/ADR/ADR-002_Folder_Responsibility.md`
- `docs/architecture/ADR/ADR-003_Dependency_Rules.md`

---

## 1. Context

DexSato Application services previously accepted collections of
primitive parameters such as:

- token,
- decision,
- confidence,
- fingerprint,
- summary,
- reasons,
- timestamps.

As services evolved, primitive arguments created several risks:

- parameters could be omitted,
- parameter names could drift,
- consumers could use incompatible contracts,
- services could require increasingly long signatures,
- primitive dictionaries could silently replace formal artifacts,
- contract changes could spread unpredictably across the repository.

The Dashboard migration demonstrated this problem clearly.

The previous style was:

```python
build_adaptive_dashboard(
    token=token,
    fingerprint=fingerprint,
    decision=decision,
    confidence=confidence,
    summary=summary,
    reasons=reasons,
    last_updated=last_updated,
)
```

The accepted contract is:

```python
build_adaptive_dashboard(
    request: DashboardRequest,
)
```

A formal request artifact is therefore required whenever a use case
contains multiple related values that represent one operation.

---

## 2. Decision

DexSato adopts formal request contracts for Application services.

When a request artifact exists, all consumers must use that artifact.

Application services must not expose parallel primitive-based APIs for
the same use case.

Official rule:

```text
Primitive Inputs
      ↓
Request Builder
      ↓
Request Artifact
      ↓
Application Service
      ↓
Result Artifact
```

---

## 3. Request Artifact Ownership

A request artifact owns the formal input contract for one use case.

Example:

```text
DashboardRequest
```

Owner:

```text
adaptive/dashboard/dashboard_request.py
```

Builder:

```text
adaptive/dashboard/dashboard_request_builder.py
```

Consumer:

```text
application/adaptive_dashboard_service.py
```

The request artifact defines:

- required fields,
- field types,
- timestamps,
- referenced domain artifacts,
- use-case identity.

The builder constructs the request.

The Application service consumes it.

The service must not redefine it.

---

## 4. Builder Responsibility

A request builder translates approved source artifacts into a request
artifact.

Example:

```text
DecisionArtifact
Knowledge Fingerprint
Timestamp
      ↓
DashboardRequestBuilder
      ↓
DashboardRequest
```

A request builder may:

- validate construction inputs,
- normalize construction values,
- call an approved request factory,
- preserve the official request contract.

A request builder must not:

- access databases,
- load history,
- invoke Application services,
- persist artifacts,
- build final presentation output,
- make trading decisions.

---

## 5. Application Service Responsibility

An Application service receives the formal request artifact.

Correct:

```python
def build_adaptive_dashboard(
    request: DashboardRequest,
) -> DashboardCard:
    ...
```

Incorrect:

```python
def build_adaptive_dashboard(
    *,
    token: str,
    fingerprint: str,
    decision: str,
    confidence: str,
    summary: str,
    reasons: list[str],
    last_updated: datetime,
) -> DashboardCard:
    ...
```

The Application service may:

- coordinate repositories,
- invoke builders,
- aggregate results,
- return a formal result artifact.

It must not:

- reconstruct its request from unrelated primitives,
- provide competing request contracts,
- mutate immutable input artifacts,
- infer missing domain values silently.

---

## 6. Collection Contract Rule

Collection services must receive collections of formal requests.

Correct:

```python
def build_dashboard_collection(
    *,
    requests: Iterable[DashboardRequest],
) -> list[DashboardCard]:
    ...
```

Incorrect:

```python
def build_dashboard_collection(
    *,
    dashboards: list[dict],
) -> list[DashboardCard]:
    ...
```

The Collection Service:

- preserves input order,
- delegates each request,
- returns formal result artifacts.

It must not reconstruct request fields from dictionaries.

---

## 7. Request Artifact Criteria

A formal request artifact should be introduced when:

- one operation requires several related inputs,
- multiple consumers must share the same input contract,
- fields represent one use-case request,
- primitive parameters are likely to grow,
- contract validation is important,
- timestamps or identifiers belong to the request,
- a builder can isolate the caller from service internals.

A request artifact is not required for a trivial function that receives
one simple value and has no meaningful contract evolution risk.

---

## 8. Domain Artifact Rule

Existing domain artifacts must be referenced directly rather than
flattened prematurely.

Preferred:

```python
DashboardRequest(
    token=token,
    decision=decision_artifact,
    knowledge_fingerprint=fingerprint,
    last_updated=timestamp,
)
```

Avoid:

```python
DashboardRequest(
    token=token,
    decision=decision_artifact.recommended_action,
    confidence=decision_artifact.confidence,
    summary=decision_artifact.summary,
    reasons=[...],
)
```

The request should preserve the authoritative artifact whenever the
service needs its complete meaning.

---

## 9. Dictionary Boundary Rule

Unstructured dictionaries may be used only at explicit boundaries such
as:

- external API payloads,
- persistence payloads,
- legacy compatibility adapters,
- temporary transport mapping.

Dictionaries must not silently become internal Application contracts
when a formal artifact exists.

The preferred flow is:

```text
External Dictionary
      ↓
Parser or Assembler
      ↓
Formal Request Artifact
      ↓
Application Service
```

---

## 10. Compatibility Rule

When migrating a primitive API to a request artifact:

1. identify every consumer,
2. introduce the request artifact,
3. introduce its builder or factory,
4. migrate Application services,
5. migrate collection services,
6. migrate Runner or API callers,
7. update tests,
8. remove the legacy signature after regression passes.

Compatibility adapters may be used temporarily, but the formal request
artifact remains authoritative.

---

## 11. Validation Rule

Request validation belongs to:

- the request factory,
- request builder,
- explicit validation component.

Application services may reject an invalid request, but they must not
silently repair missing business values.

Invalid requests must fail clearly.

---

## 12. Naming Rule

Request artifacts must use explicit names.

Examples:

```text
DashboardRequest
TokenQueryRequest
PortfolioAnalysisRequest
NotificationRequest
```

Avoid ambiguous names such as:

```text
Data
Payload
Input
Params
Object
```

A request name must identify its use case.

---

## 13. Testing Rule

Every request contract must have tests covering:

- successful construction,
- required fields,
- field preservation,
- builder delegation,
- service acceptance,
- incompatible legacy calls where relevant.

Collection services must test:

- ordering,
- empty collections,
- iterable support,
- delegation count.

---

## 14. Consequences

### Positive

- stable Application service signatures,
- fewer missing parameters,
- reduced primitive obsession,
- easier contract migration,
- clearer ownership,
- better type checking,
- safer Runner and API integration.

### Trade-offs

- additional request files,
- additional builders or factories,
- more explicit mapping code,
- migrations require consumer updates.

These trade-offs are accepted because contract stability is more
important than shorter function signatures.

---

## 15. Rejected Alternatives

### Keep primitive parameters

Rejected because signatures become fragile as use cases evolve.

### Use dictionaries for every request

Rejected because dictionaries allow silent contract drift.

### Let each consumer build its own parameter set

Rejected because consumers would create competing contracts.

### Let Application services infer missing fields

Rejected because inference hides invalid requests and weakens ownership.

---

## 16. Compliance Checklist

Before creating or changing an Application service:

- [ ] Does a formal request artifact already exist?
- [ ] Does the service accept that request artifact?
- [ ] Is there only one authoritative request contract?
- [ ] Is the builder separate from orchestration?
- [ ] Are domain artifacts preserved rather than flattened unnecessarily?
- [ ] Are dictionaries restricted to explicit boundaries?
- [ ] Are all consumers using the current contract?
- [ ] Are request and service tests updated?

---

## 17. Final Decision

DexSato adopts formal request artifact governance.

Builders construct requests.

Application services consume requests.

Collection services consume collections of requests.

Consumers must not replace formal request artifacts with primitive
parameter groups or unstructured dictionaries.