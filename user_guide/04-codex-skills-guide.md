# Ignite Sentinel Codex Skills Guide

Ignite Sentinel includes repo-local Codex skills under:

```text
.codex/skills/
```

Skills provide progressive disclosure. Codex sees the skill metadata first and loads the body only when the workflow applies.

## Available Skills

| Skill | Use When |
| --- | --- |
| `sentinel-discovery` | Ingesting raw client/stakeholder requirements |
| `sentinel-maturity` | Checking readiness before specs/backlog |
| `sentinel-specs` | Generating AI-friendly specs |
| `sentinel-backlog` | Generating epics, stories, and acceptance criteria |
| `sentinel-quality` | Generating quality/test coverage |
| `sentinel-sync` | Processing feedback, meetings, or changes |
| `sentinel-health` | Auditing health, traceability, and indexing |

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

### `sentinel-maturity`

Reads:

- gaps
- requirements
- `sentinel.config.yaml`

Creates:

- maturity report

### `sentinel-specs`

Creates:

- AI-friendly PRD/spec
- `REQ -> SPEC` traceability

### `sentinel-backlog`

Creates:

- epic
- user story
- acceptance criteria
- `SPEC -> EPIC -> US -> AC` traceability

### `sentinel-quality`

Creates:

- test case set
- `US -> TC` traceability

### `sentinel-sync`

Creates:

- change node
- impact report
- `CHG -> impacted artifact` traceability

### `sentinel-health`

Creates:

- health reports
- traceability findings
- memory indexing findings

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

