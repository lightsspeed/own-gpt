# AI Engineering Platform — Architecture Constitution

This document defines the architectural rules for this repository.

It is **not** a feature specification.

It describes the invariants that every code change must preserve.

If a requested implementation conflicts with these rules, preserve the architecture first.

---

# Mission

Build an evidence-driven AI engineering platform that continuously improves AI systems through observation, evaluation, experimentation, governance, and human approval.

The platform is designed for long-term evolution.

Optimize for maintainability, traceability, and correctness over speed.

---

# Core Philosophy

Every stage transforms information.

No stage mutates previous stages.

Every output becomes an immutable artifact.

Every artifact has lineage.

Every production change is explainable.

---

# Lifecycle

All capabilities belong to exactly one lifecycle stage.

Observe

↓

Measure

↓

Explain

↓

Propose

↓

Validate

↓

Apply

↓

Operate

Never skip stages.

Never merge stages.

---

# Platform Layers

Runtime

↓

Learning Ledger

↓

Analytics

↓

Evidence

↓

Recommendations

↓

Experiments

↓

Configuration

↓

Operations

↓

Automation

Dependencies only flow downward.

Lower layers never depend on higher layers.

---

# Artifact Principles

Artifacts are immutable.

Artifacts are append-only.

Artifacts never overwrite history.

Every artifact must include:

- id
- timestamp
- lineage
- version

Whenever possible artifacts should be dataclasses or Pydantic models.

Never return raw dictionaries for persisted artifacts.

---

# Lineage Rules

Every artifact must reference its parent.

Typical lineage:

LearningRecord

↓

AnalyticsReport

↓

Evidence

↓

Finding

↓

Recommendation

↓

ExperimentDefinition

↓

DecisionCandidate

↓

Decision

↓

ConfigurationSnapshot

Never create orphan artifacts.

---

# Capability Registry

Every major subsystem must register its capabilities.

Each capability must define:

- id
- name
- owner
- lifecycle_stage
- maturity
- dependencies
- artifacts
- api_prefix

If a new subsystem is added, update the Capability Registry.

---

# Configuration

Configuration is an artifact.

Configuration is never mutable.

Changes create a new ConfigurationSnapshot.

Rollback changes pointers.

Never modify historical snapshots.

---

# Operations

Operators interact with workspaces.

Never expose internal engines directly.

Approved workspaces:

- Findings
- Recommendations
- Experiments
- Decisions
- Configuration
- Artifact Explorer

Operator APIs should aggregate information.

Do not leak internal implementation details.

---

# Automation

Automation orchestrates existing capabilities.

Automation should never duplicate business logic.

Jobs call existing services.

Automation owns:

- schedules
- execution
- snapshots
- triggers
- reports

---

# Human Approval

The platform is intentionally human-governed.

Never automatically:

- approve recommendations
- approve experiments
- modify production configuration
- deploy configuration

Automation may recommend.

Humans apply.

---

# State

State transitions must be explicit.

Prefer immutable snapshots over mutable state.

When state changes:

Old State

↓

New State

↓

Diff

↓

Artifact

Avoid in-place mutation.

---

# APIs

REST APIs should expose business concepts.

Good:

/operations/findings

/config/snapshots

/capabilities

Bad:

/evidence_engine/run

/internal_calibration

Keep engine details internal.

---

# Dependency Rules

Prefer dependency injection.

Avoid circular imports.

Business logic belongs in services.

API routes should remain thin.

Persistence should remain isolated.

---

# Testing

Every new capability should include:

- unit tests
- integration tests where appropriate

Prefer deterministic tests.

Avoid time-dependent assertions.

---

# Logging

Logs are operational.

Artifacts are historical.

Do not confuse the two.

Never rely on logs as the system of record.

---

# Before Adding Anything

Ask:

1. Does this belong in an existing package?

2. Does an existing artifact already represent this?

3. Does this violate lifecycle boundaries?

4. Does this duplicate an existing capability?

5. Does this require a new artifact?

Only introduce new architectural concepts when existing abstractions cannot represent them.

---

# Definition of Good Code

Good code is:

- simple
- deterministic
- composable
- observable
- testable
- traceable

Avoid cleverness.

Prefer explicitness.

---

# Definition of Done

A feature is complete when:

✓ Architecture remains consistent

✓ Capability Registry updated

✓ Lineage preserved

✓ APIs documented

✓ Tests added

✓ Existing invariants preserved

Feature completeness is secondary to architectural correctness.

---

# Things To Never Do

- Bypass lineage
- Mutate artifacts
- Introduce hidden state
- Duplicate business logic
- Skip lifecycle stages
- Couple UI to engines
- Couple automation to implementation details
- Break immutable history

---

# Long-Term Goal

The platform should evolve by adding capabilities—not by redesigning architecture.

Architecture is expected to remain stable.

Implementations are expected to evolve.

When in doubt:

Preserve architecture.
