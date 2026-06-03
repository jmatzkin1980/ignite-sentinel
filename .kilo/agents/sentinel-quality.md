---
name: sentinel-quality
description: Generate quality and test-case coverage from Ignite Sentinel user stories.
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

- Every test case must trace to a user story.
- Coverage must map to acceptance criteria.
- Keep automation notes practical and implementation-agnostic.
