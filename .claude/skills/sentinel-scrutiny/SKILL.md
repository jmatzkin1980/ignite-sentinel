---
name: sentinel-scrutiny
description: "Use when an Ignite Sentinel requirement needs systematic multi-lens scrutiny against raw input plus local domain context, or a pre-flight implementability probe. Produces structured findings that `/scrutinize` validates and merges with `origin: scrutiny`, refreshing the knowledge ledger; covers `--mode implementability-probe`, the per-RU pass where a coding agent declares what it is missing to implement."
---

# Sentinel Scrutiny

Use this skill to run a systematic discovery scrutiny pass through the Ignite lens model: business, product, design, technical, quality, compliance, and delivery. This is not free-form writing. You propose cited findings; the runtime validates and persists them.

## When To Use

After `/ingest` has created `gaps.md` and `knowledge_state.md`, especially when raw client input and domain context disagree, name a topic without substance, or imply assumptions that the current gap list does not expose.

## Workflow

1. Read `workspaces/PROJECT_ID/00_raw/`, relevant domain context folders, `01_discovery/gaps.md`, and `01_discovery/knowledge_state.md`.
2. Scrutinize each declared lens. Look for unstated assumptions, contradictions, mentions without counterpart detail, and conflicts with domain context.
3. Write a JSON source file with `gaps[]` using the schema below. Every finding must include a verbatim quote from raw input or local domain context.
4. Run `python -m sentinel /scrutinize PROJECT_ID --source PATH` or limit the pass with `--lens LENS`.
5. Report merged/skipped gap IDs, updated gap counts, and the refreshed knowledge ledger path.

## Input Schema

```json
{
  "gaps": [
    {
      "id": "GAP-SCRUTINY-TECH-CONTRACT",
      "lens": "technical",
      "severity": "high",
      "finding_type": "domain-conflict",
      "question": "Which contract is authoritative for invoice status updates?",
      "evidence": "The CRM emits invoice updates nightly",
      "description": "Domain context conflicts with the requirement's real-time expectation."
    }
  ]
}
```

- `id`: stable `GAP-*` id. Reuse an existing checklist id only when you are intentionally surfacing that exact uncertainty.
- `lens`: one of `business`, `product`, `design`, `technical`, `quality`, `compliance`, `delivery`.
- `severity`: `critical | high | medium | low`.
- `finding_type`: `unstated-assumption | contradiction | mention-without-counterpart | domain-conflict`.
- `question`: the concrete question a BA can send to the client or domain owner.
- `evidence`: a verbatim substring from local raw input or domain context. No quote, no finding.
- `description`: concise statement of the missing, conflicting, or assumed knowledge.

## Implementability Probe Mode

`/scrutinize` has a second mode — the pre-flight, per-`RU-*` mirror of `/implementation-feedback`. A coding agent declares, per Requirement Unit, what it is missing to implement, **before** touching code:

```powershell
python -m sentinel /scrutinize PROJECT_ID --source PATH --mode implementability-probe
```

Differences from the default scrutiny mode:

- Every finding must anchor to an existing Requirement Unit: add `"unit": "RU-NNN"` to each gap. The runtime validates the id against the workspace's extracted units; the probe cites real units, never invents them. If no `RU-*` units exist yet, run discovery first.
- `finding_type` uses the probe vocabulary instead: `missing-context | non-inferable-gap | ambiguous-for-implementation`.
- Accepted findings merge with `origin: implementability-probe` and the runtime writes a per-unit `01_discovery/implementability_probe_report.md`.
- The probe only signals: it never auto-resolves a gap and never declares a unit implementable. The BA routes each finding like any other gap.

Example probe finding:

```json
{
  "gaps": [
    {
      "id": "GAP-PROBE-INVOICE-CONTRACT",
      "lens": "technical",
      "severity": "high",
      "finding_type": "non-inferable-gap",
      "unit": "RU-003",
      "question": "Which system is the authoritative source for invoice status, and what is its contract?",
      "evidence": "invoices must reflect the latest status",
      "description": "The unit needs an integration whose contract cannot be inferred from any local source."
    }
  ]
}
```

## Rules

- Work through lenses, never imported personas or generic external vocabulary.
- Evidence or silence: every finding cites local text. If no quote exists, leave it out or mark the uncertainty conversationally for the BA.
- The BA remains in control: scrutiny opens governed gaps and ledger units; it does not close gaps or decide assumptions.
- Local-first: no network, remote embeddings, or external MCP for client/project content.
