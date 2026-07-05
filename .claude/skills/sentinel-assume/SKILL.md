---
name: sentinel-assume
description: "Register governed BA-owned assumptions in Ignite Sentinel through /assume, with every assumption carrying a human owner, risk (importance), uncertainty with a derived priority signal, optional gap link, and a verbatim local evidence basis."
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
- Every assumption needs risk: `low`, `med`, or `high` (`medium` normalizes to `med`).
- `uncertainty` is optional: `low`, `med`, or `high`; defaults to `med`. It feeds the priority signal — see the rubric below.
- Every assumption needs a verbatim local quote as `justification`.
- `closes_gap` is provisional visibility only. It does not turn the gap into confirmed evidence.
- High-risk assumptions linked to gaps must be called out in the summary.

## Prioritization Rubric (risk × uncertainty)

`risk` captures **importance** — the impact if the assumption turns out wrong; `uncertainty` captures how unvalidated it is. The runtime derives a `priority_signal` per assumption from that matrix:

| risk \ uncertainty | low / med | high |
|---|---|---|
| **low / med** | monitor | watch closely |
| **high** | watch closely | **test before advancing** |

"Test before advancing" is a non-blocking signal: it tells the BA to validate that assumption first; it does not gate any command. Report the risk/uncertainty counts and call out every high-risk × high-uncertainty assumption in your summary.

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
      "uncertainty": "high",
      "justification": "The dashboard reads queue metrics from the existing support metrics service.",
      "closes_gap": "GAP-TECH-DATA-SOURCE"
    }
  ]
}
```

The full contract lives in `sentinel/schemas/assumption.schema.json`. The quote in `justification` must appear verbatim in local evidence (`evidence` is accepted as an alias for `justification`).

## Command

Run from the repository root:

```powershell
python -m sentinel /assume PROJECT_ID --source PATH
```

Report accepted assumption IDs, skipped duplicates, risk summary, linked gaps, `01_discovery/assumptions.md`, and refreshed `knowledge_state.md`.
