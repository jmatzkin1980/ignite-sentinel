# Ignite Sentinel Command Reference

This document explains each command in the `sentinel` CLI.

Commands can be invoked in four ways:

1. Kilo Code chat workflow: `/command PROJECT_ID [options]`
2. Codex chat router: `sentinel /command PROJECT_ID [options]`
3. Terminal fallback: `python -m sentinel /command PROJECT_ID [options]`
4. Portable launcher fallback: `.\installers\sentinel.ps1 /command PROJECT_ID [options]` on Windows or `sh installers/sentinel.sh /command PROJECT_ID [options]` on Unix-like shells

In Kilo Code, repo-local workflow files live in `.kilo/commands/`. In Codex, `AGENTS.md` and the `sentinel-command-router` skill define how chat commands map to the CLI.

## Command Protocol

Project commands use a deterministic protocol inspired by the original Sentinel command guards, adapted for vNext:

1. preflight validates workspace existence, phase, health, and command-specific prerequisites
2. command execution mutates only versionable workspace artifacts and local memory
3. postflight refreshes trace views for mutating commands
4. `06_traceability/command_protocol_log.md` records the command anchor

`/backlog` and `/quality` are blocked while project health is `DIRTY`.

Run help:

```powershell
python -m sentinel --help
```

If `python` is unavailable or points to the Windows Microsoft Store alias, use the repo-local launcher:

```powershell
.\installers\sentinel.ps1 --help
```

## `doctor`

Check whether the repo is ready for portable VS Code, Kilo Code, Codex, Codex Desktop, and CLI usage.

```powershell
python -m sentinel /doctor
```

Checks:

