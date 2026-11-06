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
python -m sentinel /dashboard --theme neutral
```

`--theme` takes a built-in theme name (only `neutral` ships in the repo) or the path to a local theme JSON; the default is `neutral`, in light and dark mode. The runtime reads all `workspaces/*/state.json` snapshots except `_template`, reuses `/status` data per workspace, embeds local markdown artifacts into a self-contained `dashboard.html`, and never mutates project state. The output is reproducible: it carries the source cut-off date and state.json fingerprints instead of a build time. Summarize the generated path, workspace count, theme, cut-off, and the fact that the HTML is a local read-only snapshot ignored by git.
