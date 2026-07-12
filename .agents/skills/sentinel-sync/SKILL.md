---
name: sentinel-sync
description: "Use when new information arrives after discovery — meeting notes, client mail, Slack, domain updates, HTML prototypes, late blockers — and must become traceable change instead of silent scope creep: /sync impact analysis and CHG nodes, autonomous detection of new or modified sources, /reindex and /retrieve for change context. Trigger on 'the client sent a change', new meeting minutes, modified domain context, or anything that may mutate requirements, specs or backlog."
---

# Sentinel Sync

Use this skill when new information may mutate existing requirements, specs, backlog, or decisions.

## Workflow

1. Run `python -m sentinel /sync PROJECT_ID` for autonomous detection of new or modified inputs.
   - Use `python -m sentinel /sync PROJECT_ID --source PATH --note "WHY_THIS_CHANGE_EXISTS"` only when the user wants one explicit file processed.
2. Review the generated impact report in `workspaces/PROJECT_ID/07_changes/`.
3. Use `python -m sentinel /retrieve PROJECT_ID --query "CHANGE_TOPIC" --workflow sync --write-pack` to build a context pack.
4. Regenerate the affected artifacts **through their owning commands** — the impact report's affected nodes and `/health` staleness findings are the to-do list: `/gaps`/`/resolve-gaps` for discovery movement, `/brief`, `/specs`, `/backlog`, `/quality` downstream. Never patch a generated artifact by hand; mutation flows only through the CLI.
5. Run `python -m sentinel /reindex PROJECT_ID`, then `python -m sentinel /health PROJECT_ID`.

The Sentinel command protocol records each sync in `workspaces/PROJECT_ID/06_traceability/command_protocol_log.md` and refreshes trace views after mutation.

## Interaction digest (opt-in sub-mode)

Unstructured interactions — meeting transcripts, mail threads, Slack — carry answers, decisions and contradictions buried in prose. `/sync PROJECT_ID --source PATH --digest` runs an **analysis layer on top of the normal sync**: it reads the change text and extracts, each quoted verbatim with a `source:line` citation, four classes of signal:

- **(a) candidate answers to open gaps** → a pre-filled `/resolve-gaps` response file (`*_gap_response_proposed.md`), every entry stamped `Decision status: PROPOSED`;
- **(b) decision candidates** (`DEC-*`) → proposed payloads for the decision channel;
- **(c) new gaps** detected in the change (raised into `gaps.md` with `origin: sync` by the normal scan; the digest lists them so it is one view of the impact);
- **(d) assumption-contradiction signals** → reused verbatim from the sync metabolism (`invalidated_assumptions` + associative candidates, IMP-125); the digest never re-detects.

Output: `07_changes/.../<source>_interaction_digest.md` plus the proposed response file when there are gap-answer candidates. Ingest→analyze→**impact**: the digest is the analyze step and stops there.

**Hard rule — the digest proposes and routes; it never applies.** Nothing it surfaces mutates governed state. Each impact still enters through its owning command with BA confirmation: `/resolve-gaps` for gap answers, `/self-review` for decisions, the assumptions flow for `ASM-*`. The pre-filled response file is deliberately non-applying — its `PROPOSED` status is not a closing status, so running `/resolve-gaps` over it as-is closes no gap. **Before confirming a gap answer, identify who said it**: a detected line can be a passing comment, not an answer from the gap's owner (cross-check against the stakeholder registry when it exists). An interaction with no signal produces an explicit empty digest, never invented content.

## Memory

- `/sync` creates a `CHG` node, indexes the change in local LanceDB memory, and links it to potentially impacted artifacts.
- Autonomous `/sync PROJECT_ID` uses `workspaces/PROJECT_ID/00_raw/source_manifest.json` to detect new and modified files by content hash.
- Use `/retrieve` with `--workflow sync` before regenerating requirements, backlog, acceptance criteria, or quality artifacts through their owning commands.
- Use filters when the task needs a domain-owned context:
  - `--domain technical`
  - `--domain design`
  - `--domain quality`
  - `--artifact-type change`

## Rules

- Treat new information as a change event, not a silent edit.
- Every change must create a `CHG` node and impact report.
- Do not mark downstream artifacts healthy until impact has been reviewed.
- If source files and memory disagree, trust source files and run `/reindex`.
- Assumption invalidation flows through the sync metabolism: `/sync` deterministically invalidates `ASM-*` rows the change contradicts (reported as `invalidated_assumptions`; the pre-change ledger unit is preserved, never deleted) and separately lists **associative impact candidates** suggested by meaning-based retrieval — those are for BA review only, nothing is auto-invalidated.
- New requirement-shaped statements detected in the change input merge into `gaps.md` as `OPEN` gaps with `origin: sync` and a `raised-by-sync` note pointing at the `CHG-*` id; previously closed gaps the change contradicts are reopened. Summarize both lists — they are the change's discovery debt.
- Regeneration visibility (IMP-011): when `/specs` or `/backlog` regenerate an existing artifact with different content, a human-readable diff record is written under `07_changes/04_regeneration/` (sections added/removed, line counts, triggering `CHG` id), traced in the graph as `regeneration_diff` with a `triggers_regeneration` edge and indexed in memory. Point the user to it when summarizing what changed after a sync. Since IMP-187 the record also carries a `Section Deltas` table using the closed `ADDED`/`MODIFIED`/`REMOVED` vocabulary (shared with the spec-unit and requirement-unit deltas), so a downstream coding agent can act on each affected section without diffing the whole file — an invalid marker can't be emitted (validated by construction).
