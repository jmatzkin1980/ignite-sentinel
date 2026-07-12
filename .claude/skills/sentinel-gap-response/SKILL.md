---
name: sentinel-gap-response
description: "Use when a client or domain owner returns answers to Ignite Sentinel discovery gaps: run /resolve-gaps, apply the governed closure rules (substantive + confirmed closes; vague or pending answers stay open), prefer EARS reformulations for functional gaps, report the knowledge metabolism the closure triggered, then re-check /maturity and /status. Trigger on 'the client answered', an answered gaps.md, or gap closure questions."
---

# Sentinel Gap Response

Use this skill after a client or domain owner returns an answered `gaps.md` or equivalent Markdown file.

## Workflow

1. Keep the response file under `input/interactions/` or `workspaces/PROJECT_ID/00_raw/05_interactions/` when possible.
2. Run:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

3. Review `workspaces/PROJECT_ID/07_changes/00_client_responses/*_gap_resolution_report.md`.
4. Review `workspaces/PROJECT_ID/01_discovery/gap_resolution_log.md`.
5. Summarize the `knowledge_metabolism` block of the result (see below).
6. Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

## Post-Response Metabolism (report it, do not just close gaps)

Every `/resolve-gaps` pass metabolizes the confirmed knowledge and returns a `knowledge_metabolism` block. Your summary must cover what actually moved, not only the closed/open counts:

- `validated_assumptions`: `ASM-*` rows whose linked gap closed with evidence flipped `ASSUMED` → `VALIDATED` in `01_discovery/assumptions.md`; each flip is also projected as a typed **promotion event** (`trigger_type: gap_closed`) in the knowledge ledger.
- `invalidated_assumptions`: assumptions contradicted by the response. The pre-change ledger unit is preserved in the append-only history with its supersessor (`superseded_units` — invalidate-not-delete); the promotion is revoked, never erased.
- `impacted_knowledge_units`: the ledger units the change touched; `knowledge_state.md`/`.json` and `01_discovery/development_readiness.json` are rebuilt (report `readiness_summary` movement).
- `downstream_stale_artifacts`: brief/PRD/specs/backlog artifacts now stale. The runtime records a `knowledge_staleness` marker in `state.json`; `/health` reports DIRTY until those artifacts are **regenerated via their governed commands** — never edited by hand.

## Candidate Options Never Close Gaps

`gaps.md` response sections can include "Cited candidate options (not selected)": options derived from local citations to make answering easier. They are elicitation aids — **an option is not an answer**. Never mark a gap closed because a candidate option looks right; the client/BA/owner must confirm an actual answer with decision status. Keep that framing when you present gaps or draft response requests.

The same contract holds for assumptions (IMP-182). A **test before advancing** assumption can carry "cited cheapest-validation candidates" in `01_discovery/assumptions.md` (and `cheapest_test_candidates` in `assumptions_projection.json`) — the smallest experiments that would validate it. A **candidate cheapest test is not a validation**: proposing one never moves the assumption. The assumption only flips `ASSUMED` → `VALIDATED`/`INVALIDATED` through the governed channels — this `/resolve-gaps` pass (via a closed linked gap, reported as `validated_assumptions` above), `/sync`, or an explicit BA decision. Present candidates as prompts for the BA to run, never as evidence that the assumption has been tested.

## Grill Mode: Guided Live Gap Closure (IMP-184)

Use grill mode when the BA wants to work the open gaps **live in chat** — one decision at a time — instead of sending the async `gaps.md` out and waiting. It is a conversational pattern with **no runtime of its own**: it only drafts the `/resolve-gaps` response file, and closure still happens through `/resolve-gaps`.

The name is from Rob Fitzgerald / Pocock "grilling": ask one question, wait for the answer, then follow the thread — because a wall of questions overwhelms and produces shallow answers.

### The loop

1. **Order the gaps.** Take the open gaps blocking-first. The interview script (`/export PROJECT_ID --artifact gaps --format interview`, IMP-183) already produces exactly this ordering grouped by lens — use it as your running agenda. Walk gap dependencies one at a time: if one gap's answer would reshape another, resolve the upstream one first.
2. **Present ONE gap.** For the current gap show, compactly: its cited context, the single question, the **cited candidate options** (IMP-113), and **one explicit recommendation** — "I'd go with Option A because `<local citation>`; confirm, pick another, or give your own answer." Never dump several gaps in one turn.
3. **Wait for the BA's decision.** Do not advance or assume. The recommendation is yours; the decision is the BA's. If the answer is vague (`TBD`, "depends"), note it and keep the gap open rather than forcing a close.
4. **Record the decision** into the response file using the exact `### GAP-ID` answer-block shape `/resolve-gaps` consumes — `Answer`, `Owner / source`, `Evidence or reference`, `Decision status` (Spanish labels in an `es` workspace). Keep the file under `input/interactions/` or `00_raw/05_interactions/`. One block per decided gap; nothing is closed yet.
5. **Repeat** for the next gap in dependency order, revisiting any gap the last answer reshaped.
6. **Only at the end, run `/resolve-gaps PROJECT_ID --source PATH`** once, then follow the normal Workflow above (report metabolism, re-check `/maturity` and `/status`). Closure, EARS normalization, and assumption promotion all happen there — never mid-loop.

