---
description: List the F-NN source registry, record who delivered a source and whether it still governs, close impact cells, settle precedence by scope and write the closing report.
argument-hint: PROJECT_ID [--id F-NN OPTIONS | --precedence SCOPE --between F-NN,F-NN | --report]
---

# Ignite Sources

Arguments received from the user invocation: `$ARGUMENTS`

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
python -m sentinel /sources PROJECT_ID --change CHG-NNN --keep-single --reason TEXT
python -m sentinel /sources PROJECT_ID --load PATH --role diseno_nuevo --change CHG-NNN --derived-from F-NN
```

Each source content gets one `F-NN` row in `00_raw/source_manifest.json`, and the counter never restarts. `/ingest`, `/sync` and `/resolve-gaps` open the row when they start and close it when the cross finishes. The same content under a second path is the same row. A known path with new content opens a new row marked as a candidate new version: the registry never decides that the newest version governs. `07_changes/source_log.md` is the generated human render; never edit it by hand.

Confirming a version of a change source (`--superseded-by`, or `--current` on a candidate) also runs the touched set of that change (IMP-418): the claims of the cross-reads whose quote stays literal are carried with their questions and answers, what to read again is marked, `01_discovery/CHG-NNN/sync_report.md` is written and the result lists it under `sync` with the commands (`/cross ... --delta`). `/next --change` names a version nobody confirmed once.

`--derived-from F-NN` (only with `--load ... --role diseno_nuevo`) records that the loaded file is a readable copy derived from the original prototype `F-NN` (for example a transcript of a prototype whose screens are built by script): citations are checked literally against the copy and every place that shows the citation also shows its origin. The origin must be a current `diseno_nuevo` source of the same change (or project); the derived row is never a candidate version of its origin.

Validity is `current`, `superseded` (corrected by another row), `retired` (a dead source, with its replacement) or `expired` (by a cut-off date, optionally for one topic).

`--keep-single --reason` records the BA's decision that a change with escalation warnings stays one change: the covered warnings become one decided notice, and a new trigger still warns. Never decide it for the BA.

Report open rows and unconfirmed versions first: `/status` warns about both. Ask the BA which version governs before passing `--superseded-by` or `--current`; never choose for them.

Each row also has an `authority` (minutes, API contract, prototype, example...) and an impact matrix: one cell per document and section the authority routes to, with what to look for there. Close each cell as `updated`, or as `reviewed` with the reason nothing changed. A retired source cascades to every document.

Precedence depends on the scope of the clash (business, scope, stack_to_be, behavior, api, compliance, legacy, design, rule). When no rule settles it the answer is `unresolved`: tell the BA, never pick the newest source. An own artifact is never an authority, and an example never closes a gap.

`--report` writes `07_changes/closing_report.md`: ADDED / MODIFIED / REMOVED per row, the cells each recipient must look at, and the originals ready to delete. It never deletes; deleting stays the BA's call.
