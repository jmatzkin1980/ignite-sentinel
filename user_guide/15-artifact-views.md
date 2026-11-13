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

## Layout, themes and reproducibility

```powershell
python -m sentinel /view PROJECT_ID --artifact prd --theme neutral
```

- The view uses the same shell as `/dashboard`:
  - a skip link;
  - a sticky top bar with a light/dark toggle that remembers your choice;
  - a sidebar with search, stats and the table of contents, which turns into a menu button below 900 px;
  - print rules.
- **Theme order:** `--theme` (a built-in name or the path to a local theme JSON), then `theme:` in the workspace config, then `neutral`. The colour legend comes from the theme.
- **Reader edition:** inline provenance (`_(GAP-… / CHG-…)_`, `[Source: …]`) is hidden by default so the body reads cleanly.
  - **Show provenance** reveals it and remembers the choice.
  - Jumping to a marker that sits inside hidden provenance reveals it automatically.
  - The Markdown keeps every anchor; only the view hides them.
- **Provenance section:** the source path, its 12-character sha256, the cut-off (the source file's modification time, not the build time) and the command that regenerates the page.
- **Reproducible:** two runs over the same workspace produce identical HTML, and the page embeds no absolute paths.
- **Notes survive rebuilds:** they keep their existing browser keys.
  - If the source changed since you saved notes, the page says so.
  - Notes whose target no longer exists are marked as orphaned, never deleted.

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

The feedback export uses existing Sentinel inputs. Comments anchored to `GAP-*` markers are exported as `### GAP-*` answer blocks with `Answer`, `Owner / source`, `Evidence or reference`, and `Decision status`, so they can be reviewed and passed to `/resolve-gaps`. Other section or marker comments are exported as review Markdown suitable for `/sync --source PATH --note "Artifact review feedback"`. The client's drafted **guided answers** are folded into the same export under a `## Guided Responses` section — answered `GAP-*` items keep the `### GAP-*` / `Answer` / `Decision status` shape for `/resolve-gaps` — so a guided draft is never left stranded in `localStorage`.

There are two local-first ways to hand the export back to the BA, both in the **Feedback Loop** panel:

- **Export Markdown** downloads a `PROJECT-ARTIFACT-feedback.md` file to your machine.
- **Draft Email To BA** opens a pre-filled draft (subject and body) in your own mail client. It only opens a draft — it never sends automatically — and because `mailto:` cannot carry attachments it reminds you to attach the downloaded `.md`.

The feedback loop lives only in the artifact views; the portfolio dashboard is status-only and has no capture panel by design.

Do not edit generated HTML. If review feedback changes scope or answers a gap, export it as local evidence and route it through `/resolve-gaps`, `/sync`, `/annotate`, or the appropriate governed command.

## Build Readiness View

```powershell
python -m sentinel /view PROJECT_ID --artifact readiness
```

This view answers "what is missing, and from whom?". It writes `08_context_packs/views/readiness.html` inside the same shell, themes and CSP as the other views. It is not built from a Markdown artifact: it reads the ready-to-build verdict that `/status` reports, plus `01_discovery/gaps.md`, the story gates, `08_context_packs/slice_plan.json` and the stakeholder registry.

- **Items.** There is one card for the workspace, one for each backlog story and one for each SLICE-PLAN wave (`CHK-WAVE-NN`). Each card carries its governed verdict:
  - The workspace card shows the verdict from `/status`.
  - A story card follows the story's Definition of Ready.
  - A wave card takes the most severe verdict among its stories. A wave without stories is never shown green.
- **Requests.** Every open gap is a request, and so is each Definition of Ready item a story is missing. Each request says whether it blocks: `start` (a blocking gap), `slice` (it blocks that story's slice) or `no`.
- **By recipient.** Requests are grouped by who has to answer:
  - A gap goes to the stakeholder registered for its lens in `/stakeholders`.
  - With no match, it is listed as unassigned client (business and product lenses) or unassigned domain. An owner is never invented.
  - Definition of Ready items go to the BA.
  - **Copy request** copies the open requests for that recipient as a ready-to-send message.
  - This view is the only place that builds the per-recipient request.
- **Local marks.** Tick a request once it was sent or answered.
  - An open request degrades a `READY` item to "ready with warnings" until it is marked.
  - Marks never upgrade a governed verdict: only `/resolve-gaps`, `/sync` and the backlog commands change what the workspace says.
  - Marks live in this browser only, under the key `ignite-sentinel:readiness:PROJECT_ID`.
  - Use **Export** and **Import**, which go through the text box, to move marks to another browser. **Clear** removes them.

The provenance block fingerprints only the fields the view reads, so the page is reproducible for the same workspace.

## To-Be Diagrams

```powershell
python -m sentinel /view PROJECT_ID --artifact diagrams
```

IMP-273 writes `08_context_packs/views/diagrams.html` from the v2 brief. A workspace that compiles v1 is refused. The view is read-only and generated deterministically: the same brief gives the same page.

| Card | From | Mermaid |
|---|---|---|
| State machine and lifecycle | §3.4 | `stateDiagram-v2` |
| Sequence / to-be flow | §3.3 | `sequenceDiagram` |
| Architecture and integrations | §5.1 components, §5.6 integration map | `flowchart`, with each component's status |
| Architecture today (As-Is) | §5.1, when a component extends, keeps or retires something | `flowchart` |
| Release series | the confirmed series (`/split --confirm`) | `flowchart` with its waves |

- **Nothing is inferred.** A diagram is drawn only from structured lines of its section:
  - `STATE → STATE: event` (also `->`), `Actor → Actor: message`, `A → B: contract`;
  - `Component (new|extends|unchanged|retired)`, Spanish accepted (`nuevo`, `extiende`, `sin cambios`, `se retira`);
  - a Markdown table whose header names its columns (`State | Event | Next state`, `From | To | Message`, `Component | Status`).
- **Dashed means pending, conditional or optional.**
  - A pending section is a dashed placeholder with its GAP.
  - A line marked conditional or optional is dashed.
  - A component that appears only in the integration map is drawn as external and listed under "what is still to define" (confirm it in §5.1).
- **Without notation.** A populated section with none of that notation is a card "without diagrammable notation" that says how to write it.
- **Each card** says what changes and what is still to define, with release and pending chips.
  - The legend appears once.
  - A diagram over 24 edges is split into parts.
- **Rendering** is offline, under the same CSP as every view.
  - The page inlines the vendored mermaid (`sentinel/vendor/mermaid`, version `11.17.2`, MIT License), whose sha256 `/doctor` checks.
  - Colours come from the theme's semantic roles, and the page re-renders when you switch light/dark mode.
  - Without the library (the minimal `.pyz` leaves it out) or when its hash does not match, each card shows its Mermaid code marked "not rendered".
  - The code is also always available under **Mermaid code**.

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
