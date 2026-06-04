# Ignite Sentinel vNext

## Working Agreements

- Treat this repository as a repo-local Codex framework for BA/Product requirements work in AI PODs.
- Keep the source of truth in versionable files under `workspaces/[PROJECT_ID]/`; memory indexes are retrieval aids only.
- Preserve traceability from raw input to requirements, gaps, decisions, specs, backlog, acceptance criteria, tests, and changes.
- Prefer small Codex skills with progressive disclosure: concise `SKILL.md`, deeper `references/`, reusable `assets/templates/`, deterministic scripts when possible.
- Do not reintroduce Roo-specific concepts such as `.roo`, `.roomodes`, `.roorules`, P3, or P5 as global architecture.

## Ignite Chat Commands

When the user sends an Ignite-style chat command, parse it as a request to run the Sentinel CLI from the repository root.

Accepted forms:

- `/doctor`
- `/init PROJECT_ID`
- `/ingest PROJECT_ID --source PATH`
- `/maturity PROJECT_ID`
- `/gaps PROJECT_ID`
- `/resolve-gaps PROJECT_ID --source PATH`
- `/brief PROJECT_ID`
- `/context-request PROJECT_ID --domain technology|design|quality|frontend|backend`
- `/status PROJECT_ID`
- `/export PROJECT_ID --artifact gaps|brief|context-request --format md`
- `/sync PROJECT_ID`
- `/sync PROJECT_ID --source PATH --note "NOTE"`
- `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW`
- `/reindex PROJECT_ID`
- `/specs PROJECT_ID`
- `/backlog PROJECT_ID`
- `/quality PROJECT_ID`
- `/trace PROJECT_ID`
- `/health PROJECT_ID`
- `/validate PROJECT_ID`
- `sentinel /init PROJECT_ID`
- `ignite /init PROJECT_ID`

Execution rule:

- Run the equivalent shell command: `python -m sentinel /COMMAND PROJECT_ID [OPTIONS]`.
- If `python` is not available, use the configured or bundled Python runtime when visible in the environment.
- For commands that mutate project artifacts, run the CLI rather than editing generated files manually.
- `/gaps PROJECT_ID` regenerates the human-friendly discovery gap document.
- `/resolve-gaps PROJECT_ID --source PATH` processes structured client/domain answers and safely closes only confirmed or not-applicable gaps.
- `/brief PROJECT_ID` refreshes `02_requirements/project-brief.md` from mature discovery evidence.
- `/context-request PROJECT_ID --domain DOMAIN` creates a domain-specific request under `08_context_packs/requests/`.
- `/status PROJECT_ID` reports phase, health, language, gap counts, and next recommended step.
- `/sync PROJECT_ID` without `--source` is the autonomous novelty scan: it detects new or modified input/context files by hash, creates `CHG` events, impact reports, trace edges, and memory entries.
- Use `/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW` as progressive disclosure for focused LanceDB context; it does not mutate source artifacts.
- Every project command runs through Sentinel vNext command protocol: preflight workspace/phase/health guard, CLI execution, trace materialization for mutating commands, and `06_traceability/command_protocol_log.md` anchor.
- `/backlog` and `/quality` are blocked while project health is `DIRTY`; use `/maturity`, `/sync`, `/health`, `/retrieve`, and gap resolution evidence before forcing downstream execution.
- Keep privacy local-only: no remote MCP, external vector databases, or external embeddings for client/project content unless explicitly approved outside this framework.
- If a Codex surface intercepts a native slash command before it reaches the agent, ask the user to send the same request as `sentinel /COMMAND PROJECT_ID`.

## Verification

- Run `python -m unittest discover -s tests` after changing Sentinel runtime code.
- If `python` is unavailable, use the bundled Codex Python runtime.
