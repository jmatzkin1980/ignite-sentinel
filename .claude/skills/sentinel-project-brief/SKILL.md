---
name: sentinel-project-brief
description: "Use when generating or refreshing the Ignite Sentinel project brief once discovery gaps and seeds are stable: check /status and /maturity, run /brief, read the per-section readiness and its gates (brief coverage, unit implementability, specification self-correction), and route each pending section to the right gap or context request. Trigger on 'generate the brief', a brief refresh after new answers, or handoff-readiness questions."
---

# Sentinel Project Brief

Use this skill to produce the mature discovery handoff.

## Workflow

1. Check current state:

```powershell
python -m sentinel /status PROJECT_ID
python -m sentinel /maturity PROJECT_ID
```

2. Generate or refresh:

```powershell
python -m sentinel /brief PROJECT_ID
```

3. Review `workspaces/PROJECT_ID/02_requirements/project-brief.md`.
4. Summarize the per-section readiness and the gate results from the `/brief` output (see below).
5. If domain teams need deeper analysis, create context requests with `sentinel-domain-request`.

## Per-Section Readiness and the Action per Pending Section

`/brief` returns `brief_section_readiness`: a `coverage_score` plus each narrative section classified `populated` or `pending` (empty body or a pending marker) with its count of local evidence citations. Every pending section comes with its `feeding_gaps` — report the section, its title, and the concrete route:

- `[PENDING INPUT]` → the feeding `GAP-*` ids are the remediation: chase them with the client via `/resolve-gaps` (`sentinel-gap-response`).
- `[PENDING DOMAIN CONTEXT]` → no client gap feeds it: raise the matching domain context request (`sentinel-domain-request`).

Never fill a pending section by hand or with unsourced narrative; the brief is compiled, and sections only populate from confirmed answers, seeds, and cited context.

## Gates at the Brief Close (explain, never force)

The `/brief` result carries three gates; `blocked: true` plus `readiness_stage` tells you which one fired:

- **Brief gate** (soft by default): warnings name each poor section and its feeding gaps. With `brief_gate.strict` and coverage below the threshold, the close blocks as `BRIEF_BELOW_THRESHOLD`.
- **Implementability gate** (soft by default): warnings name the `RU-*` units that are not implementable (non-inferable open gaps). With `implementability_gate.strict`, the close blocks as `UNITS_NOT_IMPLEMENTABLE`. Units `DEFERRED_TO_CONTEXT` (domain-discoverable) never block.
- **Specification self-correction**: before the phase closes to `READY_FOR_SPECS`, the runtime re-reads each confirmed closed-gap answer and verifies the compiled brief carries it. A discrepancy aborts the close as `SELF_CORRECTION_FAILED` (`self_correction.findings` lists what dropped) and asks for BA intervention — the check never rewrites the brief or the answers. While blocking gaps keep the phase open anyway, findings are reported without changing the stage.

When a gate blocks, explain why and recommend the prior step (resolve gaps, request context, or review the self-correction findings); do not retry the command hoping for a different verdict.

## Readiness Check

- The brief should be complete enough to guide PRD, specs, backlog, and acceptance strategy.
- It should not attempt to replace domain packs. Technology can deepen architecture/contracts later; Design can deepen flows/prototypes later; Quality can deepen test cases later.
- Critical/high gaps that are `OPEN`, `ANSWERED`, or `PARTIALLY_CLOSED` should be treated as blockers before downstream specs/backlog. The brief only advances the phase to `READY_FOR_SPECS` when no blocking gaps remain.
