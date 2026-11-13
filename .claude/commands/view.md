---
description: Generate a local read-only HTML view for one Sentinel artifact.
argument-hint: PROJECT_ID --artifact backlog|brief|gaps|prd|readiness|release-guide|prototype|specs [OPTIONS] [--release rN]
---

# Ignite View

Arguments received from the user invocation: `$ARGUMENTS`

Parse `PROJECT_ID`, `--artifact`, and optional `--open` / `--theme` from:

```text
/view PROJECT_ID --artifact prd
/view PROJECT_ID --artifact brief --open
```

Allowed artifacts: `gaps`, `brief`, `prd`, `specs`, `backlog`, and `readiness, release-guide, prototype`. `readiness` is not a Markdown artifact: it shows what is missing per item (workspace, stories, SLICE-PLAN waves) and from whom, with the ready-to-build verdict of `/status`.

`--release rN` (IMP-267b) runs this command for one release of a confirmed series: the release brief `02_requirements/rN/project-brief.md` is the input and the outputs land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`. The release keeps its own lifecycle; the project's state and artifacts are not touched. Without `--release` nothing changes.

Run from the repository root:

```powershell
python -m sentinel /view PROJECT_ID --artifact ARTIFACT
python -m sentinel /view PROJECT_ID --artifact ARTIFACT --open
python -m sentinel /view PROJECT_ID --artifact ARTIFACT --theme neutral
```

`--theme` takes a built-in theme name or the path to a local theme JSON; without it the workspace config `theme:` applies, else `neutral`.

The runtime reads the Markdown source of truth, traceability graph, and workspace state, then writes a self-contained read-only HTML snapshot under `08_context_packs/views/`. It never mutates the source artifact. The output is reproducible (source cut-off and sha256 instead of a build time), and inline provenance is hidden behind a reader toggle. Summarize the generated path, source path, theme, cut-off, section count, pending markers, citations, and trace-node count.
