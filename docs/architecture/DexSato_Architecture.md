# DexSato Architecture

**Status:** LOCKED BASELINE  
**Architecture Version:** 1.0  
**Established:** Sprint E9.5  
**Repository:** `wancupie-netizen/DexSato`

---

## 1. Purpose

DexSato is an adaptive intelligence system that:

1. observes market conditions,
2. detects signals,
3. interprets market behaviour,
4. produces explainable decisions,
5. records outcomes and learning,
6. builds historical experience,
7. presents adaptive dashboard intelligence.

The system must remain deterministic, explainable, testable,
and maintainable.

---

## 2. Architecture Principle

DexSato follows this dependency direction:

```text
Delivery
   ↓
Application
   ↓
Domain and Adaptive Contracts
   ↓
Infrastructure Implementations
```

Business decisions must not depend on:

- API frameworks,
- databases,
- dashboard presentation,
- schedulers,
- external market providers.

---

## 3. Production Flow

The official DexSato production flow is:

```text
Market Provider
      ↓
Market Normalization
      ↓
Observation
      ↓
Signal Detection
      ↓
Interpretation
      ↓
DecisionArtifact
      ↓
Knowledge Fingerprint
      ↓
Intelligence Persistence
      ↓
DashboardRequest
      ↓
Adaptive Dashboard
      ↓
Lifecycle
      ↓
Outcome
      ↓
Learning
      ↓
Knowledge
      ↓
Production Result
```

The Production Runner coordinates this flow.

The Runner must not:

- detect signals,
- interpret markets,
- make trading decisions,
- define serialization rules,
- contain domain business rules.

---

## 4. Folder Responsibilities

### `core/`

Owns stable domain artifacts and domain-level models.

Examples:

- `DecisionArtifact`
- `KnowledgeArtifact`
- `LearningArtifact`
- `OutcomeArtifact`
- `MarketSnapshot`
- domain enums

Rules:

- artifacts should be immutable where practical,
- no database access,
- no API dependency,
- no scheduler dependency,
- no presentation logic.

---

### `scanner/`

Owns the production intelligence engine and market-scanning
implementation.

Examples:

- market acquisition,
- normalization,
- observation,
- signal detection,
- interpretation,
- decision execution,
- lifecycle execution,
- serialization,
- persistence adapters,
- Production Runner.

Rules:

- engines may build Core artifacts,
- Runner performs orchestration only,
- domain decisions remain inside engines,
- persistence logic remains isolated in stores.

---

### `adaptive/`

Owns adaptive intelligence contracts and behaviour.

Examples:

- `ExperienceArtifact`
- `EvidenceArtifact`
- `HistorySummary`
- `DashboardRequest`
- `DashboardCard`
- experience compilation
- history aggregation
- dashboard builders

Rules:

- does not make the original trading decision,
- does not access external market providers,
- does not control the Production Runner,
- output must be derived from Core decisions and historical
  experience.

---

### `application/`

Owns use-case orchestration.

Examples:

- Adaptive Dashboard Service,
- Dashboard Collection Service,
- token query services,
- assemblers,
- DTO mapping.

Rules:

- coordinates domain and adaptive modules,
- does not contain market decision logic,
- does not duplicate domain calculations,
- receives and returns explicit contracts,
- must not accept primitive argument collections where a formal
  request artifact already exists.

---

### `api/`

Owns the external HTTP delivery boundary.

Rules:

- validates transport input,
- invokes Application services,
- converts results into API responses,
- contains no market intelligence logic,
- contains no direct database business workflow.

---

### `pulse/`

Owns operational job tracking.

Examples:

- job start,
- job finish,
- duration,
- execution status.

Pulse must not influence trading decisions.

---

### `scheduler/`

Owns scheduled execution.

The Scheduler may invoke the Production Runner but must not contain
scanner, interpretation, or decision logic.

---

### `validation/`

Owns engineering validation and regression workflows.

Validation scripts must use current package paths and current
artifact contracts.

---

### `tests/`

Owns automated unit, contract, and integration tests.

Tests must:

- be safe during pytest collection,
- avoid production side effects,
- use package-qualified imports,
- reflect current contracts,
- test one responsibility clearly.

---

## 5. Artifact Ownership

| Artifact | Owner |
|---|---|
| `DecisionArtifact` | `core/artifacts/decision_artifact.py` |
| `OutcomeArtifact` | `core/artifacts/outcome_artifact.py` |
| `LearningArtifact` | `core/artifacts/learning_artifact.py` |
| `KnowledgeArtifact` | `core/artifacts/knowledge_artifact.py` |
| `ExperienceArtifact` | `adaptive/artifacts/experience_artifact.py` |
| `EvidenceArtifact` | `adaptive/artifacts/evidence_artifact.py` |
| `HistorySummary` | `adaptive/history/history_summary.py` |
| `DashboardRequest` | `adaptive/dashboard/dashboard_request.py` |
| `DashboardCard` | `adaptive/dashboard/dashboard_card.py` |
| Lifecycle Package | `scanner/lifecycle_engine.py` |

