---
description: Ingest a tagged brownfield code harvest as a governed source and route what the code cannot say.
argument-hint: PROJECT_ID --source PATH
---

# Ignite Harvest

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID` and `--source PATH` from:

```text
/harvest PROJECT_ID --source PATH
```

The `--source` file is a Markdown harvest of the existing system's code, written with the `sentinel-brownfield-harvest` skill (local only): blocks `## B0 Inventory` (`- repo: name — path`) through `## B5`, and one tagged claim per line: `[HECHO repo:file]`, `[INFERIDO]`, `[NO ENCONTRADO where]`, `[FUERA DEL CÓDIGO topic]` or `[DIVERGENCIA repo:file]` (English tags work too).

Run from the repository root:

```powershell
python -m sentinel /harvest PROJECT_ID --source PATH
```

The runtime validates every tag (a fact names a repo of B0; out-of-code uses the closed topic list), redacts secrets, stores the harvest as a governed F-NN row (`built`), opens a non-blocking gap per out-of-code topic and a high gap per README/code divergence, and writes `01_discovery/harvest.json`, which the brief v2 uses in §5 and §0.2. Report the coverage per tag, the gaps opened and any rejected line.
