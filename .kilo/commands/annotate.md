---
description: Merge an agentic semantic analysis of the raw input into discovery gaps (origin: agent).
agent: sentinel-discovery
---

# Ignite Annotate

Parse `PROJECT_ID` and `--source PATH` from:

```text
/annotate PROJECT_ID --source PATH
```

The `--source` file is JSON with the agent's structured semantic analysis of the raw input: a `gaps` array (each gap has `id`, `lens`, `severity`, `question`, and a verbatim `evidence` quote from the raw input), plus optional `ambiguities` and `assumptions`.

Run from the repository root:

```powershell
python -m sentinel /annotate PROJECT_ID --source PATH
```

The runtime validates each proposed gap (declared lens, severity range, and an evidence quote found verbatim in the raw input), tags them `origin: agent`, merges them into `01_discovery/gaps.md`, and records traceability. Summarize merged and skipped gap IDs plus updated gap counts.
