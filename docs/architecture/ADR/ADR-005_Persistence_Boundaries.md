# ADR-005: Persistence Boundaries

**Status:** Accepted  
**Decision Date:** Sprint E9.5  
**Architecture Version:** 1.0  
**Supersedes:** None  

**Related Documents:**

- `docs/architecture/DexSato_Architecture.md`
- `docs/architecture/ADR/ADR-001_Artifact_Ownership.md`
- `docs/architecture/ADR/ADR-002_Folder_Responsibility.md`
- `docs/architecture/ADR/ADR-003_Dependency_Rules.md`
- `docs/architecture/ADR/ADR-004_Request_Contract_Rules.md`

---

## 1. Context

DexSato persists several categories of data:

- market events,
- Intelligence Packages,
- Outcome artifacts,
- Learning artifacts,
- Knowledge artifacts,
- adaptive experience and history data.

Persistence contract drift can occur when:

- stores receive domain artifacts directly,
- serializers omit newly required fields,
- deserializers no longer match artifact constructors,
- stores infer missing business values,
- database payloads become unofficial domain contracts,
- legacy records use older schemas,
- query services expose persistence structures directly.

The repository has already shown contract mismatches involving
deserializers and newer artifact constructors.

A formal persistence boundary is required.

---

## 2. Decision

DexSato adopts the following official persistence flow:

```text
Domain or Engine Artifact
        ↓
Serializer
        ↓
Persistence Payload
        ↓
Store
        ↓
Database
```

The official retrieval flow is:

```text
Database Record
        ↓
Store
        ↓
Persistence Payload
        ↓
Deserializer or Assembler
        ↓
Domain Artifact
```

No layer may skip these boundaries without an explicit architecture
decision.

---

## 3. Artifact Boundary

Domain artifacts are authoritative in memory.

Database records are authoritative only as persisted representations.

A database payload is not automatically a domain artifact.

Therefore:

```text
Artifact ≠ Payload
Payload ≠ Database Record
Database Record ≠ Artifact
```

Conversion must remain explicit.

---

## 4. Serializer Responsibility

A serializer converts an artifact into a persistence-safe payload.

It may:

- extract artifact fields,
- convert enums into stable values,
- convert timestamps into ISO-compatible values,
- convert nested artifacts into nested payloads,
- preserve artifact identity and version metadata.

It must not:

- make trading decisions,
- infer missing business values,
- mutate the source artifact,
- access the database,
- silently remove required fields,
- replace an artifact with a competing contract.

---

## 5. Store Responsibility

A store persists and retrieves payloads.

It may:

- insert records,
- update records,
- query records,
- apply database-specific filters,
- return persistence payloads.

It must not:

- construct trading decisions,
- calculate confidence,
- aggregate adaptive history,
- create missing domain values,
- mutate immutable artifacts,
- become the canonical artifact owner.

Stores should receive serialized payloads rather than complex domain
objects unless a specific repository abstraction explicitly owns
artifact persistence.

---

## 6. Deserializer Responsibility

A deserializer converts a persistence payload into the current formal
artifact contract.

It must:

- provide every required constructor field,
- rebuild nested artifacts explicitly,
- restore timestamps accurately,
- restore enums and metadata,
- fail clearly when required data is absent.

It must not:

- silently ignore incompatible records,
- invent required business values without a migration rule,
- return partial artifacts,
- use obsolete constructor contracts.

---

## 7. Schema Compatibility Rule

When an artifact contract changes, the following must be audited:

1. serializer,
2. store payload,
3. database schema,
4. deserializer,
5. query services,
6. fixtures,
7. historical test payloads,
8. migration requirements.

An artifact change is incomplete until persistence compatibility is
verified.

---

## 8. Required Field Rule

A newly required artifact field must not be handled by silently assigning
an arbitrary default in the deserializer.

Approved options are:

- migrate historical records,
- derive the value using an explicit deterministic migration rule,
- make the artifact field optional through a documented contract change,
- reject incompatible historical records clearly.

Silent assumptions are prohibited.

---

## 9. Payload Versioning

Persistence payloads should include version metadata where practical.

Examples:

```text
engine_version
schema_version
artifact_version
created_at
updated_at
```

Version metadata enables:

- compatibility checks,
- migrations,
- historical interpretation,
- safe deserialization.

A future dedicated ADR may introduce formal schema-version numbering.

---

## 10. Timestamp Rule

All new persisted timestamps must be timezone-aware UTC values.

Preferred in memory:

```python
datetime.now(timezone.utc)
```

Preferred persisted representation:

```text
ISO 8601 with UTC offset
```

Example:

```text
2026-07-22T10:30:00+00:00
```

