---
description: Generate traceable epics, user stories, and acceptance criteria.
argument-hint: PROJECT_ID [OPTIONS] [--release rN | --change CHG-NNN]
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

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

`--change CHG-NNN` (IMP-393) builds the stories of one change on the existing system: vertical slices by functionality and delta (IMP-416) from `03_specs/CHG-NNN/` (ADDED, MODIFIED or REMOVED; a slice above `story_size.max_units`, 5, is split with SPIDR; a REMOVED row over only not-implemented stories makes none), plus one enabler per new surface accepted from a cross-read and the slice plan `04_backlog/CHG-NNN/SLICE-PLAN.md`, under its own epic `EPIC-CHG-NNN`, written to `04_backlog/` with the change language. Each story carries the `source_units` it covers, and each `UNCHANGED` row of the change becomes a pass-to-pass acceptance criterion of every story, so the validation contract lists the behavior the change must preserve. It needs `/specs PROJECT_ID --change CHG-NNN` first; story ids are stable and never reused, `EPIC-001` and the project's own stories are not rewritten (only their status becomes `Stale`, or they gain the `modificada_por` frontmatter key, when a MODIFIED or REMOVED row affects them), `--with-task-seeds` is refused with `--change`, and `--release rN` with `--change` (IMP-429) builds the stories of one release of the change's confirmed series from the units `/specs --change --release rN` wrote: canonical `04_backlog/US-nnn.md`, with `04_backlog/CHG-nnn/rN/stories.md` (their ids linked to those files, never copies) and its `SLICE-PLAN.md` (the change's other releases keep their stories and ids; the stories of a plain backlog are reused, never duplicated). Once the series is confirmed, `--change` without `--release` is refused and names the release to derive. In a workspace that only holds changes, `/backlog PROJECT_ID` without the flag is refused with a pointer to `--change`.
