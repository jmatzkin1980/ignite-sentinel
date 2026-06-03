---
name: sentinel-backlog
description: Generate epics, user stories, and acceptance criteria from mature specs.
mode: primary
---

# Sentinel Backlog

Run:

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Rules:

- Generate value-oriented stories.
- Every story must trace to an epic/spec/requirement.
- Acceptance criteria must be testable.
