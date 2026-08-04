# ADR-003: Dependency Rules

**Status:** Accepted  
**Decision Date:** Sprint E9.5  
**Architecture Version:** 1.0  
**Supersedes:** None  
**Related Documents:**

- `docs/architecture/DexSato_Architecture.md`
- `docs/architecture/ADR/ADR-001_Artifact_Ownership.md`
- `docs/architecture/ADR/ADR-002_Folder_Responsibility.md`

---

# 1. Context

As DexSato grows, the number of modules, packages and
cross-layer interactions increases.

Without explicit dependency rules:

- circular imports become common,
- business logic leaks into infrastructure,
- services become tightly coupled,
- testing becomes increasingly difficult,
- architecture slowly degrades.

A stable dependency model is therefore required.

---

# 2. Decision

DexSato adopts **one-way dependency flow**.

Every dependency must point toward a more stable layer.

Higher layers may depend on lower layers.

Lower layers must never depend on higher layers.

---

# 3. Dependency Hierarchy

The official dependency hierarchy is:

```text
Delivery Layer
(api)

        ↓

Application Layer
(application)

        ↓

Adaptive Layer
(adaptive)

        ↓

Core Domain
(core)

        ↓

Python Standard Library
```

Infrastructure integrations are attached from the outside.

---

# 4. Layer Responsibilities

## Delivery Layer

Responsible for:

- HTTP
- REST
- FastAPI
- CLI
- WebSocket
- External transport

Allowed dependency:

```text
api
    ↓
application
```

Forbidden:

```text
api
    ↓
core
```

Business rules must never live here.

---

## Application Layer

Responsible for:

- use cases
- orchestration
- coordination

Allowed:

```text
application
    ↓
adaptive

application
    ↓
core

application
    ↓
scanner contracts
```

Forbidden:

- market interpretation
- signal detection
- trading decisions

---

## Adaptive Layer

Responsible for:

- experience
- history
- dashboard
- adaptive reasoning

Allowed:

```text
adaptive
    ↓
core
```

Forbidden:

```text
adaptive
    ↓
application

adaptive
    ↓
api
```

---

## Scanner Layer

Responsible for:

- production scanning
- intelligence engine
- lifecycle engine
- runner
- serializers
- stores

Allowed:

```text
scanner
    ↓
core
```

Scanner may invoke Application entry points where architecture
explicitly requires orchestration.

Scanner engines must never depend on Delivery.

---

## Core Layer

Core is the most stable layer.

Allowed:

```text
core
```

Only:

- standard library
- other core modules

Forbidden:

```text
core
    ↓
scanner

core
    ↓
adaptive

core
    ↓
application

core
    ↓
api
```

---

# 5. Circular Imports

Circular imports are prohibited.

Example:

❌

```text
A imports B

↓

B imports A
```

Correct:

```text
A

↓

Contract

↓

B
```

Use explicit contracts rather than bidirectional imports.

---

# 6. Dependency Inversion

Whenever orchestration requires communication across layers,
depend on stable contracts.

Example:

Instead of:

```text
Runner

↓

Dashboard Builder
```

Use:

```text
Runner

↓

DashboardRequest

↓

Application Service

↓

DashboardCard
```

Contracts remain stable while implementations evolve.

---

# 7. Import Rules

Preferred:

```python
from adaptive.dashboard.dashboard_request import (
    DashboardRequest,
)
```

Avoid:

```python
from adaptive.dashboard import *
```

Wildcard imports are prohibited.

---

# 8. Relative Imports

Within production code:

Prefer absolute imports.

Correct:

```python
from scanner.runner import run_scan
```

Avoid:

```python
from ..runner import run_scan
```

Absolute imports improve readability and reduce ambiguity.

---

# 9. Public Contracts

Only public contracts should cross folder boundaries.

Examples:

- DecisionArtifact
- DashboardRequest
- DashboardCard
- HistorySummary
- ExperienceArtifact

Private helper functions should remain internal.

---

# 10. Testing Dependencies

Tests may depend on:

- public contracts,
- builders,
- services,
- fixtures.

Tests must not redefine production contracts.

---

# 11. Future Layers

Future modules such as:

- AI Engine
- Notification Engine
- Portfolio Engine
- Analytics Engine

must follow the same dependency direction.

New layers must not violate Core stability.

---

# 12. Compliance Checklist

Before introducing a dependency:

- [ ] Is the dependency pointing downward?
- [ ] Does it introduce a circular import?
- [ ] Is there already a public contract?
- [ ] Can a service coordinate instead?
- [ ] Does it violate folder ownership?
- [ ] Will testing become harder?

---

# 13. Consequences

Positive:

- predictable architecture,
- easier refactoring,
- lower coupling,
- higher testability,
- easier onboarding,
- safer evolution.

Trade-offs:

- additional service layers,
- more explicit contracts,
- slightly more files.

These trade-offs are accepted.

---

# 14. Final Decision

DexSato adopts strict dependency governance.

Dependency direction is part of the architecture.

Any new dependency violating this ADR requires architecture review
before implementation.