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
- a filterable "Pending And Assumptions" panel where each marker links back to its exact inline highlight
- gap metadata from `gaps.md`: lens, severity, status, why it matters, what it unblocks, and expected answer format
- governed assumption metadata from `assumptions.md`: owner, risk, statement, linked gap, and status
- section certainty badges (`populated`, `pending`, `assumed`) derived from artifact markers and the local development readiness context when present
- citations and matching trace nodes in the side panel
- evidence chips that resolve trace IDs to the real graph node, show a local source fragment, and render a one-hop mini trace graph from actual `traceability_graph.json` edges
- local anchored comments stored in `localStorage`, with Markdown export for existing `/resolve-gaps` and `/sync` flows
- a Markdown source toggle for reviewers who need the canonical text

The feedback export uses existing Sentinel inputs. Comments anchored to `GAP-*` markers are exported as `### GAP-*` answer blocks with `Answer`, `Owner / source`, `Evidence or reference`, and `Decision status`, so they can be reviewed and passed to `/resolve-gaps`. Other section or marker comments are exported as review Markdown suitable for `/sync --source PATH --note "Artifact review feedback"`.

Do not edit generated HTML. If review feedback changes scope or answers a gap, export it as local evidence and route it through `/resolve-gaps`, `/sync`, `/annotate`, or the appropriate governed command.