### Non-negotiables

- **One gap per turn.** Batching questions is the anti-pattern this replaces.
- **You never close a gap.** Grill mode only drafts the response file; `/resolve-gaps` is the sole closing channel (all the closure rules below still apply — a vague answer stays open even if the BA is eager to move on).
- **Recommend, don't invent.** The options and the recommendation must come from the cited candidate options; a gap with no local evidence has no options, so ask the open question plainly instead of fabricating choices.

### Example (one turn)

> **GAP-DESIGN-STATES — UX States** (lens `design`, severity `medium`)
> Cited context: the input mentions "dashboard" but does not describe loading, empty, error, and recovery states.
> Question: what loading, empty, error, and recovery states must be handled?
> Cited candidate options:
> - Option A: apply the missing UX-states detail to the mentioned surface `dashboard`. Local citation: `dashboard`.
> - Option B: declare `dashboard` out of MVP scope and name the alternative or deferral. Local citation: `dashboard`.
> **My recommendation:** Option A — the dashboard is core to the stated goal, so its empty/error states are in scope. Confirm A, pick B, or give your own answer.

After the BA answers, append to the response file:

```markdown
### GAP-DESIGN-STATES
- Answer: Handle loading, empty (no queues at risk), error (metrics service down), and recovery states for the dashboard.
- Owner / source: Design Lead
- Evidence or reference: Live BA review 2026-07-11
- Decision status: confirmed
```

Then move to the next gap. Close everything with a single `/resolve-gaps` at the end.

## Rules

- Auto-close only applies when a `GAP-ID` block has a non-empty `Answer` or `Respuesta` and `Decision status` is `confirmed`, `not applicable`, `confirmado`, or `no aplica`.
- A non-empty answer with pending or unclear decision status becomes `PARTIALLY_CLOSED`.
- Do not rewrite client answers into confirmed seeds unless the response is structurally confirmed.
- New information that is not mapped to an existing gap should be handled as follow-up input with `/sync` or a new explicit gap.
- Preserve `CHG`, `SEED`, and `DEC` trace links created by the command.
- Gap closure nuances (IMP-010): a substantive answer with `pending` decision becomes `ANSWERED` (awaiting confirmation, still blocking when severe); a vague/deferred answer (`TBD`, `depende`, short non-answers) never closes a gap even if marked `confirmed` — it stays `PARTIALLY_CLOSED` with a `resolution_note` asking for specifics. Only substantive + confirmed/not-applicable closes. Explain these states to the user when summarizing /resolve-gaps.
- EARS guidance (IMP-047): for functional or business-rule gaps (`GAP-ACCEPTANCE`, `GAP-BUSINESS-RULES`, `GAP-PRD-FR-AC`), prefer an answer that includes a confirmed EARS statement (`When/If/While/Where/The system shall...` or Spanish variants). If the client answered in prose, do not rewrite it silently; propose a separate EARS reformulation for BA confirmation. The runtime normalizes only confirmed answers that already pass `classify_ears`; confirmed prose is marked `EARS-eligible, not normalized` and counted in `/status`.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Closing on a candidate option** — marking a gap closed because a cited option "looks right". → An option is not an answer; only a client/BA/owner confirmation with decision status closes a gap.
- **Treating a cheapest-test candidate as validation** — flipping an assumption because a validation experiment was proposed. → A proposed test is not evidence; the assumption flips only through a closed linked gap, `/sync`, or an explicit BA decision.
- **Batching questions** — sending or asking a wall of gaps at once. → In grill mode, one gap per turn: ask, wait, follow the thread.
- **Closing a vague answer** — accepting `TBD` / "depends" as `confirmed` because the BA is eager to move. → A vague answer stays `PARTIALLY_CLOSED` with a note asking for specifics, even if marked confirmed.
- **Silently rewriting client prose into a seed or EARS** — normalizing an answer the client did not confirm. → Propose a separate EARS reformulation for BA confirmation; the runtime normalizes only confirmed answers that already pass `classify_ears`.
- **Hand-editing stale downstream artifacts** — "fixing" a brief/PRD/spec flagged by `downstream_stale_artifacts`. → Regenerate each through its governed command; `/health` stays DIRTY until then.
