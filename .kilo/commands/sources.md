---
description: List the F-NN source registry and record who delivered a source and whether it still governs.
agent: sentinel-sync
---

# Ignite Sources

List or change the governed source registry. Parse `PROJECT_ID`, and `--id F-NN` with one change:

```text
/sources PROJECT_ID
/sources PROJECT_ID --id F-03 --from "Ops Lead"
/sources PROJECT_ID --id F-01 --superseded-by F-03
```

Run from the repository root:

```powershell
python -m sentinel /sources PROJECT_ID
python -m sentinel /sources PROJECT_ID --id F-NN [--from WHO] [--reason TEXT]
python -m sentinel /sources PROJECT_ID --id F-NN --superseded-by F-MM
python -m sentinel /sources PROJECT_ID --id F-NN --retire --reason TEXT [--replacement F-MM]
python -m sentinel /sources PROJECT_ID --id F-NN --expire YYYY-MM-DD [--topic TOPIC]
python -m sentinel /sources PROJECT_ID --id F-NN --current
python -m sentinel /sources PROJECT_ID --id F-NN --close
```

Each source content gets one `F-NN` row in `00_raw/source_manifest.json`, and the counter never restarts. `/ingest`, `/sync` and `/resolve-gaps` open the row when they start and close it when the cross finishes. The same content under a second path is the same row. A known path with new content opens a new row marked as a candidate new version: the registry never decides that the newest version governs. `07_changes/source_log.md` is the generated human render; never edit it by hand.

Validity is `current`, `superseded` (corrected by another row), `retired` (a dead source, with its replacement) or `expired` (by a cut-off date, optionally for one topic).

Report open rows and unconfirmed versions first: `/status` warns about both. Ask the BA which version governs before passing `--superseded-by` or `--current`; never choose for them.
