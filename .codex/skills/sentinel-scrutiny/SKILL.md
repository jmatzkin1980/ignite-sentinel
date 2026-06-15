---
name: sentinel-scrutiny
description: Use when an Ignite Sentinel requirement needs systematic multi-lens scrutiny against raw input plus local domain context. Produces structured findings that `/scrutinize` validates and merges with `origin: scrutiny`, refreshing the knowledge ledger.
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

## Rules

- Work through lenses, never imported personas or generic external vocabulary.
- Evidence or silence: every finding cites local text. If no quote exists, leave it out or mark the uncertainty conversationally for the BA.
- The BA remains in control: scrutiny opens governed gaps and ledger units; it does not close gaps or decide assumptions.
- Local-first: no network, remote embeddings, or external MCP for client/project content.
