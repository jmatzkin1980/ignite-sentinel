# Change analysis (`/sync --analysis`, IMP-337)

The agent's cited reading of one note: which confirmed items the note changes. The runtime validates it, opens one blocking `GAP-CHG-<hash>` per valid candidate, and changes nothing else until the BA runs `/gaps --id GAP-CHG-x --disposition accepted|rejected`.

```text
python -m sentinel /sync PROJECT_ID --source NOTE.md --analysis change-analysis.json
```

## Shape

```json
{
  "candidates": [
    {
      "kind": "reopen_gap",
      "target": "GAP-SCOPE",
      "note_quote": "charging a late fee online is part of the first version",
      "target_quote": "out of scope for the first version",
      "question": "Does the board decision of 12 November replace the confirmed scope?"
    },
    {
      "kind": "invalidate_assumption",
      "target": "ASM-001",
      "note_quote": "charging a late fee online is part of the first version",
      "target_quote": "Late fees are collected at the branch only"
    }
  ],
  "untouched": ["Line 4 restates the roadmap; it changes nothing confirmed."]
}
```

| Field | Required | Rule |
|---|---|---|
| `kind` | yes | `reopen_gap`, `invalidate_assumption` or `contradiction`. |
| `target` | yes | `reopen_gap`: a `GAP-*` that is `CLOSED` or `PARTIALLY_CLOSED`. `invalidate_assumption`: an `ASM-*` that is `ASSUMED` or `VALIDATED`. `contradiction`: an `F-NN` registered source. |
| `note_quote` | yes | Verbatim from the note passed with `--source` (case and whitespace are ignored, nothing else). |
| `target_quote` | yes | Verbatim from the target: the closed gap's confirmed answer (the `Gap Resolution Seeds` / `Gap Resolution Decisions` rows) or its evidence and resolution note; the assumption's statement or justification; the other source's text or its anchored statements. |
| `question` | no | The question the BA answers. Default: "Does the change replace what TARGET says?" |
| `untouched`, `absent` | no | The sweep protocol (the package's `templates/agent_sweep_protocol.md`). No `counts`, `totals`, `summary`, `figures`, `stats` or `metrics`: figures are the runtime's. |

## Rules

- Propose a candidate only when the note **changes** what the target says. A note that reaffirms the target is not a candidate, even if `prose_review.hints` listed it.
- One candidate per target per analysis; the same target twice is refused.
- The whole file is refused (exit 3) when any candidate fails, with every reason listed, and nothing is written: the note is not stored either. Fix the quotes and run `/sync` again.
- A note that declares itself not validated cannot change confirmed knowledge.
- The same candidate (kind, target and note quote) sent again does not open a second `GAP-CHG` (`skipped_existing`).

## What the BA's disposition does

| Disposition | `reopen_gap` | `invalidate_assumption` | `contradiction` |
|---|---|---|---|
| `accepted` | The gap reopens; its previous closure stays in the resolution note. | The assumption becomes `INVALIDATED`; the gap it held reopens. | Nothing to apply; the result names `/sources --precedence` to record which source governs. |
| `rejected` / `irrelevant` (need `--reason`) | The `GAP-CHG` closes as a false alarm; nothing else moves. | Same. | Same. |

In every case the `GAP-CHG` closes, the disposition counts in the `agent` channel's false-alarm rate, and with `accepted` the knowledge metabolism marks the brief, PRD and backlog stale.
