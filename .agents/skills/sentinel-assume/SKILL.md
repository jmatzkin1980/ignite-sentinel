---
name: sentinel-assume
description: Register governed BA-owned assumptions in Ignite Sentinel through /assume, with every assumption carrying a human owner, risk, optional gap link, and a verbatim local evidence basis.
---

# Sentinel Assume

Use this skill when the BA decides to proceed with an explicit assumption instead of leaving a gray area hidden or pretending it is confirmed.

## Inputs To Read

Read only the local project artifacts needed for the assumption:

- `workspaces/PROJECT_ID/01_discovery/gaps.md`
- `workspaces/PROJECT_ID/01_discovery/knowledge_state.md`
- relevant raw/domain/change evidence under `00_raw/`, `01_discovery/`, `02_requirements/`, or `07_changes/`

Do not use web or remote sources for client/project content.

## Governed Rules

- Every assumption must use an Ignite lens: business, product, design, technical, quality, compliance, or delivery.
- Every assumption needs a human owner. Use the BA, Product Owner, domain lead, or named role supplied by the user; never use "AI" as owner.
- Every assumption needs risk: `low`, `med`, or `high`.
- Every assumption needs a verbatim local quote as `justification`.
- `closes_gap` is provisional visibility only. It does not turn the gap into confirmed evidence.
- High-risk assumptions linked to gaps must be called out in the summary.

## Source JSON

Create a local JSON file shaped like this:

```json
{
  "assumptions": [
    {
      "id": "ASM-TECH-METRICS-SOURCE",
      "lens": "technical",
      "statement": "The dashboard will use the existing metrics service as the provisional source of queue risk data.",
      "owner": "Technology Lead",
      "risk": "med",
      "justification": "The dashboard reads queue metrics from the existing support metrics service.",
      "closes_gap": "GAP-TECH-DATA-SOURCE"
    }
  ]
}
```

The quote in `justification` must appear verbatim in local evidence.

## Command

Run from the repository root:

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

Report accepted assumption IDs, skipped duplicates, risk summary, linked gaps, `01_discovery/assumptions.md`, and refreshed `knowledge_state.md`.
