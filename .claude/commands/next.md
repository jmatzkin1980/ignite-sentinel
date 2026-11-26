---
description: Show only the next step, exactly as /status gives it.
argument-hint: PROJECT_ID [--release rN | --change CHG-NNN]
---

# Ignite Next

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/next PROJECT_ID
```

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

Run from the repository root:

```powershell
python -m sentinel /next PROJECT_ID
```

It prints the next step and nothing else: `key`, `title`, `text` and the `command` to run. It is the same decision as `next_action` in `/status`, so the two never disagree. Read-only.

`--change CHG-NNN` (IMP-396) gives the next step of that change alone: `scope`, `lenses`, `brief`, `requirements`, `specs`, `backlog`, `validate` or `done`, each with its command and the change's escalation `warnings`; it never suggests the PRD. In a workspace with changes the output also carries `changes` (per change: `next_step` and `warnings`); a workspace that holds only changes gives the first pending change step, never `/ingest`. With a confirmed series (IMP-429) `specs`, `backlog` and `done` name the release: `/specs P --change CHG --release rN`, `/backlog P --change CHG --release rN`, then `/split P --change CHG --close rN` once its stories are derived; each open release in order, a closed one never again, and the `done` of the change when all are closed. Without `--change` nothing else changes.

On the project (IMP-420) a request that writes rules, criteria, stories or decisions with an id (RN-, CA-, HU-, PD-; a section titled Acceptance criteria or a loose mention does not count) adds six steps after `resolve_blocking` while the project has no specs yet and its brief is v2 (a project at specs, backlog or quality, or on the brief v1, keeps its step unless an inventory or a cross-read exists), with or without a compiled brief: `crosses` (`/cross PROJECT_ID`), `extract_inventory`, `extract_proposals`, `extract_confirm` (a flagged proposal is confirmed with `--confirm-item`), `extract_orphans` and `extract_verify` (`/extract PROJECT_ID`, without `--change`); a brief compiled before the extraction gives `brief` again. A request without ids sees none of them.

Say the step in one line and offer the command. For why the project is or is not ready, use `/status`.
