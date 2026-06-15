---
description: Generate a local read-only HTML portfolio dashboard for all Ignite workspaces.
agent: sentinel-health
---

# Ignite Dashboard

Run this command from the repository root:

```powershell
python -m sentinel /dashboard
```

Optional flags:

```powershell
python -m sentinel /dashboard --root .
python -m sentinel /dashboard --open
```

The runtime reads all `workspaces/*/state.json` snapshots except `_template`, reuses `/status` data per workspace, embeds local markdown artifacts into a self-contained `dashboard.html`, and never mutates project state. Summarize the generated path, workspace count, and the fact that the HTML is a local read-only snapshot ignored by git.