- Python version
- core runtime
- `AGENTS.md`
- repository quick start
- canonical skills source, generated skill mirrors (`.agents/skills`, `.claude/skills`), and Codex hooks adapter
- required skills present at the canonical source
- skill frontmatter metadata (`FAIL` when a canonical skill's name/description is missing or unparseable, `WARN` when the description names a specific agent)
- skill invocation policy coherence (`FAIL` when the set of skills carrying `disable-model-invocation: true` drifts from the human-only registry, or when that flag disagrees between a canonical skill and its mirrors)
- Kilo Code agents adapter
- Kilo Code slash commands
- Kilo Code repo config
- command surface parity between runtime and manifest
- runtime stdlib purity (`FAIL` when a non-optional third-party import reaches the runtime)
- command mentions in operational docs (`WARN` when a `/<command>` token is missing)
- user guide and adapter guides
- portable installers and launchers
- repo write access
- agentic surface audit (`FAIL` when a committed hook/settings JSON or `kilo.jsonc` is unparseable; `WARN` when a hook command contains an unambiguously dangerous shell pattern such as `rm -rf`, a download piped to a shell, `sudo`, or `eval`)
- `kilo.jsonc` conformance to the config schema Kilo publishes (`WARN` when `$schema` is missing, or a top-level key, `permission` sub-key or action is not one the schema defines — a key Kilo does not recognize means it silently discards that whole block)
- `kilo.jsonc` declares a `permission.edit` deny for every governed artifact glob (`WARN` when one is missing)
- optional LanceDB dependency and backend mode
- optional embedding dependencies

## `dashboard`

Generate a local, read-only portfolio dashboard for every workspace under `workspaces/`.

```powershell
python -m sentinel /dashboard
python -m sentinel /dashboard --root .
python -m sentinel /dashboard --open
```

Unlike project commands, `/dashboard` does not take `PROJECT_ID`: it scans all workspaces that have `state.json`, skips `_template`, reuses the same status model exposed by `/status`, and writes a single `dashboard.html` in the repository root. The HTML is self-contained and opens offline with a double click. It embeds local workspace markdown for in-screen review, so `dashboard.html` is git-ignored and should be treated as a rebuildable local snapshot, not as source of truth.

The dashboard is read-only. It shows portfolio KPIs, per-workspace phase/health, lifecycle pipeline, gaps that can be copied for a client response, generated documents in a modal markdown view, backlog rollups, DoR/DoD gates, warnings, and suggested prompts/commands. It never mutates workspaces or runs follow-up commands.

## `view`

Generate a local, read-only HTML view for one generated artifact.

```powershell
python -m sentinel /view PROJECT_ID --artifact gaps
python -m sentinel /view PROJECT_ID --artifact brief
python -m sentinel /view PROJECT_ID --artifact prd
python -m sentinel /view PROJECT_ID --artifact specs
python -m sentinel /view PROJECT_ID --artifact backlog
python -m sentinel /view PROJECT_ID --artifact readiness
python -m sentinel /view PROJECT_ID --artifact prd --open
```

`--artifact readiness` is not a Markdown artifact: it shows the build-readiness view, with what is missing per item and from whom (see [Artifact Views](15-artifact-views.md#build-readiness-view)).

`/view` reads the Markdown source of truth, derives a lossless block model, then combines it with workspace state, assumptions, gaps, development readiness, and traceability graph data before writing `workspaces/PROJECT_ID/08_context_packs/views/ARTIFACT.html`. The HTML is self-contained, opens without a server, and is ignored by git. It is a rebuildable review surface, not a second source of truth. Pending and assumption markers link back to exact inline highlights and show their governed metadata in the side panel.

The derived block model uses a closed catalog (`section`, `requirement-table`, `persona`, `ears-statement`, `decision`, `traceability`, `pending`, `assumption`) and is round-trippable back to the original Markdown. It exists to give the view a stable intermediate representation; it does not change how generated `.md` artifacts are authored, reviewed, or versioned.

The first implementation includes section navigation, search, source-line anchors, pending/gap/assumption markers, citation chips, and matching trace nodes. It does not mutate the source artifact.

Citation chips resolve backticked trace IDs against the local traceability graph. When a node exists, the view embeds a bounded source fragment and a one-hop mini trace graph from real edges so reviewers can inspect evidence and relationships without leaving the HTML snapshot.

Guided response mode classifies visible markers into client questions, domain questions, and BA/assumption review items. The client view is selected by default and tracks draft progress in browser `localStorage`.

The feedback panel stores comments only in browser `localStorage`. Exported Markdown keeps the governed command boundary: `GAP-*` marker comments use the existing `/resolve-gaps` answer-block shape, while other anchored comments can be passed to `/sync --source PATH --note "Artifact review feedback"`.

## `init`

Create a project workspace.

```powershell
python -m sentinel /init PROJECT_ID
```

Creates:

- folder structure under `workspaces/PROJECT_ID/`
- `state.json`
- `sentinel.config.yaml`
- `00_raw/source_manifest.json`
- empty traceability graph
- local retrieval memory metadata files (`memory.lancedb/memory.json`; LanceDB table when the optional package is available)

## `ingest`

Ingest raw input and create discovery artifacts.

```powershell
python -m sentinel /ingest PROJECT_ID --source path\to\input.md
```

Creates or updates:

- raw source copy
- requirement register
- per-source synthesis (`01_discovery/source_synthesis.md`) with preserved source citations
- cited discovery-only requirement units (`01_discovery/requirement_units.md`) when named surfaces/capabilities are present
- on a re-ingest, a read-only requirement-unit delta view (`01_discovery/requirement_unit_deltas.md`, IMP-150) showing ADDED/MODIFIED/REMOVED capabilities vs. the previous iteration — a governed signal only, it never opens/closes/rewrites gaps or units
- gap report
- decision log
- digest
- initial graph nodes and edges
- memory index chunks

**Formats (IMP-270).** `.md`, `.txt`, `.html` and `.htm` are read as UTF-8 text. A `.docx` is read with the standard library, in three layers:

- the text, with headings, lists and tables, as Markdown (`00_raw/NAME.md`);
- the images from `word/media/` and `media/`, copied to `00_raw/NAME_media/` and linked inline;
- the comments, with author, date and the text they are anchored to.

The extraction is dated and carries the sha256 of the original, which is only read. It goes through the same secret redaction as any other source and is registered as an F-NN row. `/sync` reads `.docx` the same way, and its autonomous scan picks `.docx` files up.

A corrupt `.docx`, or a binary file that is not UTF-8 text (a PDF, for example), stops the command with a typed error before any F-NN row opens: convert it to Markdown first. A UTF-8 file with an unknown extension is still stored as Markdown, and the command's output says so under `source_format.warning`.

## `maturity`

Evaluate whether the requirement is ready for specs/backlog.

```powershell
python -m sentinel /maturity PROJECT_ID
```

Output:

- `01_discovery/requirement_maturity_report.md`
- `01_discovery/development_readiness.json`

Blocks when open, answered, or partially closed gaps have severities configured as blocking in `sentinel.config.yaml`.

`/maturity` also computes development certainty from the discovery knowledge ledger. The additive `development_readiness` block evaluates the mature requirement rubric as a 16-area matrix by Ignite lens. Each cell is `CONFIRMED`, `ASSUMED`, or `OPEN`, carries evidence or `[PENDING INPUT]`, contributes to lens/global scores, and reports an explicit Crystallization Gate verdict. The gate is informational by default; it does not silently force downstream progress or close gaps.

`/maturity` also exposes `maturity_metrics.requirement_quality` (IMP-111/IMP-129/IMP-130). This non-blocking score inspects `02_requirements/requirements.md` statements, including `REQ-001` and confirmed `REQ-EARS-*` rows, and cites fragments that contain vague/non-measurable terms, compound statements, unanchored quantifiers, passive voice, missing verification signals, or prose that is not normalizable to an EARS pattern. Ambiguity-like signals include a declared category and a short "why it matters" explanation so the BA can tell whether the risk is temporal, scope, quantity, or subjective wording. It helps the BA see whether the evidence is testable enough; it does not rewrite the requirement or change readiness gates.

## `gaps`

Regenerate the shareable human-friendly discovery gap document.

```powershell
python -m sentinel /gaps PROJECT_ID
```

Output:

- `01_discovery/gaps.md`

Use this before sharing gaps with a client or domain owner.

When a gap has a concrete local evidence trigger, `gaps.md` may include 2 cited candidate options. They are shortcuts for BA/client selection, not automatic answers; `/resolve-gaps` still closes only confirmed or not-applicable responses.

**Gaps as elicitation (IMP-257).**

- **Two new columns:** the trace table gains `Kind` and `Closure` (`Clase` and `Cierre` in Spanish). Both are appended at the end, so older `gaps.md` files still read.
- **Kind:**
  - `client`: the client owes it and it blocks;
  - `domain`: deferrable;
  - `synthesis`: raised by reading several sources (contradictions, agentic channels);
  - `template`: the brief v2 umbrella gaps.
- **Recommended option:** the first candidate option is marked recommended. It is an inference and never applies by itself.
- **Meanwhile:** when an active assumption closes the gap, the response section shows the value to build with meanwhile and where it appears in the brief v2.
- **Side record:** `01_discovery/gap_elicitation.json` keeps kind, closure, example, recommended option and meanwhile per gap.
- **Topic dedup:** a gap an agentic channel or a contradiction raises on the topic of an open gap (same lens, most words in common) extends that row instead of opening another.

**Rounds.** The next batch of questions comes from:

```powershell
python -m sentinel /gaps PROJECT_ID --top 5
```

It takes at most N open gaps, ordered scope > security and privacy > UX > technical, then by severity. Each question has one decision: the recommended option first and "leave pending" last. The round is written to `01_discovery/gap_round.md`.

The `/gaps` result also carries non-blocking `momtest_warnings` (IMP-180): any elicited question phrased as a hypothetical or future opinion ("would you like…?", "¿le gustaría…?") instead of asking about a concrete past event is flagged with the question cited. This is the Mom-Test principle — ask what actually happened, not what someone imagines they would do. It signals, it never blocks, and questions about future *system* capacity (load, scale) are exempt. The same warnings are folded into `/validate`.


**BA disposition on agentic gaps (IMP-271, F7).**

```powershell
python -m sentinel /gaps PROJECT_ID --id GAP-X --disposition accepted
python -m sentinel /gaps PROJECT_ID --id GAP-X --disposition rejected --reason "already covered by the SLA clause"
```

Gaps raised by an agentic channel (`agent`, `challenge`, `scrutiny`, `implementability-probe`, `self-review`) take a disposition: `accepted`, `rejected` or `irrelevant`; the last two need `--reason`. Dispositions are kept in `01_discovery/agent_dispositions.json`. `/maturity` reports, per channel, how many gaps were raised, disposed and undisposed, and the false-alarm rate, (rejected + irrelevant) / disposed, under `maturation_telemetry.agent_channel_dispositions`.

**Sweep protocol.** Every agentic channel follows `sentinel/templates/agent_sweep_protocol.md`. On top of the verbatim evidence check, the runtime rejects a payload whose `absent` entry is not `AUSENTE: <what> en <where>` (or whose "absent" phrase is actually in the source), whose `untouched` is not a list of sentences, whose `blocks` is not a boolean, or that carries figures (`counts`, `totals`, `summary`...). The runtime counts what it accepted and appends it to `01_discovery/agent_sweep_log.md`.
## `annotate`

Merge an agentic semantic analysis of the raw input into discovery gaps (IMP-021). The deterministic checklist decides gaps by token presence/absence and therefore misses what is *named but not defined* (a reassuring keyword like "security is important" suppresses the gap). The agent operating Sentinel is the only component that reads meaning; `/annotate` is its sanctioned channel — it proposes, the runtime validates and persists.

```powershell
python -m sentinel /annotate PROJECT_ID --source path\to\analysis.json
```

The `--source` file is JSON with the agent's structured analysis:

```json
{
  "gaps": [
    {
      "id": "GAP-TECH-NFR",
      "lens": "technical",
      "severity": "high",
      "question": "What concrete performance and security targets must the solution meet?",
      "evidence": "Security and performance are important to us",
      "description": "Non-functional needs are named but never quantified."
    }
  ],
  "ambiguities": ["..."],
  "assumptions": ["..."]
}
```

The runtime validates each gap and rejects the whole annotation with a clear error if any gap: has a malformed `id` (not `GAP-*`), names a lens that is not declared in `sentinel/lenses/`, has a severity outside `critical|high|medium|low`, lacks a `question`, or whose `evidence` quote is not found verbatim in the raw input (the agent cites; it never invents — invariant #3).

On success the gaps are tagged `origin: agent`, merged into `01_discovery/gaps.md` (the trace table gains an `Origin` column), and traced. They then flow through the normal `/resolve-gaps` → `/maturity` → gate lifecycle exactly like checklist gaps.

Outputs:

- updated `01_discovery/gaps.md` (with `Origin` column)
- `01_discovery/agent_annotation_log.md` (auditable record with citations, ambiguities, assumptions)
- copied source under `01_discovery/annotations/`
- `agent_annotation` traceability node linked from the raw input and to the gap report
- `gap_counts.agent_origin` in `state.json` (visible in `/status`)

## `challenge`

Run advanced elicitation (IMP-023) and merge the findings as gaps with `origin: challenge`.

```powershell
python -m sentinel /challenge PROJECT_ID --source PATH
```

`/challenge` materializes "understanding what is not being said". The agent runs the default registry-backed techniques over the maturing requirement, per lens (invariant #1): pre-mortem ("the project failed at 6 months — what did we fail to ask?"), role-play by lens (operator, auditor, attacker...), assumption inversion, and JTBD Four Forces (push, pull, anxiety, habit). The technique catalog lives under `sentinel/techniques/*.json`; adding another available technique is data-only and does not change the command surface. JTBD findings must be anchored in concrete past events or local cited observations; purely hypothetical preference phrasing is surfaced by ingest as a low-severity guardrail, not used to close scope. The findings go in a JSON `--source` file shaped like `/annotate` (a `gaps` array with `id`, `lens`, `severity`, `question`, verbatim `evidence`, and an optional `technique`), plus optional `premortem` and `assumptions_inverted` arrays.

Validation is identical to `/annotate` (declared lens, severity range, verbatim evidence — never invented). On success the gaps are tagged `origin: challenge`, merged into `gaps.md`, and a traced, indexed `01_discovery/challenge_report.md` is written grouping findings by lens with the technique that surfaced each one.

**Respondent calibration (IMP-142).** If the delivered domain context declares an explicit `respondent_profile` (`business` or `technical`, see `/context-request`), `/challenge` calibrates the *wording and length* of each technique prompt to that audience using the per-technique `calibration` block in `sentinel/techniques/*.json`; the technique, lens, and objective are unchanged — only the phrasing. The declared profile and the calibrated prompts are shown in `challenge_report.md`. The profile is never inferred: with no declared `respondent_profile`, the output is identical to the uncalibrated behavior.

Outputs:

- updated `01_discovery/gaps.md` (gaps with `origin: challenge`)
- `01_discovery/challenge_report.md` (findings by lens + technique, pre-mortem and inverted assumptions)
- copied source under `01_discovery/challenges/`
- `challenge_report` traceability node linked from the raw input and to the gap report
- `gap_counts.challenge_origin` in `state.json` (visible in `/status`)

## `scrutinize`

Run deep multi-lens scrutiny (IMP-066) and merge cited findings as gaps with `origin: scrutiny`.

```powershell
python -m sentinel /scrutinize PROJECT_ID --source PATH
python -m sentinel /scrutinize PROJECT_ID --source PATH --lens technical
```

The source JSON contains a `gaps` array. Each item declares `id`, `lens`, `severity`, `finding_type`, `question`, and verbatim `evidence`. Supported `finding_type` values are `unstated-assumption`, `contradiction`, `mention-without-counterpart`, and `domain-conflict`.

Unlike `/annotate` and `/challenge`, `/scrutinize` validates citations against raw input and domain context folders so a finding can cross the client's stated requirement with Technology, Design, Quality, Delivery, or Compliance context already ingested locally. `--lens` is optional and rejects findings outside the requested lens instead of silently mixing concerns.

On success the findings are tagged `origin: scrutiny`, merged into `gaps.md`, written to a traced and indexed `01_discovery/scrutiny_report.md`, and the discovery ledger (`knowledge_state.md/json`) is refreshed so open scrutiny units remain visible with their cited evidence.

Outputs:

- updated `01_discovery/gaps.md` (gaps with `origin: scrutiny`)
- `01_discovery/scrutiny_report.md` (findings grouped by lens and finding type)
- copied source under `01_discovery/scrutiny/`
- `scrutiny_report` traceability node linked from the raw input and to the gap report
- refreshed `01_discovery/knowledge_state.md` and `.json`
- `gap_counts.scrutiny_origin` in `state.json` (visible in `/status`)

### Sub-mode: implementability probe (IMP-119)

```powershell
python -m sentinel /scrutinize PROJECT_ID --mode implementability-probe --source PATH
```

`--mode implementability-probe` runs the pre-flight, per-Requirement-Unit mirror of `/implementation-feedback`: a coding agent declares, before any work starts, what it is missing to implement each `RU-*` (IMP-115). It reuses the same citation and merge machinery as the default `scrutiny` mode, with three differences:

- every finding **must** carry a `unit` (`RU-NNN`) anchor, and (when `requirement_units.md` exists) it must be a real RU — the probe cites units, it does not invent them;
- `finding_type` is `missing-context`, `non-inferable-gap`, or `ambiguous-for-implementation`;
- accepted findings are tagged `origin: implementability-probe`, written to `01_discovery/implementability_probe_report.md` (grouped by Requirement Unit), and copied under `01_discovery/implementability_probe/`. A `implementability_probe` traceability node is linked from the raw input (`probed_by`) and `gap_counts.implementability_probe_origin` appears in `state.json`. The source JSON follows `implementability_probe.schema.json`. Nothing is auto-resolved.

## `self-review`

Run a skeptical self-review over generated PRD/spec artifacts and register cited findings without rewriting the artifacts under review.

```powershell
python -m sentinel /self-review PROJECT_ID --source path\to\self-review.json
```

Use this after `/specs` when a BA, product reviewer, or agent wants to pressure-test the generated PRD/specs for implicit decisions, costly reversibility, missing reuse/brownfield deltas, or assumptions that should remain visible before backlog handoff.

The source JSON may contain `gaps[]`, `decisions[]`, or both:

```json
{
  "gaps": [
    {
      "id": "GAP-SELF-REVIEW-ROLLBACK",
      "lens": "product",
      "severity": "medium",
      "question": "What rollback behavior is expected if this workflow fails after submission?",
      "evidence": "submit invoices for billing"
    }
  ],
  "decisions": [
    {
      "id": "DEC-BILLING-SCOPE-LOCK",
      "title": "Billing submission is treated as in-scope",
      "lens": "product",
      "risk": "high",
      "reversibility": "hard-to-reverse",
      "decision": "The PRD scopes billing submission as a committed workflow.",
      "evidence": "submit invoices for billing",
      "consequences": ["Changing this later may invalidate acceptance criteria and backlog slicing."],
      "considered_options": [
        { "option": "Defer billing to a later release", "evidence": "submit invoices for billing" }
      ],
      "supersedes": "DEC-BILLING-SCOPE-DRAFT"
    }
  ]
}
```

Gap validation reuses the governed cited-gap rules and tags accepted items as `origin: self-review`. Decision validation requires a `DEC-*` id, a declared risk (`low`, `med`, `medium`, or `high`), reversibility (`easy`, `moderate`, `hard-to-reverse`, or `irreversible`), and verbatim local evidence from the generated PRD/spec context.

ADR-grade decision fields are optional and backwards-compatible (an older payload without them still validates — no migration): `consequences[]` records the accepted trade-offs (a decision with no trade-off is an ADR anti-pattern; forward-looking, so not citation-bound); `considered_options[]` records the cited alternatives (each `{option, evidence}`, evidence verbatim, so the choice cannot be relitigated later); and `supersedes` immutably replaces a prior `DEC-*` — the superseded decision keeps its original register entry and archived source, and a new decision records the supersession rather than editing the old one.

Outputs:

- updated `01_discovery/gaps.md` only when new cited gaps are accepted
- archived source under `03_specs/self_review/`
- `03_specs/self_review/self_review_report.md`
- `03_specs/self_review/decision_register.md`
- traceability nodes for the self-review event and hard-to-reverse decisions
- `gap_counts.self_review_origin` and `last_self_review_id` in `state.json`

`/self-review` is deliberately a review channel, not an automatic repair pass. It can make risks and hard decisions visible, but changing the PRD/spec narrative still happens through upstream evidence, `/compose`, `/sync`, or a regenerated `/specs` flow.

## `assume`

Register governed BA-owned assumptions (IMP-067) when the team chooses to proceed with explicit risk instead of hiding uncertainty or pretending it is confirmed.

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

The source JSON contains `assumptions[]`. Each item declares:

- `id`: `ASM-*`
- `lens`: one Ignite lens
- `statement`: the assumption being made
- `owner`: human owner, such as BA, Product Owner, or domain lead
- `risk`: `low`, `med`, or `high`; this is importance/impact
- `uncertainty`: `low`, `med`, or `high`; omitted legacy rows default to `med`
- `justification`: verbatim local evidence quote
- `closes_gap`: optional `GAP-*` provisionally addressed by the assumption
- `risk_category`: optional `value`, `usability`, `viability`, or `feasibility` (Cagan's four product risks); kept separate from `lens` and extensible per project via a directory override (`sentinel/risk_categories/*.json`), the same default/opt-in pattern as the `/challenge` technique registry

The runtime validates lens, owner, risk, uncertainty, local quote, and optional risk category; writes `01_discovery/assumptions.md` (grouped by `risk_category` when any assumption declares one, with rows lacking one listed under Uncategorized); traces and indexes the assumption register; and refreshes `knowledge_state.md/json` with `ASSUMED` units. Assumptions do not become confirmed evidence: high-risk linked assumptions remain visible in `/maturity` and `/status`, and downstream artifacts cite them as assumptions. `risk=high` plus `uncertainty=high` is surfaced as a non-blocking "test before advancing" priority signal.

Outputs:

- `01_discovery/assumptions.md`
- archived source under `01_discovery/assumptions/`
- refreshed `01_discovery/knowledge_state.md` and `.json`
- `assumption_register` traceability node
- `maturity_metrics.assumptions` in `/maturity` and `/status`, including per-`risk_category` coverage in the development readiness matrix when declared

## `resolve-gaps`

Process an answered `gaps.md` or equivalent Markdown file.

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\client-gap-response.md
```

**Closure (IMP-257).** Each response section has an optional `- Closure reason:` (`- Motivo de cierre:`) from a closed vocabulary:

- `answered` (the default), `by_absence`, `by_removal` (the default for "not applicable"), `by_transfer`, `accepted_debt`, `risk_accepted`;
- `split`, `reframed`, `dissolved`, `narrowed`;
- `by_decision` (cites a `DEC-*`), `already_closed_elsewhere`, `resolved_by_inference` (cites an `ASM-*`);
- `reopened_false_premise`, which reopens a closed gap and keeps the previous closure in its note.

What `/resolve-gaps` reports and changes:

- A closure without `Evidence or reference` is reported in `closure_findings`.
- `resolved_by_inference` leaves the gap `PARTIALLY_CLOSED` (still not ready).
- A confirmed answer that still says TBD is partial.
- An answer whose evidence is example data or the current practice never closes.
- Invalidating an assumption reopens the gaps it held up.
- An empty field now stays empty. Before, it read the next line.

The parser reads `### GAP-ID` blocks and extracts:

- answer
- owner or source
- evidence or reference
- decision status

The parser also accepts equivalent field labels in the detected project language so existing answered gap files remain processable.

Candidate options rendered in `gaps.md` or `/context-request` are not parsed as decisions. Copy one into the answer only after the BA/client/domain owner confirms it and adds owner, evidence/reference, and decision status.

Auto-close rule:

- answer is non-empty; and
- decision status is confirmed or not applicable.

If the answer exists but decision status is pending or unclear, the gap becomes `PARTIALLY_CLOSED`.

Knowledge metabolism:

- confirmed answers refresh `knowledge_state.md/json` and `development_readiness.json`;
- if a confirmed gap answer closes the gap linked by a governed assumption, that assumption moves from `ASSUMED` to `VALIDATED`;
- the gap resolution report includes a `Knowledge Ledger Metabolism` section with impacted `KLU-*` units, validated assumptions, and downstream artifacts that may now be stale.

Outputs:

- updated `01_discovery/gaps.md`
- copied response under `07_changes/00_client_responses/`
- `07_changes/00_client_responses/[source]_gap_resolution_report.md`
- appended `01_discovery/gap_resolution_log.md`
- refreshed `01_discovery/knowledge_state.md` and `.json`
- refreshed `01_discovery/development_readiness.json`
- confirmed seeds and decisions when applicable
- EARS-normalized requirements (IMP-026): when a confirmed answer is already written in EARS syntax (e.g. "When <trigger>, the system shall <response>." — ubiquitous, event, state, unwanted, or optional, in EN or ES), it is accumulated into `02_requirements/requirements.md` under "Normalized Requirements (EARS)" as `REQ-EARS-NNN` with its pattern and source. Prose answers stay as seeds/decisions; the runtime validates EARS structure and never invents it. `/specs` and `/backlog` cite confirmed `REQ-EARS-*` rows so downstream stories, acceptance criteria, and tests can preserve the normalized requirement IDs.

## `brief`

Generate or refresh the mature project brief.

```powershell
python -m sentinel /brief PROJECT_ID
```

Output:

- `02_requirements/project-brief.md`

Use after blocking gaps are resolved or explicitly accepted as non-blocking.

**Brief settings (IMP-252).** The brief v2 decides which of its §0–§9 places are required, conditional or N/A from three project settings:

- **Profile:** one or more of `UI`, `API`, `BAT`, `INT`, `MIG`, `REG`, `MT`.
- **Genesis:** `greenfield`, `brownfield-integration`, `brownfield-extension` or `brownfield-replacement`.
- **Validation direction:** `to-build` or `built`.

`/brief` reports them under `brief_settings`. While they are unconfirmed, that block carries a `proposal` from the raw input and the blocking gap `GAP-BRIEF-PROFILE`; the proposal is never applied. The BA confirms them:

```powershell
python -m sentinel /brief PROJECT_ID --profile UI,REG --genesis brownfield-extension
python -m sentinel /brief PROJECT_ID --validation-direction built
```

- **Partial updates:** a flag you leave out keeps the previous confirmation.
- **`MIG`:** implies `brownfield-replacement`. Another genesis with `MIG` is reported as a contradiction.
- **Mixed genesis:** passing two values (`brownfield-integration,brownfield-extension`) declares the most demanding one and notes the other.
- **Validation direction:** the confirmed one takes precedence over `validation_direction:` in `sentinel.config.yaml`.

The schema lives in `sentinel/templates/brief_v2.json`. Its ids are stable and append-only: `/doctor` checks them against `brief_v2_ids.lock.json`.

Confirming the settings does not change a v1 brief.

**Brief v2 (IMP-253a, opt-in per project).** `--brief-version 2` switches the project to the v2 compiler; `--brief-version 1` switches back.

```powershell
python -m sentinel /brief PROJECT_ID --brief-version 2 --profile UI --genesis greenfield
```

- **Gate:** it compiles only with a confirmed profile and genesis. Until then `GAP-BRIEF-PROFILE` opens in `gaps.md` and the v1 brief is kept; confirming closes the gap.
- **Body:** §0–§9 and the annexes of the schema. Each place is a quoted fact with a citation of its source row (`[[sources § … # F-NN — supports: …]]`; a confirmed gap answer cites the response that closed it and names the gap), a pending mark (`⏳ PENDING (GAP-X)` blocks, `⏳ PENDING DOMAIN (GAP-X)` can be deferred; conditional places with no evidence get the domain mark), or an N/A with its counterfactual.
- **Counts:** §0.2 shows the certainty per section and a reliability warning when more than half of the applicable places are pending; §7 lists the same marks and the open gaps.
- **Changes:** §6.3 lists what changed against the previous v2 brief (`ADDED`, `MODIFIED`, `REMOVED`). A re-run over the same inputs is byte-identical.
- **Report:** `02_requirements/brief_compile_report.json` has every place with its fill, the `fill_sites` still to fill (with what each must produce) and the `unused_sources` the brief never cites.
- `/specs`, `/maturity` and `/view` read the v2 brief through the same model as v1.
- **In-place rewrite (IMP-253b):** a confirmed answer replaces what the raw input said about the same place, and the replaced statement moves to the provenance annex. In a v2 project, `/resolve-gaps` recompiles the brief and reports `brief_v2.rewritten_places`. The self-correction gate checks each answer inside its own place.
- **Inferences:** an assumption that closes a gap shows as `(inferred) … (ASM-X)` next to that gap's `⏳`, with an `INFERRED` row in `knowledge_state.json`.
- **Contradictions:** an open contradiction's interim value carries `⏳`, or `⚠` inline with `validation_direction: built`. With `built`, §7.2 lists the divergences and §9 only Debt and Defect.
- **Transcription:**
  - Quotes are verbatim.
  - A source `TBD` stays `TBD` and keeps the place pending.
  - A doubled word is marked `[sic]`.

Per-section readiness and soft gate (IMP-025): `/brief` reports `brief_section_readiness` — each narrative section (1-6) as `populated`/`pending`, an overall `coverage_score`, and the gaps that feed each poor section. The same block appears in `/maturity` and `/status` (under `maturity_metrics`). The gate is non-blocking by default: below the coverage threshold it emits `warnings` naming the poor sections and the gaps that would populate them. Opt-in strict mode (workspace config `brief_gate: { "threshold": 0.5, "strict": true }`) instead blocks the advance to `READY_FOR_SPECS` (readiness stage `BRIEF_BELOW_THRESHOLD`) until coverage improves. Default gates are not hardened without opt-in.

Specification self-correction (IMP-145): before the brief phase closes, `/brief` re-reads each confirmed criterion — every closed-gap answer routed to a brief narrative section — and deterministically confirms the compiled brief still carries both the gap id and the verbatim statement. To make that contract hold everywhere, sections 1-3 now always append their routed confirmed answers when raw-derived narrative did not already carry them (a confirmed client answer is stronger evidence than a signal extracted from raw input). The result is reported under `self_correction` (`findings`, `criteria_checked`). A discrepancy on the actual close — the advance to `READY_FOR_SPECS` — aborts it (readiness stage `SELF_CORRECTION_FAILED`, phase `brief_self_correction_failed`) with a message citing the criterion; while blocking gaps keep the phase open, findings are reported without hijacking the normal blocked stage. The runtime never rewrites the criterion or the artifact to make the check pass, and a normal run has no observable change.

## `context-request`

Generate a domain-specific request for deeper analysis.

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
```

Allowed domains:

- `technology`
- `design`
- `quality`
- `frontend`
- `backend`

Output:

- `08_context_packs/requests/[domain]_context_request.md`

**Declaring the respondent profile (IMP-142).** When the delivered domain context is authored for a known audience, the file can carry a `respondent_profile: technical` or `respondent_profile: business` frontmatter key. `/challenge` uses it to calibrate the phrasing of elicitation prompts to that audience (see `/challenge`). Declare it only when the profile is explicitly known — never when it is merely implied by folder, role, title, or free text; absent the key, behavior is unchanged.


**Lifecycle (IMP-294).** Each request is a `CTX-NNN` node: `active` -> `answered` -> `closed`, or `obsolete`. `/sync` marks an active request `answered` when the synced change cites its id; the sync output lists it under `answered_context_requests`. Move it yourself:

```powershell
python -m sentinel /context-request PROJECT_ID --id CTX-001 --status closed --reason "domain owner confirmed the SLA"
python -m sentinel /context-request PROJECT_ID --id CTX-001 --status active
```

`closed` and `obsolete` need `--reason` and are final. An answered request can go back to `active` when the answer falls short, and regenerating a request for the same domain reopens it. Each transition is kept in `08_context_packs/requests/ctx_lifecycle.json`.
## `next`

Show only the next step (IMP-294).

```powershell
python -m sentinel /next PROJECT_ID
```

It prints `key`, `title`, `text` and the `command` to run, the same decision as `next_action` in `/status`, so the two never disagree. Read-only.

## `status`

Show whether the workspace is ready to build, and what to do next.

```powershell
python -m sentinel /status PROJECT_ID
python -m sentinel /status PROJECT_ID --full
```

The default output is the summary:

- **`verdict`**: the counts-based ready-to-build verdict, computed by `build_readiness_verdict` (the same one `/dashboard` and the MCP `sentinel_status` tool show).
  - `READY`: nothing blocks and every check ran.
  - `READY_WITH_WARNINGS`: nothing blocks, but there are warnings or checks that could not run.
  - `NOT_READY`: a blocking gap is open, discovery has not run, or a strict gate blocks.
  - `blocking_open`, `blockers`, `warnings`, and `partial_coverage` (each check that could not run and why) explain it. A check that did not run never counts as passed.
  - `DEFERRED_TO_CONTEXT` units and "test before advancing" assumptions are warnings, not blockers.
  - `by_item` gives the workspace and each backlog story (Definition of Ready).
- **`gap_counts`**: one counter over `01_discovery/gaps.md` (`open`, `answered`, `partially_closed`, `closed`, `blocking_open`, `total`), using `maturity.blocking_gap_severities` from the workspace config, plus the `<origin>_origin` counts.
- **`verdict.gate_matrix`**: gaps, brief gate, implementability gate, crystallization gate, drift and story DoR, each with its state and whether it blocks.
- **`maturity_score`**: still published next to the verdict. The maturity gates do not change.
- **`next_step`** and **`next_action`** (`key`, `title`, `text`, `command`): the single next step.

`--full` adds the detailed dump: `maturity_metrics`, `development_readiness` (once), assumptions projection, knowledge ledger, story gates, backlog rollup and the last change IDs.

## `export`

Copy a shareable artifact under the workspace export folder.

```powershell
python -m sentinel /export PROJECT_ID --artifact gaps --format md
python -m sentinel /export PROJECT_ID --artifact brief --format md
python -m sentinel /export PROJECT_ID --artifact context-request --format md --domain technology
python -m sentinel /export PROJECT_ID --artifact prd --format mdx
python -m sentinel /export PROJECT_ID --artifact gaps --format interview
python -m sentinel /export PROJECT_ID --artifact gaps --format faq
```

`--format` accepts `md` (default), `mdx`, `interview`, and `faq`; `--fmt` is an accepted short alias.

Output:

- `08_context_packs/exports/`

Markdown export copies the source artifact. PRD MDX export is optional and derived from the artifact block model: it writes `08_context_packs/exports/prd-mdx/index.mdx`, `blocks.json`, and a local `README.md`. Use it only with an offline renderer your team already controls. Sentinel does not install a renderer, call a hosted Plan MCP, or treat MDX as source of truth.

The `interview` format (gaps only) writes `08_context_packs/exports/gaps-interview.md`: the open gaps ordered as a meeting script — blocking gaps first, grouped by lens (or **by stakeholder owner** when a registry exists, see `/stakeholders`) — each with cited context, the question to ask, and 1-2 probing questions derived from the cited candidate options (never invented; a gap with no local evidence gets none). It is a read-only derived view: it never replaces `01_discovery/gaps.md`, closes no gap, and is regenerated rather than hand-edited.

The `faq` format (gaps only) writes `08_context_packs/exports/gaps-faq.md`: the mirror image of the interview script, for gaps already **closed**. Each question is an elicited gap and each answer is its **CONFIRMED** closure, quoted verbatim from the seed/decision tables (`01_discovery/`) and cited to the gap id and its source. Only confirmed gaps appear — open gaps never show up as answered (never invented). It is likewise a read-only derived view: it never replaces `01_discovery/gaps.md`, closes no gap, and is regenerated rather than hand-edited. With no confirmed gaps the FAQ is an explicit empty marker.

## `stakeholders`

Register or list the governed stakeholder registry and route elicitation by owner (IMP-192).

```powershell
python -m sentinel /stakeholders PROJECT_ID
python -m sentinel /stakeholders PROJECT_ID --add --name NAME --domain LENS [--id STK-00N] [--profile business|technical] [--topic TEXT] [--notes TEXT]
```

Output:

- `01_discovery/stakeholders.md`

Records who owns which domain/topic. The registry is a **generated artifact, mutable only through this command** — never hand-edited. Each owner governs a `--domain` (a lens: product, technical, business, design, quality) and optionally a `--topic`; `--profile` reuses the IMP-142 `respondent_profile` (`business` | `technical`) and an unrecognized value is dropped rather than invented. Ids auto-assign as `STK-NNN` when `--id` is omitted; a duplicate `--id` is rejected.

The payoff is deterministic routing: with a non-empty registry the `interview` export groups open gaps **by owner** (a gap is matched to an owner by its lens), so the script reads "these questions go to Operations; these to Technology." A gap whose lens has no registered owner is listed under an explicit **unassigned** heading — never a fabricated owner. Power×Interest scoring and communication plans are intentionally out of scope (delivery, not discovery).

## `sources`

List or change the governed source registry (IMP-250a), close impact cells, settle precedence and write the closing report (IMP-250b).

```powershell
python -m sentinel /sources PROJECT_ID
python -m sentinel /sources PROJECT_ID --id F-NN [--from WHO] [--reason TEXT]
python -m sentinel /sources PROJECT_ID --id F-NN --superseded-by F-MM
python -m sentinel /sources PROJECT_ID --id F-NN --retire --reason TEXT [--replacement F-MM]
python -m sentinel /sources PROJECT_ID --id F-NN --expire YYYY-MM-DD [--topic TOPIC]
python -m sentinel /sources PROJECT_ID --id F-NN --current
python -m sentinel /sources PROJECT_ID --id F-NN --close [--reason TEXT]
python -m sentinel /sources PROJECT_ID --id F-NN --authority AUTHORITY
python -m sentinel /sources PROJECT_ID --id F-NN --cell DOCUMENT/SECTION --mark updated|pending
python -m sentinel /sources PROJECT_ID --id F-NN --cell DOCUMENT/SECTION --mark reviewed --reason TEXT
python -m sentinel /sources PROJECT_ID --precedence SCOPE --between F-NN,F-MM
python -m sentinel /sources PROJECT_ID --report
```

Output:

- `00_raw/source_manifest.json` (the `registry` rows)
- `07_changes/source_log.md` (generated render, in the project language)
- `07_changes/closing_report.md` (with `--report`, in the project language)

Every source that enters through `/ingest`, `/sync` or `/resolve-gaps` gets one `F-NN` row, and the counter never restarts. Each row records its kind (from the bucket it arrived in), who delivered it, its sha256, the paths it arrived under, Sentinel's copies of it, the events that crossed it and the nodes it may impact.

- **Novelty by hash or by missing row, never by date.** The same content under a second path is the same row: autonomous `/sync` attaches the path and reports it under `duplicate_content` instead of crossing it again. Two `/sync` runs over the same file do not duplicate the row.
- **Candidate versions.** A known path with new content opens a new row with `pending_version_of`. The registry never decides that the newest version governs: `/status` warns until a person runs `--superseded-by` on the old row or `--current` on the new one.
- **Row lifecycle.** A row opens when its command starts and closes when the cross finishes. A row left open means a cross that never finished; `/status` warns about it until the command is re-run or the row is closed with `--close`.
- **Validity.** `current`, `superseded` (corrected by another row; cycles are rejected), `retired` (a dead source; `--reason` is required and `--replacement` must be an existing row) or `expired` (from a cut-off date, optionally only for one `--topic`). Pass one validity change at a time.

Open rows and unconfirmed versions appear in the `/status` summary under `sources` and as the non-blocking `sources` gate of the verdict. Manifests written before IMP-250a are migrated on first read: each distinct processed content becomes a closed, current row in processing order.

**Authority, impact matrix, precedence and closing report (IMP-250b).** The routing data lives in `sentinel/templates/source_routing.json`.

- **Authority.** Each new row gets an `authority`: what kind of source it is when sources clash. The bucket gives the default (a meeting is `minutes`, a design context is `prototype`, what `/ingest` takes is `client_document`), and a file named like an example (`example`, `ejemplo`, `sample`, `muestra`) is an `example`. Correct it with `--authority`.
- **Impact matrix.** Each new row gets one cell per document and section its authority routes to (`brief/business`, `requirements/functional`, `specs/contracts`, `gaps/open`...), with what to look for there. `/sync --digest` shows the matrix as section (e). Close a cell with `--mark updated`, or `--mark reviewed --reason TEXT` when nothing changed. Retiring a row cascades it to every document, even outside its routing. Pending cells appear in the `/status` summary under `sources.impact_pending`. Rows that existed before IMP-250b keep an empty matrix.
- **Precedence by scope, not linear.** `--precedence SCOPE --between F-NN,F-MM` says which row governs in one scope: `business`, `scope`, `stack_to_be`, `behavior`, `api`, `compliance`, `legacy`, `design` or `rule`. The default table: minutes govern business and scope; a decision governs the to-be stack and the tech lead governs it below a decision; what is built governs over the prototype; the API contract governs over the prototype and opens a gap; a norm governs over our own material; an externally reviewed copy governs over ours; a real legacy artifact governs over a reconstruction; a spec governs over an example; a prototype sign-off settles design doubts only. An own artifact is never an authority (echo). When no rule settles the clash, or both rows have the same authority, the answer is `unresolved`: the newest source never wins by default. Override one scope in `sentinel.config.yaml`:

  ```yaml
  precedence:
    business: client_document > minutes > interaction
  ```

- **An example never closes a rule.** A confirmed answer that `/resolve-gaps` reads from a row whose authority is `example` leaves the gap `ANSWERED`, never `CLOSED`.
- **Closing report.** `--report` writes `07_changes/closing_report.md`: per recipient (BA, tech lead, product owner, QA), each row's delta (`ADDED`, `MODIFIED`, `REMOVED`) and the cells to look at. It also lists the originals that are ready to delete (extraction saved, every cell closed, row closed) and why the rest are not. The report never deletes a file.

## `specs`

Generate the human PRD and AI-friendly spec from a mature requirement.

```powershell
python -m sentinel /specs PROJECT_ID
```

Fails if maturity is `BLOCKED`.

Foundation drift soft gate (IMP-151): before generating, `/specs` checks whether its foundation drifted since the last generation — i.e. whether the brief/requirements the recorded specs fingerprint (IMP-148) was built from have changed — and returns any `foundation_warnings` recommending you reconcile before relying on the output. It is a soft signal by default; opt-in `drift_gate.strict` blocks instead. It never rewrites anything. `/backlog` runs the same gate over its foundation (specs, and the brief behind it), so a stale upstream `specs` is surfaced there too.

Output:

- `03_specs/prd.md`
- `03_specs/specs.md`
- `03_specs/units/SPEC-U-NNN.md` when confirmed evidence supports bounded spec units
- `08_context_packs/specs_generation.json`

The PRD explains the what and why for business and human reviewers, including personas, functional requirements with acceptance criteria, NFRs, KPIs, JTBD traceability, dependencies, roadmap, governance, and audit trail. Its core narrative sections are compiled from source evidence, confirmed gap answers, EARS rows, decisions, and local-memory retrieval; unsupported details remain `[PENDING INPUT]` with the relevant `GAP-*`. The spec stays compact for agents: `specs.md` is the index and handoff contract, while `03_specs/units/SPEC-U-NNN.md` carries bounded evidence-backed execution units with trace IDs, EARS IDs, and source anchors. The context pack records the focused memory retrieval used during generation.

Per-section PRD readiness and soft gate (IMP-041): `/specs` reports `prd_section_readiness` for numbered PRD sections 1-13 with `populated`/`pending`, `coverage_score`, evidence citation counts, and feeding gaps for poor sections. The same block appears in `/maturity` and `/status` under `maturity_metrics` once `prd.md` exists. The gate is non-blocking by default: below the configured threshold it returns `warnings` and `specs_gate.below_threshold=true`, but still completes. Opt-in strict mode in workspace config blocks completion with readiness stage `SPECS_BELOW_THRESHOLD`:

```yaml
specs_gate:
  threshold: 0.75
  strict: true
```

Default gates are not hardened without opt-in.

## `compose`

Merge validated agent-authored narrative blocks into the generated PRD.

```powershell
python -m sentinel /compose PROJECT_ID --source path\to\composition.json
```

Run this only after `/specs` has created `03_specs/prd.md`. The source file is JSON with `blocks[]`; each block names a PRD section and one or more paragraphs, and every paragraph must include citations copied verbatim from local source-of-truth evidence (`00_raw/`, `01_discovery/`, `02_requirements/`, or `07_changes/`). Sentinel rejects blocks that target a pending section, cite text that is not found verbatim, or try to narrate unresolved pending markers.

Outputs:

- updated `03_specs/prd.md` with an `Agent Composition` subsection carrying `Origin: agent`
- archived source under `03_specs/compositions/`
- `03_specs/compositions/accepted_blocks.json`
- `03_specs/compositions/composition_report.md`
- traceability node and edge from the generated PRD to the composition event

If `/specs` is regenerated later, Sentinel reapplies only still-valid accepted blocks and writes `03_specs/compositions/regeneration_report.md` when stored blocks are kept or discarded. `/compose` does not harden gates by default; it is a falsable enrichment path for evidence-backed narrative, not permission to fill unknown scope.

## `backlog`

Generate initial epic, user stories, acceptance criteria, and agent-oriented backlog contracts.

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /backlog PROJECT_ID --with-task-seeds
python -m sentinel /backlog PROJECT_ID --story-format job
```

Fails if maturity is `BLOCKED`.

`--story-format` selects how each story statement is phrased. The default `user` keeps the persona-neutral user story (`As a target user, I want ... so that ...`). Passing `job` emits the JTBD-native job story (`When [situation], I want [motivation], so I can [outcome]`) — the natural shape when the input names no persona, so none is invented. It changes only the wording of the story statement: acceptance criteria, slicing, and `SPEC-U -> EPIC -> US -> AC` traceability are unchanged, and a missing outcome stays `[PENDING INPUT]` rather than being hand-completed. The format can also be set once via the `story_format: user|job` field in `sentinel.config.yaml`; the flag overrides the config field.

Outputs:

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- `04_backlog/BACKLOG.md`
- `04_backlog/SLICE-PLAN.md`
- optional `04_backlog/EPIC-002-cross-cutting-enablers.md`
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`
- `08_context_packs/slice_plan.json`

`/backlog` derives value stories from confirmed `03_specs/units/SPEC-U-NNN.md` files. Each evidence-backed Spec Unit becomes one vertical story with AC and trace IDs derived from that unit and its `REQ-EARS-*` rows. If no functional Spec Unit exists yet, Sentinel emits a single `[PENDING INPUT]` stub that points to the gaps blocking backlog slicing instead of generating placeholder scope.

The slicing strategy is loaded from `sentinel/slicing/backlog_slicing_model.json`. That file preserves the framework's existing INVEST, vertical slicing, SPIDR, Lawrence and enabler-boundary guidance, and it drives each story's `Slicing Pattern` plus `Slicing Rationale`.

`/backlog` uses progressive disclosure across living domain context. If Technology, Design, Quality, Delivery, or other domains have added context files and those files were ingested, synced, or reindexed, Sentinel can cite that evidence in `Domain Context Coverage`, derive `Agent Execution Contract` sections, and create a story-level retrieval plan for downstream execution agents. The aggregate context remains in `backlog_generation.json`, while each value story also gets a `per_story.US-NNN` mini-context built from its `SPEC-U-*` statement and the same declarative retrieval plan. Missing commands, file maps, design tokens, regression suites, or blast-radius boundaries remain `[PENDING DOMAIN CONTEXT]` instead of being invented.

`implementation_readiness.json` is the machine-friendly handoff pack. It records required domains, pending context, dependencies, validation expectations, retrieval queries, trace IDs, the per-story execution contract, and a snapshot hash of live domain context so `/health` can warn when domain owners updated their files after backlog generation. Treat that warning as a prompt to `/reindex` and retrieve focused context; rerun `/backlog` only for material story, acceptance, dependency, sequencing, or execution-contract changes.

`--with-task-seeds` is optional and should be used only when a downstream consumer explicitly asks for task-seed intentions. When enabled, each story receives a `Task Seed Contract` and `implementation_readiness.json` receives `task_seed_contract`; these seeds are derived from acceptance criteria and confirmed critical surfaces. They are not task execution: Sentinel does not estimate, assign, schedule, execute, or manage them, and downstream planning may expand, reorder, or discard them while preserving story scope and traceability. Default `/backlog` omits this section.

If story marked `Ready`, `/backlog` compares regenerated acceptance criteria with frozen `state.json#acceptance_criteria_freezes` snapshot. changed, removed, or newly added criteria after freeze written to `04_backlog/acceptance_criteria_deltas.md` and traced review-needed; approved contract no longer replaced without explicit diff trail.

`/backlog` also refreshes `04_backlog/BACKLOG.md`, a BA-facing board with summary counts, rollup by epic, status lanes, owners, readiness scores, and blockers. The board is generated from governed workspace artifacts; never edit it by hand.

`/backlog` also emits `04_backlog/SLICE-PLAN.md` and `08_context_packs/slice_plan.json`. The slice plan sequences concrete `EPIC-002` enablers before dependent value stories, groups stories into parallelizable waves, defines checkpoints, and mirrors a per-story handoff pack with position, DoR/DoD state, `execution_contract`, `retrieval_plan`, anchors, validation contract, dependencies and trace IDs. This is a handoff contract, not tasking: Sentinel does not create downstream task IDs, estimates, or implementation steps.

Backlog privacy scanning follows the same soft-gate principle as the handoff gate:

```yaml
privacy_scan:
  mode: warn
```

`warn` is the default: commands that hand off or mutate `04_backlog/` report credentials, private endpoints, emails, or private identifiers without blocking. Use `mode: block` to make those findings fail the command, or `mode: off` to skip the scan entirely.

## `backlog-status`

Generate or refresh the BA-facing backlog board and rollup.

```powershell
python -m sentinel /backlog-status PROJECT_ID
```

Run this after `/backlog` has created story files, or after reviewing lifecycle changes. Sentinel reads `state.json#story_lifecycle`, `state.json#story_gates`, `04_backlog/US-NNN.md`, and `08_context_packs/implementation_readiness.json`, then writes `04_backlog/BACKLOG.md` and persists the current `backlog_rollup` summary in `state.json`.

Outputs:

- `04_backlog/BACKLOG.md`
- `state.json#backlog_rollup`

`/backlog-status` does not change story status, owner, DoR/DoD evidence, slicing rationale, or the EPIC-002 enabler boundary. It only materializes the review view from existing source-of-truth artifacts.

## `story-status`

Update a governed story lifecycle status and owner.

```powershell
python -m sentinel /story-status PROJECT_ID --story US-001 --set Ready --owner "Delivery Lead"
python -m sentinel /story-status PROJECT_ID --story US-001 --set Done --evidence path\to\acceptance-evidence.md
```

Run this only after `/backlog` has created story files. Allowed states are `Draft`, `Ready`, `In Progress`, `In Review`, `Done`, `Blocked`, and `Stale`. Sentinel validates legal transitions, evaluates DoR/DoD gates, updates `state.json`, updates the target `04_backlog/US-NNN.md` frontmatter, lifecycle section and checklists, appends `04_backlog/status_log.md`, refreshes `04_backlog/BACKLOG.md`, and records traceability plus the command protocol log.

`/story-status` is the only supported mutation path for story status or owner. setting story `Ready` is explicit approval marker current acceptance criteria: Sentinel stores versioned snapshot in `state.json#acceptance_criteria_freezes`. `/backlog` preserves existing status/owner values when it regenerates stories, writes DoR/DoD results into `implementation_readiness.json` plus `state.json#story_gates`, and records AC diffs in `04_backlog/acceptance_criteria_deltas.md` when regenerated criteria diverge frozen snapshot.

`backlog_gate` follows the existing soft-gate pattern:

```yaml
backlog_gate:
  threshold: 1.0
  strict: false
```

Default mode is non-blocking: moving to `Ready` or `Done` returns warnings naming the missing checklist items. Opt-in strict mode blocks `Ready` when DoR is incomplete and blocks `Done` when DoD lacks traced acceptance evidence. Use `--evidence PATH` to copy a local downstream evidence file under `04_backlog/acceptance_evidence/` and link it to the story in traceability.

## `refine-backlog`

Merge validated agent-authored backlog refinement proposals into the generated backlog.

```powershell
python -m sentinel /refine-backlog PROJECT_ID --source path\to\backlog-refinement.json
```

Run this only after `/backlog` has created `04_backlog/EPIC-001.md`. The source file is JSON with `proposals[]`; each proposal declares a kind (`reslice`, `split-story`, `merge-stories`, `missing-story`, or `enabler-candidate`), target stories or source units as applicable, a recommendation, rationale, and citations copied verbatim from local source-of-truth evidence. Optional `discarded_alternative` with `option` and `reason` captures another option considered and rejected. `enabler-candidate` proposals must also declare enabled stories, supported boundary, concrete `enabled_capability`, measurable `verification_method`, risk reduced, and objective evidence. Sentinel rejects proposals that target unknown or pending stub stories, cite text that is not found verbatim, use pending Spec Units as grounding evidence, omit measurable enabler criteria, or try to promote loose preconditions into cross-cutting enablers.

Outputs:

- updated `04_backlog/EPIC-001.md` and targeted `04_backlog/US-NNN.md` files with an `Agent Backlog Refinements` section carrying `Origin: agent`
- archived source under `04_backlog/refinements/`
- `04_backlog/refinements/accepted_refinements.json`
- `04_backlog/refinements/refinement_report.md`
- traceability node and edges from epic/story/spec-unit context to the refinement event

`/refine-backlog` is a governed review channel, not an automatic rewrite. Accepted proposals preserve the existing INVEST, vertical slicing, SPIDR, Lawrence, and `EPIC-002` enabler-boundary model; the BA still decides whether a future backlog regeneration or manual upstream evidence change should act on the proposal.

## `implementation-feedback`

Merge structured downstream implementation findings back into backlog governance.

```powershell
python -m sentinel /implementation-feedback PROJECT_ID --source path\to\implementation-feedback.json
```

Run this only after `/backlog` has created story files. The JSON source contains `findings[]`; each finding declares a `type` (`new-dependency`, `gap`, `ac-challenge`, or `surface-not-covered`), target `story`, optional `acceptance_criteria`, `summary`, `evidence`, optional `source_units`, optional `gap_id`, `blocks_dod`, and `mark_stale`.

Outputs:

- archived source under `07_changes/05_implementation_feedback/`
- `07_changes/05_implementation_feedback/feedback_report.md`
- optional `01_discovery/implementation_feedback_gaps.md` for `GAP-FEEDBACK-*`
- `state.json#implementation_feedback`
- updated DoD gate item `implementation_feedback_resolved` for affected stories
- traceability node and edges from the feedback event to the story, AC, and feedback gap

`/implementation-feedback` does not rewrite stories, acceptance criteria, slicing rationale, or enabler boundaries. It records evidence-backed downstream feedback for BA/Product review, may mark only affected stories `Stale`, and may block `Done` through DoD. Default backlog gates still warn; strict mode blocks closure when open blocking feedback remains.

## `quality`

Generate quality/test-case coverage from user stories.

```powershell
python -m sentinel /quality PROJECT_ID
```

Output:

- `05_quality/TC-001.md`
- `05_quality/backlog_readiness_audit.md`

`/quality` also evaluates each story against the governed INVEST/SPIDR/Lawrence model already used by `/backlog`: governed slicing pattern, vertical behavior or concrete enabler boundary, small-but-valuable scope, AC coverage, traceability, and explicit dependencies. In parallel, it now emits a separate structural INVEST audit with one signal per letter (`Independent`, `Negotiable`, `Valuable`, `Estimable`, `Small`, `Testable`) backed by traceability, dependencies, enables, source-unit anchors, and acceptance-criteria coverage instead of prose vocabulary alone. The current `score` / `status` / `verdict` contract does not change. Results are persisted in `state.json#story_quality` and reflected as non-blocking DoR warnings in `state.json#story_gates` after `/quality` runs. Strict backlog gates remain opt-in through `config.backlog_gate.strict`.

## `trace`

Materialize graph views.

```powershell
python -m sentinel /trace PROJECT_ID
```

Outputs:

- `06_traceability/traceability_graph.json`
- `06_traceability/traceability_matrix.md`
- `06_traceability/traceability_graph.md`

## `health`

Run deterministic health checks.

```powershell
python -m sentinel /health PROJECT_ID
```

Checks:

- orphan user stories
- orphan acceptance criteria
- blocking gaps
- unbacked metrics
- memory indexing coverage
- governed drift detection (IMP-148/149): a soft warning when a derived artifact (`specs`, `backlog`) may have drifted from the cited source it was generated from. At generation time each derived artifact records a sha256 fingerprint of its sources (specs from the brief + requirements; backlog from specs); `/health` recomputes and compares, and if a source changed since generation it names the derived artifact as `DRIFTED` and which source(s) changed. It only signals — the BA decides whether to regenerate through the owning command or confirm the change is immaterial; nothing is ever rewritten. This upgrades the exists-based `downstream_stale_artifacts` list to a fingerprint-based divergence check.
- out-of-CLI edit detection (IMP-147): a soft warning when a governed artifact (`01_discovery/gaps.md`, `02_requirements/requirements.md`, `02_requirements/project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) has bytes that differ from the last version a Sentinel command produced. Every mutating command snapshots a deterministic sha256 registry into `state.json#artifact_hashes` on postflight; `/health` recomputes and compares, so a hand-edit — or a `Bash` write that bypassed the IMP-146 editor hook — is flagged by path. It is persistent and cross-process/session (unlike the in-memory optimistic-conflict snapshot of IMP-144, which only spans a single process). It only warns and names the offending file, recommending regeneration through the owning command; it never blocks or reverts, and workspaces with no registry (generated before IMP-147) stay silent.
- needs-context gate (IMP-127): a soft warning when the project holds enough indexed memory to warrant focused retrieval but has no focus context pack. The trigger is indexed volume, not whether LanceDB is present, so it fires identically in `json-hybrid`. Soft by default; it only becomes a blocking finding when `needs_context_gate.strict` is opted in. The machine-readable `needs_context_gate` block is included in `health_report.json`.

Outputs:

- `06_traceability/health_report.md`
- `06_traceability/health_report.json`

## Maturity Metrics

`/maturity` and `/status` expose a quantified `maturity_metrics` block: `gap_closure_rate`, `open_gaps_by_severity`, per-artifact `artifact_evidence_scores` (same scoring as `/validate`), `requirement_quality_score`, a combined `maturity_score` (0.0–1.0), and `trend_vs_previous_run` comparing consecutive `/maturity` runs. Use the trend to see whether new evidence is actually maturing the requirement.

`requirement_quality` is the IMP-111/IMP-129/IMP-130 requirement linter result. It scores each requirement statement and lists cited warning fragments for ambiguous terms, compound statements, unanchored quantifiers, passive voice, missing verification cues, or statements that are not EARS-normalizable. Ambiguous/compound/quantifier findings also carry `category` and `why_it_matters` fields. This is separate from `/quality`: `/maturity` scores requirement prose before specs/backlog, while `/quality` scores generated user stories against INVEST/SPIDR/Lawrence.

Once a project brief exists, the block also carries `brief_section_readiness` (IMP-025): each narrative brief section (1-6) as `populated`/`pending`, an overall `coverage_score`, and, for each poor section, the gaps that feed it — the same signal the soft `/brief` gate uses.

It also carries `maturation_telemetry` (IMP-028): `resolve_iterations` (number of `/resolve-gaps` rounds), `closed_by_origin` and `closed_by_origin_pct` (closed gaps split by gap provenance: checklist vs agent vs challenge), `closed_by_response_source` and `closed_by_response_source_pct` (closed gaps split by who supplied the answer: client, domain, or controlled inference), `reopened_by_sync_total` / `reopened_by_sync_gap_ids` (closed gaps that a later `/sync` change triggered again), `open_blocking_gaps`, and `oldest_blocking_age_rounds` (how many resolve rounds the oldest still-open blocking gap has survived). Use it to see where maturation is stalling.

It also carries `development_readiness` (IMP-068): `01_discovery/development_readiness.json` in API form. The summary includes `global_score`, per-lens scores, status counts, high-risk assumption IDs, and `crystallization_gate.state` (`NOT_READY_OPEN_UNCERTAINTY`, `NOT_READY_LOW_CERTAINTY`, `READY_WITH_GOVERNED_ASSUMPTIONS`, or `READY_LOW_UNCERTAINTY`). Use it to see whether uncertainty is confirmed, explicitly assumed with owner/risk, or still open before development handoff.

## `validate`

Validate workspace structure and graph integrity.

```powershell
python -m sentinel /validate PROJECT_ID
```

Checks:

- required workspace files
- node ID prefixes
- duplicate IDs
- missing artifact paths
- edges pointing to missing nodes
- expected semantic sections in PRD, specs, and stories
- structured citations in v2 artifacts (IMP-249)
- brief v2 integrity: marks, compile report, forbidden values and residues (IMP-255)

**Brief v2 integrity (IMP-255).** Only a v2 brief is checked; v1 is left as before. `/validate` reports:

- **Marks:** every `⏳` that points to a gap missing from `gaps.md` or already closed, and every inline `⚠` without an open contradiction gap.
- **Compile report:** every mark without a `fill_site` in `brief_compile_report.json` (and the reverse), and every `(inferred)` line without its `INFERRED` row in `knowledge_state.json`.
- **Forbidden values, as a value:** an empty cell, `-`, `—`, a bare `N/A`, the brief's own `TBD`, `ninguno`. `nada`, `ninguna` and `none` are explicit and allowed. A quoted source line (one with a `[[…]]` citation) may say TBD.
- **Edit residues:** "last updated", "antes decía", "[edit]", "this document was updated"...

A pending place with no open gap of its own points to the non-blocking umbrella gap of its section (`GAP-BRIEF-S<n>`), which the compiler opens and closes. `/doctor` checks that skills and mirrors write the v2 marker and the pending marks only in their canonical form.

**Id families and structured citations (IMP-249).** Every id family is registered in `sentinel/templates/id_families.json`, with its pattern, an example and whether it is kept (`GAP`, `ASM`, `DEC`, `US`, `SPEC-U`, `CTX`, `RU`, `REQ`, `AC`, `F`), new for v2 artifacts (`RN`, `CA`, `HU`, `SC`, `I`, `P`, `E`, `C`, `R`, `PDef`) or a view of another family (`D-N.M` is a view of `DEC`). Only `RN`, `CA` and `HU` take a release prefix (`r2-RN-04`); gaps stay global. The registry also holds the catalog keys for error codes, events, flags and routes, and the edges `HU → SPEC-U → US`. A retired id is recorded in `06_traceability/retired_ids.json` and never reused.

A v2 artifact starts with `<!-- sentinel-artifact: v2 -->` and cites as `{doc, section[, subblock], id}` plus what the id supports:

```markdown
[[brief § 2.2 › Alta # RN-04 — sostiene: el alta exige doble firma]]
```

`/validate` resolves the id inside the cited section, and reports as findings: an id that is not in that section, a section that does not exist, an id of no registered family, a retired id, a citation that does not say what it supports, and any citation by line number (`project-brief.md:120`, `línea 14`). v1 artifacts carry no marker and are validated exactly as before. Brief v2, which emits the marker, comes with IMP-252.

Requirement quality (non-blocking): the report includes `requirement_quality`, the same IMP-111/IMP-130 linter exposed by `/maturity`. It cites the exact requirement fragments that are vague, passive, missing verification cues, or not normalizable to EARS, and explains ambiguity-like findings by category. These warnings never change `verdict`; structural validity remains separate from requirement testability.

Semantic quality (non-blocking): the report includes a `semantic_quality` block that scores `project-brief.md`, `prd.md`, and `specs.md` by comparing evidence-backed signals (quoted personas/FR statements, populated KPIs, EARS rows, source citations, evidence triggers) against `[PENDING INPUT]` / `[PENDING DOMAIN CONTEXT]` markers. A PRD compiled from real evidence should classify as `evidence-backed` or `mixed`; `scaffolding` means the artifact is still mostly structure or pending content. Warnings never change the verdict: they tell you how mature the content is, not whether the structure is valid.

Cross-artifact consistency (non-blocking): the report also includes `cross_artifact_consistency`. It checks that populated brief sections flow into mapped PRD sections, confirmed `REQ-EARS-*` rows appear in `specs.md` and `03_specs/units/SPEC-U-NNN.md`, extracted `FR-E*` rows have at least one spec-unit layer to carry the detail, spec units do not cite missing EARS IDs, optional `expected_evidence` declarations match the cited source type, and unit source pointers resolve to existing files or Markdown sections. Each warning names `layer`, `artifact`, and `suggested_command` (usually `python -m sentinel /specs PROJECT_ID`). These warnings are added to `warnings`, but they never change `verdict`; structural validity remains separate.

ISO 29148 coverage (non-blocking, IMP-189): the report includes an `iso29148_coverage` block mapping the nine ISO/IEC/IEEE 29148 individual-requirement quality characteristics (Necessary, Appropriate, Unambiguous, Complete, Singular, Feasible, Verifiable, Correct, Conforming) to the deterministic checks Ignite already runs. Each existing check declares which characteristics it covers via `covers_29148` (inert metadata in `sentinel/iso29148/check_catalog.json`), and each characteristic ends up `covered` (listing the covering check IDs), an open `heuristic_gap` (a deterministic rule is feasible but not yet written — e.g. implementation-leak detection for Appropriate), or `out_of_scope` with a stated reason. Characteristics no local deterministic heuristic can honestly decide without domain knowledge — Complete, Feasible, Correct, Necessary — are declared out of scope rather than simulated. The block also lists `verifiability_findings`: requirement statements (including well-formed EARS ones the EARS scorer leaves unscrutinized) that carry no measurable or observable acceptance anchor. It is an auditability lens against the standard, zero-LLM, and never changes `verdict`.

Returns non-zero when invalid.

## `sync`

Ingest stakeholder feedback, meeting notes, or change requests.

Autonomous scan:

```powershell
python -m sentinel /sync PROJECT_ID
```

This detects new or modified files in input and workspace context folders using `00_raw/source_manifest.json`.

If a synced change triggers a gap ID that was already `CLOSED`, the impact report lists it under `Reopened Closed Gaps` and `/status` exposes the aggregate in `maturation_telemetry.reopened_by_sync_*`. Sentinel does not silently change the closed gap state; it makes the renewed uncertainty explicit for BA review.

If a synced file contains structured `### GAP-*` response blocks, Sentinel applies the same governed closure rules as `/resolve-gaps` before rebuilding the ledger. If it explicitly invalidates an `ASM-*`, Sentinel marks that assumption `INVALIDATED`, maps the linked knowledge unit back to `OPEN`, recalculates `development_readiness.json`, and flags downstream stale artifacts for `/health`.

**Contradictions, echo, proposals and cited sources (IMP-251).** Every source that `/ingest` or `/sync` crosses goes through the same pass. It is deterministic and never picks a winner.

- **Statements.** Short assertions (`el plazo de entrega es de 30 días`, `SLA: 24 h`) are anchored to their F-NN row and line in `01_discovery/statement_ledger.json`.
- **Contradiction.** Two sources with different values for the same subject keep both anchors and open a blocking gap with `origin: contradiction`. A subject a source does not mention is source silence, never a contradiction.
- **Interim value.** While that gap is open, the precedence of `/sources` says which version governs, marked `⏳` (or `⚠` with `validation_direction: built` in `sentinel.config.yaml`). When no rule settles it there is no interim value: the newest source never wins.
- **Echo.** A file Sentinel wrote (a governed artifact folder or a generated report) has authority `own_artifact`: it adds no facts and its confirmed answers stay `ANSWERED`.
- **Disguised proposal.** A source that declares itself not validated near the top (`borrador`, `no validado`, `draft`, `not validated`) only adds proposals and cannot close a gap. A line with a proposal cue, or a new technical name that nothing governed mentions, is a proposal too.
- **Cited, never delivered.** A source that leans on a document that is not in the registry ("según el contrato de API", "as defined in the SAD") opens a gap with `origin: cited_not_delivered`, saying what to ask for and to whom (the row's `--from`).
- The same topic never opens two gaps. `01_discovery/contradictions.md` lists contradictions with their interim value, proposals and cited documents.

Explicit file:

```powershell
python -m sentinel /sync PROJECT_ID --source path\to\change.md --note "why this change exists"
```

Structured digest (opt-in) for an unstructured interaction (meeting transcript, mail, chat):

```powershell
python -m sentinel /sync PROJECT_ID --source path\to\meeting.md --digest
```

The digest extracts, with a verbatim citation per line, candidate answers to open gaps (pre-filled into a `PROPOSED` gap-response file that does **not** close anything on its own), `DEC-*` candidates, new gaps, and assumption contradictions reused from the change metabolism. It **proposes and routes, never applies**: it only writes `07_changes/.../interaction_digest.md` and the proposed response file for BA review. No signal means an explicit empty digest.

Creates:

- `CHG` node
- impact report
- refreshed `knowledge_state.*` and `development_readiness.json` when knowledge moves
- `Knowledge Ledger Metabolism` and downstream staleness sections in the impact report
- an `Associative Impact Candidates (BA review)` section when a semantic embedder is active and a reworded change relates to an assumption by meaning (IMP-125) — cited suggestions only; nothing is auto-closed or auto-invalidated
- a focused, pointer-only context pack `08_context_packs/sync_focus.json` (IMP-127) so review consults focus instead of re-reading whole artifacts; its path is returned as `context_pack`
- `may_impact` edges to downstream artifacts
- source manifest entries for processed files
- LanceDB `ba_memory` rows for change and impact chunks

## `retrieve`

Retrieve focused context from the local memory index.

```powershell
python -m sentinel /retrieve PROJECT_ID --query "scope and success criteria" --workflow maturity
```

Optional filters:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product --trace-id CHG-001 --iteration-min 1
```

Additional local memory filters:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --status active --language es --sensitivity internal --section "Framework Trace Table" --max-chars 2000 --summary-only
```

Write a reusable context pack:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --write-pack
```

Bias retrieval toward recent context instead of pure relevance (IMP-126). `--order relevance` (default) keeps the existing ranking; `--order recency` reorders the same shortlist newest-first (score breaks ties):

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --order recency
```

Query the read-only episodic timeline of "what changed and when" (IMP-126) — changes, their impact reports and metabolism log, gap-resolution reports, and client/domain interactions, newest first. `--timeline` needs no `--query`/`--workflow` and accepts optional `--limit`, `--artifact-type`, and `--trace-id`:

```powershell
python -m sentinel /retrieve PROJECT_ID --timeline
python -m sentinel /retrieve PROJECT_ID --timeline --artifact-type change --limit 10
```

Output:

- `08_context_packs/[workflow].json`

## `reindex`

Rebuild local LanceDB memory from the traceability graph, versionable artifacts, and context folders.

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /reindex PROJECT_ID --full
```

Use after manual artifact edits. By default `/reindex` is incremental: unchanged artifacts are skipped by `source_hash`, active embedder, and chunking version. Use `--full` to force re-chunking and re-embedding of all indexed artifacts.
