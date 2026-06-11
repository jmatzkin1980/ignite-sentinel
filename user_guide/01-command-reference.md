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
- required LanceDB dependency
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
- local LanceDB memory metadata file

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

## `brief`

Generate or refresh the mature project brief.

```powershell
python -m sentinel /brief PROJECT_ID
```

Output:

- `02_requirements/project-brief.md`

Use after blocking gaps are resolved or explicitly accepted as non-blocking.

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
- `08_context_packs/specs_generation.json`

The PRD explains the what and why for business and human reviewers, including personas, functional requirements with acceptance criteria, NFRs, KPIs, JTBD traceability, dependencies, roadmap, governance, and audit trail. The spec stays compact for agents: it keeps trace IDs, backlog contract, progressive disclosure context map, and retrieval guidance for backlog agents. The context pack records the focused memory retrieval used during generation.

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

Semantic quality (non-blocking): the report includes a `semantic_quality` block that scores `project-brief.md`, `prd.md`, and `specs.md` by comparing evidence-backed signals (quoted personas/FR statements, populated KPIs, evidence triggers) against `[PENDING INPUT]` / `[PENDING DOMAIN CONTEXT]` markers. Each artifact is classified as `evidence-backed`, `mixed`, or `scaffolding`, with `warnings` describing what to improve. Warnings never change the verdict: they tell you how mature the content is, not whether the structure is valid.

Returns non-zero when invalid.

## `sync`

Ingest stakeholder feedback, meeting notes, or change requests.

Autonomous scan:

```powershell
python -m sentinel /sync PROJECT_ID
```

This detects new or modified files in input and workspace context folders using `00_raw/source_manifest.json`.

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
```

Use after manual artifact edits.
