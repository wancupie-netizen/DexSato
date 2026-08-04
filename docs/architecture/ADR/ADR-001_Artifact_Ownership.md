# ADR-001: Artifact Ownership

**Status:** Accepted  
**Decision Date:** Sprint E9.5  
**Architecture Version:** 1.0  
**Supersedes:** None  
**Related Document:** `docs/architecture/DexSato_Architecture.md`

---

## 1. Context

DexSato produces and consumes multiple artifacts across the
Core Engine, Adaptive Layer, Application Layer, persistence
components, and delivery boundaries.

As the system grew, several risks appeared:

- the same artifact could be reconstructed in multiple layers,
- services could redefine contracts through primitive parameters,
- ownership could shift implicitly during refactoring,
- orchestration code could begin containing domain responsibility,
- persistence components could infer or mutate business values.

A formal ownership model is required so that every artifact has:

1. one canonical contract owner,
2. an explicit construction path,
3. clearly defined consumers,
4. a controlled change process.

---

## 2. Decision

Every formal DexSato artifact must have exactly one canonical
owner.

The canonical owner:

- defines the artifact structure,
- defines its immutable contract,
- defines metadata belonging to the artifact,
- controls contract evolution,
- remains the single source of truth.

Other modules may:

- build the artifact through approved factories or builders,
- coordinate it through Application services,
- serialize and persist it,
- consume it as read-only input.

Other modules must not:

- redefine the artifact,
- duplicate its dataclass or schema,
- silently add alternative fields,
- replace the artifact with an unstructured primitive dictionary,
- mutate an immutable artifact after creation.

---

## 3. Ownership Matrix

| Artifact | Canonical Owner | Constructed By | Primary Consumers |
|---|---|---|---|
| `DecisionArtifact` | `core/artifacts/decision_artifact.py` | Decision Engine | Runner, Lifecycle Engine, Dashboard Request Builder |
| `OutcomeArtifact` | `core/artifacts/outcome_artifact.py` | Lifecycle Engine | Serializer, Learning Engine |
| `LearningArtifact` | `core/artifacts/learning_artifact.py` | Lifecycle or Learning Engine | Serializer, Knowledge Layer, Adaptive compilation |
| `KnowledgeArtifact` | `core/artifacts/knowledge_artifact.py` | Lifecycle or Knowledge Engine | Serializer, persistence, later knowledge consumers |
| `MarketSnapshot` | `core/artifacts/market_snapshot.py` | Market Snapshot Builder | Lifecycle Engine |
| `ExperienceArtifact` | `adaptive/artifacts/experience_artifact.py` | Experience Compiler or Merger | History Repository, History Builder |
| `EvidenceArtifact` | `adaptive/artifacts/evidence_artifact.py` | Evidence Builder | Dashboard Context consumers |
| `HistorySummary` | `adaptive/history/history_summary.py` | History Builder | Dashboard Builder |
| `DashboardRequest` | `adaptive/dashboard/dashboard_request.py` | Dashboard Request Builder | Adaptive Dashboard Service |
| `DashboardCard` | `adaptive/dashboard/dashboard_card.py` | Dashboard Builder | Runner result, Collection Service, UI or API |
| Lifecycle Package | `scanner/lifecycle_engine.py` | Lifecycle Engine | Runner, lifecycle persistence |
| Intelligence Package | `scanner/intelligence_engine.py` | Intelligence Engine | Runner, serializers, persistence |
| Operational Intelligence Fingerprint | `scanner/knowledge_fingerprint.py` | Production Runner through fingerprint builder | Intelligence persistence, Adaptive history lookup |
| Learning Fingerprint | `core/knowledge/fingerprint.py` | Knowledge aggregation flow | Knowledge and learning consumers |

---

## 4. Ownership Rules

### 4.1 Contract Owner

The contract owner defines:

- field names,
- field types,
- required and optional values,
- artifact metadata,
- immutability rules,
- factory functions,
- artifact versioning.

A consumer cannot alter these rules locally.

---

### 4.2 Builder

A builder may construct an artifact but does not own its contract.

Example:

```text
DashboardRequestBuilder
        ↓
DashboardRequest
```

The builder translates approved inputs into the canonical artifact.

It must not:

- introduce undocumented fields,
- return an alternative dictionary contract,
- access unrelated repositories,
- perform persistence.

---

### 4.3 Application Service

An Application service coordinates artifacts and use cases.

Example:

```text
DashboardRequest
        ↓
AdaptiveDashboardService
        ↓
HistorySummary
        ↓
DashboardCard
```

An Application service must not:

- redefine Core or Adaptive artifacts,
- duplicate domain calculations,
- replace formal requests with primitive parameter collections,
- mutate input artifacts.

---

### 4.4 Runner

The Production Runner owns orchestration, not artifact contracts.

The Runner may:

- invoke builders and engines,
- pass artifacts between boundaries,
- build the operational fingerprint once,
- coordinate persistence,
- return production results.

The Runner must not:

- define `DecisionArtifact`,
- define `DashboardRequest`,
- define `DashboardCard`,
- calculate history statistics,
- contain decision rules.

---

### 4.5 Serializer

A serializer converts an artifact into a persistence-safe payload.

```text
Artifact
   ↓
Serializer
   ↓
Payload
```

A serializer must preserve artifact meaning.

It must not:

- invent missing business values,
- change decision semantics,
- mutate the artifact,
- become an alternative artifact owner.

---

### 4.6 Store

A store persists or retrieves serialized data.

A store must not:

- construct domain artifacts from incomplete business assumptions,
- make trading decisions,
- calculate adaptive history,
- redefine artifact contracts.

