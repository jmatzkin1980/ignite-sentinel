---
name: sentinel-discovery
description: Use when Codex needs to ingest raw client requirements for Ignite Sentinel, extract requirements, gaps, assumptions, risks, pending decisions, and seed traceability for a project workspace.
---

# Sentinel Discovery

Use this skill to start or refresh discovery for a project.

## Workflow

1. Confirm or create the project workspace with `python -m sentinel /init PROJECT_ID`.
2. Place domain-owned context in the workspace context folders when available:
   - `workspaces/PROJECT_ID/00_raw/01_business_context/`
   - `workspaces/PROJECT_ID/00_raw/02_technology_context/`
   - `workspaces/PROJECT_ID/00_raw/03_design_context/`
   - `workspaces/PROJECT_ID/00_raw/04_quality_context/`
   - `workspaces/PROJECT_ID/00_raw/05_interactions/`
3. Ingest raw material with `python -m sentinel /ingest PROJECT_ID --source PATH`.
4. Use focused retrieval before analysis: `python -m sentinel /retrieve PROJECT_ID --query "DISCOVERY_TOPIC" --workflow discovery --write-pack`.
5. Review generated artifacts in `workspaces/PROJECT_ID/01_discovery/` and `02_requirements/`.
6. Run `python -m sentinel /health PROJECT_ID` before downstream specs or backlog work.

## Memory

- Sentinel uses local LanceDB memory under `workspaces/PROJECT_ID/memory.lancedb/`.
- `/ingest` indexes generated artifacts and context folders so Codex can retrieve technology, design, quality, business, and interaction evidence without generating those domain specs.
- If artifacts were edited manually, run `python -m sentinel /reindex PROJECT_ID` before relying on `/retrieve`.

## Rules

- Treat raw input as evidence, not truth.
- Treat technology, design, and quality context folders as source input owned by external domains.
- Convert missing or ambiguous information into explicit `GAP` entries.
- Do not invent metrics, users, scope, or acceptance criteria.
- Preserve traceability from `RAW` to `REQ`, `GAP`, and `DEC`.
