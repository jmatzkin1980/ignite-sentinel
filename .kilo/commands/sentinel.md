---
description: Run any Ignite Sentinel CLI command from one generic Kilo workflow.
agent: sentinel-discovery
---

# Ignite Sentinel Generic Command

Use this as a fallback when a short slash command conflicts with the chat surface.

Parse the command after `/sentinel`, for example:

```text
/sentinel /init PROJECT_ID
/sentinel /maturity PROJECT_ID
/sentinel /sync PROJECT_ID --source PATH --note "NOTE"
```

Run from the repository root:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

If `python` is unavailable or resolves to an invalid Windows alias, use the repo-local launcher:

```powershell
.\installers\sentinel.ps1 /COMMAND PROJECT_ID [OPTIONS]
```

Sentinel applies preflight and postflight protocol guards automatically. Mutating commands refresh trace views and record `06_traceability/command_protocol_log.md`.

Summarize the result and generated artifact paths.
