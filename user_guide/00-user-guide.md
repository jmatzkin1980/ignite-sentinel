# Ignite Sentinel vNext - User Guide

Ignite Sentinel vNext is a repo-local BA/Product framework for AI PODs. It helps transform raw client input into mature, traceable, AI-friendly artifacts that can be consumed by humans and agents across Product, Technology, Design, Quality, and Delivery.

This guide is written for Business Analysts, Product members, and AI-assisted delivery teams that need a reliable path from an ambiguous client request to usable specs, backlog, test coverage, and change impact analysis.

## What Ignite Sentinel Does

Ignite Sentinel supports the requirements lifecycle:

1. Ingest raw input from a client or stakeholder.
2. Extract requirements, gaps, decisions, and risks.
3. Evaluate whether the requirement is mature enough to continue.
4. Generate AI-friendly specs.
5. Generate backlog artifacts: epics, user stories, and acceptance criteria.
6. Generate quality artifacts and test-case coverage.
7. Maintain traceability across all artifacts.
8. Process changes, feedback, and meetings as controlled change events.
9. Run health and validation checks before downstream work.

## Core Ideas

### Source Of Truth

The source of truth is always the versionable workspace files under:

```text
workspaces/[PROJECT_ID]/
```

Memory indexes are retrieval aids only. If a memory result and a workspace file disagree, the workspace file wins.

### Traceability

Every meaningful artifact gets a stable ID:

| Prefix | Meaning |
| --- | --- |
| `RAW` | Raw input |
| `REQ` | Requirement |
| `GAP` | Gap or blocker |
| `DEC` | Decision or impact report |
| `SPEC` | Specification |
| `EPIC` | Epic |
| `US` | User story |
| `AC` | Acceptance criteria |
| `TC` | Test case |
| `CHG` | Change event |

The intended lineage is:

```text
RAW -> REQ -> GAP/DEC -> SPEC -> EPIC -> US -> AC -> TC
                 |
                CHG -> impacted artifacts
```

### Health

Health is a deterministic gate. A project can be:

- `CLEAN`: no blocking findings detected.
- `DIRTY`: unresolved gaps, traceability issues, unbacked metrics, or missing index coverage exist.

Do not treat `CLEAN` as business approval. Treat it as structural readiness.

## Quick Start

Use a unique project ID, for example `ACME_DASHBOARD`.

```powershell
python -m sentinel /doctor
python -m sentinel /init ACME_DASHBOARD
python -m sentinel /ingest ACME_DASHBOARD --source path\to\client-note.md
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /specs ACME_DASHBOARD
python -m sentinel /backlog ACME_DASHBOARD
python -m sentinel /quality ACME_DASHBOARD
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

If `python` is not available in your shell, use the Python runtime configured for your Codex environment.

## Workspace Layout

```text
workspaces/[PROJECT_ID]/
  00_raw/             Raw client or stakeholder input
  01_discovery/       Gaps, decisions, maturity reports, digests
  02_requirements/    Requirement register
  03_specs/           AI-friendly specs / PRD
  04_backlog/         Epics, user stories, acceptance criteria
  05_quality/         Test cases and quality coverage
  06_traceability/    Graph JSON, matrix, Mermaid, health reports
  07_changes/         Change events and impact reports
  08_context_packs/   Retrieval context packs
  memory.lancedb/     Local memory fallback/index files
  state.json
  sentinel.config.yaml
```

## Typical BA Flow

### 1. Start A Workspace

```powershell
python -m sentinel /init ACME_DASHBOARD
```

This creates the project workspace, default configuration, empty traceability graph, and local memory files.

### 2. Ingest Raw Input

```powershell
python -m sentinel /ingest ACME_DASHBOARD --source input\client-note.md
```

Outputs:

- `00_raw/[source].md`
- `01_discovery/raw_input_digest.md`
- `01_discovery/gaps.md`
- `01_discovery/decisions.md`
- `02_requirements/requirements.md`
- initial traceability graph
- indexed memory chunks

### 3. Evaluate Maturity

```powershell
python -m sentinel /maturity ACME_DASHBOARD
```

Outputs:

- `01_discovery/requirement_maturity_report.md`

If the report says `BLOCKED`, resolve the blocking gaps before generating specs or backlog.

### 4. Generate Specs

```powershell
python -m sentinel /specs ACME_DASHBOARD
```

Output:

- `03_specs/prd_ai_friendly.md`

The spec is intentionally implementation-agnostic and domain-aware.

### 5. Generate Backlog

```powershell
python -m sentinel /backlog ACME_DASHBOARD
```

Outputs:

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- trace links from `SPEC -> EPIC -> US -> AC`

### 6. Generate Quality Coverage

```powershell
python -m sentinel /quality ACME_DASHBOARD
```

Output:

- `05_quality/TC-001.md`

This gives Quality and Test Automation a traceable starting point.

### 7. Review Traceability

```powershell
python -m sentinel /trace ACME_DASHBOARD
```

Outputs:

- `06_traceability/traceability_graph.json`
- `06_traceability/traceability_matrix.md`
- `06_traceability/traceability_graph.md`

### 8. Run Health And Validation

```powershell
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

Use both:

- `health` checks BA/Product quality signals and traceability health.
- `validate` checks structural integrity of IDs, edges, and artifact paths.

## Change Flow

When new information arrives, do not edit downstream artifacts silently. Ingest it as a change event.

```powershell
python -m sentinel /sync ACME_DASHBOARD --source input\client-followup.md --note "client follow-up after demo"
```

Outputs:

- `07_changes/[source].md`
- `07_changes/[source]_impact_report.md`
- `CHG` node in the graph
- `may_impact` edges to downstream artifacts

Then build a context pack:

```powershell
python -m sentinel /retrieve ACME_DASHBOARD --query "SLA risk by queue" --workflow sync --write-pack
```

After reviewing and patching affected artifacts:

```powershell
python -m sentinel /reindex ACME_DASHBOARD
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
```

## Working With Codex Skills

Ignite Sentinel ships repo-local Codex skills in:

```text
.codex/skills/
```

Use them by asking Codex for the workflow:

- "Use `sentinel-discovery` to ingest this client note."
- "Use `sentinel-maturity` to evaluate readiness."
- "Use `sentinel-specs` to generate the AI-friendly PRD."
- "Use `sentinel-backlog` to generate backlog."
- "Use `sentinel-quality` to generate QA coverage."
- "Use `sentinel-sync` to process this change."
- "Use `sentinel-health` to audit the workspace."

The skills are intentionally short. Detailed context lives in references and runtime artifacts, so Codex only loads what it needs.

## Practical Guidance For BAs

- Do not hide uncertainty. Convert it into a `GAP`.
- Do not invent metrics. If a percentage, cost, or performance claim lacks source or baseline, treat it as a gap.
- Do not generate backlog from immature requirements.
- Do not treat generated artifacts as final client-approved documents without review.
- Use change events for feedback, meetings, and stakeholder refinements.
- Keep the graph healthy before handing work to Technology, Design, Quality, or Delivery.
