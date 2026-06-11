---
name: sentinel-sync
description: Use when Codex needs to ingest a client change, meeting note, stakeholder feedback, or internal refinement into Ignite Sentinel and calculate traceability impact before updating specs or backlog.
---

# Sentinel Sync

Use this skill when new information may mutate existing requirements, specs, backlog, or decisions.

## Workflow

1. Run `python -m sentinel /sync PROJECT_ID` for autonomous detection of new or modified inputs.
   - Use `python -m sentinel /sync PROJECT_ID --source PATH --note "WHY_THIS_CHANGE_EXISTS"` only when the user wants one explicit file processed.
2. Review the generated impact report in `workspaces/PROJECT_ID/07_changes/`.
3. Use `python -m sentinel /retrieve PROJECT_ID --query "CHANGE_TOPIC" --workflow sync --write-pack` to build a context pack.
4. Patch affected artifacts deliberately.
5. Run `python -m sentinel /reindex PROJECT_ID`, then `python -m sentinel /health PROJECT_ID`.

The Sentinel command protocol records each sync in `workspaces/PROJECT_ID/06_traceability/command_protocol_log.md` and refreshes trace views after mutation.

## Memory

- `/sync` creates a `CHG` node, indexes the change in local LanceDB memory, and links it to potentially impacted artifacts.
- Autonomous `/sync PROJECT_ID` uses `workspaces/PROJECT_ID/00_raw/source_manifest.json` to detect new and modified files by content hash.
- Use `/retrieve` with `--workflow sync` before patching requirements, backlog, acceptance criteria, or quality artifacts.
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
- Regeneration visibility (IMP-011): when `/specs` or `/backlog` regenerate an existing artifact with different content, a human-readable diff record is written under `07_changes/04_regeneration/` (sections added/removed, line counts, triggering `CHG` id), traced in the graph as `regeneration_diff` with a `triggers_regeneration` edge and indexed in memory. Point the user to it when summarizing what changed after a sync.
