---
name: sentinel-discovery
description: Use when Codex needs to ingest raw client requirements for Ignite Sentinel, extract requirements, gaps, assumptions, risks, pending decisions, and seed traceability for a project workspace.
---

# Sentinel Discovery

Use this skill to start or refresh discovery for a project.

## Workflow

1. Confirm or create the project workspace with `python -m sentinel init PROJECT_ID`.
2. Ingest raw material with `python -m sentinel ingest PROJECT_ID --source PATH`.
3. Review generated artifacts in `workspaces/PROJECT_ID/01_discovery/` and `02_requirements/`.
4. Run `python -m sentinel health PROJECT_ID` before downstream specs or backlog work.

## Rules

- Treat raw input as evidence, not truth.
- Convert missing or ambiguous information into explicit `GAP` entries.
- Do not invent metrics, users, scope, or acceptance criteria.
- Preserve traceability from `RAW` to `REQ`, `GAP`, and `DEC`.
