---
name: sentinel-self-review
description: "Use when an Ignite Sentinel PRD or specs layer needs an adversarial pass before downstream handoff: author the cited skeptical findings and hard-to-reverse decisions that /self-review validates and registers under 03_specs/self_review/ — the runtime never rewrites PRD/specs. Trigger on 'review the PRD', 'review the specs', a skeptical pass over generated artifacts, or registering hard-to-reverse decisions."
---

# Sentinel Self-Review

Use this skill to run a skeptical, adversarial review over generated PRD/spec artifacts through the sanctioned `/self-review` channel. You author cited findings; the runtime validates, registers, and traces them. It never rewrites PRD or specs — remediation flows through the owning commands.

## When To Use

After `/specs` has produced `03_specs/prd.md` or `specs.md` (the command fails before that), when the BA wants an adversarial pass before handoff: claims without local evidence, PRD/specs drifting from the brief, or decisions taken implicitly that would be expensive to reverse.

## Workflow

1. Read the grounding set the runtime validates against: `02_requirements/project-brief.md`, `03_specs/prd.md`, `03_specs/specs.md`, `03_specs/units/SPEC-U-*.md`, and `08_context_packs/`.
2. Hunt for: statements with no cited basis, divergence between brief and PRD/specs, and hard-to-reverse decisions hiding as assumptions.
3. Write a JSON file (schema below) and run `python -m sentinel /self-review PROJECT_ID --source PATH`.
4. Report merged gap IDs, skipped duplicates, registered `DEC-*` ids, and the report paths (`03_specs/self_review/self_review_report.md` and `decision_register.md`).

## Input Schema

```json
{
  "gaps": [
    {
      "id": "GAP-SELFREVIEW-KPI-BASELINE",
      "lens": "business",
      "severity": "high",
      "question": "Which measured baseline supports the 30% reduction claim in the PRD?",
      "evidence": "reduce processing time by 30%",
      "description": "The PRD states a quantified outcome with no cited baseline or source."
    }
  ],
  "decisions": [
    {
      "id": "DEC-SELFREVIEW-SYNC-CONTRACT",
      "lens": "technical",
      "title": "Nightly batch treated as the authoritative invoice sync",
      "decision": "Specs assume the nightly batch contract; real-time sync is out of scope.",
      "risk": "high",
      "reversibility": "hard-to-reverse",
      "evidence": "The CRM emits invoice updates nightly",
      "consequence": "Real-time status expectations must be renegotiated if this holds."
    }
  ]
}
```

- `gaps[]` (optional): identical rules to `/annotate` — `evidence` must be a verbatim quote from the grounding set or the finding is rejected. Merged entries carry `origin: self-review` and flow through the normal gap lifecycle (new findings turn health `DIRTY`).
- `decisions[]` (optional): `id` must start with `DEC-`; `decision` and `evidence` (verbatim quote) are required; `risk` is `low | med | high`; `reversibility` is `easy | moderate | hard-to-reverse | irreversible`; `title`, `lens`, and `consequence` are optional. Registered as `DEC-*` nodes with status `pending_review` — visibility for the BA, never auto-approval.

## Rules

- Evidence or silence: every finding and decision quotes real local text. No quote, no entry.
- The runtime does not rewrite PRD/specs. When a finding is confirmed, remediate upstream and regenerate through the owning command (`/resolve-gaps`, `/specs`).
- The BA stays in control: decisions land `pending_review`; nothing is approved by the agent.
- Local-first: the review runs entirely against local artifacts; no network or external services.