Naive UTC timestamps should not be introduced in new persistence code.

---

## 11. Intelligence Persistence

Official Intelligence persistence flow:

```text
Intelligence Package
        ↓
Intelligence Serializer
        ↓
Payload containing:
    token
    decision
    confidence
    knowledge fingerprint
    serialized intelligence package
        ↓
Intelligence Store
```

The operational Knowledge Fingerprint is built once by the Production
Runner and reused by persistence and adaptive consumers.

The store must not rebuild the fingerprint independently.

---

## 12. Lifecycle Persistence

Official Lifecycle persistence flow:

```text
Lifecycle Package
        ↓
Extract OutcomeArtifact
Extract LearningArtifact
Extract KnowledgeArtifact
        ↓
Dedicated Serializer for each artifact
        ↓
Dedicated Store for each payload
```

Each contained artifact remains owned by its Core artifact contract.

The Lifecycle Package does not replace the contained artifact contracts.

---

## 13. Adaptive Persistence

Adaptive repositories may store artifacts such as
`ExperienceArtifact`.

An Adaptive repository may:

- save experience,
- retrieve experience by fingerprint,
- clear controlled test repositories,
- return formal Adaptive artifacts where the repository contract
  explicitly guarantees it.

It must not:

- make the original trading decision,
- reconstruct unrelated Core artifacts,
- calculate presentation output,
- redefine fingerprint ownership.

---

## 14. Query Boundary

Application query services must not expose raw database rows as business
results.

Preferred flow:

```text
Store
   ↓
Payload
   ↓
Deserializer or Assembler
   ↓
Artifact or DTO
   ↓
Application Query Result
```

Raw persistence structures should remain behind the persistence boundary.

---

## 15. Legacy Record Policy

Legacy records must be classified as:

- directly compatible,
- compatible through explicit migration,
- readable through a legacy adapter,
- unsupported.

Unsupported records must fail with a clear compatibility error.

They must not produce incomplete artifacts silently.

---

## 16. Testing Rule

Persistence tests must cover:

- serializer output,
- required fields,
- timestamp representation,
- serializer–deserializer round trip,
- missing required fields,
- legacy compatibility,
- nested artifact restoration,
- store delegation,
- query service reconstruction.

A serializer test alone is insufficient when a deserializer also exists.

Round-trip tests are preferred:

```text
Artifact
   ↓ serialize
Payload
   ↓ deserialize
Artifact
```

The reconstructed artifact must preserve the original meaning.

---

## 17. Production Side-Effect Rule

Tests must not access production databases unless explicitly marked as
integration tests and configured for an isolated environment.

Unit tests should mock or replace external persistence boundaries.

Importing a test module must not write production data.

---

## 18. Failure Rule

Persistence failures must remain visible.

Stores and deserializers must not suppress:

- missing required fields,
- incompatible schemas,
- malformed timestamps,
- invalid nested payloads,
- unavailable database operations.

Failures should include enough context to identify the affected artifact
or payload type without exposing secrets.

---

## 19. Consequences

### Positive

- artifact and database contracts remain separate,
- serializer and deserializer drift becomes detectable,
- historical data compatibility becomes manageable,
- stores remain infrastructure components,
- query results become safer,
- migrations can be planned explicitly.

### Trade-offs

- additional serializer and deserializer code,
- contract changes require wider audits,
- historical records may require migrations,
- round-trip tests require more fixtures.

These trade-offs are accepted because persisted data outlives individual
code versions.

---

## 20. Rejected Alternatives

### Persist dataclasses directly

Rejected because databases require stable serialized contracts.

### Let stores infer missing fields

Rejected because stores do not own domain meaning.

### Treat database records as domain artifacts

Rejected because persistence schemas and domain contracts evolve
differently.

### Ignore legacy compatibility

Rejected because historical Intelligence and Learning records are part
of DexSato's accumulated knowledge.

---

## 21. Compliance Checklist

Before changing persistence code:

- [ ] Is the artifact contract identified?
- [ ] Is serialization explicit?
- [ ] Does the payload include every required field?
- [ ] Does the deserializer match the current constructor?
- [ ] Are timestamps timezone-aware?
- [ ] Is version metadata preserved where available?
- [ ] Does the store avoid business inference?
- [ ] Are legacy records classified?
- [ ] Do round-trip tests pass?
- [ ] Are query services protected from raw database structures?

---

## 22. Final Decision

DexSato adopts explicit persistence boundaries.

Artifacts are serialized before storage.

Stores persist payloads.

Payloads are deserialized before becoming artifacts.

Stores, serializers, and deserializers must not silently redefine domain
meaning.

Artifact changes require persistence compatibility review.