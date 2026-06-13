# Ignite Sentinel vNext

**A repo-local, local-first system that matures raw client input into traceable, agent-ready requirements — governed from first note to backlog.**

Most tools generate documents. Ignite Sentinel does something harder: it *matures requirements*. You feed it the messy first version of a client request — a note, a screenshot, a half-formed idea — and it works the material through a governed lifecycle until it becomes a project brief, PRD, specs, backlog, quality artifacts, and a full traceability graph. Nothing is invented along the way: every claim is backed by evidence you can cite, and everything missing is made explicit as a gap, never quietly filled in.

The source of truth is always the versionable files under `workspaces/PROJECT_ID/`. Local memory is a retrieval aid, never the authority. No client content leaves your machine.

---

## Why it's different

- **It matures, it doesn't fabricate.** Every downstream artifact traces back to confirmed evidence. What isn't known yet stays a visible `GAP-*` or `[PENDING INPUT]` — the framework refuses to invent scope.
- **The lifecycle is governed, not just generated.** Gates stop you from building specs on an immature requirement or a backlog on stale context. When a command blocks, it tells you the correct previous step.
- **The agent is a sanctioned analyst, not a free hand.** Agents can deepen discovery (`/annotate`, `/challenge`) and propose normalized requirements — but the runtime validates every contribution against a verbatim quote before it touches an artifact. You stay in control.
- **Local-first by default.** No remote MCP, external vector database, or external embedding service for client content. Runs fully on a locked-down VDI; LanceDB is optional and degrades to deterministic `json-hybrid`; semantic embeddings are optional local packages only.
- **One source, every agent.** The same lifecycle is driven from Codex, Kilo Code, Claude Code/Desktop, an MCP server, or the plain CLI — adapters are generated from a single manifest, so they never drift.

## The lifecycle at a glance

```text
  raw input ──/ingest──▶ discovery gaps ──(optional)──▶ /annotate · /challenge
                              │                          (agentic deepening)
                              ▼
                        /resolve-gaps ──▶ /maturity ──▶ /brief
                     (closes confirmed,      (gates,    (evidence-compiled,
                      normalizes EARS)     telemetry)    per-section readiness)
                              │
                              ▼
                /specs ──▶ /backlog ──▶ /quality ──▶ /trace · /health · /validate
```

Discovery is the heart. The checklist detects what's missing deterministically; the agent can then add the semantic gaps a reassuring keyword would otherwise hide (`/annotate`) and stress-test the requirement with a pre-mortem and per-lens role-play (`/challenge`). When confirmed answers come back, the framework can normalize functional ones into testable **EARS** statements that downstream PRD/spec/backlog artifacts cite as `REQ-EARS-*`, and compile a project brief whose every section is either evidence-backed and cited, or explicitly pending — with per-section readiness and maturation telemetry telling you exactly where discovery is still stuck.

Downstream generation stays progressively disclosed. `/specs` creates a human PRD plus a compact spec index and bounded `SPEC-U-*` units when confirmed EARS evidence exists. `/backlog` derives one value story per confirmed Spec Unit instead of expanding a fixed seed list; if no functional unit exists, it renders a `[PENDING INPUT]` stub and points back to the gaps that must be resolved. It also consumes focused context packs instead of rereading the whole workspace. The retrieval plans that drive those packs live in `sentinel/retrieval_plans/*.json`, and each retrieved result carries a `read_plan` (`source_path`, `section_path`, line anchors) so an agent can jump from summary to source.

---

## Quick Start

First time on a new machine:

```powershell
git clone <REPO_URL>
cd ignite-sentinel
python -m sentinel /doctor
```

`/doctor` verifies Python, the repo-local Kilo/Codex/Claude adapters, write access, and the optional LanceDB memory layer. The core lifecycle has **no mandatory third-party dependencies**. LanceDB is optional — without it Sentinel runs the full lifecycle in deterministic `json-hybrid` memory mode and `/doctor` reports `WARN`, not a failure. To enable vector retrieval where the environment allows it:

```powershell
python -m pip install -e .[memory]
python -m sentinel /doctor
```

Semantic embeddings are a separate optional local layer. They never call an external embedding API at runtime and require a local model path or pre-seeded cache:

```powershell
python -m pip install -e .[memory-semantic]
$env:SENTINEL_MODEL2VEC_MODEL="C:\approved-models\model2vec-multilingual"
python -m sentinel /doctor
```

**Windows note:** if `python` opens the Microsoft Store, it's the App Execution alias — real Python isn't on `PATH`. Use the `py` launcher, run `.\verify.ps1` / `.\installers\sentinel.ps1`, or disable the alias. The repo-local launcher resolves the interpreter for you (tries `SENTINEL_PYTHON`, `.venv`, `python`, `py`, and the bundled Codex runtime):

```powershell
.\installers\sentinel.ps1 /doctor          # Windows
sh installers/sentinel.sh /doctor          # Unix-like
```

