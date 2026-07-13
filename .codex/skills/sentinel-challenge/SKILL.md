---
name: sentinel-challenge
description: "Use when an Ignite Sentinel requirement is maturing and the agent should actively stress-test what is NOT being said — running the registry's elicitation techniques (pre-mortem, role-play, assumption inversion, JTBD forces, red/blue team, first principles, stakeholder round-robin) to surface risks the client never stated. Produces the structured findings that `/challenge` validates and merges with `origin: challenge`, plus a versionable challenge_report.md."
---

# Sentinel Challenge

Use this skill to materialize "understanding what is not being said". `/annotate` captures gaps you read directly from the input; `/challenge` goes further — it applies deliberate elicitation techniques to imagine failures and invert assumptions, then routes the findings through the same governed validation as `/annotate`. You propose with evidence; the runtime validates and persists. You never edit artifacts by hand.

## When to use

After `/ingest` (and optionally `/annotate`), when the requirement is maturing and you want to pressure-test it before committing to a brief. This is the Ignite equivalent of an adversarial review, executed through the lens model — not as generic personas.

## Techniques (run per lens — invariant #1)

The catalog is the runtime registry (`sentinel/techniques/*.json`); tag each finding with the technique id. Run the four **default** techniques on every pass; add the three **extended** ones when their trigger fits.

Default set:

1. **Pre-mortem** (`pre-mortem`): assume the project failed six months after launch. For each lens (business, product, quality, technical, compliance, delivery, design), ask "what did we fail to ask that caused this failure?". Then **classify each imagined failure mode** using the taxonomy below, so the BA knows where to spend scarce discovery effort.
2. **Role-play by lens** (`role-play`): step into the lens's adversarial role — operator, auditor, attacker, support agent, regulator — and ask what that role would need that the input never mentions.
3. **Assumption inversion** (`assumption-inversion`): list the implicit assumptions, invert each ("what if the opposite is true?"), and surface the gap the inversion exposes.
4. **JTBD Four Forces** (`jtbd-forces`): stress-test the requirement through the push of the current situation, the pull of the new solution, the anxiety about switching, and the habit/inertia holding the old behavior. **Anti-hypothetical guardrail:** anchor every force in a concrete past event, observed quote, or local evidence — a purely hypothetical preference question ("would you use X?") stays a narrative note and never merges as a gap.

Extended set (opt-in):

5. **Red/blue team** (`red-blue-team`): red-team the requirement for misuse, failure, ambiguity, and invalid success claims; blue-team the minimum evidence needed to defend it. Use for security-, audit-, or abuse-sensitive requirements.
6. **First principles** (`first-principles`): decompose the request into irreducible user, value, data, rule, interface, quality, and governance facts; flag facts that are implied but not evidenced. Use for novel or over-packaged requirements ("just like X but…").
7. **Stakeholder round-robin** (`stakeholder-round-robin`): rotate through likely stakeholders and ask what each would need to approve, operate, test, support, or audit the requirement. Use when many actors orbit the requirement but only one voice wrote it.

## Pre-mortem risk taxonomy (Tigers / Paper Tigers / Elephants)

The pre-mortem technique's imagined failure modes are not equally worth chasing. Classify each one so the pressure-test drives effort where it matters. The catalog is declarative — the labels and their meaning live in `sentinel/techniques/pre-mortem.json` (`risk_taxonomy`) and are echoed into `challenge_report.md`, so this list can never desync:

- **Tiger** — a real, dangerous risk: high likelihood and high impact, already visible in the evidence. **Hunt it**: raise the question that closes it and treat the underlying gap as `high`/`critical` severity.
- **Paper Tiger** — looks threatening but is low real risk once examined (low likelihood or low impact). **Note it and move on**: don't spend scarce discovery effort; keep any gap at `low`/`medium` severity.
- **Elephant** — a large, obvious risk that no one is naming (the elephant in the room); the failure mode is the silence itself. **Surface it explicitly** and force it into a decision or a gap; never let it stay unstated.

The taxonomy sets *severity and where to spend effort* — it does not relax the evidence contract: a Tiger still needs a verbatim quote (or explicit silence) to merge as a gap, exactly like any other finding.

## Respondent calibration (`respondent_profile`)

Technique prompts calibrate their wording to the declared profile of whoever will answer the questions: `business` (outcomes, policy, users, acceptance — no implementation jargon) or `technical` (data contracts, interfaces, constraints, failure modes).

- **How it is declared:** frontmatter `respondent_profile: technical` or `respondent_profile: business` in a domain context file under `workspaces/PROJECT_ID/00_raw/` context folders. The runtime honors only that explicit declaration; folder names, roles, titles, and free text are deliberately ignored. Aliases normalize (`negocio`/`domain` → business; `técnico`/`technology`/`engineering` → technical).
- **What it changes:** `/challenge` picks the profile up automatically and appends each technique's calibration line to its prompt in `challenge_report.md`. Validation rules do not change — evidence contracts stay identical.
- **What you do:** when the BA tells you who will answer (e.g. "the client's CTO"), suggest adding that frontmatter to the relevant context file (context files are domain-owned source input, so the BA adds it), and write your `question` fields in that register too.

## Workflow

1. Read `workspaces/PROJECT_ID/00_raw/` and `01_discovery/gaps.md`.
2. Run the default techniques per lens, plus any extended technique whose trigger fits. Keep findings grounded: each must tie to a verbatim quote from the raw input (evidence or explicit silence — invariant #3).
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
- `technique` (optional): any registry id — `pre-mortem | role-play | assumption-inversion | jtbd-forces | red-blue-team | first-principles | stakeholder-round-robin` — shown per gap in the challenge report.
- `premortem` / `assumptions_inverted` (optional): narrative captured in `challenge_report.md` for the BA.

## Rules

- Evidence or silence: every finding quotes real input text. No quote, no gap.
- Techniques run through the lens model, never as generic personas (invariant #1).
- Propose; do not decide. The runtime validates, tags `origin: challenge`, and merges. The BA stays in control (invariant #5).
- Duplicates already open in `gaps.md` are skipped and reported.
- Local-first: `/challenge` runs entirely on the local CLI. No network, no external services.

## Agentic Spirit (applies to every proposal you author)

- **Citation rejection loop:** when the runtime rejects a citation, never paraphrase the quote to make it pass. Re-read the source and shorten to the exact verbatim substring (typos included; never translate or normalize), or drop the finding. Evidence or silence applies to your proposals too.
- **Severity rubric** (when your payload carries `severity`): does it block understanding the scope? `critical`/`high`. Does it invalidate downstream decisions (brief, specs, backlog)? `high`. Is it a refinement the BA can safely defer? `medium`/`low`. Critical/high open gaps block maturity — assign severity for the lifecycle, not for emphasis.
- **Project language:** write client-facing text (`question` fields, narrative paragraphs) in the workspace's `project_language` (`sentinel.config.yaml`); citations always stay verbatim in their original language.
- **Focus first:** in large workspaces, run `/retrieve PROJECT_ID --query "TOPIC" --workflow WORKFLOW --write-pack` and work from the focus pack instead of reading all of `00_raw/` into context.
