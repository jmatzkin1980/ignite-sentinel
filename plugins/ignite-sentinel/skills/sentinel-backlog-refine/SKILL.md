---
name: sentinel-backlog-refine
description: "Use when proposing governed backlog refinements through the sanctioned /refine-backlog channel: reslicing, split/merge, missing stories, or enabler candidates, every proposal grounded in verbatim source-of-truth citations and landing as agent-origin proposals for BA review. Trigger on 'this story is too big', slicing improvements, enabler candidates, or backlog restructuring ideas. Not for deriving the backlog from specs (use sentinel-backlog) or reporting implementation blockers (use sentinel-implementation-feedback)."
---

# Sentinel Backlog Refine

Use this skill when the backlog already exists and an agent has a proposed improvement to slicing, story boundaries, missing stories, or enabler candidates.

## Workflow

1. Inspect `workspaces/PROJECT_ID/04_backlog/EPIC-001.md`, relevant `US-NNN.md` files, `03_specs/units/SPEC-U-NNN.md`, and focused context packs.
2. Create a JSON source file with `proposals[]` following `sentinel/schemas/backlog_refinement.schema.json`.
3. Run `sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /refine-backlog PROJECT_ID --source PATH`.
4. Review `workspaces/PROJECT_ID/04_backlog/refinements/refinement_report.md`. If no proposal is accepted the command exits 3 and changes nothing but that report; its message lists why each proposal was refused.
5. Report accepted and rejected proposals. Do not edit generated backlog artifacts by hand.

## Proposal Rules

- Every proposal must include verbatim `citations[]` from local source-of-truth files.
- Optional `discarded_alternative` may capture `{ "option": "...", "reason": "..." }` when another option was considered and rejected; include it only when it adds BA decision context.
- Use only existing story IDs and `SPEC-U-*` IDs unless the proposal kind is `missing-story`.
- Do not propose refinements over `[PENDING INPUT]` stories or pending Spec Units.
- Express slicing recommendations inside the existing INVEST/SPIDR/Lawrence model; do not alter the model.
- Enabler candidates must name the supported boundary, enabled stories, concrete `enabled_capability`, measurable `verification_method`, risk reduced, and objective evidence. Reject generic setup, environment availability, broad hardening, or vague accessibility as enablers unless tied to confirmed project functionality and completion evidence.
- Proposals accumulate across runs. Sending a proposal already on record (same content) adds nothing; its id comes back in `unchanged`. A new proposal without `id` whose default `BREF-NNN` is taken gets the next free number; an explicit `id` already on record replaces that proposal.
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
      "discarded_alternative": {
        "option": "Split all dashboard queues into separate stories immediately.",
        "reason": "The cited evidence only confirms the first data dependency slice."
      },
      "citations": ["verbatim local quote"]
    }
  ]
}
```

## Change (`--change CHG-NNN`)

When the BA is working on one change (a request that modifies a system that already exists), refine the stories of that change instead of the project's. In chat: "refine this change's stories" or "this story of CHG-001 is too big". Behind it, run `sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /refine-backlog PROJECT_ID --source PATH --change CHG-NNN`, after `/backlog --change` and `/quality --change` have run.

- `target_stories` are stories of that change (`04_backlog/US-NNN.md` with `change: CHG-NNN`), and `source_units` are units the change owns: those of the change and of its releases. A story or unit of the project, or of another change, is refused.
- Citations are verbatim lines of the change's own text: its request, brief, specs, stories and context packs. The project's raw input is not part of it.
- The proposals open in the change (`04_backlog/CHG-NNN/refinements/`), with their own report. `/refine-backlog PROJECT_ID` without `--change` leaves the stories of a change alone, and a refinement of the change makes its quality audit stale: run `/quality PROJECT_ID --change CHG-NNN` again.
- If `/specs --change` regenerated the units after the backlog, the backlog of the change is behind: the command refuses ("The backlog of CHG-NNN is missing or behind") and names `/backlog PROJECT_ID --change CHG-NNN`, as `/quality --change` does.
- In a workspace that only has changes, the form without `--change` refuses (the project has no `EPIC-001` and its health is not clean); use `--change`. `--release` is not accepted.

## Formato

The example of `/refine-backlog --change`: it is parsed by the real validator in the test suite, against the stories and units of a change and the request of a made-up Compras change (guardar borrador en el alta de proveedores):

```sentinel-example kind=refinement-proposals lang=es
{
  "proposals": [
    {
      "kind": "reslice",
      "target_stories": ["US-001"],
      "source_units": ["SPEC-U-001"],
      "slicing_pattern": "Workflow Steps",
      "recommendation": "Dejar en una historia sólo guardar el borrador incompleto, sin la consulta posterior.",
      "rationale": "El pedido separa guardar lo cargado de consultar y retomar los borradores.",
      "citations": ["después consultar sus borradores y retomarlos para terminar el alta"]
    },
    {
      "kind": "missing-story",
      "source_units": ["SPEC-U-002"],
      "recommendation": "Agregar una historia para retomar un borrador y terminar el alta.",
      "rationale": "El pedido lo nombra y ninguna historia lo cubre todavía.",
      "citations": ["retomarlos para terminar el alta"]
    }
  ]
}
```

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
