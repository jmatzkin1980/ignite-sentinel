---
name: sentinel-maturity
description: Use when Codex needs to evaluate whether an Ignite Sentinel requirement is mature enough to generate specs or backlog, including domain readiness and blocking gap detection.
---

# Sentinel Maturity

Use this skill before specs or backlog generation.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. Read `workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md`.
3. If readiness is `BLOCKED`, resolve critical or high gaps before proceeding.
4. If readiness is `READY_FOR_SPECS`, continue with `sentinel-specs` or `sentinel-backlog`.

## Rules

- Critical and high open gaps block downstream generation.
- Maturity is a gate, not a writing exercise.
- Prefer concise gap remediation questions over speculative completion.
