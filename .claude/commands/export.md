---
description: Export a shareable Ignite Sentinel artifact.
---

# Ignite Export

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--artifact`, and optional `--format md|mdx` / `--fmt md|mdx` from:

```text
/export PROJECT_ID --artifact gaps --format md
/export PROJECT_ID --artifact prd --format mdx
```

Allowed Markdown artifacts: `gaps`, `brief`, `context-request`, `prd`.
Allowed MDX artifact: `prd` only.

Run from the repository root:

```powershell
python -m sentinel /export PROJECT_ID --artifact ARTIFACT --format md
python -m sentinel /export PROJECT_ID --artifact prd --format mdx
```

Markdown export copies the artifact under `08_context_packs/exports/`. MDX export writes a local derived folder under `08_context_packs/exports/prd-mdx/` with `index.mdx`, `blocks.json`, and `README.md`. It is for teams that already have an offline MDX renderer; it does not enable hosted/remote rendering and does not replace Markdown as source of truth.
