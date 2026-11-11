---
name: sentinel-self-review
description: "Use when an Ignite Sentinel PRD or specs layer needs an adversarial pass before downstream handoff: author the cited skeptical findings and hard-to-reverse decisions that /self-review validates and registers under 03_specs/self_review/ — the runtime never rewrites PRD/specs. Trigger on 'review the PRD', 'review the specs', a skeptical pass over generated artifacts, or registering hard-to-reverse decisions. Not for discovery-stage scrutiny of raw input (use sentinel-scrutiny)."
---

# Sentinel Self-Review

Use this skill to run a skeptical, adversarial review over generated PRD/spec artifacts through the sanctioned `/self-review` channel. You author cited findings; the runtime validates, registers, and traces them. It never rewrites PRD or specs — remediation flows through the owning commands.

## When To Use

After `/specs` has produced `03_specs/prd.md` or `specs.md` (the command fails before that), when the BA wants an adversarial pass before handoff: claims without local evidence, PRD/specs drifting from the brief, or decisions taken implicitly that would be expensive to reverse.

## Workflow

1. Read the grounding set the runtime validates against: `02_requirements/project-brief.md`, `03_specs/prd.md`, `03_specs/specs.md`, `03_specs/units/SPEC-U-*.md`, and `08_context_packs/`.
2. Hunt for: statements with no cited basis, divergence between brief and PRD/specs, and hard-to-reverse decisions hiding as assumptions.
3. Write a JSON file (schema below) and run `sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /self-review PROJECT_ID --source PATH`.
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
      "consequences": [
        "Real-time status expectations must be renegotiated if this holds.",
        "Downstream specs may need rework if the CRM later exposes a streaming API."
      ],
      "considered_options": [
        { "option": "Real-time sync", "evidence": "The CRM emits invoice updates nightly" }
      ],
      "supersedes": "DEC-SELFREVIEW-SYNC-DRAFT"
    }
  ]
}
```

- `gaps[]` (optional): identical rules to `/annotate` — `evidence` must be a verbatim quote from the grounding set or the finding is rejected. Merged entries carry `origin: self-review` and flow through the normal gap lifecycle (new findings turn health `DIRTY`).
- `decisions[]` (optional): `id` must start with `DEC-`; `decision` and `evidence` (verbatim quote) are required; `risk` is `low | med | high`; `reversibility` is `easy | moderate | hard-to-reverse | irreversible`; `title` and `lens` are optional. Registered as `DEC-*` nodes with status `pending_review` — visibility for the BA, never auto-approval.
- ADR-grade optional fields (all backwards-compatible — an old payload without them still validates, no migration):
  - `consequences[]` (or legacy singular `consequence`): the trade-offs the decision accepts. **A decision with no stated trade-off is an ADR anti-pattern** — if nothing gets harder, it was not really a decision. Consequences are forward-looking, so they are *not* citation-bound.
  - `considered_options[]`: the alternatives that were on the table, each `{ "option": <label>, "evidence": <verbatim quote> }`. **Every option must be cited** (same verbatim rule as `evidence`) so the choice cannot be relitigated in a later "time-travel" debate; an uncited option is rejected.
  - `supersedes`: a prior `DEC-*` id this decision replaces. Decisions are **immutable** — never edit a registered `DEC-*`; emit a new one that supersedes it (coherente con invalidar-no-borrar). The superseded decision keeps its original register entry and archived source intact; only the back-reference is recorded.

## Sweep protocol (IMP-271)

Follow `sentinel/templates/agent_sweep_protocol.md`. The runtime rejects the whole payload when:

- an `absent` entry is not `AUSENTE: <what> en <where>`, or what it calls absent is in the source;
- `untouched` is not a list of sentences;
- `blocks` is not true or false;
- the payload carries figures (`counts`, `totals`, `summary`, `figures`, `stats`, `metrics`): the runtime counts and writes them in `01_discovery/agent_sweep_log.md`.

After the merge, ask the BA to record a disposition on each new gap: `/gaps PROJECT_ID --id GAP-X --disposition accepted|rejected|irrelevant [--reason TEXT]`.

## Rules

- Evidence or silence: every finding and decision quotes real local text. No quote, no entry.
- The runtime does not rewrite PRD/specs. When a finding is confirmed, remediate upstream and regenerate through the owning command (`/resolve-gaps`, `/specs`).
- The BA stays in control: decisions land `pending_review`; nothing is approved by the agent.
- Local-first: the review runs entirely against local artifacts; no network or external services.
- Immutability: never rewrite a registered `DEC-*` to change its meaning. When a decision changes, author a new one with `supersedes` pointing at the old id; the old entry stays intact.

## Y-Statement (optional short format)

When a full decision record is heavier than the moment warrants, capture the `decision` text as a one-line Y-statement — it forces the trade-off to the surface, which is the ADR discipline in miniature:

> In the context of **\<use case / scenario\>**, facing **\<concern\>**, we decided for **\<option\>** and against **\<alternatives\>**, to achieve **\<quality\>**, accepting **\<downside\>**.

The `and against <alternatives>` clause maps to `considered_options[]` and the `accepting <downside>` clause maps to `consequences[]`; fill those structured fields when you want them cited and traceable, or keep the Y-statement inline when a lightweight note is enough.

## Sufficiency Mode (IMP-259): "what is missing to start tomorrow?"

Run it on a brief v2, before or without a PRD. Use it as an independent pass, not as the author of the brief.

1. **Clean context.** Read only `02_requirements/project-brief.md` and the sources it cites (`07_changes/source_log.md`, `00_raw/`). Do not use the conversation, earlier reviews or your memory of the project.
2. **For every applicable place and every §9 item (`C-NN`)**, ask: could a builder start tomorrow with only this? Classify each:
   - **covered:** enough to start;
   - **missing:** say what text would resolve it (`would_resolve`), and only if that text is not already in the brief;
   - **ambiguous:** quote the vague words verbatim from that place;
   - **contradictory:** quote both places verbatim (`conflicts_with: {place, quote}`).
3. **Each non-covered obstacle carries one question** that the client or the domain can answer, ending with "?".
4. **Write the payload and run the command:**

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /self-review PROJECT_ID --sufficiency --source round1.json
```

5. **Report the result:** gaps opened (`GAP-SUF-*`), obstacles that extended an open gap, rejected obstacles with their reason, and the verdict. Repeat the round after answers arrive, until a round reports only covered places.

The runtime rejects a place that does not exist, a quote that is not verbatim, and a `would_resolve` the brief already says. Never edit the brief yourself.

## Crosses Mode (IMP-260b): do the lenses agree?

1. **Read the brief v2** and the rule catalog `sentinel/templates/semantic_crosses.json`.
2. **For each rule**, look for:
   - a **conflict**: two places that cannot both be true. Quote both verbatim, `a` on the rule's `from` side and `b` on its `to` side.
   - a **missing counterpart**: what `a` states needs something the brief never gives. Quote `a` and name `missing_in`.
3. **Write one `finding`** (what does not fit) and one `question` per cross.

```powershell
sh "${CLAUDE_PLUGIN_ROOT}/python.sh" "${CLAUDE_PLUGIN_ROOT}/launcher.py" /self-review PROJECT_ID --crosses --source crosses.json
```

4. **Report** the `GAP-XRV-*` gaps opened and the rejected crosses with their reason. Never edit the brief.

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
