# Artifact views

`/view` turns one Sentinel artifact into a local HTML page that is easier to read, search and review than the Markdown. This page is for BAs, product managers, stakeholders and agents who review artifacts in a browser: it lists the 11 views, what each shows, where the file lands, and how the shared page behaves. For the portfolio page across all projects see [Dashboard](14-dashboard.md); for the look and feel see [Themes](17-themes.md).

## Build a view

```bash
/view ACME_PORTAL --artifact prd
python -m sentinel /view ACME_PORTAL --artifact prd --open
```

| Option | Effect |
|---|---|
| `--artifact NAME` | Required. One of the 11 names below. |
| `--open` | Open the page in your default browser when it is built. |
| `--theme NAME_OR_PATH` | A built-in theme name, a local theme name, or the path to a theme JSON. Without it: `theme:` in `sentinel.config.yaml`, then `neutral`. See [Themes](17-themes.md). |
| `--release rN` | Build the view for one release of a confirmed series. |

`/view` is read-only: it never changes a governed artifact. If the source artifact does not exist yet, it refuses with exit 4 (`Artifact not generated yet for /view: ...`) and the next step "Run /next PROJECT_ID to see which command comes first"; run the command that creates it first.

**Output path.** The file is `workspaces/<PROJECT_ID>/08_context_packs/views/<artifact>.html`. With `--release rN` it is `workspaces/<PROJECT_ID>/08_context_packs/rN/views/<artifact>.html`. Views are ignored by git and safe to delete: rebuild them any time. The Markdown stays the source of truth; do not edit the HTML.

## The 11 artifacts

