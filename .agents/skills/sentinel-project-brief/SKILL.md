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

## Non-Goals (governed scope exclusions, IMP-185)

Section 3 carries a `### No-Objetivos (Non-Goals)` block projected only from governed data: gaps closed out-of-scope/not-applicable (a `/resolve-gaps` closure with decision status `no aplica` / `not applicable`) and scope decisions, each entry cited by its `GAP-*` id and change source. With no such closures the block shows the explicit marker "Sin non-goals registrados / No non-goals recorded" — never an invented exclusion. The same governed list feeds the PRD's `### Non-Goals` under Scope (`sentinel-specs`). To add a non-goal, close the relevant gap as not-applicable through `/resolve-gaps`; do not hand-write it.

## Gates at the Brief Close (explain, never force)

The `/brief` result carries three gates; `blocked: true` plus `readiness_stage` tells you which one fired:

- **Brief gate** (soft by default): warnings name each poor section and its feeding gaps. With `brief_gate.strict` and coverage below the threshold, the close blocks as `BRIEF_BELOW_THRESHOLD`.
- **Implementability gate** (soft by default): warnings name the `RU-*` units that are not implementable (non-inferable open gaps). With `implementability_gate.strict`, the close blocks as `UNITS_NOT_IMPLEMENTABLE`. Units `DEFERRED_TO_CONTEXT` (domain-discoverable) never block.
- **Specification self-correction**: before the phase closes to `READY_FOR_SPECS`, the runtime re-reads each confirmed closed-gap answer and verifies the compiled brief carries it. A discrepancy aborts the close as `SELF_CORRECTION_FAILED` (`self_correction.findings` lists what dropped) and asks for BA intervention — the check never rewrites the brief or the answers. While blocking gaps keep the phase open anyway, findings are reported without changing the stage.

When a gate blocks, explain why and recommend the prior step (resolve gaps, request context, or review the self-correction findings); do not retry the command hoping for a different verdict.

## Adaptive Decision Ladder (coaching posture)

When a section is pending or a gate blocks, offer the routes as numbered rungs — *use this when…* and the *why* — rather than one directive. Never fill a section by hand. (Posture: the Adaptive Decision Ladder, Peters.)

1. **Chase the feeding gaps** — use this when the pending section is `[PENDING INPUT]` or a gate names blocking `GAP-*`. Route through `/resolve-gaps` (`sentinel-gap-response`). Why: the section only populates from confirmed answers, not from narrative you supply.
2. **Raise a domain context request** — use this when the section is `[PENDING DOMAIN CONTEXT]` (no client gap feeds it). Route via `sentinel-domain-request`. Why: the missing input is domain knowledge, discoverable without the client.
3. **Review the self-correction findings** — use this when the close aborts as `SELF_CORRECTION_FAILED`. Why: a confirmed answer dropped from the compiled brief; the fix is to reconcile the discrepancy, not to re-run hoping for a different verdict.
4. **Advance to specs** — use this when no blocking gaps remain and the coverage/implementability gates are green (or a soft warning the BA accepts). Continue with `sentinel-specs`. Why: the brief is a floor for downstream work — deepen domain packs later rather than blocking the phase now.

Name the rung and the reason; the BA chooses whether to advance or keep maturing.

## Readiness Check

- The brief should be complete enough to guide PRD, specs, backlog, and acceptance strategy.
- It should not attempt to replace domain packs. Technology can deepen architecture/contracts later; Design can deepen flows/prototypes later; Quality can deepen test cases later.
- Critical/high gaps that are `OPEN`, `ANSWERED`, or `PARTIALLY_CLOSED` should be treated as blockers before downstream specs/backlog. The brief only advances the phase to `READY_FOR_SPECS` when no blocking gaps remain.
