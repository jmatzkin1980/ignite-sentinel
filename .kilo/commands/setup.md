---
description: Turn on semantic memory: install the pinned local model, verified by sha256.
agent: sentinel-health
---

# Ignite Setup

Run this command only when the user asks to turn on semantic memory, in chat or by typing it. It is never automatic and not an MCP tool. It is the one Sentinel command that may use the network, and only to download one pinned model whose files are checked by sha256 before anything is activated.

```powershell
python -m sentinel /setup --semantic-memory
```

Without network (air-gapped), point it at a folder that already holds the model files:

```powershell
python -m sentinel /setup --semantic-memory --offline-from DIR
```

To re-check an installed model without network, add `--status` instead.

Summarize the result: `installed` (path, revision, workspaces reindexed and any warnings with the command to retry), `missing`, or `mismatch`. If it reports that `model2vec` is not installed, give the user the pip command it names and let them run it. Exit codes: `0` done; `3` bad input (an `--offline-from` folder without the model files, a failed download or a sha256 mismatch: fix the input and retry); `4` a missing prerequisite (`model2vec` not installed: the refusal's next step is `pip install -r constraints/memory-semantic.txt`). In Kilo the command asks before it runs. If `python` is unavailable, tell the user to run the same command with their approved Python runtime.
