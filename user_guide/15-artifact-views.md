# Artifact Views

`/view` creates a local HTML review surface for one Sentinel artifact:

```powershell
python -m sentinel /view PROJECT_ID --artifact prd
```

Allowed artifacts are `gaps`, `brief`, `prd`, `specs`, and `backlog`.

The generated file lives under:

```text
workspaces/PROJECT_ID/08_context_packs/views/ARTIFACT.html
```

The view is derived from the Markdown source of truth. It is self-contained, read-only, ignored by git, and safe to rebuild at any time. Use it when a BA, product owner, stakeholder, or implementation agent needs a more navigable artifact without editing the underlying `.md` file.

What the first version shows:

- section table of contents and search
- source line anchors for each section
- pending, gap, and assumption markers highlighted inline
- citations and matching trace nodes in the side panel
- a Markdown source toggle for reviewers who need the canonical text

Do not edit generated HTML. If review feedback changes scope or answers a gap, capture it as local evidence and route it through `/resolve-gaps`, `/sync`, `/annotate`, or the appropriate governed command.
