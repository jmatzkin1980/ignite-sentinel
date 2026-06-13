---
name: sentinel-backlog-refine
description: Use when Codex needs to propose governed backlog refinements through the sanctioned `/refine-backlog` channel, with every proposal grounded in verbatim local source-of-truth citations.
---

# Sentinel Backlog Refine

Use this skill when the backlog already exists and an agent has a proposed improvement to slicing, story boundaries, missing stories, or enabler candidates.

## Workflow

1. Inspect `workspaces/PROJECT_ID/04_backlog/EPIC-001.md`, relevant `US-NNN.md` files, `03_specs/units/SPEC-U-NNN.md`, and focused context packs.
2. Create a JSON source file with `proposals[]` following `sentinel/schemas/backlog_refinement.schema.json`.
3. Run `python -m sentinel /refine-backlog PROJECT_ID --source PATH`.
4. Review `workspaces/PROJECT_ID/04_backlog/refinements/refinement_report.md`.
5. Report accepted and rejected proposals. Do not edit generated backlog artifacts by hand.

## Proposal Rules

- Every proposal must include verbatim `citations[]` from local source-of-truth files.
- Use only existing story IDs and `SPEC-U-*` IDs unless the proposal kind is `missing-story`.
- Do not propose refinements over `[PENDING INPUT]` stories or pending Spec Units.
- Express slicing recommendations inside the existing INVEST/SPIDR/Lawrence model; do not alter the model.
- Enabler candidates must name the supported boundary, enabled stories, risk reduced, and objective evidence. Reject generic setup, environment availability, broad hardening, or vague accessibility as enablers unless tied to confirmed project functionality and completion evidence.
- Accepted proposals are governed backlog refinements for BA review. They do not automatically rewrite stories, create scope, or replace the enabler boundary.

## JSON Shape

```json
{
  "proposals": [
    {
      "id": "BREF-001",
      "kind": "reslice",
      "target_stories": ["US-001"],
      "source_units": ["SPEC-U-001"],
      "slicing_pattern": "Data / External Dependency",
      "recommendation": "Refine the story boundary to isolate the confirmed data dependency first.",
      "rationale": "The cited Spec Unit confirms the dependency and acceptance surface.",
      "citations": ["verbatim local quote"]
    }
  ]
}
```
