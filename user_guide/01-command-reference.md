# Ignite Sentinel Command Reference

This document explains each command in the `sentinel` CLI.

Commands can be invoked in three ways:

1. Kilo Code chat workflow: `/command PROJECT_ID [options]`
2. Codex chat router: `sentinel /command PROJECT_ID [options]`
3. Terminal fallback: `python -m sentinel /command PROJECT_ID [options]`

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

## `doctor`

Check whether the repo is ready for portable VS Code usage.

```powershell
python -m sentinel /doctor
```

Checks:

- Python version
- core runtime
- Codex skills adapter
- Kilo Code agents adapter
- Kilo config
- user guide
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

Blocks when open gaps have severities configured as blocking in `sentinel.config.yaml`.

## `specs`

Generate AI-friendly specs from a mature requirement.

```powershell
python -m sentinel /specs PROJECT_ID
```

Fails if maturity is `BLOCKED`.

Output:

- `03_specs/prd_ai_friendly.md`

## `backlog`

Generate initial epic, user story, and acceptance criteria.

```powershell
python -m sentinel /backlog PROJECT_ID
```

Fails if maturity is `BLOCKED`.

Outputs:

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`

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
