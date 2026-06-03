---
name: sentinel-sync
description: Use when Codex needs to ingest a client change, meeting note, stakeholder feedback, or internal refinement into Ignite Sentinel and calculate traceability impact before updating specs or backlog.
---

# Sentinel Sync

Use this skill when new information may mutate existing requirements, specs, backlog, or decisions.

## Workflow

1. Run `python -m sentinel sync PROJECT_ID --source PATH --note "WHY_THIS_CHANGE_EXISTS"`.
2. Review the generated impact report in `workspaces/PROJECT_ID/07_changes/`.
3. Use `python -m sentinel retrieve PROJECT_ID --query "CHANGE_TOPIC" --workflow sync --write-pack` to build a context pack.
4. Patch affected artifacts deliberately.
5. Run `python -m sentinel reindex PROJECT_ID`, then `python -m sentinel health PROJECT_ID`.

## Rules

- Treat new information as a change event, not a silent edit.
- Every change must create a `CHG` node and impact report.
- Do not mark downstream artifacts healthy until impact has been reviewed.
