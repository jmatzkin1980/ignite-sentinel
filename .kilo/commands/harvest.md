---
description: Ingest a tagged brownfield code harvest as a governed source and route what the code cannot say.
agent: sentinel-discovery
---

# Ignite Harvest

Parse `PROJECT_ID` and `--source PATH` from:

```text
/harvest PROJECT_ID --source PATH
/harvest PROJECT_ID --source PATH --change CHG-NNN
```

The `--source` file is a Markdown harvest of the existing system's code, written with the `sentinel-brownfield-harvest` skill (local only): blocks `## B0 Inventory` (`- repo: name — path` for code, `- doc: name — path` for documents) through `## B8` (B6 screens, B7 flows, B8 rules and roles, read from documents), and one tagged claim per line: `[HECHO name:file]`, `[INFERIDO]`, `[NO ENCONTRADO where]`, `[FUERA DEL CÓDIGO topic]` or `[DIVERGENCIA name:file]` (`name` is a repo or doc of B0) (English tags work too).

Run from the repository root:

```powershell
python -m sentinel /harvest PROJECT_ID --source PATH
python -m sentinel /harvest PROJECT_ID --source PATH --change CHG-NNN
```

The runtime validates every tag (a fact or divergence names a repo or doc of B0; out-of-code uses the closed topic list), redacts secrets, stores the harvest as a governed F-NN row (`built`), opens a non-blocking gap per out-of-code topic and a high gap per README/code divergence, and writes `01_discovery/harvest.json`, which the brief v2 uses in §5 and §0.2. Report the coverage per tag, the gaps opened and any rejected line.

With `--change CHG-NNN` (IMP-384) the harvest's gaps (GAP-HRV-*) open in that change instead of the project. A workspace that only has changes refuses a harvest without the flag.
