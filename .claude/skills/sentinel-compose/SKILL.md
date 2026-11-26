---
name: sentinel-compose
description: "Use when proposing polished PRD narrative through the sanctioned /compose channel: agent-authored paragraphs grounded in verbatim local citations, validated by the runtime and merged as agent-origin blocks — never hand-edits to prd.md. Trigger on 'improve the PRD wording', narrative enrichment for a section, or a rejected composition block. Not for generating the PRD itself (use sentinel-specs) or an adversarial review of it (use sentinel-self-review)."
---

# Sentinel Compose

Use this skill to add agent-authored PRD narrative without editing `prd.md` by hand.

## Workflow

1. Confirm `python -m sentinel /specs PROJECT_ID` has generated `03_specs/prd.md`.
2. Read the target PRD section and identify source-of-truth evidence under `00_raw/`, `01_discovery/`, `02_requirements/`, or `07_changes/`.
3. Create a JSON draft with `blocks[]`; each block has `section` and `paragraphs[]`, and each paragraph has `text` plus verbatim `citations[]`.
4. Run `python -m sentinel /compose PROJECT_ID --source PATH`.
5. Report accepted and rejected block IDs, plus `03_specs/compositions/composition_report.md`. If no block is accepted the command exits 3, changes nothing but the report, and its message lists why each block was refused: fix them and submit again.

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

## Change (`--change CHG-NNN`)

When the BA is working on one change (a request that modifies a system that already exists), compose the PRD of that change. In chat: "compose the PRD of this change". Behind it, run `python -m sentinel /compose PROJECT_ID --source PATH --change CHG-NNN`, after `/specs --change` has written `03_specs/CHG-NNN/prd.md`.

- The sections are those of `03_specs/CHG-NNN/prd.md`. A citation is a verbatim line of the change's own text: its request, brief, specs and units. The project's raw input is not part of it.
- The accepted blocks live in `03_specs/CHG-NNN/compositions/` and `/specs --change` writes them back into the PRD each time it regenerates it; a block whose citation no longer holds is left out and listed in `regeneration_report.md`.
- `/compose PROJECT_ID` without `--change` is the project's PRD and does not touch the change's. A workspace that only has changes refuses the form without `--change` and names the one to use. `--release` is not accepted.

## Formato

The example of `/compose --change`: it is parsed by the real validator in the test suite, against the sections of a PRD and the request of a made-up Compras change (guardar borrador en el alta de proveedores):

```sentinel-example kind=compose-blocks lang=es
{
  "blocks": [
    {
      "section": "1",
      "paragraphs": [
        {
          "text": "El alta normal del proveedor no cambia: el borrador es un camino aparte.",
          "citations": ["El envío normal del formulario tiene que seguir funcionando como hoy"]
        }
      ]
    }
  ]
}
```

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
