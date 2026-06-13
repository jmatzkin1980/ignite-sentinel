---
description: Update governed backlog story lifecycle status and owner.
---

# Ignite Story Status

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--story US-NNN`, `--set STATE`, optional `--owner NAME`, and optional local `--evidence PATH` from:

```text
/story-status PROJECT_ID --story US-001 --set Done --owner "Team A" --evidence evidence.md
```

Allowed states: `Draft`, `Ready`, `In Progress`, `In Review`, `Done`, `Blocked`, `Stale`. The runtime validates legal transitions, evaluates DoR/DoD gates, updates `state.json`, updates the story frontmatter/checklists, records traceability, and writes the command protocol log. `backlog_gate.strict` is opt-in; default mode warns about missing DoR/DoD items without blocking. Use `--evidence` to attach traced downstream acceptance evidence before `Done`. Do not edit `US-NNN.md` or `state.json` by hand.

Run from the repository root:

```powershell
python -m sentinel /story-status PROJECT_ID --story US-NNN --set STATE --owner "NAME" [--evidence PATH]
```

Summarize the previous status, new status, owner, DoR/DoD warnings, evidence path when present, story path, and change ID.
