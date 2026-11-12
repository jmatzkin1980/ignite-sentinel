---
name: sentinel-release-split
description: "Use when a brief v2 may be too big for one release and the BA wants a release series: read the /split --assess result, walk the release split model (sentinel/templates/release_split_model.json), write the proposal JSON for /split --propose (core and variations, criteria written before cutting, base with its negative list, shared contracts as graph nodes, the series table, conditionals with their gap, sketches, inheritance and the integrator's consumption table), get the partition green for /split --confirm and read the compiled series. Trigger on 'split this project into releases', 'propose a release series', 'should this be several releases', 'confirm the partition'. Not for slicing a backlog into stories (use sentinel-backlog) or for editing a release brief by hand (the series recompiles from the whole brief)."
---

# Sentinel Release Split

Use this skill to propose how a brief v2 becomes a series of releases. You write a proposal; the runtime validates it and stores it as a **proposal**. Nothing is compiled and the brief is never touched. `/split --confirm` validates the partition deterministically (contracts, waves, coverage, single owner) and, only when it is green, records the BA's and the technical team's confirmation. The client's confirmation stays an open gap (`GAP-SPLIT-CLIENT`).

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
   - **The releases:** type, wave, goal, `closing_check` (the outcome someone external verifies; for an enabler, how it is shown done) and the units of the brief each one contains (`{place, quote}`, `{item: C-NN}` or `{item: P-N}`).
   - **Contracts as nodes:** every shared schema, API, file format, event, role, parameter or spike DEC is a `contracts` entry `{id: K<N>, name, kind, created_by, definition}`. One release creates it; the others use it under the same name.
   - **Edges:** `depends_on` / `enables` in symmetric pairs, each with its `why` and strength. A hard `depends_on` names the contract it consumes (`consumes: K<N>`), which its target creates.
   - **Conditionals** with their open gap.
   - **Spikes** with 1–3 questions and a time-box.
   - **Interleaved releases** as `r<N>.<M>` with their subtype.
   - **Sketches** for what lies outside the horizon: a goal, a pattern and the units they take (`contains`).
   - **Coverage n of n:** every scope line of §6.1, every `C-NN` of §9 and every screen `P-N` goes to exactly one release or sketch.
   - **Relaxed rules** (`relaxed_rules`): a rule a first release relaxes names `restored_in`, a later release. Never a legal, regulatory or Must rule.
   - **Inheritance:** each open gap goes to the first release that needs it.
   - **Suggested scope**, marked.
   - **Integrator:** its consumption table.
7. **Evaluate the cut** (model `cut_evaluation`):
   - Are the sizes similar?
   - Does each release meet release INVEST?
   - Is there something you could delete?
   - Is there an obvious first?

   Re-cut before writing if one of these fails.
