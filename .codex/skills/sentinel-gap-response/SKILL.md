---
name: sentinel-gap-response
description: Use when Codex needs to process client or domain answers to Ignite Sentinel discovery gaps and safely close confirmed structured gaps.
---

# Sentinel Gap Response

Use this skill after a client or domain owner returns an answered `gaps.md` or equivalent Markdown file.

## Workflow

1. Keep the response file under `input/interactions/` or `workspaces/PROJECT_ID/00_raw/05_interactions/` when possible.
2. Run:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

3. Review `workspaces/PROJECT_ID/07_changes/00_client_responses/*_gap_resolution_report.md`.
4. Review `workspaces/PROJECT_ID/01_discovery/gap_resolution_log.md`.
5. Run:

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

## Rules

- Auto-close only applies when a `GAP-ID` block has a non-empty `Answer` or `Respuesta` and `Decision status` is `confirmed`, `not applicable`, `confirmado`, or `no aplica`.
- A non-empty answer with pending or unclear decision status becomes `PARTIALLY_CLOSED`.
- Do not rewrite client answers into confirmed seeds unless the response is structurally confirmed.
- New information that is not mapped to an existing gap should be handled as follow-up input with `/sync` or a new explicit gap.
- Preserve `CHG`, `SEED`, and `DEC` trace links created by the command.