Deserialization must be handled by an explicit deserializer or
assembler.

---

## 5. DecisionArtifact Ownership

`DecisionArtifact` belongs exclusively to:

```text
core/artifacts/decision_artifact.py
```

It is the official output of the Decision Engine.

Its ownership includes:

- recommended action,
- confidence,
- summary,
- decision context,
- explainable reasons,
- metadata,
- artifact identity.

The Adaptive Layer may consume this artifact but must not alter the
original trading decision.

Dashboard components may extract presentation fields from the
artifact, but the original artifact remains authoritative.

---

## 6. Dashboard Artifact Ownership

The official flow is:

```text
DecisionArtifact
      ↓
DashboardRequestBuilder
      ↓
DashboardRequest
      ↓
AdaptiveDashboardService
      ↓
HistorySummary
      ↓
DashboardBuilder
      ↓
DashboardCard
```

Ownership is divided as follows:

- `DashboardRequest` owns the formal input contract.
- `HistorySummary` owns the historical summary contract.
- `DashboardCard` owns the presentation-ready adaptive result.
- `AdaptiveDashboardService` owns orchestration only.
- `DashboardCollectionService` owns collection orchestration only.

The Collection Service must receive:

```python
Iterable[DashboardRequest]
```

and return:

```python
list[DashboardCard]
```

It must not reconstruct request fields from primitive dictionaries.

---

## 7. Experience and History Ownership

`ExperienceArtifact` represents accumulated historical experience.

It is owned by:

```text
adaptive/artifacts/experience_artifact.py
```

The History Repository may store and retrieve Experience artifacts.

The History Builder may aggregate them into `HistorySummary`.

Neither component owns the `ExperienceArtifact` contract.

`HistorySummary` is a separate artifact and must not be treated as a
mutable form of `ExperienceArtifact`.

---

## 8. Fingerprint Ownership

DexSato currently has two distinct fingerprint contracts.

### 8.1 Operational Intelligence Fingerprint

Owner:

```text
scanner/knowledge_fingerprint.py
```

Input:

```text
Intelligence Package
```

Purpose:

- identify a normalized decision and interpretation state,
- support Intelligence persistence,
- support Adaptive history lookup.

Construction rule:

```text
Production Runner builds it once
        ↓
Persistence and Dashboard reuse it
```

It must not be rebuilt independently by every consumer.

---

### 8.2 Learning Fingerprint

Owner:

```text
core/knowledge/fingerprint.py
```

Input:

```text
LearningArtifact collection
```

Purpose:

- support knowledge aggregation,
- represent learning-derived identity.

This is not interchangeable with the operational Intelligence
fingerprint.

A future ADR may rename either contract, but until then they remain
separate.

---

## 9. Lifecycle Package Ownership

The Lifecycle Package is owned by:

```text
scanner/lifecycle_engine.py
```

It coordinates lifecycle outputs such as:

- Outcome,
- Learning,
- Knowledge.

The package is an orchestration result. Its contained artifacts
remain owned by their respective Core artifact modules.

Therefore:

```text
Lifecycle Engine owns the package
Core owns the contained artifact contracts
```

---

## 10. Contract Change Rule

Any change to a locked artifact requires:

1. repository audit,
2. consumer audit,
3. serializer and deserializer audit,
4. persistence compatibility review,
5. targeted contract tests,
6. relevant regression tests,
7. a new ADR or an amendment to this ADR.

A contract change must not be introduced only because one consumer
needs an extra primitive field.

The preferred sequence is:

```text
Change Artifact Contract
        ↓
Update Builder
        ↓
Update Services
        ↓
Update Serializer
        ↓
Update Deserializer
        ↓
Update Tests
```

---

## 11. Consequences

### Positive

- artifact contracts have one source of truth,
- ownership disputes are resolved explicitly,
- primitive obsession is reduced,
- Runner responsibilities remain bounded,
- service contracts become more stable,
- serializer and persistence drift become easier to detect,
- future refactoring becomes safer.

### Trade-offs

- contract changes require broader review,
- new fields may require updates across several consumers,
- compatibility adapters may temporarily be necessary,
- legacy dictionary contracts cannot be changed casually.

These trade-offs are accepted because contract stability is more
important than short-term convenience.

---

## 12. Rejected Alternatives

### Alternative A: Allow every layer to define its own DTO

Rejected because it creates multiple competing definitions of the
same business object.

### Alternative B: Use dictionaries for all cross-layer data

Rejected because dictionaries provide weak contracts and allow
silent field drift.

### Alternative C: Let Application services own artifacts

Rejected because Application services own use-case orchestration,
not stable domain contracts.

### Alternative D: Let the Runner define integration artifacts

Rejected because the Runner is an orchestrator and must not become
a domain owner.

---

## 13. Compliance Checklist

Before introducing or modifying an artifact, confirm:

- [ ] The canonical owner is identified.
- [ ] No duplicate artifact definition exists.
- [ ] A factory or builder constructs it.
- [ ] Consumers treat it as read-only.
- [ ] Application services do not redefine it.
- [ ] Serializer preserves its meaning.
- [ ] Store does not infer business values.
- [ ] Tests cover the official contract.
- [ ] Contract changes are documented by ADR.

---

## 14. Final Decision

DexSato adopts single-owner artifact governance.

Each formal artifact has one canonical contract owner.

Builders construct artifacts.

Application services coordinate artifacts.

Serializers transform artifacts.

Stores persist payloads.

Consumers read artifacts.

No layer may silently redefine an artifact owned by another layer.
