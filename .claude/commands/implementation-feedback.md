---
description: Merge structured downstream implementation feedback into traced backlog feedback without rewriting stories directly.
argument-hint: PROJECT_ID --source PATH
---

# Ignite Implementation Feedback

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/implementation-feedback PROJECT_ID --source PATH
```

The `--source` file is JSON with `findings[]`. Each finding declares a `type` (`new-dependency`, `gap`, `ac-challenge`, or `surface-not-covered`), target `story`, optional `acceptance_criteria`, `summary`, `evidence`, optional `source_units`, optional `gap_id`, `blocks_dod`, and `mark_stale`.

Run from the repository root:

```powershell
python -m sentinel /implementation-feedback PROJECT_ID --source PATH
```

The runtime validates story and AC existence, requires evidence, archives the source under `07_changes/05_implementation_feedback/`, writes `feedback_report.md`, opens `GAP-FEEDBACK-*` records when applicable, creates `CHG` trace anchors linked to the story, may mark only affected stories `Stale`, and feeds DoD through `implementation_feedback_resolved`. It does not rewrite backlog scope directly. Summarize accepted/rejected finding IDs, stale stories, opened feedback gaps, and the report path.

Findings over the stories of a change (`change: CHG-NNN` in the story frontmatter) need no flag: the story knows its change. Their `source_units` must be units that change owns (those of the change and of its releases); any other unit, a project unit included, is refused with `source unit does not exist for CHG-NNN`, so a change-scoped finding never marks a project story `Stale`, and the report adds a `Change` column only when an accepted finding is on a change story.
