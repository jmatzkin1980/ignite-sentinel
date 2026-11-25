---
description: Generate the PRD and AI-friendly specification when maturity allows it.
argument-hint: PROJECT_ID [--release rN | --change CHG-NNN]
---

# Ignite Specs

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` from:

```text
/specs PROJECT_ID
```

Run:

```powershell
python -m sentinel /specs PROJECT_ID
```

If maturity is blocked, report the blocker instead of forcing generation.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

`--change CHG-NNN` (IMP-388) builds spec units only from that change's `REQ-EARS` rows (ADDED, MODIFIED, REMOVED) into `03_specs/CHG-NNN/`. It needs the change brief (`/brief PROJECT_ID --change CHG-NNN`) and no blocking gap open; it writes `specs.md` by functionality (IMP-416: one `FUN-nn` section per functionality with eight blocks of registered data and a traceability table), the units with the line citation of their element, and `prd.md` when the final brief is exported; it does not combine with `--release`.
