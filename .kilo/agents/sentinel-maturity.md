---
name: sentinel-maturity
description: Evaluate whether a requirement is mature enough for AI-friendly specs and backlog generation.
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

- If readiness is `BLOCKED`, stop downstream generation.
- Use `sentinel.config.yaml` as the maturity gate configuration.
- Ask for missing information instead of filling it speculatively.
