---
description: Generate or refresh the Ignite traceability matrix and graph.
agent: sentinel-health
---

# Ignite Trace

Parse `PROJECT_ID`, and optional `--reviewed CHG-NNN` with `--reason TEXT`, from:

```text
/trace PROJECT_ID
/trace PROJECT_ID --reviewed CHG-005 --reason "Export cut checked with the Product Owner; stories unaffected."
```

Run:

```powershell
python -m sentinel /trace PROJECT_ID
```

Summarize graph and matrix locations.

`--reviewed CHG-NNN` records the BA review of the semantic change `/health` names ("Semantic change may invalidate downstream trace links for CHG-NNN"): the flagged trace links are marked reviewed and the finding clears. Use it only after reading the targets, when nothing downstream has to change; otherwise regenerate (`/brief`, `/specs`, `/backlog`), which clears it too. Report the change id, the links marked reviewed and the health verdict.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.
