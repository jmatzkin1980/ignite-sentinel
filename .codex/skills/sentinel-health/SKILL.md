---
name: sentinel-health
description: Use when Codex needs to audit Ignite Sentinel project health, traceability, open gaps, unbacked metrics, orphan stories, and memory indexing status.
---

# Sentinel Health

Use this skill as the final gate for any Sentinel workflow.

## Workflow

1. Run `python -m sentinel health PROJECT_ID`.
2. Review `workspaces/PROJECT_ID/06_traceability/health_report.md`.
3. If verdict is `DIRTY`, fix the findings and rerun health.
4. Use `python -m sentinel trace PROJECT_ID` when findings mention traceability.

## Rules

- Health is based on versionable artifacts and deterministic checks.
- LanceDB or fallback memory cannot override source files.
- Metrics without explicit source or baseline are findings.
