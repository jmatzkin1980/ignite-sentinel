---
name: sentinel-assume
description: "Use when a BA needs to register governed, BA-owned assumptions in Ignite Sentinel through /assume: every assumption carries a human owner, risk (importance), uncertainty with a derived priority signal, an optional gap link, and a verbatim local evidence basis. Also for recording an assumption inside a change (/assume --change) and for validating or invalidating it later. Not for closing gaps with client answers (use sentinel-gap-response)."
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
- Every assumption needs a verbatim local quote as `justification`. In a change (`--change`) the quote is at least 4 words, never comes from an answer file saved by `/resolve-gaps`, and `GAP-SCOPE` cannot be closed with an assumption (confirm the border instead).
- `closes_gap` is provisional visibility only. It does not turn the gap into confirmed evidence, and it never unblocks a blocking gap: `/maturity` stays `BLOCKED` and `/next` says so. When the BA wants to move on without the client, tell them the exit: confirm the answer in their own name with `/resolve-gaps` (`Decision status: confirmed`, `Owner / source`: the BA); the assumption becomes `VALIDATED`.
- High-risk assumptions linked to gaps must be called out in the summary.
- `risk_category` is optional and separate from `lens` — a lens is whose evidence scope the assumption sits in; `risk_category` is which of Cagan's four product risks it is about: `value`, `usability`, `viability` (business viability), or `feasibility`. Do not conflate the two or try to derive one from the other. Old payloads without `risk_category` remain valid.

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
      "closes_gap": "GAP-TECH-DATA-SOURCE",
      "risk_category": "feasibility"
    }
  ]
}
```

The full contract lives in `sentinel/schemas/assumption.schema.json`. The quote in `justification` must appear verbatim in local evidence (`evidence` is accepted as an alias for `justification`). `risk_category`'s default set (`sentinel/risk_categories/*.json`) can be extended per project with additional categories via a directory override, the same molde as the `/challenge` technique registry — add JSON, not Python; the runtime rejects any value outside the declared set with the exact enum.

## Command

Run from the repository root:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /assume PROJECT_ID --source PATH
```

Report accepted assumption IDs, skipped duplicates, risk summary, linked gaps, `01_discovery/assumptions.md`, and refreshed `knowledge_state.md`. When any assumption carries a `risk_category`, `assumptions.md` groups its register by category (rows without one fall under "Uncategorized") and the development readiness matrix (`/maturity`) reports coverage per category alongside its existing per-lens coverage.

## Cheapest-Test Candidates (IMP-182)

When an assumption reaches the **test before advancing** signal (high risk × high uncertainty) and carries a local cited basis, the runtime proposes 1-3 **cited cheapest-test candidates** — the smallest experiment that would validate it — shaped by its Cagan `risk_category` (`value` → problem interview, `usability` → low-fi prototype, `viability` → business/stakeholder check, `feasibility` → timeboxed spike). They render as a `## Cheapest validation candidates` section in `01_discovery/assumptions.md` and as `cheapest_test_candidates` in `08_context_packs/assumptions_projection.json`.

These are the exact same contract as gap candidate options (IMP-113), mirrored for assumptions:

- **Cited or silent.** Every candidate cites the assumption's verbatim local basis. An assumption without a local basis quote gets **no candidates** — never invent an experiment to fill the space.
- **Never auto-validates.** Proposing a cheapest test does not move the assumption. Its status changes only through the existing channels: a gap response (`/resolve-gaps`), `/sync`, or an explicit BA decision. The candidate is a prompt for the BA, not a state transition.
- The candidates are suggestions for the BA to run outside the tool; do not treat "candidate proposed" as "assumption tested."

## Change assumptions (IMP-412)

In a change (`/assume PROJECT_ID --change CHG-NNN --source PATH`) the BA decides to go on without the answer, so the assumption **closes** the question: it stays `CLOSED` with closure `assumed` and note `supuesto ASM-…: a validar con <dominio>`, counted apart in `gap_counts.assumed`, until someone validates or invalidates it. Same item shape as above, with:

- `closes_gap`: an open question of that change (a question that does not exist, or is already closed, rejects the whole file; an assumption never replaces a decision).
- `justification`: a verbatim quote of a local source of the change, never of the assumptions register itself.
- `validate_with` (optional): who or what area validates it; default the owner.

Register it only when the BA said to proceed with the risk, and transcribe their words; never assume for them. The register is `01_discovery/CHG-nnn/assumptions.md` (the project's `assumptions.md` is not touched).

Life cycle, always with the BA's reason in their words:

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /assume PROJECT_ID --change CHG-NNN --id ASM-ID --validate --reason "TEXT"
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /assume PROJECT_ID --change CHG-NNN --id ASM-ID --invalidate --reason "TEXT"
```

Validating keeps the closure as an answer; invalidating opens the question again with its previous closure on record. An assumption is not a decision: it does not preload later questions and is not listed with the decisions.

## Formato

The example of `/assume --change`: one item per assumption; it is parsed by the real validator in the test suite (the Compras domain is made up):

```sentinel-example kind=change-assumptions
{
  "assumptions": [
    {
      "id": "ASM-HISTORIAL-PESTANA",
      "lens": "design",
      "statement": "El historial del auditor se muestra como una pestaña del detalle del alta.",
      "owner": "BA de Compras",
      "risk": "med",
      "justification": "quiero consultar quién aprobó cada alta y cuándo",
      "closes_gap": "GAP-SRD-3F9A1C07",
      "validate_with": "Diseño"
    }
  ]
}
```

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
