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
- Codex skills and hooks adapter
- required Codex skills
- Kilo Code agents adapter
- Kilo Code slash commands
- Kilo Code repo config
- user guide and adapter guides
- portable installers and launchers
- repo write access
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
- gap report
- decision log
- digest
- initial graph nodes and edges
- memory index chunks

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

## `gaps`

Regenerate the shareable human-friendly discovery gap document.

```powershell
python -m sentinel /gaps PROJECT_ID
```

Output:

- `01_discovery/gaps.md`

Use this before sharing gaps with a client or domain owner.

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

`/challenge` materializes "understanding what is not being said". The agent first runs three techniques over the maturing requirement, per lens (invariant #1): pre-mortem ("the project failed at 6 months — what did we fail to ask?"), role-play by lens (operator, auditor, attacker...), and assumption inversion. The findings go in a JSON `--source` file shaped like `/annotate` (a `gaps` array with `id`, `lens`, `severity`, `question`, verbatim `evidence`, and an optional `technique`), plus optional `premortem` and `assumptions_inverted` arrays.

Validation is identical to `/annotate` (declared lens, severity range, verbatim evidence — never invented). On success the gaps are tagged `origin: challenge`, merged into `gaps.md`, and a traced, indexed `01_discovery/challenge_report.md` is written grouping findings by lens with the technique that surfaced each one.

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
- `risk`: `low`, `med`, or `high`
- `justification`: verbatim local evidence quote
- `closes_gap`: optional `GAP-*` provisionally addressed by the assumption

The runtime validates the lens, owner, risk, and local quote; writes `01_discovery/assumptions.md`; traces and indexes the assumption register; and refreshes `knowledge_state.md/json` with `ASSUMED` units. Assumptions do not become confirmed evidence: high-risk linked assumptions remain visible in `/maturity` and `/status`, and downstream artifacts cite them as assumptions.

Outputs:

- `01_discovery/assumptions.md`
- archived source under `01_discovery/assumptions/`
- refreshed `01_discovery/knowledge_state.md` and `.json`
- `assumption_register` traceability node
- `maturity_metrics.assumptions` in `/maturity` and `/status`

## `resolve-gaps`

Process an answered `gaps.md` or equivalent Markdown file.

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\client-gap-response.md
```

The parser reads `### GAP-ID` blocks and extracts:

- answer
- owner or source
- evidence or reference
- decision status

The parser also accepts equivalent field labels in the detected project language so existing answered gap files remain processable.

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

Per-section readiness and soft gate (IMP-025): `/brief` reports `brief_section_readiness` — each narrative section (1-6) as `populated`/`pending`, an overall `coverage_score`, and the gaps that feed each poor section. The same block appears in `/maturity` and `/status` (under `maturity_metrics`). The gate is non-blocking by default: below the coverage threshold it emits `warnings` naming the poor sections and the gaps that would populate them. Opt-in strict mode (workspace config `brief_gate: { "threshold": 0.5, "strict": true }`) instead blocks the advance to `READY_FOR_SPECS` (readiness stage `BRIEF_BELOW_THRESHOLD`) until coverage improves. Default gates are not hardened without opt-in.

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

## `status`

Show phase, health, language, privacy mode, readiness, gap counts, knowledge ledger summary, development readiness, last change IDs, and next recommended step.

```powershell
python -m sentinel /status PROJECT_ID
```

## `export`

Copy a shareable artifact under the workspace export folder.

```powershell
python -m sentinel /export PROJECT_ID --artifact gaps --format md
python -m sentinel /export PROJECT_ID --artifact brief --format md
python -m sentinel /export PROJECT_ID --artifact context-request --format md --domain technology
```

Output:

- `08_context_packs/exports/`

## `specs`

Generate the human PRD and AI-friendly spec from a mature requirement.

```powershell
python -m sentinel /specs PROJECT_ID
```

Fails if maturity is `BLOCKED`.

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
```

Fails if maturity is `BLOCKED`.

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

`/story-status` is the only supported mutation path for story status or owner. `/backlog` preserves existing status/owner values when it regenerates stories and writes DoR/DoD results into `implementation_readiness.json` plus `state.json#story_gates`.

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

Run this only after `/backlog` has created `04_backlog/EPIC-001.md`. The source file is JSON with `proposals[]`; each proposal declares a kind (`reslice`, `split-story`, `merge-stories`, `missing-story`, or `enabler-candidate`), target stories or source units as applicable, a recommendation, rationale, and citations copied verbatim from local source-of-truth evidence. Sentinel rejects proposals that target unknown or pending stub stories, cite text that is not found verbatim, use pending Spec Units as grounding evidence, or try to promote loose preconditions into cross-cutting enablers.

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

`/quality` also evaluates each story against the governed INVEST/SPIDR/Lawrence model already used by `/backlog`: governed slicing pattern, vertical behavior or concrete enabler boundary, small-but-valuable scope, AC coverage, traceability, and explicit dependencies. Results are persisted in `state.json#story_quality` and reflected as non-blocking DoR warnings in `state.json#story_gates` after `/quality` runs. Strict backlog gates remain opt-in through `config.backlog_gate.strict`.

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

Outputs:

- `06_traceability/health_report.md`
- `06_traceability/health_report.json`

## Maturity Metrics

`/maturity` and `/status` expose a quantified `maturity_metrics` block: `gap_closure_rate`, `open_gaps_by_severity`, per-artifact `artifact_evidence_scores` (same scoring as `/validate`), a combined `maturity_score` (0.0–1.0), and `trend_vs_previous_run` comparing consecutive `/maturity` runs. Use the trend to see whether new evidence is actually maturing the requirement.

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

Semantic quality (non-blocking): the report includes a `semantic_quality` block that scores `project-brief.md`, `prd.md`, and `specs.md` by comparing evidence-backed signals (quoted personas/FR statements, populated KPIs, EARS rows, source citations, evidence triggers) against `[PENDING INPUT]` / `[PENDING DOMAIN CONTEXT]` markers. A PRD compiled from real evidence should classify as `evidence-backed` or `mixed`; `scaffolding` means the artifact is still mostly structure or pending content. Warnings never change the verdict: they tell you how mature the content is, not whether the structure is valid.

Cross-artifact consistency (non-blocking): the report also includes `cross_artifact_consistency`. It checks that populated brief sections flow into mapped PRD sections, confirmed `REQ-EARS-*` rows appear in `specs.md` and `03_specs/units/SPEC-U-NNN.md`, extracted `FR-E*` rows have at least one spec-unit layer to carry the detail, spec units do not cite missing EARS IDs, and unit source pointers resolve to existing files or Markdown sections. Each warning names `layer`, `artifact`, and `suggested_command` (usually `python -m sentinel /specs PROJECT_ID`). These warnings are added to `warnings`, but they never change `verdict`; structural validity remains separate.

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

Explicit file:

```powershell
python -m sentinel /sync PROJECT_ID --source path\to\change.md --note "why this change exists"
```

Creates:

- `CHG` node
- impact report
- refreshed `knowledge_state.*` and `development_readiness.json` when knowledge moves
- `Knowledge Ledger Metabolism` and downstream staleness sections in the impact report
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

Output:

- `08_context_packs/[workflow].json`

## `reindex`

Rebuild local LanceDB memory from the traceability graph, versionable artifacts, and context folders.

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /reindex PROJECT_ID --full
```

Use after manual artifact edits. By default `/reindex` is incremental: unchanged artifacts are skipped by `source_hash`, active embedder, and chunking version. Use `--full` to force re-chunking and re-embedding of all indexed artifacts.
