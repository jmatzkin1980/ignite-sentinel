# Ignite Sentinel Workflows

This document describes the main workflows and when to use them.

## Workflow 1: New Requirement

Use when a client provides a new request, idea, email, brief, or meeting note.

```powershell
python -m sentinel init PROJECT_ID
python -m sentinel ingest PROJECT_ID --source input\client-note.md
python -m sentinel maturity PROJECT_ID
```

If maturity is `BLOCKED`, review:

```text
workspaces/PROJECT_ID/01_discovery/gaps.md
workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md
```

Then ask stakeholders for missing information.

## Workflow 2: Specs Generation

Use when the requirement is mature enough to become an AI-friendly spec.

```powershell
python -m sentinel maturity PROJECT_ID
python -m sentinel specs PROJECT_ID
python -m sentinel trace PROJECT_ID
python -m sentinel health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/03_specs/prd_ai_friendly.md
```

## Workflow 3: Backlog Generation

Use when specs are ready to become execution-oriented backlog.

```powershell
python -m sentinel backlog PROJECT_ID
python -m sentinel quality PROJECT_ID
python -m sentinel trace PROJECT_ID
python -m sentinel health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/04_backlog/
workspaces/PROJECT_ID/05_quality/
```

## Workflow 4: Change Or Meeting Sync

Use when the client, POD, or stakeholder introduces new information.

```powershell
python -m sentinel sync PROJECT_ID --source input\change.md --note "source and intent"
python -m sentinel retrieve PROJECT_ID --query "main change topic" --workflow sync --write-pack
```

Review:

```text
workspaces/PROJECT_ID/07_changes/
workspaces/PROJECT_ID/08_context_packs/
```

Then patch affected artifacts and rerun:

```powershell
python -m sentinel reindex PROJECT_ID
python -m sentinel trace PROJECT_ID
python -m sentinel health PROJECT_ID
python -m sentinel validate PROJECT_ID
```

## Workflow 5: Health Audit

Use before handing artifacts to another domain or agent.

```powershell
python -m sentinel health PROJECT_ID
python -m sentinel validate PROJECT_ID
python -m sentinel trace PROJECT_ID
```

Hand off only when:

- health is `CLEAN`
- validation is `VALID`
- traceability matrix is understandable
- known business uncertainties are represented as gaps

## Workflow 6: Context Retrieval

Use when Codex needs focused context without loading the entire workspace.

```powershell
python -m sentinel retrieve PROJECT_ID --query "acceptance criteria and SLA risk" --workflow backlog --limit 5
```

Use filters when possible:

```powershell
python -m sentinel retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product
```

Create a context pack:

```powershell
python -m sentinel retrieve PROJECT_ID --query "SLA risk" --workflow sync --write-pack
```

## Recommended Handoff Checklist

Before sharing with another domain:

- Product: requirement and gaps are clear.
- Technology: scope and constraints are visible.
- Design: user journey implications are explicit or flagged.
- Quality: acceptance criteria and test cases exist.
- Delivery: open gaps, risks, and change impacts are visible.
- Agents: trace IDs and source artifacts are present.

