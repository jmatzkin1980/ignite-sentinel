---
name: sentinel-intake-triage
description: "Use before /init when facing a pile of unstructured initial intake — client requests, RFQs, mails, chat threads — that has not yet become one or more projects: group the pile by theme with a verbatim citation to each source, propose requirement candidates and whether it is one project or several, flag what is noise or out of scope, and hand the BA a decision. Trigger on 'triage these requests', a stack of initial asks, or deciding how many projects a pile of intake should become."
---

# Sentinel Intake Triage

Use this skill **before `/init`**, when you are handed a pile of unstructured initial intake — a stack of client requests, an RFQ inbox, a thread of mails or chat messages — and it is not yet clear how many Ignite projects it should become. It turns that pile into a **cited, BA-reviewable triage proposal**. It never creates a workspace itself.

## When to use / when not

- **Use** before any workspace exists: the input is raw intake and the question is "is this one project or several, and what is even in scope?".
- **Do not use** once a project exists. After `/init`, new information flows through `/ingest` (fresh evidence) or `/sync` (changes) — see `sentinel-discovery` and `sentinel-sync`. This skill is strictly the pre-project step.

## Workflow

1. **Enumerate the pile.** List every source item and assign each a short local id (`R1`, `R2`, …) so every downstream claim can point back to it. Keep the ids stable — they carry the citation into `/ingest`.
2. **Group by theme — with citations.** Cluster the items by the need they express. Every theme must quote the source item(s) it comes from verbatim (`R2: "..."`). A theme with no citing source is not proposed (cite-or-silent): you never invent a theme the pile does not support.
3. **Propose requirement candidates.** For each theme, write a one-line candidate requirement, each still cited to its source. These are *proposals*, not confirmed requirements.
4. **Propose the project shape.** Recommend whether the pile is **one project or N**, grounded in the themes: cohesive themes → one project; clearly separable value streams with different owners/systems → a split. State the rationale and mark cross-cutting items. This is a recommendation; the **BA decides**.
5. **Flag noise and out-of-scope — explicitly.** Duplicates, off-topic items, and asks that are clearly out of scope are listed with their citation and a one-line reason. Never drop an item silently.
6. **Hand the BA a decision.** Present the triage as a proposal table (themes → candidate → source citations → proposed project; plus an out-of-scope list). Stop there. The skill does not run `/init`.
7. **Only after the BA confirms the split**, execute per chosen project: `/init PROJECT_ID`, then `/ingest PROJECT_ID --source PATH` routing each source item to the project it was assigned, so the `R#` citations become governed discovery evidence.

## Output

A **triage proposal** rendered inline (or as a local scratch note), not a governed artifact. This is deliberate (IMP-193 spike): the triage is skill-only. If the *same* pile has to be re-triaged repeatedly, that is the signal to revisit whether a versionable triage artifact is warranted — do not create one pre-emptively.

## Rules

- **Cite-or-silent.** Every theme, every candidate, every out-of-scope call quotes the source item it rests on. No invented themes, requirements, or exclusions.
- **Propose, never decide.** The skill groups and recommends; the BA owns the project-boundary decision. Nothing mutates a workspace until the BA confirms and `/init` runs.
- **No workspace mutation.** This runs before any workspace exists — it does not touch `state.json`, gaps, decisions, or memory.
- **Preserve traceability from day zero.** Keep the `R#` ids so `/ingest` carries each source citation forward into governed discovery.
- **Privacy, local-first.** The intake pile stays on the machine; nothing is sent to an external service. See `sentinel-privacy-local-first`.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Inventing a theme with no source** — proposing a need the pile never states. → Cite-or-silent: a theme exists only if a source item is quoted for it.
- **Auto-running `/init`** — creating workspaces before the BA decides the split. → The skill proposes the shape; the BA decides, then `/init` runs.
- **Silently dropping an item** — discarding an ask as "noise" without a trace. → Every out-of-scope/duplicate item is listed with its citation and reason.
- **Losing the source link** — triaging into projects but forgetting which request fed which. → Keep the `R#` ids and route them through `/ingest` so the citation survives.
