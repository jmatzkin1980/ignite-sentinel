---
description: Update governed backlog story lifecycle status and owner.
---

# Ignite Story Status

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--story US-NNN`, `--set STATE`, and optional `--owner NAME` from:

```text
/story-status PROJECT_ID --story US-001 --set Ready --owner "Team A"
```

Allowed states: `Draft`, `Ready`, `In Progress`, `In Review`, `Done`, `Blocked`, `Stale`. The runtime validates legal transitions, updates `state.json`, updates the story frontmatter, records traceability, and writes the command protocol log. Do not edit `US-NNN.md` or `state.json` by hand.

Run from the repository root:

```powershell
python -m sentinel /story-status PROJECT_ID --story US-NNN --set STATE --owner "NAME"
```

Summarize the previous status, new status, owner, story path, and change ID.
