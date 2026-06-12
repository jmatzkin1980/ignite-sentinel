---
name: sentinel-challenge
description: Use when an Ignite Sentinel requirement is maturing and the agent should actively stress-test what is NOT being said — running pre-mortem, per-lens role-play, and assumption inversion to surface risks the client never stated. Produces the structured findings that `/challenge` validates and merges with `origin: challenge`, plus a versionable challenge_report.md.
---

# Sentinel Challenge

Use this skill to materialize "understanding what is not being said". `/annotate` captures gaps you read directly from the input; `/challenge` goes further — it applies deliberate elicitation techniques to imagine failures and invert assumptions, then routes the findings through the same governed validation as `/annotate`. You propose with evidence; the runtime validates and persists. You never edit artifacts by hand.

## When to use

After `/ingest` (and optionally `/annotate`), when the requirement is maturing and you want to pressure-test it before committing to a brief. This is the Ignite equivalent of an adversarial review, executed through the lens model — not as generic personas.

## Techniques (run per lens — invariant #1)

1. **Pre-mortem**: assume the project failed six months after launch. For each lens (business, product, quality, technical, compliance, delivery, design), ask "what did we fail to ask that caused this failure?".
2. **Role-play by lens**: step into the lens's adversarial role — operator, auditor, attacker, support agent, regulator — and ask what that role would need that the input never mentions.
3. **Assumption inversion**: list the implicit assumptions, invert each ("what if the opposite is true?"), and surface the gap the inversion exposes.

## Workflow

1. Read `workspaces/PROJECT_ID/00_raw/` and `01_discovery/gaps.md`.
2. Run the three techniques per lens. Keep findings grounded: each must tie to a verbatim quote from the raw input (evidence or explicit silence — invariant #3).
3. Write a JSON file (schema below). Run `python -m sentinel /challenge PROJECT_ID --source PATH`.
4. Report merged and skipped gap IDs and updated gap counts. The merged gaps flow through the normal `/resolve-gaps` → `/maturity` → gate lifecycle like any other gap, tagged `origin: challenge`, and a traced `01_discovery/challenge_report.md` is written.

## Input schema

```json
{
  "gaps": [
    {
      "id": "GAP-GOVERNANCE-CONSTRAINTS",
      "lens": "compliance",
      "severity": "high",
      "technique": "pre-mortem",
      "question": "Which audit-trail and data-retention obligations must the approval flow satisfy?",
      "evidence": "the solution must respect our compliance obligations",
      "description": "Compliance is named but no concrete obligation is specified."
    }
  ],
  "premortem": ["At 6 months an auditor rejected the trail because no retention window was ever defined."],
  "assumptions_inverted": ["Assumed approvals are internal-only; if an external delegate can approve, the whole access model changes."]
}
```

- `id`, `lens`, `severity`, `question`, `evidence`, `description`: identical rules to `/annotate`. Evidence must be a verbatim substring of the raw input or the whole challenge is rejected.
- `technique` (optional): `pre-mortem | role-play | assumption-inversion`, shown per gap in the challenge report.
- `premortem` / `assumptions_inverted` (optional): narrative captured in `challenge_report.md` for the BA.

## Rules

- Evidence or silence: every finding quotes real input text. No quote, no gap.
- Techniques run through the lens model, never as generic personas (invariant #1).
- Propose; do not decide. The runtime validates, tags `origin: challenge`, and merges. The BA stays in control (invariant #5).
- Duplicates already open in `gaps.md` are skipped and reported.
- Local-first: `/challenge` runs entirely on the local CLI. No network, no external services.
