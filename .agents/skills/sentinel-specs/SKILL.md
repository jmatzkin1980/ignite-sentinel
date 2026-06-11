---
name: sentinel-specs
description: Use when Codex needs to generate PRD and AI-friendly specification artifacts from mature Ignite Sentinel requirements while preserving source traceability.
---

# Sentinel Specs

Use this skill to create the PRD and AI-friendly spec layer.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. If ready, run `python -m sentinel /specs PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/03_specs/prd.md` for the complete human/business PRD: personas, FRs/ACs, NFRs, KPIs, JTBD traceability, execution plan, governance, and audit trail.
4. Review `workspaces/PROJECT_ID/03_specs/specs.md` for the agent-ready backlog contract.
5. Review `workspaces/PROJECT_ID/08_context_packs/specs_generation.json` to see which focused memory context was used.
6. Run `python -m sentinel /trace PROJECT_ID` to confirm `REQ/project_brief -> PRD -> SPEC` linkage.

## Rules

- Specs must elaborate existing requirements.
- Do not proceed while maturity is `BLOCKED`.
- Keep Product, Technology, Design, Quality, and Delivery signals visible.
- PRD explains what and why for humans with traceable requirements and acceptance criteria; specs preserves the compact agent contract, retrieval plan, trace IDs, and backlog handoff cues.
- PRD generation performs evidence-backed extraction (IMP-005): personas, requirement-like statements, and quantitative metrics are quoted verbatim from the raw client input under `00_raw/00_client_requirement/` with `REQ-001` citations. When no signal exists, sections keep `[PENDING INPUT]` instead of inventing content.
