# ADR-0011: Lockfile-based Dependency Pinning

**Status:** Accepted

**Date:** 2026-07-23

**Decision Makers:**
- Akhilesh Choure

**Supersedes:**
- None

**Superseded By:**
- None

## Context

Benchmark reproducibility requires that two runs at different times use the same dependency versions. Unpinned or loosely-pinned dependencies (e.g., `ragas>=0.1`) introduce an uncontrolled variable — a benchmark improvement could be caused by a new library version rather than a pipeline change. CI builds must produce the same environment as local development.

## Decision

Maintain two requirement files:

- **`requirements.txt`** — Direct dependencies with exact pins (e.g., `ragas==0.2.5`). Used for documentation and quick setup.
- **`requirements-lock.txt`** — All transitive dependencies with exact pins. Produced by `pip freeze` after a clean install. Used as the canonical install source in CI.

Add `scripts/verify_install.py` that checks:
1. All 11 key imports resolve without error
2. The lockfile hash matches expected value (detects manual edits to lockfile)
3. Optionally (`--clean`), install from scratch in a temporary venv

## Consequences

- **Positive**: CI and local environments are identical — eliminates dependency drift as a variable
- **Positive**: Lockfile hash provides a quick integrity check
- **Positive**: Explicit dependency upgrades — switching from `ragas==0.2.5` to `0.3.0` is a deliberate commit, not a silent CI change
- **Negative**: Lockfile maintenance overhead — must regenerate when dependencies change
- **Negative**: Security updates require manual lockfile regeneration — not automatic

## Alternatives Considered

- **`>=` pins in requirements.txt**: Simple but permits drift. Rejected for reproducibility.
- **Pipenv/Poetry lockfiles**: Richer dependency management but adds a new tool to the stack. Rejected for minimal toolchain.
- **No lockfile**: Simplest but guarantees non-reproducible builds. Rejected.
