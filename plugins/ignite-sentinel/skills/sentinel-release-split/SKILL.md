---
name: sentinel-release-split
description: "Use when a brief v2 may be too big for one release and the BA wants a release series: read the /split --assess result, walk the release split model (sentinel/templates/release_split_model.json) and write the proposal JSON for /split --propose (core and variations, criteria written before cutting, base with its negative list, the series table, conditionals with their gap, sketches, inheritance and the integrator's consumption table). Trigger on 'split this project into releases', 'propose a release series', 'should this be several releases'. Not for slicing a backlog into stories (use sentinel-backlog) or for compiling the series (that is /split --confirm, after the partition validation)."
---

# Sentinel Release Split

Use this skill to propose how a brief v2 becomes a series of releases. You write a proposal; the runtime validates it and stores it as a **proposal**. Nothing is compiled and the brief is never touched until `/split --confirm` (IMP-266), which needs the partition validation in green and the BA's and the technical team's confirmation. The client's confirmation stays an open gap.

## Workflow

1. **Assess first.** Run `/split PROJECT_ID --assess` and read `01_discovery/split_assessment.md`. When it says `no_split`, tell the BA and stop unless they ask to go on. When it says `cannot_decide`, put the signals in conflict to the BA before proposing.
2. **Read only the brief and the model.** Read `02_requirements/project-brief.md` (v2) and `sentinel/templates/release_split_model.json`. Never use the conversation as a source.
3. **Step 0.** Answer the model's three questions:
   - Is the brief valuable by itself?
   - Does it already fit the budget? If it fits, stop and do not cut.
   - Is there a measurable goal (1.3)?
4. **Write the criteria before cutting.** Pick two or three cut criteria (C1–C14). C1 (verifiable value) always leads and C14 is never alone. Each criterion carries its `why` and an anchor quoted **verbatim** from its place in the brief.
5. **Walk the flow.** Go through steps 1–12 in order until the stopping criterion holds. Each release records its pattern (P1–P24, never P24 as the cut) and the criteria it uses, all among the written ones.
6. **Shape the series:**
   - **Core and variations:** each with its anchor.
   - **The base:** each piece with its reason, plus the negative list (`not_in_base`) of what stays with a sibling and which one.
   - **The releases:** type, wave, goal and the units of the brief each one contains (`{place, quote}` or `{item: C-NN}`).
   - **Edges:** `depends_on` / `enables`, each with its `why` and strength.
   - **Conditionals** with their open gap.
   - **Spikes** with 1–3 questions and a time-box.
   - **Interleaved releases** as `r<N>.<M>` with their subtype.
   - **Sketches** for what lies outside the horizon: a goal and a pattern.
   - **Inheritance:** each open gap goes to the first release that needs it.
   - **Suggested scope**, marked.
   - **Integrator:** its consumption table.
7. **Evaluate the cut** (model `cut_evaluation`):
   - Are the sizes similar?
   - Does each release meet release INVEST?
   - Is there something you could delete?
   - Is there an obvious first?

   Re-cut before writing if one of these fails.
8. **Submit:** `/split PROJECT_ID --propose --source proposal.json`. A refused proposal lists every finding with its code. Fix them all and submit again.

## Proposal format

```json
{"core": {"text": "file a claim and see it registered", "anchor": {"place": "1.1", "quote": "<verbatim>"}},
 "variations": [{"id": "V1", "text": "adjuster approval", "anchor": {"place": "2.1", "quote": "<verbatim>"}}],
 "criteria": [{"id": "C1", "why": "each release is accepted by the claims lead", "anchor": {"place": "1.3", "quote": "<verbatim>"}}],
 "base": {"pieces": [{"piece": "shared authorization filter", "reason": "r1 and r2 both apply it", "used_by": ["r1", "r2"]}],
          "not_in_base": [{"piece": "payment adapter", "goes_to": "r3", "reason": "only r3 pays"}]},
 "releases": [
   {"id": "r1", "name": "Online claim filing", "type": "functional", "wave": 1, "pattern": "P15", "criteria": ["C1"],
    "goal": "a policyholder files a claim and sees it registered", "closing_check": "file one claim end to end",
    "contains": [{"place": "3.2", "quote": "<verbatim>"}, {"item": "C-01"}],
    "needs": ["GAP-..."], "depends_on": [{"release": "r0", "why": "it applies the base filter", "strength": "hard"}],
    "suggested_scope": false}],
 "sketches": [{"name": "mobile channel", "goal": "policyholders file from the app", "pattern": "P10"}],
 "inheritance": [{"gap": "GAP-...", "release": "r3", "why": "the first release that needs it"}],
 "integrator_consumption": [{"piece": "claims workspace", "uses": "approval API", "from": "r2"}]}
```

The contract is `sentinel/schemas/release_split_proposal.schema.json`. The release types come from the model:
- `enabler`, `measuring` and `already_built` may carry no unit of the brief;
- `functional`, `conditional`, `interleaved`, `integrator` and `segment_cutover` may not.

## Rules

- Every anchor is quoted verbatim from its place. A quote found elsewhere, or paraphrased, is refused.
- A release is a complete variation of the core: entry, exit and something visible. It is never a technical layer and never a phase.
- An enabler names the capability it supports, the risk it reduces and how it is shown done (`goal`). It is not "prepare environments".
- Each open gap is inherited by the first release that lists it in `needs`, by wave and then by id.
- A conditional names the open gap that decides it. A spike carries 1–3 questions and a time-box and closes with a DEC.
- Mark `suggested_scope: true` on what the analysis suggests and the business did not ask for.
- The partition stays a **proposal**. The runtime records the assessment next to it. Re-scopes after confirmation are `/split --move` (H17a′), never an edit.

## Anti-patterns

- Cutting by layer ("Backend", "Database", "UI") or putting only §4 or only §5 units in a functional release. The runtime refuses it as `layer_cut`.
- A release with no unit of the brief that is not an enabler, measuring or already built (`empty_release`).
- A criterion without its anchor (`criterion_without_source`), or criteria made up after cutting (`criterion_not_written`).
- Inheriting an open gap into a later release than the first one that needs it (`misplaced_inheritance`).
- A spec per release that repeats the domain and glossary: release briefs refer to the base, they never copy it.
