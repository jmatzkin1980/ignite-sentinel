---
name: sentinel-annotate
description: "Use when an agent has read a raw client requirement for Ignite Sentinel and wants to contribute the semantic gaps, ambiguities, and implicit assumptions it detected — gaps the lexical checklist misses because a reassuring keyword is present. Produces the structured analysis that `/annotate` validates and merges with `origin: agent`."
---

# Sentinel Annotate

Use this skill to turn the agent's reading of the raw requirement into governed, traceable gaps. The deterministic checklist (`/ingest`) decides gaps by token presence/absence and therefore misses what is *named but not defined* ("security is important", "there are business rules"). You, the agent, are the only component that reads meaning — but you must never edit artifacts by hand. `/annotate` is the sanctioned channel: you propose, the runtime validates and persists.

## When to use

After `/ingest` has produced `01_discovery/gaps.md`, when you have read `00_raw/` and can identify real gaps the checklist suppressed. This is the Ignite equivalent of a `/clarify` pass, executed through the lens model.

## Workflow

1. Read the raw input under `workspaces/PROJECT_ID/00_raw/` and the existing `01_discovery/gaps.md`.
2. Identify gaps that are genuinely unresolved even though a keyword is present. Scrutinize through the lenses: business, product, quality, technical, compliance, delivery, design.
3. Write a JSON analysis file (see schema below). Every gap MUST carry a verbatim quote from the raw input — evidence or explicit silence (invariant #3). You cite; you never invent.
4. Run `python -m sentinel /annotate PROJECT_ID --source PATH`.
5. Report the merged and skipped gap IDs and the updated gap counts. The merged gaps now flow through the normal `/resolve-gaps` → `/maturity` → gate lifecycle exactly like checklist gaps.

## Input schema

```json
{
  "gaps": [
    {
      "id": "GAP-TECH-NFR",
      "lens": "technical",
      "severity": "high",
      "question": "What are the concrete performance, security, and availability targets the solution must meet?",
      "evidence": "Security and performance are important to us",
      "description": "Non-functional targets are named but never quantified."
    }
  ],
  "ambiguities": ["'successful once approvers are happy' has no measurable definition of success."],
  "assumptions": ["The approval workflow is internal-only; no external party submits expenses."]
}
```

- `id`: stable `GAP-*` id. Reuse a checklist id when you are firing a gap the checklist suppressed; use a new `GAP-*` id for a genuinely novel gap.
- `lens`: one of the declared lenses (business, product, quality, technical, compliance, delivery, design). An undeclared lens is rejected.
- `severity`: `critical | high | medium | low`.
- `question`: the concrete elicitation question for the client/domain.
- `evidence`: a verbatim substring of the raw input. If it is not found verbatim, the runtime rejects the whole annotation.
- `description` (optional): one-line statement of what is missing.
- `ambiguities` / `assumptions` (optional): recorded in the annotation log for the BA, not merged as gaps.

## Rules

- Evidence or silence: every gap quotes real input text. No quote, no gap.
- Work through the lens model — gaps are classified by lens, never as generic personas (invariant #1).
- Propose; do not decide. The runtime validates, tags `origin: agent`, and merges. The BA stays in control (invariant #5).
- Do not duplicate gaps already open in `gaps.md`; the runtime skips duplicates and reports them.
- Local-first: `/annotate` runs entirely on the local CLI. No network, no external services.

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
