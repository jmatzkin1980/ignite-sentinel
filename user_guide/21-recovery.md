# When something went wrong

This page is for the moment after a mistake: a wrong file went in, a wrong answer was applied, someone edited a file by hand, a file is gone, or a command refused. Each case says what happened, what to run, and what to check. The rule behind all of them is the same: fix the cause through the command that owns it, never by patching a generated file.

Examples use the project `ACME_PORTAL`. Commands are written in chat form; in a terminal, prefix them with `python -m sentinel`.

## A wrong file was ingested

**If it was the first file (`/ingest`)** and it is not the client requirement you meant, replace the primary requirement on purpose:

```text
/ingest ACME_PORTAL --source input/the-right-request.md --replace
```

Gaps are rebuilt from the new file, so answered gaps open again. The result lists the saved answer files under `07_changes/00_client_responses/`; re-apply them with `/resolve-gaps`.

**If it came in later (`/sync`, or any other source)**, retire its source row so it stops governing:

```text
/sources ACME_PORTAL
/sources ACME_PORTAL --id F-04 --retire --reason "wrong file, loaded by mistake"
```

Use `--replacement F-NN` when another row takes its place. Retiring does not delete any file:

- The copy under `00_raw/` or `07_changes/` stays on disk for audit, but its text leaves the local memory. `/retrieve` and context packs stop returning it, and `/reindex` (with or without `--full`) skips it. The result lists the memory ids removed in `memory_removed`. If you retired the wrong row, `/sources ACME_PORTAL --id F-04 --current` brings it back, then run `/reindex ACME_PORTAL`.
- Sentinel's own reports about the file (its impact report, for example) stay in memory: they record what happened.
- A retired source reaches every document: its row gets a `pending` impact cell for each one. Review each cell and close it with `/sources ACME_PORTAL --id F-04 --cell DOCUMENT/SECTION --mark reviewed --reason "..."` (or `updated` after you regenerated it).
- Gaps the wrong file opened stay in `gaps.md`. Decide them with the BA. For a gap an agent raised, record `/gaps ACME_PORTAL --id GAP-X --disposition irrelevant --reason "came from a retired source"`.

**Check:** `/sources ACME_PORTAL` shows the row as retired; `/retrieve` on a phrase from the wrong file no longer returns it; `/status ACME_PORTAL` no longer warns about its open cells once they are closed.

## A wrong answer was applied

`/resolve-gaps` closed a gap with an answer that turned out to be wrong (a wrong value, a misunderstanding, an answer meant for another gap). Do not edit `gaps.md`. Reopen the gap through the same channel, with a response file that holds a block for it:

```markdown
### GAP-PAYMENT-LIMITS
- Answer: The limit we confirmed was for another product.
- Owner / source: Client PM
- Evidence or reference: email of 2026-05-12
- Decision status: pending
- Closure reason: reopened_false_premise
```

```text
/resolve-gaps ACME_PORTAL --source input/interactions/reopen-payment-limits.md
/maturity ACME_PORTAL
```

The gap goes back to `OPEN`, and the earlier closure stays on record in its resolution note. Ask the question again and apply the right answer in the next round. In a Spanish workspace the label is `Motivo de cierre`.

**Check:** the gap is `OPEN` in `gaps.md`; `/status ACME_PORTAL` names it again if it blocks.

## Someone edited a generated file by hand

Generated files (the gaps, the requirements, the brief, specs, backlog) change only through commands. A hand edit is never absorbed in silence:

- Before a mutating command runs, Sentinel copies every hand-edited file to `.sentinel/hand_edits/<timestamp>-<command>/`.
- If the command then changes that file, it prints a `sentinel warning:` on stderr naming the file and the copy. A command that does not touch the file leaves it flagged.

```text
/health ACME_PORTAL
```

`/health` warns about a hand edit of any checksummed file, and about every kept copy whose text is no longer in the file. Then pick one:

- **Revert it**: undo the edit (from git, or your editor's history) and run `/health` again.
- **Carry it through the owning command**: if the edit held real new information, take it from the file or from its copy under `.sentinel/hand_edits/`, put it where it belongs and let the command rewrite the file. A client answer goes through `/resolve-gaps`; new evidence through `/sync --source`; a PRD addition through `/compose`; a backlog change through `/refine-backlog`. The [artifact reference](02-artifact-reference.md) says which command writes each file. Then delete the copy.

**Check:** `/health` no longer reports the hand edit or a kept copy.

## A file was deleted or is corrupted

Regenerate it with the command that owns it. The [artifact reference](02-artifact-reference.md) has a "Written by" column for every file. For example, a missing `02_requirements/project-brief.md` makes `/validate` fail with a finding like "points to a path that does not exist"; `/brief ACME_PORTAL` writes it again.

Two kinds of file cannot be regenerated, because they are the input, not the output:

- **Raw evidence** under `00_raw/` and the copies under `07_changes/`: restore them from git or your backup, or bring the original in again with `/sync --source`.
- **`state.json`** (the project's state): every command refuses with exit 3 while it is missing or does not parse, and names the fix. Every state update first copies the previous file to `.sentinel/state.json.bak`: copy that file back to `state.json` in the workspace folder (you lose at most the last update), or restore it from git or your backup. A workspace with no artifacts yet can be recreated with `/init`. `/doctor` lists the workspaces whose `state.json` is missing or damaged.

Any other workspace JSON file that does not parse stops the command with exit 3 and its name. Restore it from git, or regenerate it with the command that writes it; for a file under `memory.lancedb/`, run `/reindex ACME_PORTAL`. The `next step:` line says which.

Then run `/health ACME_PORTAL` and `/validate ACME_PORTAL`.

## A command refused

A refusal is not a failure of the tool: the command checked something and stopped before writing. Read the two lines it printed, `sentinel error: ...` and `next step: ...`, then the exit code:

- **2**: the command line is wrong (a missing option, an unknown value).
- **3**: the input is wrong (a file that does not exist, a refused payload, a bad id, a missing or damaged `state.json`). Nothing was stored.
- **4**: a prerequisite is missing (no workspace, nothing ingested yet, health `DIRTY`, maturity `BLOCKED`). Run the step it names.
- **5**: `/validate` or `/doctor` gave an unfavourable verdict; the findings are printed.
- **6**: another command is using the workspace; wait and run again.

The full table is in [exit codes](01-command-reference.md#exit-codes), the conditions per command in the [gate matrix](01-command-reference.md#gate-matrix), and a decision chart in [A gate refused](03-workflows.md#a-gate-refused). When in doubt, `/next ACME_PORTAL` prints the next step alone.

## Next

- [Workflows: what to do in each situation](03-workflows.md)
- [Artifact reference](02-artifact-reference.md)
- [Command reference](01-command-reference.md)
