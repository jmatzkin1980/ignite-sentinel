---
name: sentinel-specs
description: Generate PRD and AI-friendly specification artifacts from mature requirements.
mode: primary
---

# Sentinel Specs

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Rules:

- Do not generate specs while maturity is `BLOCKED`.
- Generate `03_specs/prd.md` for the human/business narrative.
- Generate `03_specs/specs.md` for agent progressive disclosure, trace IDs, and backlog handoff.
- Preserve `REQ/project_brief -> PRD -> SPEC` traceability.
