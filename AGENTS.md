# Ignite Sentinel vNext

## Working Agreements

- Treat this repository as a repo-local framework for BA/Product requirements work in AI PODs, usable from Codex, Kilo Code, or the CLI.
- Keep the source of truth in versionable files under `workspaces/[PROJECT_ID]/`; memory indexes are retrieval aids only.
- Preserve traceability from raw input to requirements, gaps, decisions, specs, backlog, acceptance criteria, tests, and changes.
- Prefer small repo-local agents/skills with progressive disclosure: concise entry instructions, deeper references, reusable templates, and deterministic scripts when possible.

## Framework Operational Memory

- Ignite Sentinel should be usable after cloning the repository on a new laptop or PC, opening the repo root in VS Code, and using Kilo Code or Codex from repo-local files.
- Documentation should be understandable for someone unfamiliar with the framework: prefer Spanish narrative, concrete scenarios, checklists, command examples, and plain explanations over overly synthetic reference notes.
- Discovery is the core upstream workflow: raw client material is iterated through critical product, technology, design, and quality review until it becomes a mature `project-brief.md`.
- A mature requirement should hit the practical sweet spot: enough information for PRD/specs/backlog and for Technology or Design to deepen their own context packs, without pretending to include every low-level implementation contract.
- Gaps must be human-friendly when shared with clients: include project/version context, stable gap IDs, clear questions, answer examples, owner/source, evidence, and decision status.
- The language of generated human artifacts should follow the detected or configured project language. Spanish is the current default expectation unless project context indicates otherwise.
- Privacy is a first-class constraint: prefer local-only operation, local files as source of truth, local LanceDB/JSON indexes as retrieval aids, and no remote MCP or external embeddings for client/code content unless explicitly approved.
- When extracting lessons from chats, examples, prior harnesses, or confidential files, persist only generalized framework rules. Never persist source paths, client names, system names, URLs, account IDs, raw payloads, private business facts, or wording that can identify the inspiration source.
- When improving the framework, update runtime, skills, slash commands, Kilo/Codex adapters, docs, and tests together so the cloned-repo experience remains coherent.
- When the user provides previous framework drafts, external research, examples, or harness outputs, treat them as inspiration only: extract reusable workflow intent, templates, validation ideas, and cognitive patterns, then translate them into agnostic Sentinel rules.
- When the user provides confidential examples, reverse-engineer only generic maturity patterns and never write client-specific names, systems, data, URLs, endpoints, business facts, or decisions into repo artifacts.
- Discovery should not be thin extraction. It should critically pressure-test raw input through Product/BA, Technology, Design, Quality, Delivery, and Compliance lenses, turning uncertainty into explicit gaps or pending seeds.
- Discovery should capture downstream backlog readiness signals when they are knowable: first valuable slice, workflow paths, variants, deferrable rules, meaningful story boundaries, cross-functional dependencies, and concrete enabler candidates from SAD, architecture, design, backend, frontend, integration, data, auth, audit, or observability context.
- Treat Sentinel artifacts as living versionable snapshots. New client evidence, gap responses, Technology/Design/Quality/Delivery context, or domain updates should enter through `/ingest`, `/sync`, `/resolve-gaps`, `/context-request`, or `/reindex`, then refresh impacted artifacts with traceability instead of silently patching downstream documents.
- Backlog slicing should apply INVEST pragmatically. Interpret `Small` as `small but valuable`: the smallest independently meaningful, testable, useful slice. Avoid micro-stories for isolated buttons, endpoints, tables, fields, or technical steps that cannot produce accepted value on their own.
- Backlog artifacts should remain human-readable and agent-friendly: one Markdown file per epic as the primary review unit, embedded story map and stories, individual `US-00x.md` mirrors for traceability/quality handoff, explicit source context, dependencies, acceptance criteria, Definition of Ready, Definition of Done, and trace IDs.
- Backlog generation should consume living multi-domain context through progressive disclosure. Technology may provide architecture, commands, critical surfaces, contracts and practices; Design may provide journeys, states, prototypes and tokens; Quality may provide regression, test data and evidence expectations. Missing domain context must remain visible as pending input rather than invented detail.
- Backlog generation should emit `08_context_packs/implementation_readiness.json` as the machine-friendly handoff contract for planning, implementation, and testing agents, including story readiness, required domains, pending context, retrieval queries, validation expectations, dependencies, trace IDs, and freshness snapshot.
- If Technology, Design, Quality, Delivery, or other domain context changes after backlog generation, `/health` should mark the backlog stale and require `/reindex` plus `/backlog` before implementation handoff.
- Cross-cutting enablers are valid only when they are concrete implementation work that must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces inside the project boundary. Generic setup, broad hardening, environment availability, or vague accessibility/operability work are preconditions or external tasks unless tied to specific project functionality and objective completion evidence.
- Prefer autonomous lifecycle flows that call the right skills/CLI commands and use progressive disclosure via `/retrieve` instead of loading entire workspaces.
- If a user describes a Sentinel situation in plain language instead of providing an exact command, map the intent to the appropriate lifecycle command sequence, run it when safe, and summarize generated artifacts plus the next recommended step.
- Before pushing framework changes to `main`, run the unit suite, `/doctor`, at least one lifecycle smoke test when runtime changed, inspect staged files, and scan staged diffs for sensitive/confidential terms.
- Do not stage or commit unrelated local deletions, generated project workspaces, or user-owned files unless the user explicitly asks to manage them.
- Prefer Spanish explanations for framework behavior unless project language or user request indicates otherwise, with concise but concrete examples of commands, artifacts, inputs, and outputs.

## Ignite Chat Commands

When the user sends an Ignite-style chat command, parse it as a request to run the Sentinel CLI from the repository root.

When the user explains a situation without a command, infer the likely Sentinel workflow. Examples: new client input usually maps to `/init`, `/ingest`, and `/status`; answered gaps map to `/resolve-gaps`, `/maturity`, and `/status`; updated domain context maps to `/reindex` and `/health`; backlog handoff maps to `/backlog`, `/quality`, `/trace`, `/health`, and `/validate` when gates allow it.

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
