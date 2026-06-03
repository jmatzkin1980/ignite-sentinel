# Ignite Sentinel vNext

Repo-local BA/Product requirements framework for AI PODs.

Ignite Sentinel turns raw client input into traceable requirements, specs, backlog, quality artifacts, change impact reports, and retrieval context packs. The source of truth is always the versionable workspace files; memory indexes are only retrieval aids.

## Quick Start

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

## Change Flow

```powershell
python -m sentinel /sync PROJECT_ID --source input\change.md --note "client follow-up"
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
python -m sentinel /reindex PROJECT_ID
python -m sentinel /health PROJECT_ID
```

## Workspace Layout

```text
workspaces/PROJECT_ID/
  00_raw/
    00_client_requirement/
    01_business_context/
    02_technology_context/
    03_design_context/
    04_quality_context/
    05_interactions/
  01_discovery/
  02_requirements/
  03_specs/
  04_backlog/
  05_quality/
  06_traceability/
  07_changes/
    00_client_responses/
    01_meetings/
    02_mail_slack/
    03_domain_updates/
  08_context_packs/
  memory.lancedb/
  state.json
  sentinel.config.yaml
```

The repository also includes:

- `input/`: place local source files here before ingestion.
- `workspaces/_template/`: versionable empty workspace scaffold.

## Design Rules

- Keep `main` as a clean framework branch with no client or test project data.
- Run real project workflows in project branches, for example `project/ACME_DASHBOARD`.
- Merge only framework improvements back to `main`; do not merge generated project workspaces unless explicitly approved.
- Keep truth in workspace files, not in memory indexes.
- Preserve lineage across `RAW`, `REQ`, `GAP`, `DEC`, `SPEC`, `EPIC`, `US`, `AC`, `TC`, and `CHG`.
- Use `sentinel.config.yaml` to tune project domains and maturity gates.
- Use Codex skills in `.codex/skills/` for progressive disclosure.
- Use Kilo Code agents in `.kilo/agents/` when Codex is unavailable.

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
- [VS Code Portable Install](user_guide/06-installation-vscode.md)
- [Kilo Code Adapter](user_guide/07-kilo-code-adapter.md)
- [Codex Adapter](user_guide/08-codex-adapter.md)
- [Secure Environments](user_guide/09-secure-environments.md)
- [Repo And Branching Strategy](user_guide/10-repo-and-branching-strategy.md)
