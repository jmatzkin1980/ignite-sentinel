# Ignite Sentinel Workflows

This document describes the main workflows and when to use them.

## Workflow 1: New Requirement

Use when a client provides the initial project package: synchronization guide, architecture or repository references, UX/UI references, sketches, snapshots, design system files, quality context, or delivery constraints.

Recommended source organization before ingestion:

```text
input/
  client_requirement/
  business_context/
  technology_context/
  design_context/
  quality_context/
  interactions/
```

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /maturity PROJECT_ID
```

If maturity is `BLOCKED`, review:

```text
workspaces/PROJECT_ID/01_discovery/gaps.md
workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md
```

Then ask stakeholders for missing information.

Typical gaps to surface include:

- missing user access or navigation path;
- undefined data source, calculation logic, metric owner, or refresh frequency;
- missing UX behavior, empty/error/loading states, or design-system constraints;
- missing non-functional expectations, permissions, auditability, or compliance constraints;
- acceptance criteria that are not measurable or testable.

## Workflow 2: Specs Generation

Use when the requirement is mature enough to become an AI-friendly spec.

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/03_specs/prd_ai_friendly.md
```

## Workflow 3: Backlog Generation

Use when specs are ready to become execution-oriented backlog.

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/04_backlog/
workspaces/PROJECT_ID/05_quality/
```

## Workflow 4: Change Or Meeting Sync

Use when the client, POD, or stakeholder introduces new information: client answers to gaps, email or Slack content, meeting transcripts, architecture notes, design updates, QA observations, or delivery decisions.

```powershell
python -m sentinel /sync PROJECT_ID --source input\change.md --note "source and intent"
python -m sentinel /retrieve PROJECT_ID --query "main change topic" --workflow sync --write-pack
```

Review:

```text
workspaces/PROJECT_ID/07_changes/
workspaces/PROJECT_ID/08_context_packs/
```

Then patch affected artifacts and rerun:

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

Use this loop until the shared understanding is stable enough to generate or refresh specs and backlog.

## Workflow 4B: Project Branch Execution

Use a dedicated Git branch for real project execution or workflow tests.

```powershell
git switch main
git pull
git switch -c project/PROJECT_ID
```

Run Ignite commands in that branch:

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\sync-guide.md
```

Do not merge project branches into `main` when they contain client documents, generated workspaces, or test artifacts. Merge back only isolated improvements to the framework itself.

## Workflow 5: Health Audit

Use before handing artifacts to another domain or agent.

```powershell
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Hand off only when:

- health is `CLEAN`
- validation is `VALID`
- traceability matrix is understandable
- known business uncertainties are represented as gaps

## Workflow 6: Context Retrieval

Use when Codex needs focused context without loading the entire workspace.

```powershell
python -m sentinel /retrieve PROJECT_ID --query "acceptance criteria and SLA risk" --workflow backlog --limit 5
```

Use filters when possible:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product
```

Create a context pack:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --write-pack
```

## Recommended Handoff Checklist

Before sharing with another domain:

- Product: requirement and gaps are clear.
- Technology: scope and constraints are visible.
- Design: user journey implications are explicit or flagged.
- Quality: acceptance criteria and test cases exist.
- Delivery: open gaps, risks, and change impacts are visible.
- Agents: trace IDs and source artifacts are present.
