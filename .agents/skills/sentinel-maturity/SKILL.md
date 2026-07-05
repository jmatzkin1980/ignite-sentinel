---
name: sentinel-maturity
description: "Use when deciding whether an Ignite Sentinel requirement is mature enough to generate specs or backlog: run /maturity, read the maturity report and its metrics (gap closure rate, maturity score, trend), and recommend gap resolution when readiness is BLOCKED. Trigger on 'is it ready', 'can we generate specs/backlog yet', maturity checks, or a downstream command blocked by maturity."
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
- `/maturity` returns a `metrics` block (IMP-008): `gap_closure_rate`, `open_gaps_by_severity`, `artifact_evidence_scores`, combined `maturity_score` and `trend_vs_previous_run`. Summarize the score and trend to the user along with readiness, and recommend gap resolution when the trend is flat or negative.
