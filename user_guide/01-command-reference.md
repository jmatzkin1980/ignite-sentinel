# Ignite Sentinel Command Reference

This document explains each command in the `sentinel` CLI.

Run help:

```powershell
python -m sentinel --help
```

## `init`

Create a project workspace.

```powershell
python -m sentinel init PROJECT_ID
```

Creates:

- folder structure under `workspaces/PROJECT_ID/`
- `state.json`
- `sentinel.config.yaml`
- empty traceability graph
- local memory fallback file

## `ingest`

Ingest raw input and create discovery artifacts.

```powershell
python -m sentinel ingest PROJECT_ID --source path\to\input.md
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
python -m sentinel maturity PROJECT_ID
```

Output:

- `01_discovery/requirement_maturity_report.md`

Blocks when open gaps have severities configured as blocking in `sentinel.config.yaml`.

## `specs`

Generate AI-friendly specs from a mature requirement.

```powershell
python -m sentinel specs PROJECT_ID
```

Fails if maturity is `BLOCKED`.

Output:

- `03_specs/prd_ai_friendly.md`

## `backlog`

Generate initial epic, user story, and acceptance criteria.

```powershell
python -m sentinel backlog PROJECT_ID
```

Fails if maturity is `BLOCKED`.

Outputs:

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`

## `quality`

Generate quality/test-case coverage from user stories.

```powershell
python -m sentinel quality PROJECT_ID
```

Output:

- `05_quality/TC-001.md`

## `trace`

Materialize graph views.

```powershell
python -m sentinel trace PROJECT_ID
```

Outputs:

- `06_traceability/traceability_graph.json`
- `06_traceability/traceability_matrix.md`
- `06_traceability/traceability_graph.md`

## `health`

Run deterministic health checks.

```powershell
python -m sentinel health PROJECT_ID
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
python -m sentinel validate PROJECT_ID
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

```powershell
python -m sentinel sync PROJECT_ID --source path\to\change.md --note "why this change exists"
```

Creates:

- `CHG` node
- impact report
- `may_impact` edges to downstream artifacts

## `retrieve`

Retrieve focused context from the local memory index.

```powershell
python -m sentinel retrieve PROJECT_ID --query "scope and success criteria" --workflow maturity
```

Optional filters:

```powershell
python -m sentinel retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product --trace-id CHG-001
```

Write a reusable context pack:

```powershell
python -m sentinel retrieve PROJECT_ID --query "SLA risk" --workflow sync --write-pack
```

Output:

- `08_context_packs/[workflow].json`

## `reindex`

Rebuild local memory from the traceability graph and versionable artifacts.

```powershell
python -m sentinel reindex PROJECT_ID
```

Use after manual artifact edits.