| `--artifact` | Shows | Reads | Create the source with |
|---|---|---|---|
| `gaps` | Discovery gaps, with the guided-response panel for answering them. | `01_discovery/gaps.md` | `/ingest` |
| `brief` | The project brief. | `02_requirements/project-brief.md` | `/brief` |
| `prd` | The PRD. | `03_specs/prd.md` | `/specs` |
| `specs` | The spec index. | `03_specs/specs.md` | `/specs` |
| `backlog` | The backlog board (falls back to `EPIC-001.md` if `BACKLOG.md` is missing). | `04_backlog/BACKLOG.md` | `/backlog` |
| `readiness` | What is missing, and from whom: a request per open gap and per missing Definition of Ready item. | Status verdict, `gaps.md`, story gates, `slice_plan.json`, stakeholder registry | Works from any workspace; see [below](#readiness) |
| `diagrams` | To-be diagrams drawn from the v2 brief. | The brief's sections 3.3, 3.4, 5.1, 5.6 | `/brief`; see [below](#diagrams) |
| `release-guide` | The status of each release of a series. | `02_requirements/series/release-guide.md` | `/split --confirm` |
| `prototype` | The prototype inventory. | `02_requirements/prototype/inventory.md` | `/prototype --inventory` |
| `prototype-trace` | Element to data to contract to rule, per screen. | `02_requirements/prototype/trace.md` | `/prototype --trace` |
| `prototype-manual` | The printable user manual of the prototype. | `02_requirements/prototype/manual.md` | `/prototype --manual` |

## What a Markdown view shows

Nine of the views are built from one Markdown file: `gaps`, `brief`, `prd`, `specs`, `backlog`, `release-guide`, `prototype`, `prototype-trace` and `prototype-manual`. They share one design:

- a table of contents and search, with source line anchors per section;
- pending markers, gaps and assumptions highlighted inline, and a filterable **Pending and assumptions** panel where each marker links back to its place;
- gap details taken from `gaps.md` (lens, severity, status, why it matters, what answering unblocks, expected answer format) and assumption details from `assumptions.md` (owner, risk, status, linked gap);
- section badges: `populated`, `pending` or `assumed`;
- **evidence chips**: a citation such as `REQ-001` or `SPEC-U-001` is resolved only if a matching node exists in the traceability graph. A matched chip shows a local source fragment and a one-hop mini graph made of real trace edges; an unmatched citation stays visible as unmatched. A view never invents evidence;
- a Markdown source toggle for the canonical text.

### Reader edition and provenance

- Inline provenance (`_(GAP-… / CHG-…)_`, `[Source: …]`) is hidden by default so the body reads cleanly. **Show provenance** reveals it and remembers the choice; the Markdown keeps every anchor.
- The **Provenance** section lists the source path, its 12-character sha256, the cut-off (the source file's modification time, not the build time) and the command that regenerates the page. It is written in the page language: a Spanish workspace gets **Procedencia** with *Fuente*, *fecha de corte* and *Regenerar*, like the dashboard.
- Two runs over the same workspace produce identical HTML, and the page contains no absolute paths.

### Review, answer and feedback

Everything below is local to your browser (`localStorage`); nothing is written back to the workspace.

- **Guided response** lists the gaps a client can answer (business and product) first, separates domain gaps (technology, design, quality, compliance, delivery) and BA-owned assumptions, and tracks draft progress.
- **Comments** are anchored to a marker or section. They survive a rebuild; if the source changed since you saved, the page says so, and a comment whose target disappeared is marked orphaned, never deleted.
- **Export Markdown** downloads `PROJECT-ARTIFACT-feedback.md`. Comments on a `GAP-*` marker become `### GAP-*` answer blocks (`Answer`, `Owner / source`, `Evidence or reference`, `Decision status`) that you pass to `/resolve-gaps`. Other comments are review notes to pass to `/sync --source PATH --note "Artifact review feedback"`. Guided answers are folded in under `## Guided Responses`.
- **Draft Email To BA** opens a pre-filled draft in your mail client. It never sends anything, and it reminds you to attach the downloaded file.

Review feedback that changes scope or answers a gap must enter through `/resolve-gaps`, `/sync`, `/annotate` or `/compose`, never by editing the HTML or the governed Markdown.

## Readiness

```bash
/view ACME_PORTAL --artifact readiness
```

This view answers "what is missing, and from whom?". It is not built from one Markdown file.

- **Items.** One card for the workspace, one per backlog story and one per SLICE-PLAN wave. Each carries its governed verdict: the workspace card shows the `/status` verdict, a story card follows its Definition of Ready, a wave card takes the most severe verdict among its stories (a wave with no stories is never green).
- **Requests.** Every open gap is a request, and so is each Definition of Ready item a story is missing. Each says whether it blocks: `start` (a blocking gap), `slice` (it blocks that story's slice) or `no`.
- **By recipient.** A gap goes to the stakeholder registered for its lens with `/stakeholders`. With no match it is listed as unassigned client (business and product lenses) or unassigned domain; an owner is never invented. Definition of Ready items go to the BA. **Copy request** copies a recipient's open requests as a ready-to-send message.
- **Local marks.** Tick a request once it was sent or answered. An open request lowers a `READY` item to "ready with warnings" until it is marked. Marks never upgrade a governed verdict: only `/resolve-gaps`, `/sync` and the backlog commands change what the workspace says. They live in this browser only; **Export** and **Import** move them to another browser, **Clear** removes them.

## Diagrams

```bash
/view ACME_PORTAL --artifact diagrams
```

The diagrams view reads the **v2** brief. If the brief does not exist, it refuses with exit 4 and the next step "Run /brief PROJECT_ID first." If the workspace compiles brief v1, it fails with exit 3.

| Card | From | Mermaid type |
|---|---|---|
| State machine and lifecycle | Section 3.4 | `stateDiagram-v2` |
| Sequence / to-be flow | Section 3.3 | `sequenceDiagram` |
| Architecture and integrations | Sections 5.1 and 5.6 | `flowchart`, with each component's status |
| Architecture today (As-Is) | Section 5.1, when a component extends, keeps or retires something | `flowchart` |
| Release series | The confirmed series | `flowchart` with its waves |

- **Nothing is inferred.** A diagram is drawn only from structured lines: `STATE → STATE: event`, `Actor → Actor: message`, `A → B: contract`, `Component (new|extends|unchanged|retired)` (Spanish forms accepted), or a Markdown table whose header names its columns (`State | Event | Next state`, `From | To | Message`, `Component | Status`).
- **Dashed means pending, conditional or optional.** A pending section is a dashed placeholder with its GAP. A component that only appears in the integration map is drawn as external and listed under "what is still to define".
- A populated section with none of that notation becomes a card "without diagrammable notation" that says how to write it. A diagram over 24 edges is split into parts.
- **Rendering is offline.** The page inlines a vendored Mermaid whose hash `/doctor` checks. Without the library (the minimal `.pyz` leaves it out) or on a hash mismatch, each card shows its Mermaid code marked "not rendered". The code is always available under **Mermaid code**.

## Shared page shell

Every view and the [dashboard](14-dashboard.md) use the same shell: a skip link, a sticky top bar with a light/dark toggle that remembers your choice, a sidebar with search, statistics and the table of contents (a menu button below 900 px), and print rules. The colour legend is generated from the theme, so every colour has a stated meaning. The page follows the project language for its labels (`es` or `en`). Pages are self-contained, load no external resources and make no network requests.

## Next

- [Themes](17-themes.md): change colours, fonts and labels.
- [Dashboard](14-dashboard.md): the portfolio page across all workspaces.
- [Workflows](03-workflows.md): sending a view to a client and bringing the answers back.
