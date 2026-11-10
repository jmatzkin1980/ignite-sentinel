---
name: sentinel-project-brief
description: "Use when generating or refreshing the Ignite Sentinel project brief once discovery gaps and seeds are stable: check /status and /maturity, confirm the brief settings (profile, genesis, validation direction, brief version), run /brief, read the per-section readiness, the brief v2 compile report and the gates (brief coverage, unit implementability, specification self-correction), and route each pending place to the right gap or context request. Trigger on 'generate the brief', a brief refresh after new answers, or handoff-readiness questions. Not for the PRD or the specification layer (use sentinel-specs)."
---

# Sentinel Project Brief

Use this skill to produce the mature discovery handoff. The brief is **compiled**: never write its body by hand, never fill a pending place with narrative you supply.

## Workflow

1. Check current state:

```powershell
python -m sentinel /status PROJECT_ID
python -m sentinel /maturity PROJECT_ID
```

2. Confirm the brief settings with the BA (below), then generate or refresh:

```powershell
python -m sentinel /brief PROJECT_ID
```

3. Review `workspaces/PROJECT_ID/02_requirements/project-brief.md`. For a v2 brief, also read `02_requirements/brief_compile_report.json`.
4. Summarize the per-section readiness, the fill sites and the gate results from the `/brief` output.
5. Route what is missing: client gaps through `/resolve-gaps` (`sentinel-gap-response`), domain context through `sentinel-domain-request`.

## Brief Settings: Profile, Genesis, Validation Direction and Version

The `/brief` output carries `brief_settings`. Profile and genesis decide which brief v2 places are required, conditional or N/A:

- **Profile:** one or more of `UI`, `API`, `BAT`, `INT`, `MIG`, `REG`, `MT`.
- **Genesis:** `greenfield` or `brownfield-integration|extension|replacement`.
- **Validation direction:** `to-build` or `built`.
- **Brief version:** `1` (default) or `2` (opt-in per project).

While profile and genesis are unconfirmed, the output shows a `proposal` built from keyword cues in the raw input.

- **Never apply the proposal yourself.** Ask the BA and record the answer:

```powershell
python -m sentinel /brief PROJECT_ID --brief-version 2 --profile UI,REG --genesis brownfield-extension
```

- **`MIG` implies `brownfield-replacement`.** Any other genesis with `MIG` comes back as a contradiction; resolve it with the BA. An initial load in greenfield is not `MIG`.
- **Mixed genesis:** pass both values, comma-separated. The most demanding one is declared and the other is noted.
- **Opting in without confirmed settings** opens the blocking gap `GAP-BRIEF-PROFILE` and keeps the v1 brief. Confirming closes it.

## The Brief v2

§0–§9 plus the glossary and provenance annexes, in the project language. Every place is exactly one of:

- **Fact:** a sentence quoted from a source, with `[[sources § … # F-NN — supports: …]]`. A confirmed gap answer cites the response that closed it and names its `GAP-*`.
- **Pending:** `⏳ PENDING (GAP-X)` when the client owes the data (blocks), `⏳ PENDING DOMAIN (GAP-X)` when domain context owes it (deferrable). Conditional places with no evidence carry the domain mark.
- **Inference:** `(inferred) …` with its `ASM-*`, next to the pending mark it waits on. It is the value to build with meanwhile, never a fact, and it has an `INFERRED` row in the knowledge ledger.
- **N/A:** with its counterfactual ("If …, it opens"), grouped as the schema says.

Rules the compiler applies and you must not undo:

- **In-place rewrite.** When `/resolve-gaps` closes a gap, a v2 brief is recompiled: the answer replaces the mark (or the earlier raw statement) in its own place, and the replaced statement moves to the provenance annex. Nothing is appended elsewhere. The output's `brief_v2.rewritten_places` lists what moved.
- **Transcription.** Quotes are verbatim: contracted enumerations and capped values ("up to 30") keep their form. A source `TBD` stays `TBD` and the place stays pending. A doubled word is reproduced and marked `[sic]`.
- **Contradictions.** An open contradiction's interim value goes in its place with `⏳` (or `⚠` inline with `validation_direction: built`, where §7 lists the divergences and §9 carries only Debt and Defect).
- **Counts.** §0.2 (certainty per section, reliability warning) and §7 count the same marks; if they disagree, that is a bug, not a judgement call. §6.3 lists the changes against the previous v2 brief; a re-run over the same inputs is byte-identical.

Drive the BA from `brief_compile_report.json`:

- `fill_sites`: place, class, gap, whether that gap is open, and what the place must produce. `client` sites go to `/resolve-gaps`; `domain` sites go to a context request.
- `inferred`: inferences waiting on a gap; ratify them by closing that gap.
- `replaced`: statements an answer superseded (check the BA agrees).
- `unused_sources`: a delivered source the brief never cites is either noise or a missed fact.

## Per-Section Readiness and the Action per Pending Section

`/brief` returns `brief_section_readiness`: a `coverage_score` plus each of the six lenses (`1` Identidad y Valor … `6` Gobernanza y Restricciones) classified `populated` or `pending`, with its evidence citations. A v2 brief maps onto the same lenses (§5.11 and §6 feed lens 6) and adds `brief_version: 2`. Every pending lens comes with its `feeding_gaps`:

- Feeding `GAP-*` ids → chase them with the client via `/resolve-gaps` (`sentinel-gap-response`).
- No feeding gap, or a `⏳ PENDING DOMAIN` mark → raise the matching domain context request (`sentinel-domain-request`).

## Non-Goals (governed scope exclusions, IMP-185)

The v1 brief's section 3 carries a `### No-Objetivos (Non-Goals)` block projected only from governed data: gaps closed out-of-scope/not-applicable (a `/resolve-gaps` closure with decision status `no aplica` / `not applicable`) and scope decisions, each cited by its `GAP-*` id and change source. With no such closures the block shows "Sin non-goals registrados / No non-goals recorded" — never an invented exclusion. The same governed list feeds the PRD's `### Non-Goals` (`sentinel-specs`). To add a non-goal, close the relevant gap as not-applicable through `/resolve-gaps`; do not hand-write it.

## Gates at the Brief Close (explain, never force)

The `/brief` result carries three gates; `blocked: true` plus `readiness_stage` tells you which one fired:

- **Brief gate** (soft by default): warnings name each poor lens and its feeding gaps. With `brief_gate.strict` and coverage below the threshold, the close blocks as `BRIEF_BELOW_THRESHOLD`.
- **Implementability gate** (soft by default): warnings name the `RU-*` units that are not implementable (non-inferable open gaps). With `implementability_gate.strict`, the close blocks as `UNITS_NOT_IMPLEMENTABLE`. Units `DEFERRED_TO_CONTEXT` never block.
- **Specification self-correction**: before the phase closes to `READY_FOR_SPECS`, the runtime re-reads each confirmed closed-gap answer and verifies the brief carries it — in v1 anywhere in the narrative, in v2 inside the answer's own place with its gap id. A discrepancy aborts the close as `SELF_CORRECTION_FAILED` (`self_correction.findings` lists what dropped). The check never rewrites the brief or the answers. While blocking gaps keep the phase open anyway, findings are reported without changing the stage.

When a gate blocks, explain why and recommend the prior step (resolve gaps, request context, or review the self-correction findings); do not retry the command hoping for a different verdict.

## Adaptive Decision Ladder (coaching posture)

When a place is pending or a gate blocks, offer the routes as numbered rungs — *use this when…* and the *why* — rather than one directive. (Posture: the Adaptive Decision Ladder, Peters.)

1. **Chase the client gaps** — use this when a lens is pending with feeding gaps, or a v2 fill site has class `client`. Route through `/resolve-gaps`. Why: the place only fills from confirmed answers, and a v2 brief rewrites it in place.
2. **Raise a domain context request** — use this when no client gap feeds it or the mark is `⏳ PENDING DOMAIN`. Route via `sentinel-domain-request`. Why: the missing input is domain knowledge.
3. **Confirm the settings** — use this when `GAP-BRIEF-PROFILE` is open or the settings carry a contradiction. Why: applicability decides which places exist at all.
4. **Review the self-correction findings** — use this when the close aborts as `SELF_CORRECTION_FAILED`. Why: a confirmed answer dropped from the compiled brief; reconcile it, do not re-run hoping for a different verdict.
5. **Advance to specs** — use this when no blocking gaps remain and the gates are green (or a soft warning the BA accepts). Continue with `sentinel-specs`. Why: the brief is a floor for downstream work.

Name the rung and the reason; the BA chooses whether to advance or keep maturing.

## Readiness Check

- The brief should be complete enough to guide PRD, specs, backlog, and acceptance strategy.
- It should not replace domain packs. Technology deepens architecture and contracts later; Design deepens flows and prototypes; Quality deepens test cases.
- Critical/high gaps that are `OPEN`, `ANSWERED`, or `PARTIALLY_CLOSED` are blockers before downstream specs/backlog. The brief only advances the phase to `READY_FOR_SPECS` when no blocking gaps remain. In v2, §0.2 states it as "Ready to build".
