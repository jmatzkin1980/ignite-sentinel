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

## Rules

- Auto-close only applies when a `GAP-ID` block has a non-empty `Answer` or `Respuesta` and `Decision status` is `confirmed`, `not applicable`, `confirmado`, or `no aplica`.
- A non-empty answer with pending or unclear decision status becomes `PARTIALLY_CLOSED`.
- Do not rewrite client answers into confirmed seeds unless the response is structurally confirmed.
- New information that is not mapped to an existing gap should be handled as follow-up input with `/sync` or a new explicit gap.
- Preserve `CHG`, `SEED`, and `DEC` trace links created by the command.
- Gap closure nuances (IMP-010): a substantive answer with `pending` decision becomes `ANSWERED` (awaiting confirmation, still blocking when severe); a vague/deferred answer (`TBD`, `depende`, short non-answers) never closes a gap even if marked `confirmed` — it stays `PARTIALLY_CLOSED` with a `resolution_note` asking for specifics. Only substantive + confirmed/not-applicable closes. Explain these states to the user when summarizing /resolve-gaps.
- EARS guidance (IMP-047): for functional or business-rule gaps (`GAP-ACCEPTANCE`, `GAP-BUSINESS-RULES`, `GAP-PRD-FR-AC`), prefer an answer that includes a confirmed EARS statement (`When/If/While/Where/The system shall...` or Spanish variants). If the client answered in prose, do not rewrite it silently; propose a separate EARS reformulation for BA confirmation. The runtime normalizes only confirmed answers that already pass `classify_ears`; confirmed prose is marked `EARS-eligible, not normalized` and counted in `/status`.
