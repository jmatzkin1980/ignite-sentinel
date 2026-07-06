---
name: sentinel-maturity
description: Evaluate whether a requirement is mature enough to generate specs or backlog, and read the development readiness matrix.
mode: primary
---

# Sentinel Maturity

Run:

```powershell
python -m sentinel /maturity PROJECT_ID
```

Read:

```text
workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md
```

Rules:

- If readiness is `BLOCKED`, stop downstream generation and route the gap to the right channel; ask for missing information instead of filling it speculatively.
- Read the report metrics (gap closure rate, maturity score, trend, requirement quality) and the `development_readiness.json` matrix (16 areas as CONFIRMED / ASSUMED / OPEN) to recommend the right remediation per case.
- `sentinel.config.yaml` holds the maturity gate configuration.
- Depth lives in `user_guide/`.
