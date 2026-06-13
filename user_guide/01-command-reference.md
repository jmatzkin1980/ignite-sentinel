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

Blocks when open, answered, or partially closed gaps have severities configured as blocking in `sentinel.config.yaml`.

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

Outputs:

- updated `01_discovery/gaps.md`
- copied response under `07_changes/00_client_responses/`
- `07_changes/00_client_responses/[source]_gap_resolution_report.md`
- appended `01_discovery/gap_resolution_log.md`
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

Show phase, health, language, privacy mode, readiness, gap counts, last change IDs, and next recommended step.

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
```

Fails if maturity is `BLOCKED`.

Outputs:

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- optional `04_backlog/EPIC-002-cross-cutting-enablers.md`
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`

`/backlog` uses progressive disclosure across living domain context. If Technology, Design, Quality, Delivery, or other domains have added context files and those files were ingested, synced, or reindexed, Sentinel can cite that evidence in `Domain Context Coverage`, derive `Agent Execution Contract` sections, and create a story-level retrieval plan for downstream execution agents. Missing commands, file maps, design tokens, regression suites, or blast-radius boundaries remain `[PENDING DOMAIN CONTEXT]` instead of being invented.

`implementation_readiness.json` is the machine-friendly handoff pack. It records required domains, pending context, dependencies, validation expectations, retrieval queries, trace IDs, and a snapshot hash of live domain context so `/health` can detect if the backlog became stale after domain owners updated their files.

## `quality`

Generate quality/test-case coverage from user stories.

```powershell
python -m sentinel /quality PROJECT_ID
```

Output:

- `05_quality/TC-001.md`

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

Explicit file:

```powershell
python -m sentinel /sync PROJECT_ID --source path\to\change.md --note "why this change exists"
```

Creates:

- `CHG` node
- impact report
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
