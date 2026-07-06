---
name: sentinel-quality
description: Generate quality and test-case coverage from Ignite Sentinel user stories and audit backlog readiness.
mode: primary
---

# Sentinel Quality

Run:

```powershell
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Rules:

- Requires existing user stories; if none exist, report the blocker rather than inventing coverage.
- Every test case traces to a user story and its acceptance criteria (US -> TC).
- `/quality` also runs the dynamic backlog readiness audit and INVEST/SPIDR/Lawrence story scoring; surface DoR warnings from `story_gates` instead of silently overriding them (an override needs a cited `DEC-*`).
- Keep automation notes practical and implementation-agnostic; never hand-edit generated quality artifacts.
- Depth lives in `user_guide/`.
