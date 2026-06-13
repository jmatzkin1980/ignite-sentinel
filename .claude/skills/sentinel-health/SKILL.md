---
name: sentinel-health
description: Use when Codex needs to audit Ignite Sentinel project health, traceability, open gaps, unbacked metrics, orphan stories, and memory indexing status.
---

# Sentinel Health

Use this skill as the final gate for any Sentinel workflow.

## Workflow

1. Run `python -m sentinel /health PROJECT_ID`.
2. Review `workspaces/PROJECT_ID/06_traceability/health_report.md`.
3. If verdict is `DIRTY`, fix the findings and rerun health.
4. Use `python -m sentinel /trace PROJECT_ID` when findings mention traceability.

## Rules

- Health is based on versionable artifacts and deterministic checks.
- LanceDB or fallback memory cannot override source files.
- Metrics without explicit source or baseline are findings.
- `/validate` also emits a non-blocking `semantic_quality` block (IMP-006): per-artifact score and classification (`evidence-backed` / `mixed` / `scaffolding`) for brief, PRD, and specs, plus `warnings`. Use it to decide whether downstream handoff content is mature, separate from structural validity.
- `/validate` also emits non-blocking `cross_artifact_consistency` warnings (IMP-045): brief->PRD continuity, confirmed `REQ-EARS-*` coverage in specs/spec units, FR extraction coverage, resolvable spec-unit source pointers, and orphan EARS references. Report the layer, artifact, and suggested corrective command without treating the warning as a failed structural verdict.