Then open the repo root in your editor (`code .`) and drive Sentinel from chat.

## Driving it from chat (recommended)

You don't need to memorize commands. Describe the situation in plain language and the agent maps it to the right sequence:

```text
I have a new client requirement at input\client_requirement\initial-request.md.
Create project ACME_DASHBOARD, ingest it, and tell me the next step.
```

If you prefer exact commands, every surface speaks the same lifecycle:

- **Kilo Code** — slash commands: `/init ACME_DASHBOARD`
- **Codex** — `sentinel` prefix if intercepted: `sentinel /init ACME_DASHBOARD`
- **Claude Code / Desktop** — slash commands from `.claude/commands/` plus `CLAUDE.md` routing
- **Any MCP client** — the local stdio server (`pip install -e .[mcp]`, then `python -m sentinel.mcp`)
- **Terminal** — `python -m sentinel /COMMAND PROJECT_ID [OPTIONS]`

A typical discovery-to-brief run:

```powershell
python -m sentinel /init ACME_DASHBOARD
python -m sentinel /ingest ACME_DASHBOARD --source input\client_requirement\initial-request.md
python -m sentinel /gaps ACME_DASHBOARD
python -m sentinel /annotate ACME_DASHBOARD --source input\interactions\analysis.json   # optional: agentic gaps
python -m sentinel /challenge ACME_DASHBOARD --source input\interactions\findings.json   # optional: pre-mortem
python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /brief ACME_DASHBOARD
```

Downstream, once the brief is mature:

```powershell
python -m sentinel /context-request ACME_DASHBOARD --domain technology
python -m sentinel /specs ACME_DASHBOARD
python -m sentinel /compose ACME_DASHBOARD --source input\interactions\prd-composition.json   # optional: cited PRD narrative
python -m sentinel /backlog ACME_DASHBOARD
python -m sentinel /quality ACME_DASHBOARD
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

See the [Scenarios guide](user_guide/12-scenarios.md) for situation-by-situation walkthroughs written for non-technical users (what to type, what to expect, what the output means).

## Resolving change over time

A requirement keeps moving after discovery. Two distinct flows handle that:

- **Structured gap answers** — when an answered `gaps.md` returns:

  ```powershell
  python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
  python -m sentinel /maturity ACME_DASHBOARD
  ```

  Confirmed answers become seeds and decisions; functional answers written in EARS syntax also become testable `REQ-EARS-*` statements in `requirements.md`, and generated specs/backlog artifacts cite those IDs downstream. Confirmed functional prose is marked `EARS-eligible, not normalized` and counted in `/status` so the BA or agent can propose a separate EARS rewrite for confirmation.

- **New or unmapped information** — meeting notes, email, a demo comment, a late blocker:

  ```powershell
  python -m sentinel /sync ACME_DASHBOARD --source input\change.md --note "client follow-up"
  python -m sentinel /sync ACME_DASHBOARD                 # autonomous novelty scan of known folders
  python -m sentinel /health ACME_DASHBOARD
  ```

Use `/resolve-gaps` for `### GAP-ID` documents; use `/sync` for everything that doesn't map to an existing gap, so new scope becomes traceable change instead of silent scope creep.

If a synced change triggers a gap ID that had already been `CLOSED`, Sentinel records it in the impact report under `Reopened Closed Gaps` and surfaces aggregate counts in `/status` under `maturation_telemetry.reopened_by_sync_*`. The runtime does not silently reopen or rewrite the closed gap; it makes the renewed uncertainty visible for BA review.

After `/specs`, agents may enrich the PRD through `/compose` by submitting JSON blocks with paragraph-level verbatim citations from local source-of-truth evidence. Accepted blocks are marked `Origin: agent`; pending sections and unsupported citations are rejected instead of being filled by narrative guesswork.

When `/specs` is regenerated after changes, Sentinel writes unit-level deltas for `SPEC-U-*` files and propagates stale-unit hints into implementation readiness. Review those deltas before handing existing backlog work to implementation agents.

`/validate` keeps structural validity separate from maturity signals. It returns non-zero only for structural problems, while `semantic_quality` and `cross_artifact_consistency` emit non-blocking warnings for scaffolding content, missing EARS/spec-unit continuity, dangling spec-unit source pointers, or PRD/spec drift. Use those warnings as corrective guidance, not as hardened gates.

## Command Protocol

Every project command runs through the same governed protocol:

1. **Preflight** guard — workspace, phase, health, and command preconditions.
2. **Execution** against versionable workspace artifacts only.
3. **Postflight** trace materialization for mutating commands.
4. **Anchor** in `06_traceability/command_protocol_log.md`.

This keeps execution repo-local, deterministic, and auditable across Codex, Kilo Code, Claude, MCP, and direct CLI usage — and is what lets the gates and traceability be trusted.

## Local memory

