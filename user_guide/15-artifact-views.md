# Artifact Views And Optional MDX Export

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

## What The View Shows

- section table of contents and search
- source line anchors for each section
- pending, gap, and assumption markers highlighted inline
- a filterable "Pending And Assumptions" panel where each marker links back to its exact inline highlight
- gap metadata from `gaps.md`: lens, severity, status, why it matters, what it unblocks, and expected answer format
- governed assumption metadata from `assumptions.md`: owner, risk, statement, linked gap, and status
- section certainty badges (`populated`, `pending`, `assumed`) derived from artifact markers and the local development readiness context when present
- citations and matching trace nodes in the side panel
- evidence chips that resolve trace IDs to the real graph node, show a local source fragment, and render a one-hop mini trace graph from actual `traceability_graph.json` edges
- guided response mode that shows client-answerable gaps by default, separates domain and BA/assumption items, and tracks local draft progress
- local anchored comments stored in `localStorage`, with Markdown export for existing `/resolve-gaps` and `/sync` flows
- a Markdown source toggle for reviewers who need the canonical text

## Derived Block Model

Before rendering, Sentinel converts the Markdown artifact into a governed block model. The catalog is intentionally small and closed:

- `section`
- `requirement-table`
- `persona`
- `ears-statement`
- `decision`
- `traceability`
- `pending`
- `assumption`

Blocks preserve exact Markdown slices, so `md -> blocks -> md` remains idempotent in the covered fixtures. The model exists to make review behavior more stable; it is not a new authoring format and it is not a second source of truth.

## Guided Responses And Feedback

Guided response mode is derived from marker metadata. Business and product gaps are treated as client questions; technology, design, quality, compliance, and delivery gaps are treated as domain questions; governed assumptions are separated for BA review. Drafts stay in browser `localStorage` until exported or routed through a governed command.

The feedback export uses existing Sentinel inputs. Comments anchored to `GAP-*` markers are exported as `### GAP-*` answer blocks with `Answer`, `Owner / source`, `Evidence or reference`, and `Decision status`, so they can be reviewed and passed to `/resolve-gaps`. Other section or marker comments are exported as review Markdown suitable for `/sync --source PATH --note "Artifact review feedback"`.

Do not edit generated HTML. If review feedback changes scope or answers a gap, export it as local evidence and route it through `/resolve-gaps`, `/sync`, `/annotate`, or the appropriate governed command.

## Optional PRD MDX Export

Teams that already run an offline MDX renderer can export the PRD as a local derived MDX folder:

```powershell
python -m sentinel /export PROJECT_ID --artifact prd --format mdx
```

This writes:

```text
workspaces/PROJECT_ID/08_context_packs/exports/prd-mdx/
  index.mdx
  blocks.json
  README.md
```

`index.mdx` mirrors the PRD Markdown with block comments and export metadata. `blocks.json` contains the derived block interlingua used to build the MDX. `README.md` explains the local-only contract.

The MDX export is optional. Sentinel does not install a renderer, does not call a hosted Plan MCP or other remote renderer, and does not treat MDX as authoritative content. Regenerate it from `/export` when the PRD changes.
