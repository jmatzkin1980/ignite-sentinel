---
name: sentinel-backlog
description: Use when Codex needs to transform mature Ignite Sentinel specs into AI-friendly epics, user stories, and acceptance criteria with traceability.
---

# Sentinel Backlog

Use this skill to generate execution-ready backlog artifacts.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. Run `python -m sentinel /backlog PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/04_backlog/`.
4. Run `python -m sentinel /health PROJECT_ID`.

## Rules

- Generate vertical, value-oriented stories.
- Every story must have an ancestor requirement or spec.
- Acceptance criteria must be testable by Quality and Automation.
