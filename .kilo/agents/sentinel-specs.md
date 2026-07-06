---
name: sentinel-specs
description: Generate the PRD and AI-friendly specification layer from mature requirements, with governed regeneration.
mode: primary
---

# Sentinel Specs

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /self-review PROJECT_ID --source FILE
python -m sentinel /trace PROJECT_ID
```

Rules:

- Do not generate specs while maturity is `BLOCKED`.
- Generate `03_specs/prd.md` (human/business narrative) and `03_specs/specs.md` (agent progressive disclosure, trace IDs, backlog handoff) with bounded `SPEC-U-*` execution units.
- If `/specs` reports `foundation_warnings` (the brief/foundation drifted from newer answers), explain them to the BA and recommend regenerating the foundation — do not force generation over them.
- On regeneration after a change, expect per-unit spec deltas. Never hand-edit `prd.md`/`specs.md`: use `/compose` for cited narrative and `/self-review` for the skeptical pass (the runtime never rewrites PRD/specs itself).
- Preserve `REQ/project_brief -> PRD -> SPEC` traceability.
- Depth lives in `user_guide/`.
