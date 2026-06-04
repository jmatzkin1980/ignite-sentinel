# Ignite Sentinel vNext

Repo-local BA/Product requirements framework for AI PODs.

Ignite Sentinel turns raw client input into traceable requirements, specs, backlog, quality artifacts, change impact reports, and retrieval context packs. The source of truth is always the versionable workspace files; memory indexes are only retrieval aids.

## Quick Start

First time on a new laptop or PC:

```powershell
git clone https://github.com/jmatzkin1980/ignite-sentinel.git
cd ignite-sentinel
python -m sentinel /doctor
```

If `/doctor` reports missing dependencies, install the repo into the active Python environment and run the check again:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

Then open the repo root in VS Code:

```powershell
code .
```

For Kilo Code, make sure the extension can see `.kilo/agents/`, `.kilo/commands/`, and `kilo.jsonc`. For Codex, make sure `.codex/skills/` and `AGENTS.md` are visible from the opened folder.

Kilo Code chat:

```text
/doctor
/init PROJECT_ID
/ingest PROJECT_ID --source input\client_requirement\sync-guide.md
/gaps PROJECT_ID
/resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
/maturity PROJECT_ID
/brief PROJECT_ID
```

Codex chat:

```text
sentinel /init PROJECT_ID
sentinel /maturity PROJECT_ID
```

PowerShell fallback:

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /gaps PROJECT_ID
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /brief PROJECT_ID
python -m sentinel /context-request PROJECT_ID --domain technology
python -m sentinel /specs PROJECT_ID
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

`/doctor` verifies Python, required dependencies such as LanceDB, repo-local Kilo/Codex adapter files, write access, and a local LanceDB open/create probe. If LanceDB is missing, install repo dependencies in the active Python environment:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Change Flow

Structured gap response flow:

```powershell
python -m sentinel /gaps PROJECT_ID
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /brief PROJECT_ID
```

General novelty/change flow:

```powershell
python -m sentinel /sync PROJECT_ID
python -m sentinel /sync PROJECT_ID --source input\change.md --note "client follow-up"
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
python -m sentinel /reindex PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Use `/resolve-gaps` for answered `gaps.md` documents. Use `/sync PROJECT_ID` for autonomous novelty detection. It scans known input/context folders, compares hashes in `00_raw/source_manifest.json`, and processes new or modified files as change events.

## Command Protocol

Every project command runs through the Sentinel vNext protocol:

1. preflight guard for workspace, phase, health, and command preconditions
2. CLI execution against versionable workspace artifacts
3. postflight trace materialization for mutating commands
4. command anchor in `06_traceability/command_protocol_log.md`

This replaces the old Roo hook model with repo-local, deterministic runtime checks.

## Local Memory

Ignite Sentinel uses local LanceDB memory under each workspace:

```text
workspaces/PROJECT_ID/memory.lancedb/
```

`/ingest`, `/sync`, and `/reindex` populate memory from generated artifacts and domain-owned context folders such as technology, design, quality, business, and interactions. Use `/retrieve` to build focused context packs before Codex or Kilo Code executes a workflow.

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
    requests/
    exports/
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
- Keep project privacy local-only by default: no remote MCP, external vector database, or external embedding service for client/project content.
- Preserve lineage across `RAW`, `REQ`, `GAP`, `DEC`, `PRD`, `SPEC`, `EPIC`, `US`, `AC`, `TC`, and `CHG`.
- Use `sentinel.config.yaml` to tune project domains and maturity gates.
- Use Codex skills in `.codex/skills/` for progressive disclosure.
- Use Kilo Code agents in `.kilo/agents/` and slash workflows in `.kilo/commands/` when Codex is unavailable.

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
- [Chat Commands](user_guide/11-chat-commands.md)
- [Operational Scenarios](user_guide/12-scenarios.md)
