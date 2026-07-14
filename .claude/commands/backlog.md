---
description: Generate traceable epics, user stories, and acceptance criteria.
---

# Ignite Backlog

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, optional `--with-task-seeds`, and optional `--story-format user|job` from:

```text
/backlog PROJECT_ID
/backlog PROJECT_ID --with-task-seeds
/backlog PROJECT_ID --story-format job
```

Run:

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /backlog PROJECT_ID --with-task-seeds
python -m sentinel /backlog PROJECT_ID --story-format job
```

Default mode generates epics, stories, acceptance criteria, implementation readiness, and slice plan with no task seeds. `--with-task-seeds` is opt-in and adds a per-story Task Seed Contract: ordered implementation intentions traced to AC and critical surfaces. These are not executed, estimated, assigned, scheduled, or managed by Ignite. `--story-format` selects how each story statement is phrased: `user` (default) keeps the persona-neutral user story ("As a target user, I want ... so that ..."), while `job` emits the JTBD-native job story ("When [situation], I want [motivation], so I can [outcome]") -- the natural shape when the input names no persona. It changes only the wording of the story statement; acceptance criteria, slicing, and traceability are unchanged, and a missing outcome stays `[PENDING INPUT]` rather than being invented. The format can also be set once via the `story_format` field in `sentinel.config.yaml`; the flag overrides the config. Summarize generated epic, story, acceptance criteria IDs, the story format used, and whether task seed contracts were enabled.
