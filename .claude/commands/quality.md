---
description: Generate initial quality and test-case coverage from the backlog.
argument-hint: PROJECT_ID [OPTIONS] [--release rN] [--change CHG-NNN]
---

# Ignite Quality

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and optional `--override PATH` from:

```text
/quality PROJECT_ID
/quality PROJECT_ID --override PATH
/quality PROJECT_ID --change CHG-NNN
```

Run:

```powershell
python -m sentinel /quality PROJECT_ID
python -m sentinel /quality PROJECT_ID --override PATH
python -m sentinel /quality PROJECT_ID --change CHG-NNN
```

The runtime generates `05_quality/backlog_readiness_audit.md`, returns the audit verdict (`PASS` / `PARTIAL` / `ATTENTION`), and keeps per-story quality plus INVEST findings. If BA/Product intentionally proceeds below `PASS`, `--override PATH` accepts a JSON object with cited `decisions[]` in `DEC-*` shape and records the human rationale under `06_traceability/gate_overrides/` without changing the audit verdict. Summarize the verdict, generated test cases, coverage notes, and any override report/register paths.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

`--change CHG-NNN` (IMP-431) audits only that change's stories (the backlog of the change must be current; with a confirmed series, the stories of every derived release) into `05_quality/CHG-NNN/`, in the change's language, with its own verdict kept in the change record; the project's state and its `/quality` output are not touched. It does not combine with `--release`. A workspace that only has changes refuses the project form.