Each workspace carries a local memory index under `workspaces/PROJECT_ID/memory.lancedb/`. `/ingest`, `/sync`, and `/reindex` populate it from generated artifacts and domain-owned context folders (technology, design, quality, business, interactions). `/retrieve` builds focused context packs — progressive disclosure — before an agent executes a workflow, so it reads the exact section it needs instead of the whole workspace.

When LanceDB is available, Sentinel uses local hybrid retrieval: vector search plus FTS on `text`, combined with reciprocal rank fusion. When LanceDB is unavailable or degraded, it stays in deterministic `json-hybrid` mode. Chunks are heading-aware, preserve Markdown tables, carry `section_path` plus approximate `line_start` / `line_end` anchors, and reindex incrementally by `source_hash`, `embedding_version`, and `chunking_version`. Generated context packs preserve those anchors as `read_plan`; the index is always reconstructible from the source files and is never the authority.

## Workspace layout

```text
workspaces/PROJECT_ID/
  00_raw/                     # client requirement + domain context (the evidence)
    00_client_requirement/  01_business_context/  02_technology_context/
    03_design_context/      04_quality_context/   05_interactions/
  01_discovery/               # gaps.md, seeds, lens review, annotation & challenge reports
  02_requirements/            # requirements.md (+ EARS), project-brief.md
  03_specs/                   # prd.md, specs.md, SPEC-U units, optional composition reports
  04_backlog/                 # epics, user stories, acceptance criteria
  05_quality/                 # test cases, backlog readiness audit
  06_traceability/            # graph, matrix, command protocol log
  07_changes/                 # client responses, meetings, mail/slack, domain updates
  08_context_packs/           # focused retrieval packs + exports
  memory.lancedb/             # local retrieval index (reconstructible)
  state.json   sentinel.config.yaml
```

The repo also ships `input/` (drop local source files here before ingestion) and `workspaces/_template/` (the versionable empty scaffold). `main` stays clean — no client or test-project data.

## Design rules

- Truth lives in workspace files, not in memory indexes.
- Privacy is local-only by default: no remote MCP, external vector DB, or external embedding service for client content.
- Mutate generated artifacts only through Sentinel commands — never edit downstream outputs by hand.
- Preserve lineage across `RAW`, `REQ`, `GAP`, `DEC`, `PRD`, `SPEC`, `EPIC`, `US`, `AC`, `TC`, and `CHG`.
- Keep `main` a clean framework branch; run real projects in project branches (e.g. `project/ACME_DASHBOARD`) and merge only framework improvements back.
- Tune project domains and maturity gates in `sentinel.config.yaml`.
- Skills are authored once in `.codex/skills/` and mirrored to the Agent Skills standard directories (`.agents/skills/`, `.claude/skills/`); command adapters for Kilo and Claude are generated from a single manifest, so no surface drifts.

## Verification

The recommended one step resolves the interpreter on its own and runs the unit suite, `/doctor`, and the eval harness:

```powershell
.\verify.ps1            # tests + /doctor + evals  (-SkipEvals for just tests + doctor)
```

Equivalent manual steps (use `py` instead of `python` if the Store alias gets in the way):

```powershell
python -m unittest discover -s tests
python -m sentinel /doctor
python tests\evals\run_discovery_evals.py
```

The eval harness covers discovery, brief, PRD, specs, and backlog. Backlog answer keys check expected stories/source units, no-invention behavior, slicing-pattern baseline, and opt-in anchor/context metrics for later backlog work. Retrieval evals run through the unit suite (`tests/test_evals_retrieval.py`) and write gitignored JSON reports under `tests/evals/reports/`, including metrics by active backend (`json-hybrid` or `lancedb-hybrid`) and golden queries across all eval fixtures.

If a change added or modified a command or skill, run `python -m sentinel.adapters` first to regenerate the Kilo/Claude command files and skill mirrors, then verify. Don't push framework changes while tests or `/doctor` fail.

## User documentation

- [User Guide](user_guide/00-user-guide.md) — start here; the lifecycle end to end.
- [Command Reference](user_guide/01-command-reference.md) — every command, its output, and its gate.
- [Artifact Reference](user_guide/02-artifact-reference.md) — what each generated file means.
- [Workflows](user_guide/03-workflows.md) — recommended lifecycle flows.
- [Scenarios](user_guide/12-scenarios.md) — situation → what to run → what to expect (non-technical).
- [Chat Commands](user_guide/11-chat-commands.md) — natural language → command mapping.
- [Codex Skills Guide](user_guide/04-codex-skills-guide.md)
- [Traceability And Memory](user_guide/05-traceability-and-memory.md)
- [VS Code Portable Install](user_guide/06-installation-vscode.md)
- [Kilo Code Adapter](user_guide/07-kilo-code-adapter.md)
- [Codex Adapter](user_guide/08-codex-adapter.md)
- [Secure Environments](user_guide/09-secure-environments.md)
- [Repo And Branching Strategy](user_guide/10-repo-and-branching-strategy.md)
- [Claude Adapter](user_guide/13-claude-adapter.md)