Artifact ownership means:

- the owner defines the contract,
- builders may construct the artifact,
- services may coordinate it,
- consumers may read it,
- consumers must not redefine it.

---

## 6. Dashboard Ownership

The official Dashboard flow is:

```text
DecisionArtifact
      ↓
DashboardRequestBuilder
      ↓
DashboardRequest
      ↓
AdaptiveDashboardService
      ↓
HistoryRepository
      ↓
HistorySummary
      ↓
DashboardBuilder
      ↓
DashboardCard
```

For multiple tokens:

```text
Iterable[DashboardRequest]
      ↓
DashboardCollectionService
      ↓
list[DashboardCard]
```

The Collection Service must not reconstruct or duplicate
`DashboardRequest` fields.

---

## 7. Fingerprint Ownership

DexSato currently contains two distinct fingerprint concepts.

### 7.1 Operational Intelligence Fingerprint

Location:

```text
scanner/knowledge_fingerprint.py
```

Purpose:

- derived from an Intelligence Package,
- identifies decision and interpretation state,
- used by Intelligence persistence,
- used for Adaptive history lookup,
- built once by the Production Runner.

### 7.2 Learning Fingerprint

Location:

```text
core/knowledge/fingerprint.py
```

Purpose:

- derived from `LearningArtifact` collections,
- belongs to knowledge aggregation,
- currently uses a placeholder implementation.

These two fingerprints must not be treated as the same contract.

A future ADR may rename them to remove semantic ambiguity. Until
that ADR is approved, their responsibilities remain separate.

---

## 8. Dependency Rules

### Allowed

```text
api → application
application → adaptive
application → core
application → scanner contracts
adaptive → core
scanner → core
scheduler → scanner runner
```

### Disallowed

```text
core → scanner
core → application
core → api
adaptive → api
adaptive → scheduler
scanner engines → api
domain artifacts → databases
```

Circular imports are prohibited.

---

## 9. Request Contract Rule

Whenever a formal request artifact exists, Application services
must receive that request artifact.

Correct:

```python
build_adaptive_dashboard(
    request: DashboardRequest,
)
```

Incorrect:

```python
build_adaptive_dashboard(
    token=...,
    decision=...,
    confidence=...,
    fingerprint=...,
)
```

This rule prevents contract drift and primitive obsession.

---

## 10. Persistence Rule

Persistence flow must remain explicit:

```text
Artifact
   ↓
Serializer
   ↓
Payload
   ↓
Store
```

Stores must not:

- construct domain decisions,
- infer missing business values,
- mutate immutable artifacts,
- silently redefine artifact contracts.

---

## 11. Time Rule

New timestamps must be timezone-aware UTC values.

Preferred:

```python
datetime.now(timezone.utc)
```

Deprecated for new code:

```python
datetime.utcnow()
```

Existing usages may be migrated incrementally through dedicated
refactoring modules.

---

## 12. Engineering Change Rule

Every architecture-sensitive change must follow:

```text
Issue
  ↓
Repository Audit
  ↓
Dependency Audit
  ↓
Root Cause
  ↓
Architecture Decision
  ↓
Full File or Full Section Replacement
  ↓
Targeted Test
  ↓
Relevant Regression Test
  ↓
PASS
  ↓
Commit
  ↓
LOCK
```

No architecture contract is considered locked until its tests pass
and the change is committed.

---

## 13. Current Locked Contracts

The following contracts are locked:

- `DecisionArtifact`
- `DashboardRequest`
- `DashboardRequestBuilder`
- `AdaptiveDashboardService`
- `DashboardCard`
- `DashboardCollectionService`
- Module 04C Production Runner integration

Changes to these contracts require a new Architecture Decision
Record.

---

## 14. Legacy Code Policy

Legacy modules must not be deleted merely because they fail current
tests.

Each legacy module must first be classified as:

- migrate,
- replace,
- archive,
- delete.

Deletion requires evidence that no active production path, test,
import, or consumer depends on the module.

---

## 15. Definition of Done

A module is complete only when:

- ownership is clear,
- contracts are explicit,
- dependency direction is valid,
- targeted tests pass,
- relevant regression tests pass,
- no production side effects occur during test collection,
- changes are committed,
- status is marked `LOCKED`.

---

## 16. Architecture Change Control

Any proposal that changes:

- artifact ownership,
- dependency direction,
- service request contracts,
- Production Runner responsibilities,
- persistence boundaries,
- folder responsibilities,

must be documented in a new ADR before implementation.

The Architecture Constitution remains the baseline. ADRs explain
approved exceptions or evolution without silently rewriting prior
decisions.
