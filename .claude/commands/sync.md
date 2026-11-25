---
description: Metabolize client responses, meetings, Slack/email content, or domain updates.
argument-hint: PROJECT_ID [OPTIONS]
---

# Ignite Sync

Arguments received from the user invocation: `$ARGUMENTS`

Parse the project ID, optional source path, and optional note from:

```text
/sync PROJECT_ID
/sync PROJECT_ID --source PATH --note "NOTE"
/sync PROJECT_ID --change CHG-NNN [--source PATH --role ROLE [--supersedes F-NN]] [--note "NOTE"]
```

Run:

```powershell
python -m sentinel /sync PROJECT_ID
python -m sentinel /sync PROJECT_ID --source PATH --note "NOTE"
python -m sentinel /sync PROJECT_ID --change CHG-NNN --source PATH --role pedido|linea_de_base|plan_previo|diseno_nuevo [--supersedes F-NN]
```

Without `--source`, Sentinel scans known input and workspace context folders, detects new or modified files by hash, processes each novelty as a `CHG` event, and indexes the result into local LanceDB memory. With `--source`, Sentinel processes only the specified file.

With `--change CHG-NNN`, Sentinel syncs one open change instead: it loads the new source by role (or scans the shared role folders for files not yet registered to another change), confirms whether it is a new version (`--supersedes F-NN` confirms it; without it the version stays a candidate until `/sources --id F-NN --superseded-by F-MM`), carries the claims that stay literal and marks what to re-read in `01_discovery/CHG-NNN/sync_report.md`. The project `/sync` is unchanged.

A change can invalidate prior assumptions: the ledger moves the affected `ASM-*` (invalidated_assumption, superseded) and raises `origin: sync` gaps, and impacted downstream artifacts are marked stale. The impact report also surfaces associative candidates worth reviewing. The command protocol records the sync anchor in `06_traceability/command_protocol_log.md` and refreshes trace views after the mutation.

Summarize the change ID, impacted artifacts, and newly detected gaps, then regenerate any affected downstream artifact through its owning command (never by hand). Pull a focused context pack first:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "change topic" --workflow sync --write-pack
```
