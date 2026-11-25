---
name: sentinel-project-brief
description: "Use when generating or refreshing the Ignite Sentinel project brief once discovery gaps and seeds are stable: check /status and /maturity, confirm the brief settings (profile, genesis, validation direction, brief version), run /brief, read the per-section readiness, the brief v2 compile report and the gates (brief coverage, unit implementability, specification self-correction), and route each pending place to the right gap or context request. Also when consolidating the change brief before the final export (apply the closed decisions to the request text, or keep the text). Trigger on 'generate the brief', a brief refresh after new answers, consolidating the change brief, or handoff-readiness questions. Not for the PRD or the specification layer (use sentinel-specs)."
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
- **Brief version:** `2` (the default a new project gets from `/init`) or `1` (`/init --brief-version 1`, or `/brief --brief-version 1` to switch).

While profile and genesis are unconfirmed, the output shows a `proposal` built from keyword cues in the raw input, `/next` and `/status` ask for them, and `/maturity` stays `BLOCKED` on `GAP-BRIEF-PROFILE`.

- **Never apply the proposal yourself.** Ask the BA and record the answer:

```powershell
python -m sentinel /brief PROJECT_ID --brief-version 2 --profile UI,REG --genesis brownfield-extension
```

- **`MIG` implies `brownfield-replacement`.** Any other genesis with `MIG` comes back as a contradiction; resolve it with the BA. An initial load in greenfield is not `MIG`.
- **Mixed genesis:** pass both values, comma-separated. The most demanding one is declared and the other is noted.
- **New projects compile the brief v2 by default** (`/init --brief-version 1` keeps v1; older workspaces stay on v1). Without confirmed settings `/brief` opens the blocking `GAP-BRIEF-PROFILE`, keeps the v1 brief and the project cannot reach `/specs`. Confirm profile and genesis with the BA first; confirming closes the gap.

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

`/validate` checks a v2 brief's integrity: every mark points to an open gap (the gap routed to that place, else its section's umbrella `GAP-BRIEF-S<n>`), marks match `fill_sites`, inferences have their ledger rows, and there are no forbidden values (`-`, `—`, bare `N/A`, own `TBD`, `ninguno`) or edit residues. Anchors must hold: every statement outside the exempt list (`templates/anchor_exempt.json`) cites a current, non-echo source, and a line about two gaps needs one anchor per gap. Fix a finding by recompiling, closing the gap or updating the source registry, never by editing the body.

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

## The Brief of a Change

```powershell
python -m sentinel /brief PROJECT_ID --change CHG-001
```

Use it when the request is a change on a system that already exists (`/ingest --change`) and the BA wants it matured on its own. It writes `02_requirements/CHG-001/project-brief.md` and `change_brief_report.json`: nine sections (context and baseline, problem and result, border, as-is to to-be process, per lens, preserved behavior, rules and acceptance, blast radius and impact, pending). Every content line cites its origin (the change note, the baseline file a closed gap quoted, the border, a confirmed answer). Nothing is invented: an open question is a `⏳ PENDIENTE (GAP-X)` mark when it blocks, and `⏳ PENDIENTE DOMINIO (GAP-X)` when it is deferred. Report the path and `blocking_open`; section 9 lists what is still open.

- It is not the product's brief and not a PRD. The project's brief, state and brief settings are never touched, and `--change` does not combine with `--profile`, `--genesis`, `--validation-direction` or `--brief-version` (exit 3).
- A workspace that only has changes refuses a plain `/brief` and names the change to use; a project with its own requirement still compiles its brief without the flag.
- A change's specs come from `/specs --change CHG-nnn` (never from the brief); it still has no backlog. Say so; do not improvise one.
- To review or send it: `/view PROJECT_ID --artifact brief --change CHG-001` and `/export PROJECT_ID --artifact brief --change CHG-001`. The export is a draft while pending marks remain; `--final` refuses while blocking ones do. The brief is recompiled from the answers, never hand-edited.

## Consolidating the change brief (IMP-414)

The final export of a change (`/export --artifact brief --change CHG-001 --final`) delivers one text, not the request next to its decisions. Before it, every element of the request that a closed decision touches has to say how it reads now. Without it the final export is refused and `/next --change` says `consolidate` (or `consolidate_confirm` when a replacement waits for the BA).

**Which elements.** A closed decision (a divergence with the design, a design-only surface, an answer that took a side) linked to an element, by the element or by a line it quotes, whose chosen option does not keep the request text. The element stays pending to consolidate until the BA does one of two things:

1. **Write the text with the decision applied** and confirm it. Transcribe, do not draft: each sentence comes word for word from the element or from the answer of the decision. A number, amount, date, percentage or id that is in neither, or a `no`/`sin`/`nunca` of the element that disappears or that neither the element nor the answer has, is refused unless the block says `Tipo: extension` (an extension is flagged and confirmed one by one). Write the block in a file and run `/extract PROJECT_ID --change CHG-001 --consolidate PATH`; the worksheet is `01_discovery/CHG-001/consolidation_control.md` (internal, never part of the deliverable). Each block carries:
   - `### ELEMENT` (for example `RN-02`) and `Decisión: GAP-…` (the closed decision that motivates it; one that is not linked, or whose option keeps the request text, is refused);
   - `Líneas:` the lines of the element in the request, `Texto:` how the element reads now (continuation lines indented), optionally `Tipo: extension` and `Ubicación: 3.6` (a place of the brief v2; `Reemplaza:` may repeat the element);
   - the extraction of the element has to be confirmed first.
   Then the BA confirms **one by one**: `/extract PROJECT_ID --change CHG-001 --confirm-replacement ELEMENT`. With `--delegated --note "the BA's words"` the agent confirms for them only when they said so; it is listed to review and confirming again without `--delegated` ratifies it. Never confirm a replacement the BA has not read.
2. **Keep the request text** for that element: `/extract PROJECT_ID --change CHG-001 --keep-text ELEMENT --gap GAP-… --reason "the BA's words"`. Only for a decision that does change the content and whose request text the BA still keeps (a "the request governs" option needs nothing: the element is already included). Refused when the option already keeps the text or when the decision takes the element out of the change (propose it as a discard in the extraction). The reason is the BA's, never yours.

**What the final export then holds.** Decisions applied with the GAP reference, the requirements as the literal text of the request (the EARS rows stay internal to the working export and the specs), what was discarded only under 6.2 "No entra", the structure of a v2 request respected, and the annex `A.decisions` ("Registro de decisiones") listing each decision with who decided and where it landed. The working export (without `--final`) does not change. `/status --change` shows `consolidation` (included, modified, excluded, pending, unconfirmed). If the change moves afterwards, the final export is out of date and `/next --change` asks for it again.

## Formato

The example of the consolidation file (`/extract --consolidate`): it is parsed by the real parser and its anchoring in the test suite. The Compras domain here is made up; the decision answered "Rige el diseño: el umbral de aprobación es 1.000.000." on a request whose rule said 5.000.000.

```sentinel-example kind=consolidation lang=es
### RN-02
- Decisión: GAP-DIS-3F9A1C07
- Líneas: 31
- Texto: | RN-02 | Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras. |
```

The same in English (`Decision`, `Lines`, `Text`; the labels in Spanish are accepted too):

```sentinel-example kind=consolidation lang=en
### RN-02
- Decision: GAP-DIS-3F9A1C07
- Lines: 31
- Text: | RN-02 | Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras. |
```
