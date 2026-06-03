# Ignite Sentinel vNext

Repo-local BA/Product requirements framework for AI PODs.

Ignite Sentinel turns raw client input into traceable requirements, specs, backlog, quality artifacts, change impact reports, and retrieval context packs. The source of truth is always the versionable workspace files; memory indexes are only retrieval aids.

## Quick Start

```powershell
python -m sentinel init PROJECT_ID
python -m sentinel ingest PROJECT_ID --source path\to\client-note.md
python -m sentinel maturity PROJECT_ID
python -m sentinel specs PROJECT_ID
python -m sentinel backlog PROJECT_ID
python -m sentinel quality PROJECT_ID
python -m sentinel trace PROJECT_ID
python -m sentinel health PROJECT_ID
python -m sentinel validate PROJECT_ID
```

## Change Flow

```powershell
python -m sentinel sync PROJECT_ID --source path\to\change.md --note "client follow-up"
python -m sentinel retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
python -m sentinel reindex PROJECT_ID
python -m sentinel health PROJECT_ID
```

## Workspace Layout

```text
workspaces/PROJECT_ID/
  00_raw/
  01_discovery/
  02_requirements/
  03_specs/
  04_backlog/
  05_quality/
  06_traceability/
  07_changes/
  08_context_packs/
  memory.lancedb/
  state.json
  sentinel.config.yaml
```

## Design Rules

- Keep truth in workspace files, not in memory indexes.
- Preserve lineage across `RAW`, `REQ`, `GAP`, `DEC`, `SPEC`, `EPIC`, `US`, `AC`, `TC`, and `CHG`.
- Use `sentinel.config.yaml` to tune project domains and maturity gates.
- Use Codex skills in `.codex/skills/` for progressive disclosure.

## Verification

```powershell
python -m unittest discover -s tests
```

## User Documentation

- [User Guide](user_guide/00-user-guide.md)
- [Command Reference](user_guide/01-command-reference.md)
- [Artifact Reference](user_guide/02-artifact-reference.md)
- [Workflows](user_guide/03-workflows.md)
- [Codex Skills Guide](user_guide/04-codex-skills-guide.md)
- [Traceability And Memory](user_guide/05-traceability-and-memory.md)
