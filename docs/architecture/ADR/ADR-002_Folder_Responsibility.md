ADR-002: Folder Responsibility

Status: AcceptedDecision Date: Sprint E9.5Architecture Version: 1.0Supersedes: NoneRelated Documents:

docs/architecture/DexSato_Architecture.md

docs/architecture/ADR/ADR-001_Artifact_Ownership.md

1. Context

DexSato has grown into a multi-layer Python system containing production scanning, domain artifacts, adaptive intelligence, application services, delivery components, operational tracking, scheduling, validation, and automated tests.

Without explicit folder ownership, business logic can drift into delivery or orchestration code, services can duplicate domain calculations, infrastructure code can redefine contracts, and new modules can be placed according to convenience rather than architecture.

A formal folder-responsibility model is required so each top-level package has a clear purpose, dependency direction, and change boundary.

2. Decision

Each top-level DexSato folder has one primary architectural responsibility.

Folder

Primary Responsibility

core/

Stable domain artifacts and domain-level contracts

scanner/

Production market intelligence engine and orchestration entry point

adaptive/

Adaptive intelligence contracts and historical reasoning

application/

Use-case orchestration and service coordination

api/

External HTTP or transport delivery boundary

pulse/

Operational job tracking and execution telemetry

scheduler/

Scheduled invocation of application or runner entry points

validation/

Engineering validation and contract verification

tests/

Automated unit, contract, integration, and regression tests

docs/

Architecture, ADRs, SOPs, and technical documentation

A module must be placed according to what it owns, not merely according to which feature currently uses it.

3. Global Placement Rule

DecisionArtifact contract          → core/
Signal detection engine            → scanner/
DashboardRequest contract          → adaptive/
Dashboard use-case orchestration   → application/
HTTP route                         → api/
Job duration tracking              → pulse/
Scheduled scan trigger             → scheduler/
Architecture contract test         → validation/ or tests/
ADR document                       → docs/

4. core/

core/ owns stable business and domain contracts.

It may depend on the Python standard library and other stable modules inside core/.

It must not depend on scanner/, adaptive/, application/, api/, pulse/, scheduler/, databases, external market APIs, or web frameworks.

It must not fetch market data, persist records, orchestrate use cases, expose HTTP routes, schedule jobs, or calculate presentation-specific output.

5. scanner/

scanner/ owns the production market-intelligence pipeline.

Typical contents include market acquisition, pair selection, normalization, observation building, signal detection, interpretation, decision execution, knowledge gating, operational fingerprint construction, lifecycle execution, serializers, deserializers, stores, and the Production Runner.

The Runner may invoke engines, pass Core artifacts, build the operational fingerprint once, invoke Application services, coordinate persistence, and return the production result.

The Runner must not detect signals directly, interpret markets directly, make trading decisions directly, calculate adaptive history, redefine domain artifacts, or contain database-specific business rules.

6. adaptive/

adaptive/ owns historical and adaptive intelligence derived from Core decisions, outcomes, learning, and accumulated experience.

Typical contents include ExperienceArtifact, EvidenceArtifact, HistorySummary, DashboardRequest, DashboardCard, compilers, mergers, repositories, history builders, evidence builders, and dashboard builders.

It must not make the original market decision, fetch external market data, control the Runner, expose HTTP routes, schedule execution, redefine Core artifacts, or own database business workflows directly.

Preferred dependency:

adaptive → core

Not:

core → adaptive

7. application/

application/ owns use-case orchestration.

It may receive formal request artifacts, invoke repositories and builders, coordinate Core and Adaptive artifacts, compose use-case results, and enforce workflow order.

It must not contain signal-detection rules, market-interpretation rules, trading decisions, duplicate domain calculations, redefine artifacts, or accept primitive parameter collections when a formal request artifact already exists.

Correct:

build_adaptive_dashboard(
    request: DashboardRequest,
)

Incorrect:

