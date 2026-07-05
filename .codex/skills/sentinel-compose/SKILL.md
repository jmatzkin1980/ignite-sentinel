---
name: sentinel-compose
description: "Use when proposing polished PRD narrative through the sanctioned /compose channel: agent-authored paragraphs grounded in verbatim local citations, validated by the runtime and merged as agent-origin blocks — never hand-edits to prd.md. Trigger on 'improve the PRD wording', narrative enrichment for a section, or a rejected composition block."
---

# Sentinel Compose

Use this skill to add agent-authored PRD narrative without editing `prd.md` by hand.

## Workflow

1. Confirm `python -m sentinel /specs PROJECT_ID` has generated `03_specs/prd.md`.
2. Read the target PRD section and identify source-of-truth evidence under `00_raw/`, `01_discovery/`, `02_requirements/`, or `07_changes/`.
3. Create a JSON draft with `blocks[]`; each block has `section` and `paragraphs[]`, and each paragraph has `text` plus verbatim `citations[]`.
4. Run `python -m sentinel /compose PROJECT_ID --source PATH`.
5. Report accepted and rejected block IDs, plus `03_specs/compositions/composition_report.md`.

## Draft Shape

```json
{
  "blocks": [
    {
      "section": "1",
      "paragraphs": [
        {
          "text": "Short human-facing narrative grounded in evidence.",
          "citations": ["verbatim quote from source evidence"]
        }
      ]
    }
  ]
}
```

## Rules

- The agent proposes; the runtime validates and persists.
- Do not edit generated PRD artifacts directly.
- Every citation must be a verbatim substring of local source-of-truth evidence.
- Do not compose narrative for a PRD section that still carries `[PENDING INPUT]`; resolve the feeding gap first.
- If a later regeneration invalidates a citation, Sentinel omits that block and reports it in `03_specs/compositions/regeneration_report.md`.
