# Dashboard

`/dashboard` builds one local HTML page that shows every Sentinel workspace side by side: phase, health, gaps, documents, backlog readiness and the recommended next step. Use it in review meetings, or whenever you manage several projects and want the picture without opening many Markdown files. For a single artifact use [Artifact views](15-artifact-views.md).

## Language

The dashboard follows the project language (`project_language` in each workspace's `state.json`), like the [views](15-artifact-views.md). Spanish (`es`, or any `es-*` tag) gives a Spanish page; anything else, including `auto`, gives English.

- **Each workspace speaks its own language.** Its card, side panel, suggested prompts and gap copy use that workspace's language, so a Spanish and an English project can sit on the same page.
- **The page frame uses the majority.** The header, indicators, filters, side menu and colour legend use the language most workspaces use. A tie, or a folder with no workspace, gives English.

Only the interface is translated. Project ids, file names, gap text and your documents stay as they are.

## Build it

Run it from the repository root, where the `workspaces/` folder lives.

```bash
/dashboard
python -m sentinel /dashboard --open
```

| Option | Effect |
|---|---|
| `--open` | Open the page in your default browser when it is built. |
| `--theme NAME_OR_PATH` | A built-in theme name, or the path to a theme JSON. Default `neutral`. See [Themes](17-themes.md). |
| `--root PATH` | The repository root to read (default: the current folder). |

The command writes `dashboard.html` at `--root` (by default the folder you run it from). It is self-contained and opens offline. In a clone it is git-ignored because it can embed local workspace Markdown; with the plugin or the wheel it lands in your project folder, where nothing ignores it, so keep it out of commits yourself. Treat it as a rebuildable snapshot, not as a source of truth: it is not refreshed by other commands, so rerun `/dashboard` whenever workspace state changes.

The dashboard lists every folder under `workspaces/` that has a `state.json` and a valid project id. It skips `_template` and any folder commands could not act on, and it does not read release series: it shows each project as a whole. `--release` is not supported.

## What it shows

Each section appears only when there is data for it.

| Section (English / Spanish label) | What it tells you |
|---|---|
| Indicators / Indicadores | Portfolio totals and attention signals across all workspaces. |
| Workspaces | One card per workspace: phase, health, language, privacy mode, maturity, development certainty, open gaps, backlog roll-up, warnings. |
| Next step / Proximo paso | The recommended next step for that workspace (see `/next`). |
| Actions by situation / Acciones segun la situacion | Five ready-made prompts with the command chain for common situations: client answered gaps, new context arrived, a requirement changed, a meeting or email brought new definitions, prepare the handoff to development. |
| Maturity lifecycle / Lifecycle de maduracion | Whether the workspace is still in discovery, moving through specs, or ready for backlog and implementation review. |
| Summary / Resumen | The `/status` summary, including the development-certainty score and the Crystallization Gate state, so confirmed, assumed and open uncertainty stays visible at portfolio level. |
| Pending gaps / Gaps pendientes | Open gaps, which you can copy for client or domain follow-up. |
| Documents / Documentos | The workspace documents, opened inside the dashboard. The canonical files stay in each workspace. |
| Backlog, Story gates (DoR / DoD), Warnings | Backlog totals, the latest Definition of Ready and Done evaluation per story, and warnings. |

The page also carries the colour legend and a provenance block. Their behaviour is the same as in the views, described under [Shared page shell](15-artifact-views.md#shared-page-shell); on the dashboard, the provenance shows the cut-off date (the newest modification time among the files read), a 12-character sha256 of every `state.json`, and the command that regenerates the page. Two runs over the same workspaces give byte-identical HTML, and an inconsistent model fails instead of writing a misleading page.

The dashboard has no feedback panel by design; capture and comments exist only in the artifact views.

## Guardrails

- **Read-only.** It never changes a workspace.
- **Local-first.** No remote rendering, no external services, no network calls.
- **Governed.** Follow-up changes still go through the lifecycle commands: `/resolve-gaps`, `/sync`, `/story-status`, `/health`, `/validate`.

## From chat

You can ask in natural language, in either language:

```text
Show me the Sentinel dashboard and summarize what needs attention.
Mostrame el estado de los workspaces.
```

The agent should run `/dashboard`, report the generated path, summarize the portfolio signals, and stop before running any mutating command unless you ask for the next action. The exact form that Codex accepts is `sentinel /dashboard`.

## Next

- [Artifact views](15-artifact-views.md): per-artifact pages, the shared shell and provenance.
- [Themes](17-themes.md): change colours and fonts.
- [Workflows](03-workflows.md): what to do after reading the dashboard.