build_adaptive_dashboard(
    token=...,
    decision=...,
    confidence=...,
    fingerprint=...,
)

8. api/

api/ owns transport and HTTP delivery.

It may contain routes, request parsing, response serialization, transport validation, HTTP status mapping, and authentication boundary code.

It must not make market decisions, calculate adaptive history, implement persistence business flows directly, redefine domain artifacts, or duplicate Application orchestration.

Preferred dependency:

api → application

9. pulse/

pulse/ owns operational execution tracking such as job start, job finish, status, duration, error recording, and telemetry.

Pulse may observe execution but must not influence market decisions.

10. scheduler/

scheduler/ owns time-based invocation.

It may determine when a scan runs, invoke a public Runner or Application entry point, and record scheduling metadata.

It must not duplicate scanning logic, build observations, detect signals, interpret markets, make decisions, or persist domain artifacts directly.

The Scheduler triggers work; it does not own the work.

11. validation/

validation/ owns explicit engineering verification beyond ordinary unit tests.

Validation modules must use current package-qualified imports, avoid obsolete module paths, avoid production side effects during import, fail with clear messages, and reflect current locked contracts.

12. tests/

tests/ owns automated verification.

Tests must be safe during pytest collection, avoid production side effects at import time, use package-qualified imports, mock external boundaries where appropriate, test current contracts, and avoid depending on incidental execution order.

Engineering scripts that execute and assert at import time should be migrated into explicit pytest test functions or moved outside pytest collection paths.

13. docs/

docs/ owns long-lived technical documentation including the Architecture Constitution, ADRs, Engineering SOPs, migration notes, module lifecycle records, and runbooks.

Documentation may be created or updated directly through the GitHub connector only when explicitly authorized by the repository owner.

This permission does not extend to production code, tests, configuration, or repository automation unless separately authorized.

14. Cross-Folder Dependency Rules

Allowed:

api → application
application → adaptive
application → core
application → scanner contracts
adaptive → core
scanner → core
scheduler → scanner runner or application entry point
validation → public contracts under test
tests → public contracts under test

Disallowed:

core → scanner
core → adaptive
core → application
core → api
adaptive → api
adaptive → scheduler
scanner engines → api
pulse → decision logic
scheduler → internal scanner engines
production artifacts → tests

Circular imports are prohibited.

15. Moving Modules

Before moving a module:

identify its primary responsibility,

identify all importers,

verify the destination folder owns that responsibility,

update package-qualified imports,

update tests and validation scripts,

run targeted and relevant regression tests,

document ownership changes in an ADR when necessary.

A file move must not hide unresolved responsibility overlap.

16. New Module Checklist

Primary responsibility is clear.

Destination folder owns that responsibility.

Dependencies follow the approved direction.

No existing contract or service is duplicated.

No circular import is introduced.

Public contract is explicit.

Relevant tests are planned.

Architecture documentation is updated when ownership changes.

17. Consequences

Positive consequences include predictable folder placement, easier dependency audits, bounded Runner and Application responsibilities, isolated domain contracts, and easier legacy classification.

Trade-offs include legacy migrations, removal of convenience imports, broader import updates during moves, and occasional adapter modules.

These trade-offs are accepted because long-term architectural clarity is more valuable than short-term placement convenience.

18. Rejected Alternatives

Organizing only by feature name is rejected because one feature can cross several architectural layers.

Placing all business logic in application/ is rejected because Application owns orchestration, not all domain logic.

Letting the Runner own every production concern is rejected because it would become a monolith.

Permitting unrestricted imports is rejected because it creates circular dependencies and implicit ownership.

19. Final Decision

DexSato adopts responsibility-based folder governance.

Each top-level folder has one primary architectural purpose.

Modules must be placed according to ownership and dependency direction.

No folder may silently absorb responsibilities owned by another layer.

Material changes to folder boundaries require architecture review and a new ADR.
