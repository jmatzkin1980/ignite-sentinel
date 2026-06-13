# Ignite Sentinel Codex Skills Guide

Ignite Sentinel includes repo-local Codex skills under:

```text
.codex/skills/
```

Skills provide progressive disclosure. Codex sees the skill metadata first and loads the body only when the workflow applies.

Skills delegate deterministic work to the same local CLI used by Kilo Code and terminal workflows. The normal command is `python -m sentinel ...`; if `python` is unavailable in Codex Desktop or VS Code, use the repo-local launcher `.\installers\sentinel.ps1 ...` from the repository root.

## Available Skills

| Skill | Use When |
| --- | --- |
| `sentinel-discovery` | Ingesting raw client/stakeholder requirements |
| `sentinel-maturity` | Checking readiness before specs/backlog |
| `sentinel-specs` | Generating PRD and AI-friendly specs |
| `sentinel-backlog` | Generating epics, stories, and acceptance criteria |
| `sentinel-quality` | Generating quality/test coverage |
| `sentinel-sync` | Processing feedback, meetings, or changes |
| `sentinel-health` | Auditing health, traceability, and indexing |
| `sentinel-gap-response` | Processing answered discovery gaps |
| `sentinel-project-brief` | Generating or refreshing the mature project brief |
| `sentinel-domain-request` | Asking domains for deeper context packs |
| `sentinel-privacy-local-first` | Enforcing local-only privacy rules |

## How To Ask Codex

Examples:

```text
Use sentinel-discovery to ingest this client note for project ACME_DASHBOARD.
```

```text
Use sentinel-maturity and tell me why the project is blocked.
```

```text
Use sentinel-sync to ingest this follow-up and generate an impact report.
```

```text
Use sentinel-gap-response to process this answered gaps file.
```

```text
Use sentinel-domain-request to ask Technology for a context pack.
```

```text
Use sentinel-health to audit ACME_DASHBOARD before handoff.
```

## Skill Responsibilities

### `sentinel-discovery`

Creates:

- raw copy
- digest
- requirement
- gaps
- decisions
- initial traceability
- local LanceDB memory entries for generated artifacts and workspace context folders

Can regenerate the human-friendly gap response contract with:

```powershell
python -m sentinel /gaps PROJECT_ID
```

Uses the maturity gap checklist:

```text
.codex/skills/sentinel-discovery/references/requirement-maturity-gap-checklist.md
```

This checklist helps agents decide whether unclear product, design/prototype, technology, frontend, backend, or quality information should be marked as a gap.

Before deeper analysis, use:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "discovery topic" --workflow discovery --write-pack
```

### `sentinel-maturity`

Reads:

- gaps
- requirements
- `sentinel.config.yaml`

Creates:

- maturity report
- project brief when readiness reaches `READY_FOR_SPECS`

### `sentinel-gap-response`

Runs:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

Creates:

- copied client response
- gap resolution report
- gap resolution log
- confirmed seeds and decisions for structurally confirmed answers
- trace links from `CHG` to `GAP`, `SEED`, and `DEC`

### `sentinel-project-brief`

Runs:

```powershell
python -m sentinel /brief PROJECT_ID
```

Creates or refreshes:

- `02_requirements/project-brief.md`

### `sentinel-domain-request`

Runs:

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
```

Creates:

- `08_context_packs/requests/[domain]_context_request.md`

### `sentinel-privacy-local-first`

Use this when handling project data, memory, retrieval, or exports.

Rules:

- no remote MCP for client/project content;
- no external embedding APIs;
- no external vector database;
- LanceDB and JSON fallback stay under the project workspace;
- source files remain the source of truth.

### `sentinel-specs`

Creates:

- `03_specs/prd.md` for the human/business narrative
- `03_specs/specs.md` for agent progressive disclosure
- `REQ/project_brief -> PRD -> SPEC` traceability

### `sentinel-backlog`

Creates:

- one Markdown file per epic as the primary human review artifact
- `US-00x.md` story mirrors for traceability and quality tooling
- one value story per confirmed `SPEC-U-*` unit, or a `[PENDING INPUT]` stub when no evidence-backed unit exists
- user stories with domain context coverage, agent execution contracts, and retrieval plans
- acceptance criteria with fail-to-pass, pass-to-pass, and evidence classifications
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`
- `SPEC-U -> EPIC -> US -> AC` traceability, with `SPEC-001` retained as the index contract

Rules:

- prefer vertical, value-oriented stories;
- derive story scope from confirmed `03_specs/units/SPEC-U-NNN.md` files; do not expand a fixed placeholder story list;
- keep `[PENDING DOMAIN CONTEXT]` visible instead of inventing missing implementation detail;
- create a cross-cutting enabler epic only for concrete implementation work that must be built in advance to support confirmed project functionality;
- rerun `/reindex` and `/backlog` if domain context changes after backlog generation.

### `sentinel-quality`

Creates:

- test case set
- `US -> TC` traceability

### `sentinel-sync`

Creates:

- change node
- impact report
- `CHG -> impacted artifact` traceability
- local LanceDB memory entries for the change

### `sentinel-health`

Creates:

- health reports
- traceability findings
- memory indexing findings
- stale domain context findings when backlog was generated from an older domain snapshot

## Guardrail Hooks

Optional hooks live in:

```text
.codex/hooks/
```

They are reminders and guardrails, not the primary enforcement mechanism. The deterministic CLI commands remain the source of validation:

```powershell
python -m sentinel /validate PROJECT_ID
python -m sentinel /health PROJECT_ID
```

The post-tool hook also attempts to index edited workspace `.md` and `.txt` artifacts into local memory. Run `/reindex PROJECT_ID` if a workflow depends on fresh context.

