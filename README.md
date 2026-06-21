# Ignite Sentinel vNext

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Privacy](https://img.shields.io/badge/privacy-local--first-2ea44f.svg)](#design-rules)
[![Lifecycle](https://img.shields.io/badge/lifecycle-discovery%20%E2%86%92%20specs%20%E2%86%92%20backlog-blue.svg)](#the-lifecycle)

> A repo-local, local-first system that **matures** raw client input into traceable, agent-ready requirements — governed from first note to backlog.

Most tools generate documents. Ignite Sentinel does something harder: it *matures requirements*. You feed it the messy first version of a client request — a note, a screenshot, a half-formed idea — and it works the material through a governed lifecycle until it becomes a project brief, PRD, specs, backlog, quality artifacts, and a full traceability graph. **Nothing is invented:** every claim is backed by citable evidence, and everything missing stays an explicit `GAP-*` or `[PENDING INPUT]`.

The source of truth is always the versionable files under `workspaces/PROJECT_ID/`. Local memory is a retrieval aid, never the authority. No client content leaves your machine.

```text
  raw input ──/ingest──▶ discovery gaps ──(optional)──▶ /annotate · /challenge · /scrutinize · /assume
                              │                          (agentic deepening)
                              ▼
                        /resolve-gaps ──▶ /maturity ──▶ /brief
                     (closes confirmed,      (gates,    (evidence-compiled,
                      normalizes EARS)     telemetry)    per-section readiness)
                              │
                              ▼
                /specs ──▶ /backlog ──▶ /quality ──▶ /trace · /health · /validate
```

## Contents

- [Why it's different](#why-its-different)
- [Who it's for](#who-its-for)
- [The lifecycle](#the-lifecycle)
- [Commands](#commands)
- [Quick Start](#quick-start)
- [Driving it from chat](#driving-it-from-chat-recommended)
- [Governed backlog](#governed-backlog)
- [Resolving change over time](#resolving-change-over-time)
- [Command protocol](#command-protocol)
- [Local memory](#local-memory)
- [Workspace layout](#workspace-layout)
- [Design rules](#design-rules)
- [Verification](#verification)
- [FAQ](#faq)
- [Documentation](#documentation)

## Why it's different

- **Purpose-built for maturing requirements — not a generic spec generator.** Unlike general spec-driven (SDD) or BMAD-style frameworks, Ignite targets the specific BA/Product pain: working raw client input into a *robust* spec. Discovery is the heart of the system, not an afterthought.
- **It matures, it doesn't fabricate.** Every downstream artifact traces back to confirmed evidence. What isn't known yet stays a visible `GAP-*` or `[PENDING INPUT]` — the framework refuses to invent scope.
- **The lifecycle is governed, not just generated.** Gates stop you from building specs on an immature requirement or a backlog on stale context. When a command blocks, it tells you the correct previous step.
- **The agent is a sanctioned analyst, not a free hand.** Agents can deepen discovery (`/annotate`, `/challenge`, `/scrutinize`), register BA-owned assumptions (`/assume`), enrich the PRD (`/compose`) and refine the backlog (`/refine-backlog`) — but the runtime validates every contribution against a verbatim quote before it touches an artifact. You stay in control.
- **Vector-backed progressive disclosure.** A *local* vector index (LanceDB, or a deterministic fallback) feeds each phase and activity only the context it needs — generation reads the exact section instead of rereading the whole workspace.
- **Local-first by default.** No remote MCP, external vector database, or external embedding service for client content. Runs fully on a locked-down VDI; LanceDB is optional and degrades to deterministic `json-hybrid`; semantic embeddings are optional local packages only.
- **One source, every agent.** The same lifecycle drives Codex, Kilo Code, Claude Code/Desktop, an MCP server, or the plain CLI — adapters are generated from a single manifest, so they never drift.

## Who it's for

- **Business analysts & product managers** who must turn a vague client request into a defensible brief, PRD, and spec — and need to show *why* every decision is backed by evidence.
- **Consultants & agencies** working client material under privacy constraints, where nothing can leave the machine.
- **Teams handing work to AI coding agents** who want a traceable, agent-ready backlog instead of prompt-and-pray.

If your hardest problem is *maturing* requirements — not writing them up after the fact — this is built for you.

## The lifecycle

Three phases, one governed flow: **Discovery → Specs → Backlog.**

Discovery is the heart. The checklist detects what's missing deterministically; the agent then adds the semantic gaps a reassuring keyword would otherwise hide (`/annotate`), stress-tests the requirement with a pre-mortem and per-lens role-play (`/challenge`), can run cited multi-lens scrutiny across raw input plus domain context (`/scrutinize`), and can register explicit BA-owned assumptions (`/assume`) when the team chooses to proceed with visible risk. Confirmed functional answers are normalized into testable **EARS** statements (`REQ-EARS-*`) that downstream artifacts cite, and the project brief is compiled section by section — each one evidence-backed, explicitly assumed, or pending, with per-section readiness, development certainty, knowledge metabolism, and maturation telemetry showing exactly where discovery is stuck.

Downstream generation stays **progressively disclosed**: each command reads the exact context it needs, never the whole workspace.

## Commands

Drive these from chat in plain language, or call them directly. Every surface speaks the same lifecycle.

**Discovery & maturation**

| Command | What it does |
|---------|--------------|
| `/init` | Create a project workspace |
| `/ingest` | Ingest raw client / domain / interaction evidence and index local memory |
| `/gaps` | (Re)generate the shareable discovery gaps document |
| `/annotate` | Merge agent-proposed **semantic** gaps (verbatim-cited, `origin: agent`) |
| `/challenge` | Advanced elicitation: pre-mortem + per-lens role-play |
| `/scrutinize` | Deep multi-lens scrutiny against raw input and domain context |
| `/self-review` | Skeptical PRD/spec review: cited gaps plus hard-to-reverse decisions |
| `/assume` | Register BA-owned governed assumptions with owner, risk, and cited basis |
| `/resolve-gaps` | Process answered gaps; normalize confirmed functional ones to EARS |
| `/maturity` | Evaluate readiness for specs/backlog (gates + telemetry + development certainty) |
| `/brief` | Compile the evidence-backed project brief |
| `/context-request` | Generate a domain-specific context request |

**Specs**

| Command | What it does |
|---------|--------------|
| `/specs` | Generate the human PRD, a compact spec index, and bounded `SPEC-U-*` units |
| `/compose` | Merge agent-authored PRD narrative with paragraph-level verbatim citations |
| `/self-review` | Register adversarial PRD/spec findings without rewriting the source artifacts |

**Backlog**

| Command | What it does |
|---------|--------------|
| `/backlog` | Derive epics/stories/AC from Spec Units; emit `SLICE-PLAN.md` + readiness packs |
| `/backlog --with-task-seeds` | Add optional task-seed contracts (bounded intentions, never executed) |
| `/backlog-status` | Refresh the BA-facing `04_backlog/BACKLOG.md` rollup board |
| `/story-status` | Govern a story's lifecycle, owner, and DoR/DoD gates (not manual edits) |
| `/refine-backlog` | Merge cited agent refinement proposals (`origin: agent`, BA review) |
| `/implementation-feedback` | Metabolize downstream findings into traced gaps / DoD |
| `/quality` | Score stories (INVEST/SPIDR/Lawrence); write test cases + dynamic audit |

**Change & governance**

| Command | What it does |
|---------|--------------|
| `/sync` | Metabolize new/unmapped info (meetings, mail, blockers) as traceable change |
| `/trace` | (Re)generate the traceability matrix and graph |
| `/health` | Audit workspace health, staleness, and readiness |
| `/validate` | Structural validity + non-blocking quality/consistency warnings |

**Memory & utility**

| Command | What it does |
|---------|--------------|
| `/reindex` | Rebuild local memory incrementally (`--full` for a total rebuild) |
| `/retrieve` | Build a focused context pack (progressive disclosure) |
| `/dashboard` | Generate a local read-only `dashboard.html` portfolio view for all workspaces |
| `/view` | Generate a local read-only HTML view for one artifact |
| `/status` | Phase, health, gap counts, telemetry, and next step |
| `/export` | Export a shareable artifact, including optional local PRD MDX |
| `/doctor` | Verify Python, adapter parity, write access, and the optional memory layer |
| `/sentinel` | Generic fallback to run any command from one entry point |

## Quick Start

First time on a new machine:

```powershell
git clone <REPO_URL>
cd ignite-sentinel
python -m sentinel /doctor
```

`/doctor` verifies Python, the repo-local Kilo/Codex/Claude adapters, command surface parity between runtime and manifest, best-effort command mentions in operational docs, write access, and the optional LanceDB memory layer. The core lifecycle has **no mandatory third-party dependencies** — without LanceDB, Sentinel runs the full lifecycle in deterministic `json-hybrid` mode and `/doctor` reports `WARN`, not a failure.

Optional layers (only where the environment allows):

```powershell
python -m pip install -e .[memory]            # LanceDB vector retrieval
python -m pip install -e .[memory-semantic]   # local semantic embeddings (no external API)
$env:SENTINEL_MODEL2VEC_MODEL="C:\approved-models\model2vec-multilingual"
```

> **Windows note:** if `python` opens the Microsoft Store, it's the App Execution alias — real Python isn't on `PATH`. Use the `py` launcher, run `.\verify.ps1` / `.\installers\sentinel.ps1`, or disable the alias. The repo-local launcher resolves the interpreter for you (`SENTINEL_PYTHON`, `.venv`, `python`, `py`, then the bundled Codex runtime):
>
> ```powershell
> .\installers\sentinel.ps1 /doctor          # Windows
> sh installers/sentinel.sh /doctor          # Unix-like
> ```

## Driving it from chat (recommended)

You don't need to memorize commands. Describe the situation and the agent maps it to the right sequence:

```text
I have a new client requirement at input\client_requirement\initial-request.md.
Create project ACME_DASHBOARD, ingest it, and tell me the next step.
```

For a portfolio view across local workspaces, ask in chat:

```text
Show me the Sentinel dashboard and summarize what needs attention.
```

The `sentinel-dashboard` skill routes that intent to `/dashboard`, generates the git-ignored local `dashboard.html`, and reports the read-only status signals without mutating project artifacts.

For a navigable view of one artifact, run:

```powershell
python -m sentinel /view ACME_DASHBOARD --artifact prd
```

`/view` writes a self-contained read-only HTML snapshot under `workspaces/ACME_DASHBOARD/08_context_packs/views/`. The Markdown artifact remains the source of truth; the HTML is a rebuildable review surface.

The artifact review surface includes:

- a lossless block model behind the view, so sections, tables, decisions, EARS rows, pending markers, assumptions, and traceability signals can be handled without changing the Markdown contract;
- a marker panel for `GAP-*`, pending-input, and governed-assumption signals, with gap/assumption metadata, section certainty badges, and inline anchors;
- citation chips backed by the local traceability graph, including source fragments and one-hop mini graphs when evidence exists;
- guided response mode, which separates client questions from domain and BA/assumption items and tracks local draft progress;
- local anchored comments in `localStorage`, exportable as Markdown for `/resolve-gaps` or `/sync`, with no direct writes from HTML to source artifacts.

For teams that already have an offline MDX renderer, Sentinel can also export a derived local PRD MDX folder:

```powershell
python -m sentinel /export ACME_DASHBOARD --artifact prd --format mdx
```

That writes `08_context_packs/exports/prd-mdx/` with `index.mdx`, `blocks.json`, and `README.md`. It is optional, local-only, and derived from the same block model; it does not install a renderer, call a hosted service, or replace Markdown as the source of truth.

If you prefer exact commands, every surface speaks the same lifecycle:

| Surface | How you invoke it |
|---------|-------------------|
| **Kilo Code** | Slash commands — `/init ACME_DASHBOARD` |
| **Codex** | `sentinel` prefix if intercepted — `sentinel /init ACME_DASHBOARD` |
| **Claude Code / Desktop** | Slash commands from `.claude/commands/` + `CLAUDE.md` routing |
| **Any MCP client** | Local stdio server — `pip install -e .[mcp]`, then `python -m sentinel.mcp` |
| **Terminal** | `python -m sentinel /COMMAND PROJECT_ID [OPTIONS]` |

A typical discovery-to-brief run:

```powershell
python -m sentinel /init ACME_DASHBOARD
python -m sentinel /ingest ACME_DASHBOARD --source input\client_requirement\initial-request.md
python -m sentinel /gaps ACME_DASHBOARD
python -m sentinel /annotate ACME_DASHBOARD --source input\interactions\analysis.json     # optional: agentic gaps
python -m sentinel /challenge ACME_DASHBOARD --source input\interactions\findings.json     # optional: pre-mortem
python -m sentinel /scrutinize ACME_DASHBOARD --source input\interactions\scrutiny.json   # optional: multi-lens scrutiny
python -m sentinel /assume ACME_DASHBOARD --source input\interactions\assumptions.json    # optional: governed assumptions
python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /brief ACME_DASHBOARD
```

Downstream, once the brief is mature:

```powershell
python -m sentinel /specs ACME_DASHBOARD
python -m sentinel /self-review ACME_DASHBOARD --source input\interactions\self-review.json
python -m sentinel /backlog ACME_DASHBOARD
python -m sentinel /backlog-status ACME_DASHBOARD
python -m sentinel /story-status ACME_DASHBOARD --story US-001 --set Ready --owner "Delivery Lead"
python -m sentinel /quality ACME_DASHBOARD
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

See the [Scenarios guide](user_guide/12-scenarios.md) for situation-by-situation walkthroughs written for non-technical users.

## Governed backlog

`/backlog` derives **one value story per confirmed Spec Unit** instead of expanding a fixed seed list. If no functional unit exists, it renders a `[PENDING INPUT]` stub and points back to the gaps that must be resolved. What the phase guarantees:

- **Evidence-derived, never invented.** Stories come from `SPEC-U-*` units and cite their `REQ-EARS-*`; missing evidence becomes a stub, not a guess.
- **Your slicing model, preserved.** Lives in `sentinel/slicing/backlog_slicing_model.json` — INVEST ("small but valuable"), vertical slicing, SPIDR and Lawrence guidance — selecting and explaining one pattern per story.
- **Cross-cutting enablers stay bounded.** Concrete `EPIC-002` enablers must name the capability they support, the risk they reduce, and the evidence that closes them; loose setup is rejected.
- **Progressive disclosure per story.** `backlog_generation.json` keeps the aggregate view plus a `per_story.US-NNN` mini-context; each retrieved result carries a `read_plan` (`source_path`, `section_path`, line anchors) propagated into story execution signals so an agent jumps from summary to the exact source range.
- **Deterministic handoff, no tasking.** `SLICE-PLAN.md` + `slice_plan.json` order enablers first, then parallelizable waves with checkpoints, per-story handoff packs, and a pre-handoff DoR gate (warns by default; blocks only when `backlog_gate.strict` is on). It stops at the seam — Ignite exposes ordering and context, but never creates task IDs or executes implementation.
- **Optional task seeds.** `/backlog --with-task-seeds` adds bounded intentions traced to AC and critical surfaces; default omits them, and even opt-in seeds never execute, estimate, assign, or schedule.
- **Governed lifecycle + rollup.** `/story-status` moves a story through `Draft → Ready → In Progress → In Review → Done` (+ `Blocked`/`Stale`), assigns owner, evaluates DoR/DoD, and refreshes `BACKLOG.md`. `/backlog` preserves status/owner across regeneration.
- **Quality that scores, not just lists.** `/quality` scores each story against the governed INVEST/SPIDR/Lawrence model and writes the dynamic `backlog_readiness_audit.md`, feeding non-blocking DoR warnings via `state.json#story_gates`.
- **Closed feedback loop.** `/implementation-feedback` lets downstream agents return findings (dependencies, gaps, invalid AC, missing surfaces); Sentinel traces them, may open `GAP-FEEDBACK-*`, may mark stories `Stale`, and feeds DoD — without rewriting backlog scope.
- **Privacy at the seam.** Backlog handoff/validation runs a deterministic local scan over `04_backlog/` for credentials, private endpoints, emails, or private identifiers. It warns by default, blocks only with `privacy_scan.mode: block`, and can be disabled with `privacy_scan.mode: off`.

## Resolving change over time

A requirement keeps moving after discovery. Two distinct flows handle that:

- **Structured gap answers** — `/resolve-gaps` on an answered `gaps.md`. Confirmed answers become seeds and decisions; functional answers in EARS syntax become testable `REQ-EARS-*`; confirmed functional prose is marked `EARS-eligible, not normalized` and counted in `/status`. When a confirmed answer validates a governed assumption, Sentinel updates `assumptions.md`, rebuilds `knowledge_state.*`, recomputes `development_readiness.json`, and records the impacted knowledge units.
- **New or unmapped information** — `/sync` for meeting notes, email, Markdown notes, HTML prototypes, a demo comment, or a late blocker, so new scope becomes traceable change instead of silent creep. If the accumulated workspace context is still not mature enough for downstream execution, Sentinel adds a governed `origin: sync` gap to `gaps.md`; if the uncertainty is already answered, it traces the change without duplicating the gap. If a synced change contains a structured confirmed gap response, Sentinel applies it through the same governed closure logic; if it explicitly invalidates an `ASM-*`, Sentinel marks that assumption `INVALIDATED`, opens the ledger unit, recalculates development certainty, and names stale downstream artifacts in the impact report and `/health`.

Other governed channels, each validated against verbatim local evidence:

- **`/compose`** — agents enrich the PRD with cited JSON blocks; accepted blocks are `Origin: agent`, unsupported citations are rejected.
- **`/self-review`** — agents run a skeptical pass over PRD/specs; accepted findings become `origin: self-review` gaps and hard-to-reverse decisions in `03_specs/self_review/`, while PRD/spec files stay unchanged.
- **Spec deltas** — regenerating `/specs` writes unit-level deltas for `SPEC-U-*` and propagates stale-unit hints; a `/sync` that touches a unit's source marks only the stories derived from it as `Stale`.
- **`/refine-backlog`** — agents propose reslicing, split/merge, missing stories, or enabler candidates; accepted proposals land under `04_backlog/refinements/` as `Origin: agent` proposals only.
- **`/implementation-feedback`** — findings are archived under `07_changes/05_implementation_feedback/`, linked as `implementation_feedback`, optionally surfaced as `GAP-FEEDBACK-*`, and can block a story's DoD.

Backlog is intentionally stable after generation. Domain context updates should usually be consumed through `/reindex`, `/retrieve`, and `implementation_readiness.json`; rerun `/backlog` only when the new evidence materially changes story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

`/validate` keeps structural validity separate from maturity: it returns non-zero only for structural problems, while `semantic_quality` and `cross_artifact_consistency` emit non-blocking warnings (scaffolding content, missing EARS/spec-unit continuity, dangling pointers, PRD/spec drift) as corrective guidance.

## Command protocol

Every project command runs through the same governed protocol:

1. **Preflight** guard — workspace, phase, health, and command preconditions.
2. **Execution** against versionable workspace artifacts only.
3. **Postflight** trace materialization for mutating commands.
4. **Anchor** in `06_traceability/command_protocol_log.md`.

This keeps execution repo-local, deterministic, and auditable across Codex, Kilo Code, Claude, MCP, and direct CLI — and is what lets the gates and traceability be trusted.

## Local memory

Each workspace carries a local memory index under `workspaces/PROJECT_ID/memory.lancedb/`. `/ingest`, `/sync`, and `/reindex` populate it from generated artifacts and domain-owned context folders, including Markdown/Text files and HTML prototypes; `/retrieve` builds focused context packs (progressive disclosure) so an agent reads the exact section it needs. Discovery also writes `01_discovery/knowledge_state.md` and `.json`: a lens-by-lens ledger of confirmed, inferred, assumed, and open knowledge, always backed by evidence or `[PENDING INPUT]`. `/maturity` derives `01_discovery/development_readiness.json`, a 16-area lens matrix that distinguishes `CONFIRMED`, `ASSUMED`, and `OPEN` development certainty; `/resolve-gaps` and `/sync` now metabolize confirmed or invalidating evidence back into those same files and flag stale downstream artifacts when knowledge moved after brief/spec/backlog generation.

When LanceDB is available, Sentinel uses local hybrid retrieval (vector + FTS on `text`, combined with reciprocal rank fusion). When it's unavailable or degraded, it stays in deterministic `json-hybrid` mode. Chunks are heading-aware, preserve Markdown tables, carry `section_path` plus approximate `line_start`/`line_end` anchors, and reindex incrementally by `source_hash`, `embedding_version`, and `chunking_version`. Context packs preserve those anchors as `read_plan`. The index is always reconstructible from source files and is never the authority.

## Workspace layout

```text
workspaces/PROJECT_ID/
  00_raw/                     # client requirement + domain context (the evidence)
    00_client_requirement/  01_business_context/  02_technology_context/
    03_design_context/      04_quality_context/   05_interactions/
  01_discovery/               # gaps.md, seeds, knowledge_state, development_readiness, lens review, agentic reports
  02_requirements/            # requirements.md (+ EARS), project-brief.md
  03_specs/                   # prd.md, specs.md, SPEC-U units, optional composition reports
  04_backlog/                 # epics, user stories, acceptance criteria, BA board
  05_quality/                 # test cases, dynamic backlog readiness audit
  06_traceability/            # graph, matrix, command protocol log
  07_changes/                 # client responses, meetings, mail/slack, domain updates
  08_context_packs/           # focused retrieval packs + exports
  memory.lancedb/             # local retrieval index (reconstructible)
  state.json   sentinel.config.yaml
```

The repo also ships `input/` (drop local source files here before ingestion) and `workspaces/_template/` (the versionable empty scaffold). `main` stays clean — no client or test-project data.

## Design rules

- **Truth lives in workspace files,** not in memory indexes.
- **Privacy is local-only by default** — no remote MCP, external vector DB, or external embedding service for client content. The lifecycle runs fully offline on a locked-down machine, so your project data stays yours.
- **Mutate generated artifacts only through Sentinel commands** — never edit downstream outputs by hand.
- **Preserve lineage** across `RAW`, `REQ`, `GAP`, `DEC`, `PRD`, `SPEC`, `EPIC`, `US`, `AC`, `TC`, and `CHG`.
- **Configure to taste** in `sentinel.config.yaml` — project domains, maturity gates, language, and the optional backlog privacy scan.

> **Contributing to the framework itself?** See [MAINTAINERS.md](MAINTAINERS.md) for repository conventions (branching, keeping surfaces in sync, handling examples). Those are maintainer rules for *this* repo — they don't constrain how you use Ignite in your own projects.

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

The eval harness covers discovery, brief, PRD, specs, and backlog. It includes happy-path fixtures plus adversarial lifecycle cases: thin intakes that must remain blocked, partial gap responses that must not over-close discovery, fabricated citations that must be rejected without mutating artifacts, and downstream guards that prevent specs/backlog from running while blocking uncertainty remains. Backlog answer keys also check expected stories/source units, no-invention behavior, slicing-pattern baseline, opt-in anchor/context metrics, optional task-seed contracts, story-quality scoring, pre-handoff DoR warnings, story-level staleness from Spec Unit changes, and implementation feedback that opens traced `GAP-FEEDBACK-*` and blocks DoD. Retrieval evals run through the unit suite (`tests/test_evals_retrieval.py`) and write gitignored JSON reports under `tests/evals/reports/`.

> If a change added or modified a command or skill, run `python -m sentinel.adapters` first to regenerate the Kilo/Claude command files and skill mirrors, then verify. Don't push framework changes while tests or `/doctor` fail.

## FAQ

**Does any client data leave my machine?** No. The lifecycle is local-first: no remote MCP, no external vector database, and no external embedding service for client content. It runs fully on a locked-down VDI.

**Do I need internet or a GPU?** No. The core lifecycle has no mandatory third-party dependencies and runs on CPU. LanceDB and semantic embeddings are optional local layers.

**What happens without LanceDB?** Everything still works — Sentinel falls back to deterministic `json-hybrid` retrieval and `/doctor` reports `WARN`, not a failure.

**Which LLM or agent do I need?** None to run the deterministic lifecycle. An agent (Codex, Claude, Kilo Code, or any MCP client) is optional and only *proposes* contributions — the runtime validates every one against a verbatim citation before it touches an artifact.

**Will it edit my own files?** It only writes inside `workspaces/PROJECT_ID/`, and only through commands. Generated artifacts aren't meant to be hand-edited; you change them by re-running the relevant command.

## Documentation

| Guide | What's inside |
|-------|---------------|
| [User Guide](user_guide/00-user-guide.md) | Start here — the lifecycle end to end |
| [Command Reference](user_guide/01-command-reference.md) | Every command, its output, and its gate |
| [Artifact Reference](user_guide/02-artifact-reference.md) | What each generated file means |
| [Workflows](user_guide/03-workflows.md) | Recommended lifecycle flows |
| [Scenarios](user_guide/12-scenarios.md) | Situation → what to run → what to expect (non-technical) |
| [Chat Commands](user_guide/11-chat-commands.md) | Natural language → command mapping |
| [Dashboard](user_guide/14-dashboard.md) | Local read-only portfolio dashboard across workspaces |
| [Traceability & Memory](user_guide/05-traceability-and-memory.md) | How lineage and retrieval work |
| [Secure Environments](user_guide/09-secure-environments.md) | Running on locked-down VDIs |
| [Repo & Branching Strategy](user_guide/10-repo-and-branching-strategy.md) | How `main` and project branches relate |
| Adapters | [Codex Skills](user_guide/04-codex-skills-guide.md) · [Kilo Code](user_guide/07-kilo-code-adapter.md) · [Codex](user_guide/08-codex-adapter.md) · [Claude](user_guide/13-claude-adapter.md) · [VS Code Install](user_guide/06-installation-vscode.md) |

## License

[MIT](LICENSE) © 2026 jmatzkin1980

Release history lives in [CHANGELOG.md](CHANGELOG.md).
