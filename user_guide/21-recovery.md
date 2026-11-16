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

Use `--replacement F-NN` when another row takes its place. Retiring does not delete anything:

- The copy under `00_raw/` or `07_changes/` stays, and so does its text in the local memory. `/retrieve` can still return it, and `/reindex` indexes it again while the file is in the workspace. When a retrieved excerpt comes from a retired `F-NN`, do not use it.
- A retired source reaches every document: its row gets a `pending` impact cell for each one. Review each cell and close it with `/sources ACME_PORTAL --id F-04 --cell DOCUMENT/SECTION --mark reviewed --reason "..."` (or `updated` after you regenerated it).
- Gaps the wrong file opened stay in `gaps.md`. Decide them with the BA. For a gap an agent raised, record `/gaps ACME_PORTAL --id GAP-X --disposition irrelevant --reason "came from a retired source"`.

**Check:** `/sources ACME_PORTAL` shows the row as retired; `/status ACME_PORTAL` no longer warns about its open cells once they are closed.

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

Generated files (the gaps, the requirements, the brief, specs, backlog) change only through commands. A hand edit is not kept safely: the next regeneration overwrites it, and nothing traces it.

```text
/health ACME_PORTAL
```

`/health` warns about a hand edit of any checksummed file. Then pick one:

- **Revert it**: undo the edit (from git, or your editor's history) and run `/health` again.
- **Carry it through the owning command**: if the edit held real new information, put that information where it belongs and let the command rewrite the file. A client answer goes through `/resolve-gaps`; new evidence through `/sync --source`; a PRD addition through `/compose`; a backlog change through `/refine-backlog`. The [artifact reference](02-artifact-reference.md) says which command writes each file.

**Check:** `/health` no longer reports the hand edit.

## A file was deleted or is corrupted

Regenerate it with the command that owns it. The [artifact reference](02-artifact-reference.md) has a "Written by" column for every file. For example, a missing `02_requirements/project-brief.md` makes `/validate` fail with a finding like "points to a path that does not exist"; `/brief ACME_PORTAL` writes it again.

Two kinds of file cannot be regenerated, because they are the input, not the output:

- **Raw evidence** under `00_raw/` and the copies under `07_changes/`: restore them from git or your backup, or bring the original in again with `/sync --source`.
- **`state.json`** (the project's state): restore it from git or your backup.

Then run `/health ACME_PORTAL` and `/validate ACME_PORTAL`.

## A command refused

A refusal is not a failure of the tool: the command checked something and stopped before writing. Read the two lines it printed, `sentinel error: ...` and `next step: ...`, then the exit code:

- **2**: the command line is wrong (a missing option, an unknown value).
- **3**: the input is wrong (a file that does not exist, a refused payload, a bad id). Nothing was stored.
- **4**: a prerequisite is missing (no workspace, nothing ingested yet, health `DIRTY`, maturity `BLOCKED`). Run the step it names.
- **5**: `/validate` or `/doctor` gave an unfavourable verdict; the findings are printed.
- **6**: another command is using the workspace; wait and run again.

The full table is in [exit codes](01-command-reference.md#exit-codes), the conditions per command in the [gate matrix](01-command-reference.md#gate-matrix), and a decision chart in [A gate refused](03-workflows.md#a-gate-refused). When in doubt, `/next ACME_PORTAL` prints the next step alone.

## Next

- [Workflows: what to do in each situation](03-workflows.md)
- [Artifact reference](02-artifact-reference.md)
- [Command reference](01-command-reference.md)
