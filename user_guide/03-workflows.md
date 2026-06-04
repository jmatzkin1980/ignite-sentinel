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
python -m sentinel /gaps PROJECT_ID
python -m sentinel /maturity PROJECT_ID
```

If maturity is `BLOCKED`, review:

```text
workspaces/PROJECT_ID/01_discovery/gaps.md
workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md
```

Then ask stakeholders for missing information.

When the answered gap document returns:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

When maturity reaches `READY_FOR_SPECS`, Sentinel also materializes:

```text
workspaces/PROJECT_ID/02_requirements/project-brief.md
```

You can also refresh the brief explicitly:

```powershell
python -m sentinel /brief PROJECT_ID
```

The brief is the closing artifact for discovery. It consolidates the iterated requirement across business/product, technology, design, quality, governance, decisions, seeds, inferences, and open uncertainty radar. Downstream PRD/spec/backlog generation should treat it as the mature requirement handoff.

Discovery maturity does not mean every domain artifact is fully designed. The brief should provide enough signal for domain agents to deepen their work in context packs:

- Design gets affected journeys, users, screens, states, copy constraints, and visual evidence references.
- Technology gets system boundaries, endpoint/event inventory, create/modify/reuse decisions, source-of-truth ownership, constraints, and risks.
- Frontend and Backend get enough behavior, surface, integration, validation, and failure-mode context to split implementation responsibly.
- Quality gets acceptance strategy, critical flows, edge cases, test data needs, and trace expectations.

Generate domain requests when the brief is ready for deeper analysis:

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
python -m sentinel /context-request PROJECT_ID --domain design
python -m sentinel /context-request PROJECT_ID --domain quality
```

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
workspaces/PROJECT_ID/02_requirements/project-brief.md
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

Use when the client, POD, or stakeholder introduces new information that is not a structured gap response: email or Slack content, meeting transcripts, architecture notes, design updates, QA observations, delivery decisions, or new requirement signals.

For answered `gaps.md`, prefer:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
```

Autonomous mode:

```powershell
python -m sentinel /sync PROJECT_ID
```

Sentinel scans known input and workspace context folders, compares file hashes against `00_raw/source_manifest.json`, and processes new or modified files as change events.

Explicit mode:

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

Use when Codex or Kilo needs focused context without loading the entire workspace. This is a read-only progressive disclosure step; it queries local LanceDB memory and can write a reusable context pack.

```powershell
python -m sentinel /retrieve PROJECT_ID --query "acceptance criteria and SLA risk" --workflow backlog --limit 5
```

Use filters when possible:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product
```

Add filters and budgets to keep context tight:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "scope" --workflow discovery --language es --sensitivity internal --max-chars 2000 --summary-only
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
