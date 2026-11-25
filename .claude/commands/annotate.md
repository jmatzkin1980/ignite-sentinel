---
description: Merge an agentic semantic analysis of the raw input into discovery gaps (origin: agent).
argument-hint: PROJECT_ID --source PATH [--change CHG-NNN]
---

# Ignite Annotate

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/annotate PROJECT_ID --source PATH
/annotate PROJECT_ID --source PATH --change CHG-NNN
```

The `--source` file is JSON with the agent's structured semantic analysis of the raw input: a `gaps` array (each gap has `id`, `lens`, `severity`, `question`, and a verbatim `evidence` quote from the raw input), plus optional `ambiguities` and `assumptions`.

Run from the repository root:

```powershell
python -m sentinel /annotate PROJECT_ID --source PATH
python -m sentinel /annotate PROJECT_ID --source PATH --change CHG-NNN
```

The runtime validates each proposed gap (declared lens, severity range, and an evidence quote found verbatim in the raw input), tags them `origin: agent`, merges them into `01_discovery/gaps.md`, and records traceability. Summarize merged and skipped gap IDs plus updated gap counts.

With `--change CHG-NNN` (IMP-418) the evidence may quote the change's request, brief and baseline, the gaps open in that change (`01_discovery/CHG-NNN/gaps.md`) and the log is `01_discovery/CHG-NNN/agent_annotation_log.md`; the project's gaps and state are not touched. A workspace that only has changes refuses the project form.