8. **Submit:** `/split PROJECT_ID --propose --source proposal.json`. A refused proposal lists every finding with its code. Fix them all and submit again. A stored proposal comes back with `partition_preview`: the codes `--confirm` would still refuse.
9. **Confirm with the people who own it:** once the BA and the technical team agree, run `/split PROJECT_ID --confirm --ba NAME --tech TEAM`. It refuses with every finding unless the partition is green, and refuses when the brief changed since the proposal. A confirmation freezes each contract by hash; changing one later needs an audited `contract_deltas` row `{contract, why, finding}`. Never run it on your own: the names are theirs.
10. **Read the compiled series:** the confirmation writes `02_requirements/series/index.md` and one `02_requirements/r<N>/project-brief.md` per release. Report the index's sync findings. A release brief is never edited by hand: change the whole brief or the partition, and the series recompiles. A unit flagged "not routed" means the brief grew: propose the series again.
11. **Derive by release:** `/specs PROJECT_ID --release rN`, then `/backlog PROJECT_ID --release rN`; read the results under `03_specs/rN/` and `04_backlog/rN/`, and the verdict with `/status PROJECT_ID --release rN`.
12. **Move a unit when the cut changes:** `/split PROJECT_ID --move --unit "C-NN|P-N|<quote>" --from rA --to rB --reason "..." [--finding F-NN] --ba NAME --tech TEAM`; `--to sketch:<name>` sends it out of the horizon. The partition must stay green and the BA and the technical team confirm it again. Report `releases_changed` and `stale_derivations` (re-run their `--release` derivations). A round trip (A→B→A) is refused and opens `GAP-SPLIT-CRITERION`: write the cut criterion that decides it and name it with `--criterion Cn`. Moving to a sketch closes no gap: excluded is not resolved.
13. **Close a release when it is done:** once every story of the release is Done and its closing check ran, `/split PROJECT_ID --close rN --evidence PATH --ba NAME --tech TEAM`, where PATH is the local result of the closing check. A release that depends hard on one not closed is NOT READY by inheritance. Read the series state in `02_requirements/series/release-guide.md` (`/view PROJECT_ID --artifact release-guide`).

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
    "contains": [{"place": "3.2", "quote": "<verbatim>"}, {"place": "6.1", "quote": "<verbatim>"}, {"item": "C-01"}],
    "needs": ["GAP-..."],
    "depends_on": [{"release": "r0", "why": "it applies the base filter", "strength": "hard", "consumes": "K1"}],
    "enables": [{"release": "r2", "why": "r2 approves the claims r1 registers", "strength": "hard"}],
    "suggested_scope": false}],
 "contracts": [{"id": "K1", "name": "Authorization filter", "kind": "service", "created_by": "r0",
                "definition": "authorize(user, action) -> allow or deny",
                "operations": [{"name": "authorize", "consumers": ["r1", "r2"]}]}],
 "sketches": [{"name": "mobile channel", "goal": "policyholders file from the app", "pattern": "P10", "contains": [{"item": "C-04"}]}],
 "inheritance": [{"gap": "GAP-...", "release": "r3", "why": "the first release that needs it"}],
 "relaxed_rules": [{"rule": "attachments are optional in r1", "anchor": {"place": "3.2", "quote": "<verbatim>"},
                    "release": "r1", "restored_in": "r2"}],
 "integrator_consumption": [{"piece": "claims workspace", "uses": "K3", "from": "r2"}]}
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
- A hard dependency always points to an earlier wave. A cycle is never forced: it means a contract is missing or a dependency is extra (`missing_contract`); go back to the pattern step.
- A committed release never hard-depends on a conditional one: the conditional edge stays dotted until its gap is decided.
- An artifact extended by two or more siblings carries a `cross_note` and a `merge_order` of exactly those siblings. A shared service exposes only operations with a consumer.
- The gap that decides a conditional must not repeat in two or more siblings (`tentacle_partition_defect`): cut again. A gap that holds back the start of `UMBRAL_TRANSVERSAL` (75 %) or more of the releases is reported as transversal readiness: resolve it before the series starts; it is not a cut defect.
- The integrator depends, directly or transitively, on every non-conditional release, and its consumption table uses something from each release it depends on.
- The partition stays a **proposal** until `--confirm`. The runtime records the assessment next to it. Re-scopes after confirmation are `/split --move`, never an edit; every move is dated in `02_requirements/series/scope_changes.md`.

## Anti-patterns

- Cutting by layer ("Backend", "Database", "UI") or putting only §4 or only §5 units in a functional release. The runtime refuses it as `layer_cut`.
- A release with no unit of the brief that is not an enabler, measuring or already built (`empty_release`).
- A criterion without its anchor (`criterion_without_source`), or criteria made up after cutting (`criterion_not_written`).
- Inheriting an open gap into a later release than the first one that needs it (`misplaced_inheritance`).
- An enabler without a demonstration of done (`enabler_without_demo`), or a release without the outcome someone external verifies (`release_without_outcome_metric`).
- A spike without its 1–3 questions or time-box (`spike_contract`).
- The same table, event or role created by two releases (`duplicate_owner`).
- A spec per release that repeats the domain and glossary: release briefs refer to the base, they never copy it.
