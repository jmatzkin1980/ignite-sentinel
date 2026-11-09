---
description: List the F-NN source registry, record who delivered a source and whether it still governs, close impact cells, settle precedence by scope and write the closing report.
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
python -m sentinel /sources PROJECT_ID --id F-NN --authority AUTHORITY
python -m sentinel /sources PROJECT_ID --id F-NN --cell DOCUMENT/SECTION --mark updated
python -m sentinel /sources PROJECT_ID --id F-NN --cell DOCUMENT/SECTION --mark reviewed --reason TEXT
python -m sentinel /sources PROJECT_ID --precedence SCOPE --between F-NN,F-MM
python -m sentinel /sources PROJECT_ID --report
```

Each source content gets one `F-NN` row in `00_raw/source_manifest.json`, and the counter never restarts. `/ingest`, `/sync` and `/resolve-gaps` open the row when they start and close it when the cross finishes. The same content under a second path is the same row. A known path with new content opens a new row marked as a candidate new version: the registry never decides that the newest version governs. `07_changes/source_log.md` is the generated human render; never edit it by hand.

Validity is `current`, `superseded` (corrected by another row), `retired` (a dead source, with its replacement) or `expired` (by a cut-off date, optionally for one topic).

Report open rows and unconfirmed versions first: `/status` warns about both. Ask the BA which version governs before passing `--superseded-by` or `--current`; never choose for them.

Each row also has an `authority` (minutes, API contract, prototype, example...) and an impact matrix: one cell per document and section the authority routes to, with what to look for there. Close each cell as `updated`, or as `reviewed` with the reason nothing changed. A retired source cascades to every document.

Precedence depends on the scope of the clash (business, scope, stack_to_be, behavior, api, compliance, legacy, design, rule). When no rule settles it the answer is `unresolved`: tell the BA, never pick the newest source. An own artifact is never an authority, and an example never closes a gap.

`--report` writes `07_changes/closing_report.md`: ADDED / MODIFIED / REMOVED per row, the cells each recipient must look at, and the originals ready to delete. It never deletes; deleting stays the BA's call.
