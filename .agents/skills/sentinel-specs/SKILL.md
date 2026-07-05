---
name: sentinel-specs
description: "Use when generating or reviewing the Ignite Sentinel PRD and AI-friendly specification layer with /specs: the human PRD, the compact spec index, bounded SPEC-U-* execution units, retrieval plans, and the REQ->PRD->SPEC trace. Trigger on 'generate the PRD', 'generate specs', spec-unit questions, or preparing the downstream handoff from a mature brief."
---

# Sentinel Specs

Use this skill to create the PRD and AI-friendly spec layer.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. If ready, run `python -m sentinel /specs PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/03_specs/prd.md` for the complete human/business PRD: personas, FRs/ACs, NFRs, KPIs, JTBD traceability, execution plan, governance, and audit trail.
4. Review `workspaces/PROJECT_ID/03_specs/specs.md` for the agent-ready backlog contract and spec-unit index.
5. Review `workspaces/PROJECT_ID/03_specs/units/SPEC-U-NNN.md` for bounded, evidence-backed execution units before backlog slicing.
6. Review `workspaces/PROJECT_ID/08_context_packs/specs_generation.json` to see which declarative retrieval plan sections, focused memory context, and source `read_plan` anchors were used.
7. Run `python -m sentinel /trace PROJECT_ID` to confirm `REQ/project_brief -> PRD -> SPEC -> SPEC-U` linkage.

## Rules

- Specs must elaborate existing requirements.
- Do not proceed while maturity is `BLOCKED`.
- Keep Product, Technology, Design, Quality, and Delivery signals visible.
- Retrieval plans live in `sentinel/retrieval_plans/*.json`; tune section queries, filters, budgets, and lenses there instead of editing Python.
- PRD explains what and why for humans with traceable requirements and acceptance criteria; specs preserves the compact agent contract, retrieval plan, trace IDs, spec-unit index, and backlog handoff cues.
- Do not treat fixed placeholder IDs as execution scope. Use `SPEC-U-*` files when they exist; each unit carries frontmatter with trace IDs, EARS IDs, and source anchors.
- PRD generation performs evidence-backed extraction (IMP-005): personas, requirement-like statements, and quantitative metrics are quoted verbatim from the raw client input under `00_raw/00_client_requirement/` with `REQ-001` citations. When no signal exists, sections keep `[PENDING INPUT]` instead of inventing content.
