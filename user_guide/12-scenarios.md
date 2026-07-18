# Scenarios

This document describes concrete situations that can happen while using Ignite Sentinel vNext. It is written for people working from VS Code with Kilo Code or Codex chat, not only for people comfortable with a terminal.

The normal experience is:

1. Clone or download the repository.
2. Open the repository root folder in VS Code.
3. Open Kilo Code chat or Codex chat.
4. Type a short command or explain what you want to do.
5. Review the generated files under `workspaces/[PROJECT_ID]/`.

All scenarios share the same rule: the source of truth lives in `workspaces/[PROJECT_ID]/`. Local memory is a retrieval aid, not final authority.

## How To Use These Scenarios From Chat

There are three ways to drive Sentinel, in order of preference for non-technical users:

1. **Plain language in chat (recommended).** Just describe your situation; the agent maps it to the right commands. This is the primary flow — you do not need to memorize anything.

   ```text
   I have a new client requirement at input\client_requirement\initial-request.md.
   Create a project called ACME_DASHBOARD, ingest the file, and tell me the next step.
   ```

2. **A specific slash command** when you already know exactly what you want to run. In Kilo Code use the slash command directly (`/status ACME_DASHBOARD`); in Codex add the `sentinel` prefix if the slash command is intercepted (`sentinel /status ACME_DASHBOARD`).

3. **The terminal** only for troubleshooting or restricted environments (see "Terminal Fallback" at the end). Not the primary flow for non-technical users.

Each scenario below shows all three. Start with the plain-language version; the command and terminal forms are there if you need precision or your chat extension is unavailable.

If terminal troubleshooting is needed and `python` is unavailable or invalid on Windows, use:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /status ACME_DASHBOARD
```

## Command Coverage Map

Every canonical Sentinel command appears in at least one scenario below. This table is the auditable index; each scenario shows the command in context. For the exhaustive per-command contract (flags, gates, outputs) see [`01-command-reference.md`](01-command-reference.md) and [`02-artifact-reference.md`](02-artifact-reference.md) — the scenarios reference that reference, they do not restate it.

| Command | Scenario(s) |
| --- | --- |
| `/init` | A1 |
| `/ingest` | A1, A7 |
| `/status` | A1, B1 |
| `/reindex` | A2, C3, F2 |
| `/retrieve` | A2, F1 |
| `/gaps` | A3 |
| `/annotate` | A4 |
| `/challenge` | A5 |
| `/assume` | A8 |
| `/scrutinize` | A9 |
| `/stakeholders` | A10 |
| `/resolve-gaps` | B1, B2 |
| `/maturity` | B1, B3 |
| `/brief` | B3 |
| `/context-request` | C1, C2 |
| `/sync` | B2, E1, E2, E3, E4, G2 |
| `/trace` | B2, D4, E3, G1 |
| `/specs` | D1 |
| `/self-review` | D6 |
| `/compose` | D7 |
| `/backlog` | D2, D3 |
| `/story-status` | D8 |
| `/backlog-status` | D9 |
| `/refine-backlog` | D10 |
| `/implementation-feedback` | D11 |
| `/quality` | D4 |
| `/health` | C3, D5, G1, G2 |
| `/validate` | D5, G1 |
| `/export` | F3, F4 |
| `/view` | F5 |
| `/dashboard` | G5 |
| `/doctor` | G4 |

Sub-flags and skills also have dedicated scenarios:

| Flow / skill | Scenario |
| --- | --- |
| `/sync --digest` (metabolize an unstructured interaction) | E4 |
| `/export --format interview` / `--format faq` | F4 |
| `/scrutinize --mode implementability-probe` | A9 |
| `sentinel-intake-triage` skill (pre-`/init`) | A6 |
| `sentinel-brownfield-harvest` skill | A7 |
| `sentinel-handoff-datasets` skill | G6 |

## Block A: Discovery Start

### Scenario A1: A Client Sends The First Requirement Package

**Context:** The client sends the first set of information. It may be a Markdown file, Mermaid diagrams, an HTML prototype, a business note, screenshots curated by Design, system references, or an incomplete bundle of all of those. No project workspace exists yet.

> **Fictional illustration — for copying into a throwaway project, not for seeding here.** The requirement below is invented for this guide (zero real client data) and deliberately incomplete, so discovery has real gaps to surface. Nothing is seeded under `input/`; if you want to run the flow, paste it into your own scratch file first.

```text
# Internal Expense Approval Tool — Initial Request (FICTIONAL SAMPLE)

We need an internal tool where employees submit expenses and a manager approves them.

- An employee logs in, loads a new expense (amount, date, category, receipt attached) and submits it.
- Their manager receives it and approves or rejects it. Big expenses should need an extra approval.
- Finance should be able to see everything and export it for accounting.
- It has to integrate with our HR system for the employee/manager relationship.
- Obviously it must be secure and compliant.

Categories are the usual ones (travel, meals, software, etc.). We'll sort out the rest of the details later.
```

That sample is intentionally vague exactly where a real discovery pass must probe: "big expenses" names no threshold or currency, "an extra approval" names no second role or approval chain, the HR "integration" names no system, protocol, or direction, "secure and compliant" names no concrete rule, and reimbursement, edit/withdraw, and rejection-with-comments flows are simply absent. Running `/init` + `/ingest` on it should produce a `DIRTY` project with those exact gaps — which is the point.

**In VS Code chat, type:**

```text
/init ACME_DASHBOARD
/ingest ACME_DASHBOARD --source input\client_requirement\initial-request.md
/status ACME_DASHBOARD
```

For Codex, use:

```text
sentinel /init ACME_DASHBOARD
sentinel /ingest ACME_DASHBOARD --source input\client_requirement\initial-request.md
sentinel /status ACME_DASHBOARD
```

Plain-language option:

```text
I have a new client requirement at input\client_requirement\initial-request.md.
Create project ACME_DASHBOARD, ingest it, and summarize the project status.
```

**What Sentinel does:** Creates the workspace, copies the raw input, detects project language, initializes local-first configuration, generates the first requirement record, reviews the material through Product, Technology, Design, Quality, Delivery, and Compliance lenses, and creates gaps when evidence is insufficient.

**Main outputs:**

- `00_raw/`
- `01_discovery/gaps.md`
- `01_discovery/identity_seed_bank.md`
- `01_discovery/lens_review.md`
- `02_requirements/requirements.md`
- `06_traceability/traceability_graph.json`
- `memory.lancedb/memory.json`

**How to interpret it:** If the project becomes `DIRTY`, that is not a failure. It means Sentinel found uncertainty that should be resolved before specs, backlog, or implementation.

### Scenario A2: Domain Context Exists Before Or During Discovery

**Context:** The team already has Technology, Design, Quality, Delivery, or Business context that did not come from the main client document. Examples include architecture notes, endpoints, prototypes, QA rules, compliance restrictions, or rollout constraints.

**Put files here when possible:**

```text
workspaces/ACME_DASHBOARD/00_raw/02_technology_context/
workspaces/ACME_DASHBOARD/00_raw/03_design_context/
workspaces/ACME_DASHBOARD/00_raw/04_quality_context/
workspaces/ACME_DASHBOARD/07_changes/03_domain_updates/
```

**In VS Code chat, type:**

```text
/reindex ACME_DASHBOARD
/retrieve ACME_DASHBOARD --query "endpoint inventory and affected surfaces" --workflow discovery --write-pack
```

For Codex:

```text
sentinel /reindex ACME_DASHBOARD
sentinel /retrieve ACME_DASHBOARD --query "endpoint inventory and affected surfaces" --workflow discovery --write-pack
```

Plain-language option:

```text
Technology and Design added context files to the ACME_DASHBOARD workspace.
Refresh local memory and retrieve focused discovery context about endpoint inventory and affected surfaces.
```

**What Sentinel does:** Indexes domain context locally and makes it available through focused retrieval.

**Main outputs:**

- updated `memory.lancedb/`
- optional `08_context_packs/discovery.json`

**How to interpret it:** Domain context helps close ambiguity, but it does not automatically turn an assumption into confirmed truth. If something remains unsupported or undecided, keep it as a gap.

### Scenario A3: The Team Needs A Client-Friendly Gap Document

**Context:** The initial analysis detected missing information. The team needs a clear document the client can answer without knowing Sentinel internals.

**In VS Code chat, type:**

```text
/gaps ACME_DASHBOARD
```

For Codex:

```text
sentinel /gaps ACME_DASHBOARD
```

Plain-language option:

```text
Generate the client-friendly gap document for ACME_DASHBOARD and tell me where it was written.
```

**What Sentinel does:** Regenerates `01_discovery/gaps.md` in the project language. The document includes metadata, instructions, one section per gap, answer examples, owner/source fields, evidence fields, and decision status.

**Main output:**

- `01_discovery/gaps.md`

**How to interpret it:** This file is both human-friendly and machine-processable. A stakeholder can answer under each `### GAP-ID`, and Sentinel can later process those answers with `/resolve-gaps`.

### Scenario A4: The Agent Spotted Gaps The Checklist Missed

**Context:** While reading the raw requirement, the agent (or you) notices missing information that the automatic checklist did not flag — often because a reassuring keyword is present ("security is important", "there are business rules") even though the substance is undefined. You want those gaps captured properly, not lost.

**In chat, plain language (recommended):**

```text
Read the raw requirement for ACME_DASHBOARD and add the gaps you find that the
checklist missed, citing the exact text from the input for each one.
```

The agent prepares a small analysis file and runs the command for you. If you want to run it yourself once the analysis file exists:

```text
/annotate ACME_DASHBOARD --source input\interactions\analysis.json   (Kilo)
sentinel /annotate ACME_DASHBOARD --source input\interactions\analysis.json   (Codex)
```

**What Sentinel does:** Validates every proposed gap against the raw input — it must quote real text, name a declared lens, and use a valid severity — then merges the valid ones into `gaps.md` tagged `origin: agent`. Anything without a verbatim quote is rejected. The agent proposes; the runtime never invents.

**Main outputs:**

- updated `01_discovery/gaps.md` (new gaps carry `origin: agent`)
- `01_discovery/agent_annotation_log.md` (auditable record with citations)

**How to interpret it:** These gaps behave like any other — share them in `gaps.md` and resolve them with `/resolve-gaps`. The point is that nothing real gets silently dropped just because a keyword was present.

### Scenario A5: Stress-Test The Requirement Before Committing

**Context:** The requirement looks reasonable, but you want to pressure-test what is *not* being said before producing a brief — imagine how it could fail and what nobody asked.

**In chat, plain language (recommended):**

```text
Run a pre-mortem on ACME_DASHBOARD: imagine the project failed six months after
launch and tell me what we failed to ask, per lens. Capture the findings as gaps.
```

If you prefer the exact command (after the agent writes the findings file):

```text
/challenge ACME_DASHBOARD --source input\interactions\findings.json   (Kilo)
sentinel /challenge ACME_DASHBOARD --source input\interactions\findings.json   (Codex)
```

**What Sentinel does:** The agent runs the default `/challenge` techniques per lens — pre-mortem, role-play (operator, auditor, attacker...), assumption inversion, and JTBD Four Forces — from the declarative catalog in `sentinel/techniques/*.json` (red/blue team, first principles, and stakeholder round-robin are opt-in additions). Each finding is validated against the raw input exactly like `/annotate`, merged as a gap tagged `origin: challenge`, and summarized in a versionable report.

**Main outputs:**

- updated `01_discovery/gaps.md` (gaps with `origin: challenge`)
- `01_discovery/challenge_report.md` (findings grouped by lens and technique, plus imagined failures and inverted assumptions)

**How to interpret it:** This is how you surface the risks a client never states. The findings enter the normal `/resolve-gaps` → `/maturity` flow, so the challenge becomes traceable evidence, not a lost conversation.

### Scenario A6: Triage A Pile Of Unstructured Intake Before Starting

**Context:** You were handed a pile of raw intake — a stack of client requests, an RFQ inbox, a thread of mails or chat messages — and it is not yet clear how many projects it should become or what is even in scope. No workspace exists yet, and running `/init` blindly would fuse unrelated value streams into one project.

**What it is for:** The `sentinel-intake-triage` skill turns that pile into a cited, BA-reviewable triage proposal before any workspace exists. It is strictly the pre-`/init` step; once a project exists, new material flows through `/ingest` (fresh evidence) or `/sync` (changes) instead.

**In chat, plain language (recommended):**

```text
Triage these initial requests for me: group them by theme with a verbatim quote for
each, propose requirement candidates, tell me whether this is one project or several,
and flag anything that is noise or out of scope.
```

**What it needs:** The raw intake items available locally. No command, no workspace, no gates — this is a skill, not a CLI command. Cite-or-silent: every theme, candidate, and out-of-scope call must quote a source item.

**What it produces:** A triage proposal rendered inline (or as a local scratch note, not a governed artifact) — themes grouped with a verbatim citation per source item (`R1`, `R2`, …), one-line requirement candidates, a one-project-or-N recommendation with rationale, and an explicit out-of-scope list. The skill proposes and never runs `/init` itself. Only after you confirm the split do you run `/init PROJECT_ID` then `/ingest` per project, routing each `R#` source to its assigned project so the citations become governed discovery evidence.

### Scenario A7: Harvest An Existing Codebase For Technical Context (Brownfield)

**Context:** The project extends or touches a system that already exists in code, that codebase is available on this machine, and you need its real architecture, surfaces, integrations, data models, and constraints as grounded evidence instead of assumptions.

**What it is for:** The `sentinel-brownfield-harvest` skill reads the existing code and writes cited technical-context docs that the normal `/ingest` then consumes as technical domain evidence — no runtime change. It reads code; it does not interview people (that is `/context-request --domain technology`, see C1), and it is not for greenfield projects (nothing to harvest).

**In chat, plain language (recommended):**

```text
Harvest the existing system at <local path> for ACME_DASHBOARD: read the code and write
cited technical context — architecture, integrations, data models, constraints — marking
every claim OBSERVED or INFERRED.
```

**What it needs:** The existing system's repository present locally, plus an initialized workspace to write into. Privacy is non-negotiable: the code never leaves the machine (no external service, remote embeddings, or remote MCP), and only genericized patterns/structure are persisted — never client names, system names, endpoints, or credentials.

**What it produces:** One or more Markdown docs under `00_raw/02_technology_context/`, each a set of headings whose every bullet is a single claim tagged `[OBSERVED]` (backed by a code citation) or `[INFERRED]`, with unknowns left as `[PENDING DOMAIN CONTEXT]`. These are ordinary domain-context inputs — not a governed artifact of their own; hand them to `/ingest ACME_DASHBOARD --source ...` so discovery, `/gaps`, and specs can cite the harvested context.

### Scenario A8: Proceed With An Explicit Governed Assumption

**Context:** Discovery surfaced uncertainty the team wants to move past deliberately — not by hiding it and not by pretending it is confirmed. The BA chooses to proceed on a stated assumption, with an owner and a risk attached.

**What it is for:** `/assume` registers governed, BA-owned assumptions so uncertainty stays visible and traceable rather than silently baked into downstream artifacts. Authoring the structured findings is the `sentinel-assume` skill; the runtime validates and merges them.

**In chat, plain language (recommended):**

```text
We are going to proceed on the assumption that approvals are single-manager for now.
Register it for ACME_DASHBOARD as a BA-owned assumption, high risk, citing the input,
and keep it visible in maturity.
```

Exact command (after the agent writes the assumptions file):

```text
/assume ACME_DASHBOARD --source input\interactions\assumptions.json   (Kilo)
sentinel /assume ACME_DASHBOARD --source input\interactions\assumptions.json   (Codex)
```

**What it needs:** A JSON `assumptions[]` source; each item declares an `ASM-*` id, a lens, the `statement`, a human `owner`, `risk` and `uncertainty` (low/med/high), a verbatim local `justification` quote, and optionally `closes_gap` and a Cagan `risk_category` (value/usability/viability/feasibility). The runtime rejects any assumption without a valid lens, owner, risk, and local quote — it never invents one.

**What it produces:** `01_discovery/assumptions.md` (grouped by `risk_category` when declared), an archived source copy, refreshed `knowledge_state.md/.json` with `ASSUMED` units, an `assumption_register` trace node, and `maturity_metrics.assumptions` surfaced in `/maturity` and `/status`. Assumptions never become confirmed evidence; `risk=high` + `uncertainty=high` shows as a non-blocking "test before advancing" signal.

### Scenario A9: Deep Multi-Lens Scrutiny (And The Implementability Probe)

**Context:** The requirement is maturing and you want a systematic pass that crosses the client's stated requirement with local domain context (Technology, Design, Quality, Delivery, Compliance) to surface unstated assumptions, contradictions, mentions without a counterpart, and domain conflicts. A related need: before a coding agent starts, confirm each requirement unit is actually implementable.

**What it is for:** `/scrutinize` runs deep multi-lens scrutiny and merges cited findings as gaps tagged `origin: scrutiny`. Its `--mode implementability-probe` sub-mode is the pre-flight, per-`RU-*` mirror of `/implementation-feedback` (see D11): the agent declares up front what it is missing to implement each requirement unit. The `sentinel-scrutiny` skill authors the findings.

**In chat, plain language (recommended):**

```text
Run deep scrutiny on ACME_DASHBOARD crossing the client requirement with the ingested
technology and quality context; capture contradictions and unstated assumptions as gaps.
```

Exact commands (after the agent writes the findings file):

```text
/scrutinize ACME_DASHBOARD --source input\interactions\scrutiny.json [--lens technical]
/scrutinize ACME_DASHBOARD --mode implementability-probe --source input\interactions\probe.json
```

For Codex prefix each with `sentinel`.

**What it needs:** A JSON `gaps` array; each finding declares `id`, `lens`, `severity`, `finding_type`, `question`, and verbatim `evidence`, validated against raw input and domain-context folders. `--lens` optionally rejects out-of-lens findings. In probe mode every finding must carry a real `RU-*` `unit` anchor and a probe-specific `finding_type` (`missing-context`, `non-inferable-gap`, or `ambiguous-for-implementation`).

**What it produces:** Updated `gaps.md` (gaps tagged `origin: scrutiny`, or `origin: implementability-probe`), `01_discovery/scrutiny_report.md` (or `implementability_probe_report.md` grouped by RU), a copied source, a trace node, refreshed `knowledge_state.*`, and `gap_counts.scrutiny_origin` / `gap_counts.implementability_probe_origin` in `state.json` (visible in `/status`). Nothing is auto-resolved.

### Scenario A10: Register Stakeholders And Route Elicitation By Owner

**Context:** Several people own different domains and topics, and you want the gap questions to reach the right owner instead of a generic "ask the client" bucket.

**What it is for:** `/stakeholders` maintains the governed stakeholder registry and enables deterministic routing: with a non-empty registry the interview export (see F4) groups open gaps by owner. Power×Interest scoring and communication plans are intentionally out of scope (delivery, not discovery).

**In VS Code chat, type:**

```text
/stakeholders ACME_DASHBOARD
/stakeholders ACME_DASHBOARD --add --name "Operations Lead" --domain business --topic "approval thresholds"
```

For Codex prefix with `sentinel`.

Plain-language option:

```text
Register the Operations Lead as the business owner for approval thresholds in ACME_DASHBOARD, then list the registry.
```

**What it needs:** For `--add`, a `--name` and a `--domain` (a lens: product, technical, business, design, quality); optionally `--id STK-NNN` (auto-assigned when omitted; a duplicate id is rejected), `--profile business|technical`, `--topic`, and `--notes`. The registry is mutable only through this command — never hand-edited.

**What it produces:** `01_discovery/stakeholders.md`. Downstream, a gap whose lens has no registered owner is listed under an explicit **unassigned** heading in the interview export — never a fabricated owner.

## Block B: Gap Resolution And Maturity

### Scenario B1: The Client Returns Answered Gaps

**Context:** The client or a domain owner returns the answered `gaps.md`. Some answers are confirmed, some partial, and some still pending.

**In VS Code chat, type:**

```text
/resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
/maturity ACME_DASHBOARD
/status ACME_DASHBOARD
```

For Codex:

```text
sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
sentinel /maturity ACME_DASHBOARD
sentinel /status ACME_DASHBOARD
```

Plain-language option:

```text
The client answered gaps in input\interactions\answered-gaps.md.
Process the answers for ACME_DASHBOARD, check maturity, and tell me what remains open.
```

**What Sentinel does:** Reads `### GAP-ID` sections, extracts answers, owner/source, evidence, and decision status. It closes a gap automatically only when there is a non-empty answer with a confirmed or not-applicable decision status.

**Main outputs:**

- `01_discovery/gap_resolution_log.md`
- `07_changes/00_client_responses/`
- updated `01_discovery/gaps.md`
- updated `01_discovery/requirement_maturity_report.md`

**How to interpret it:** `CLOSED` means the answer can be used as confirmed truth. `PARTIALLY_CLOSED` means useful information arrived, but not enough to unblock maturity if the gap is critical or high severity. Tip: when a confirmed answer to a functional gap is written in EARS form ("When <trigger>, the system shall <response>." and the other four patterns, in English or Spanish), Sentinel also records it as a testable `REQ-EARS-*` statement in `requirements.md`, so specs and backlog inherit precise, parseable requirements instead of prose.

### Scenario B2: The Gap Response Adds New Scope

**Context:** The client answers a gap but also introduces something new, such as a new export, a new user type, or a behavior not covered by existing gaps.

**In VS Code chat, type:**

```text
/resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
/sync ACME_DASHBOARD --source input\interactions\answered-gaps.md --note "gap response includes new scope"
/trace ACME_DASHBOARD
```

For Codex, prefix with `sentinel`.

Plain-language option:

```text
The answered gaps file also includes new scope.
Process the known gap answers, register the new information as a change, and refresh traceability for ACME_DASHBOARD.
```

**What Sentinel does:** `/resolve-gaps` processes what maps to existing structured gaps. `/sync` registers new content as a change event and creates an impact report.

**Main outputs:**

- `07_changes/00_client_responses/`
- `07_changes/03_domain_updates/` or another change bucket, depending on source type
- impact report linked as a decision node
- new `CHG` trace node

**How to interpret it:** Not all feedback should close a gap. If new scope appears, treat it as a change or new requirement signal so the brief, specs, and backlog do not silently absorb scope creep.

### Scenario B3: The Project Is Mature Enough For A Brief

**Context:** Discovery has enough confirmed evidence. Critical and high blocking gaps are resolved or explicitly accepted as non-blocking.

**In VS Code chat, type:**

```text
/maturity ACME_DASHBOARD
/brief ACME_DASHBOARD
```

For Codex:

```text
sentinel /maturity ACME_DASHBOARD
sentinel /brief ACME_DASHBOARD
```

Plain-language option:

```text
Check whether ACME_DASHBOARD is mature enough for specs.
If it is ready, generate or refresh the project brief.
```

**What Sentinel does:** Evaluates gap status and compiles `02_requirements/project-brief.md` section by section from real evidence (requirements, closed-gap answers, seeds, decisions, raw input), citing the source for each claim; sections with no evidence stay as explicit `[PENDING INPUT]` instead of invented text. It also reports per-section readiness: how many of the six narrative sections are evidence-backed, and which gaps would fill the weak ones.

**Main outputs:**

- `01_discovery/requirement_maturity_report.md`
- `02_requirements/project-brief.md`

**How to interpret it:** Read the `brief_section_readiness` and warnings in the output: if a section is still poor, the message names the gaps that feed it, so you know exactly what to ask for next. By default a low-coverage brief is generated with a warning (not blocked); a team can opt into a strict mode (workspace config `brief_gate`) that holds the brief back until coverage improves. `/status` and `/maturity` also show maturation telemetry — how many resolve rounds ran and how the oldest blocking gap is aging — so you can see where things are stuck. The brief should be clear enough for PRD/specs/backlog and for Technology or Design to deepen their own context packs, without pretending to contain every implementation-level contract.

## Block C: Domain Context Requests

### Scenario C1: Technology Needs A Focused Context Request

**Context:** The product requirement is mature enough for Technology to analyze affected systems, architecture, data, integration, commands, risks, and implementation surfaces.

**In VS Code chat, type:**

```text
/context-request ACME_DASHBOARD --domain technology
```

For Codex:

```text
sentinel /context-request ACME_DASHBOARD --domain technology
```

Plain-language option:

```text
Create a Technology context request for ACME_DASHBOARD so the tech owner knows what architecture, surfaces, commands, and risks to document.
```

**Main output:**

- `08_context_packs/requests/technology_context_request.md`

**How to interpret it:** This does not replace technical analysis. It tells Technology what to deepen and which brief/gap references should guide the work.

### Scenario C2: Design Needs A Focused Context Request

**Context:** The requirement is mature enough for Design to analyze journeys, screens, states, prototypes, copy, accessibility, and validation behavior.

**In VS Code chat, type:**

```text
/context-request ACME_DASHBOARD --domain design
```

For Codex:

```text
sentinel /context-request ACME_DASHBOARD --domain design
```

Plain-language option:

```text
Create a Design context request for ACME_DASHBOARD focused on journeys, screens, states, prototype needs, and accessibility.
```

**Main output:**

- `08_context_packs/requests/design_context_request.md`

**How to interpret it:** Sentinel does not produce the final prototype. It makes the request to Design concrete, traceable, and based on mature discovery.

### Scenario C3: Domain Owners Update Their Context Files

**Context:** Technology, Design, Quality, or Delivery adds new context after PRD, specs, or backlog were generated.

**In VS Code chat, type:**

```text
/reindex ACME_DASHBOARD
/health ACME_DASHBOARD
```

For Codex:

```text
sentinel /reindex ACME_DASHBOARD
sentinel /health ACME_DASHBOARD
```

Plain-language option:

```text
Domain owners updated context files for ACME_DASHBOARD.
Refresh memory and check whether any downstream artifacts are stale.
```

**What Sentinel does:** Rebuilds local memory and checks whether downstream artifacts may be stale.

**How to interpret it:** If `/health` reports that domain context changed after backlog generation, first use `/reindex` and focused `/retrieve` so implementation agents consume the current context. Rerun `/backlog` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

## Block D: Specs, Backlog, And Quality

### Scenario D1: Generate PRD And Specs

**Context:** A mature `project-brief.md` exists. The team needs a PRD for humans and a compact, agent-friendly spec.

**In VS Code chat, type:**

```text
/specs ACME_DASHBOARD
```

For Codex:

```text
sentinel /specs ACME_DASHBOARD
```

Plain-language option:

```text
Generate the PRD and agent-friendly specs for ACME_DASHBOARD from the mature project brief.
```

**Main outputs:**

- `03_specs/prd.md`
- `03_specs/specs.md`
- `03_specs/units/SPEC-U-NNN.md` when confirmed EARS requirements exist
- `08_context_packs/specs_generation.json`

**How to interpret it:** The PRD explains what should be built and why. `specs.md` acts as the compact operational contract and index for agents. `SPEC-U-*` files are the bounded, evidence-backed execution units. `specs_generation.json` records the declarative retrieval plan and `read_plan` source anchors used during generation.

### Scenario D2: Generate Backlog With Execution Readiness

**Context:** Specs exist and health allows downstream generation.

**In VS Code chat, type:**

```text
/backlog ACME_DASHBOARD
```

For Codex:

```text
sentinel /backlog ACME_DASHBOARD
```

Plain-language option:

```text
Generate the backlog for ACME_DASHBOARD with epics, user stories, acceptance criteria, retrieval plans, and implementation readiness.
```

**Main outputs:**

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- optional `04_backlog/EPIC-002-cross-cutting-enablers.md`
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`

**How to interpret it:** This is an initial traceable backlog, not the final sprint plan. Review whether stories are vertical, valuable, testable, and correctly bounded. Check that missing domain context remains visible instead of invented.

### Scenario D3: A Cross-Cutting Enabler Is Needed

**Context:** The project needs concrete implementation work in advance, such as shared auth rules, an API contract, a persistence/query capability, an integration contract, audit logging, or a UI shell that supports multiple confirmed stories.

**In VS Code chat, type:**

```text
/backlog ACME_DASHBOARD
```

Plain-language option:

```text
Generate or refresh the backlog for ACME_DASHBOARD.
Pay special attention to whether a cross-cutting enabler epic is justified by the available evidence.
```

**What Sentinel does:** If evidence is specific enough, creates `EPIC-002-cross-cutting-enablers.md`.

**How to interpret it:** Valid enablers support confirmed functionality across stories, epics, FRs, or implementation surfaces. Generic environment setup, broad hardening, or vague "make this accessible" work should not become backlog enablers unless tied to project-specific functionality and objective completion evidence.

### Scenario D4: Generate Quality Artifacts

**Context:** User stories and acceptance criteria exist.

**In VS Code chat, type:**

```text
/quality ACME_DASHBOARD
/trace ACME_DASHBOARD
```

For Codex, prefix each line with `sentinel`.

Plain-language option:

```text
Generate quality artifacts for ACME_DASHBOARD from the backlog, then refresh traceability.
```

**Main outputs:**

- `05_quality/TC-001.md`
- `05_quality/backlog_readiness_audit.md`
- updated traceability graph and matrix

**How to interpret it:** Quality artifacts should preserve fail-to-pass, pass-to-pass, and evidence expectations. They are a test-planning handoff, not proof that implementation has already been tested.

### Scenario D5: Backlog Or Quality Is Blocked

**Context:** Someone tries to generate backlog or quality while health is `DIRTY`.

**In VS Code chat, type:**

```text
/health ACME_DASHBOARD
/validate ACME_DASHBOARD
```

Plain-language option:

```text
Backlog or quality generation is blocked for ACME_DASHBOARD.
Check health and validation, then explain what needs to be fixed before continuing.
```

**How to interpret it:** This protects the team from generating documentary debt or stories based on unresolved assumptions. Fix gaps, context, traceability, or stale artifacts first.

### Scenario D6: Adversarial Self-Review Of PRD/Specs Before Handoff

**Context:** `/specs` produced a PRD and spec layer, and before backlog handoff you want a skeptical pass — implicit decisions, costly-to-reverse choices, missing reuse/brownfield deltas, assumptions that should stay visible.

**What it is for:** `/self-review` registers cited skeptical findings and hard-to-reverse `DEC-*` decisions **without rewriting the artifacts under review** — the runtime never edits the PRD/specs. The `sentinel-self-review` skill authors the findings.

**In chat, plain language (recommended):**

```text
Do an adversarial self-review of the ACME_DASHBOARD PRD and specs: flag implicit
decisions and hard-to-reverse choices, cite the exact text, and register them.
```

Exact command (after the agent writes the JSON):

```text
/self-review ACME_DASHBOARD --source input\interactions\self-review.json   (Kilo)
sentinel /self-review ACME_DASHBOARD --source input\interactions\self-review.json   (Codex)
```

**What it needs:** `/specs` already run. A JSON source with `gaps[]`, `decisions[]`, or both. Gaps reuse the cited-gap rules; each decision needs a `DEC-*` id, a declared `risk`, a `reversibility`, and verbatim local evidence from the generated PRD/spec context. ADR-grade fields (`consequences[]`, `considered_options[]`, `supersedes`) are optional and backwards-compatible.

**What it produces:** Updated `01_discovery/gaps.md` only when new cited gaps are accepted, an archived source under `03_specs/self_review/`, `self_review_report.md` and `decision_register.md`, trace nodes for the review event and hard-to-reverse decisions, and `gap_counts.self_review_origin` + `last_self_review_id` in `state.json`. It is a review channel, not an automatic repair pass; changing the narrative still goes through upstream evidence, `/compose`, `/sync`, or a regenerated `/specs`.

### Scenario D7: Enrich The PRD Narrative With Cited Agent-Authored Blocks

**Context:** The generated PRD is accurate but thin in places, and an agent can propose better-written narrative — as long as every sentence is backed by local evidence.

**What it is for:** `/compose` merges validated agent-authored narrative blocks into the PRD as an `Agent Composition` subsection tagged `Origin: agent`. It is a falsable enrichment path, not permission to fill unknown scope, and never a hand-edit to `prd.md`. The `sentinel-compose` skill authors the blocks.

**In chat, plain language (recommended):**

```text
Improve the wording of the ACME_DASHBOARD PRD overview section with agent-authored
paragraphs, each citing local evidence verbatim.
```

Exact command:

```text
/compose ACME_DASHBOARD --source input\interactions\composition.json   (Kilo)
sentinel /compose ACME_DASHBOARD --source input\interactions\composition.json   (Codex)
```

**What it needs:** `/specs` already produced `03_specs/prd.md`. A JSON with `blocks[]`; each block names a PRD section and paragraphs, and every paragraph must cite text found verbatim in `00_raw/`, `01_discovery/`, `02_requirements/`, or `07_changes/`. Blocks that target a pending section, cite text not found verbatim, or narrate unresolved pending markers are rejected.

**What it produces:** Updated `03_specs/prd.md` with the `Agent Composition` subsection, an archived source under `03_specs/compositions/`, `accepted_blocks.json`, `composition_report.md`, and a trace node/edge from the PRD to the composition event. On a later `/specs` regeneration only still-valid accepted blocks are reapplied.

### Scenario D8: Move A Story Through Its Governed Lifecycle

**Context:** A backlog exists and a story needs its status or owner updated — marked `Ready` for pickup, `In Progress`, `Done` with acceptance evidence, or `Blocked`.

**What it is for:** `/story-status` is the only supported mutation path for story status or owner. It validates legal transitions and evaluates DoR/DoD gates; you never hand-edit `US-NNN.md`, `state.json`, or `BACKLOG.md`. The `sentinel-backlog` skill covers the lifecycle model.

**In VS Code chat, type:**

```text
/story-status ACME_DASHBOARD --story US-001 --set Ready --owner "Delivery Lead"
/story-status ACME_DASHBOARD --story US-001 --set Done --evidence input\interactions\acceptance-evidence.md
```

For Codex prefix with `sentinel`.

Plain-language option:

```text
Mark US-001 in ACME_DASHBOARD as Ready and assign the Delivery Lead.
```

**What it needs:** `/backlog` already run. `--story` and `--set` (one of `Draft`, `Ready`, `In Progress`, `In Review`, `Done`, `Blocked`, `Stale`); optional `--owner` and `--evidence PATH`. Marking `Ready` freezes a versioned acceptance-criteria snapshot. The `backlog_gate` is soft by default (warns on missing checklist items); strict opt-in blocks `Ready` when DoR is incomplete and `Done` without traced acceptance evidence.

**What it produces:** Updated `state.json`, the target `US-NNN.md` frontmatter/lifecycle/checklists, an appended `04_backlog/status_log.md`, a refreshed `04_backlog/BACKLOG.md`, copied evidence under `04_backlog/acceptance_evidence/` when `--evidence` is used, and traceability plus the command protocol log.

### Scenario D9: Regenerate The BA Backlog Board

**Context:** Story statuses or gates changed and the team wants the current review board and rollup.

**What it is for:** `/backlog-status` materializes the BA-facing board and rollup from existing source-of-truth artifacts. It only builds the view; it changes no story status, owner, gate evidence, slicing rationale, or the `EPIC-002` enabler boundary.

**In VS Code chat, type:**

```text
/backlog-status ACME_DASHBOARD
```

For Codex prefix with `sentinel`.

Plain-language option:

```text
Refresh the backlog board for ACME_DASHBOARD.
```

**What it needs:** `/backlog` already created story files. It reads `state.json#story_lifecycle` / `#story_gates`, the `US-NNN.md` files, and `08_context_packs/implementation_readiness.json`.

**What it produces:** `04_backlog/BACKLOG.md` and a persisted `state.json#backlog_rollup`. Do not hand-edit `BACKLOG.md`.

### Scenario D10: Propose Governed Backlog Refinements

**Context:** A story is too big, two should merge, one is missing, or an enabler candidate emerged — and you want it recorded as a reviewable proposal grounded in citations, not a silent rewrite.

**What it is for:** `/refine-backlog` merges validated agent-authored refinement proposals as an `Agent Backlog Refinements` overlay tagged `Origin: agent`. It preserves the existing INVEST/SPIDR/Lawrence and `EPIC-002` enabler-boundary model; the BA still decides what a future regeneration acts on. The `sentinel-backlog-refine` skill authors proposals.

**In chat, plain language (recommended):**

```text
US-003 is too big for ACME_DASHBOARD — propose a vertical reslice, citing the spec
units verbatim, as an agent proposal for BA review.
```

Exact command:

```text
/refine-backlog ACME_DASHBOARD --source input\interactions\backlog-refinement.json   (Kilo)
sentinel /refine-backlog ACME_DASHBOARD --source input\interactions\backlog-refinement.json   (Codex)
```

**What it needs:** `/backlog` already created `04_backlog/EPIC-001.md`, and health not `DIRTY`. A JSON with `proposals[]`; each declares a `kind` (`reslice`, `split-story`, `merge-stories`, `missing-story`, or `enabler-candidate`), targets, a recommendation, rationale, and verbatim citations. Enabler candidates must declare enabled stories, supported boundary, a concrete `enabled_capability`, a measurable `verification_method`, risk reduced, and objective evidence. Proposals targeting unknown/pending stubs, citing text not found verbatim, grounding on pending Spec Units, or promoting loose preconditions into enablers are rejected.

**What it produces:** Updated `04_backlog/EPIC-001.md` and targeted `04_backlog/US-NNN.md` files with the overlay section, an archived source under `04_backlog/refinements/`, `accepted_refinements.json`, `refinement_report.md`, and trace nodes/edges to the refinement event.

### Scenario D11: A Downstream Agent Reports An Implementation Blocker

**Context:** A planning, implementation, or testing agent hits a blocker in a story — a new dependency, a discovery gap, an acceptance criterion that cannot hold, or an uncovered surface — and must report it through governance instead of silently changing scope.

**What it is for:** `/implementation-feedback` records evidence-backed downstream findings for BA/Product review. It does not rewrite stories, acceptance criteria, slicing, or enabler boundaries; it may mark only affected stories `Stale` and may block `Done` via DoD. The `sentinel-implementation-feedback` skill authors findings.

**In chat, plain language (recommended):**

```text
The implementation of US-002 in ACME_DASHBOARD found the acceptance criterion can't
hold without an HR-sync dependency. Register it as governed feedback.
```

Exact command:

```text
/implementation-feedback ACME_DASHBOARD --source input\interactions\implementation-feedback.json   (Kilo)
sentinel /implementation-feedback ACME_DASHBOARD --source input\interactions\implementation-feedback.json   (Codex)
```

**What it needs:** `/backlog` already run. A JSON with `findings[]`; each declares a `type` (`new-dependency`, `gap`, `ac-challenge`, or `surface-not-covered`), a target `story`, optional `acceptance_criteria`, `summary`, `evidence`, optional `source_units` / `gap_id`, `blocks_dod`, and `mark_stale`.

**What it produces:** An archived source under `07_changes/05_implementation_feedback/`, a `feedback_report.md`, an optional `01_discovery/implementation_feedback_gaps.md` for `GAP-FEEDBACK-*`, `state.json#implementation_feedback`, an updated DoD item `implementation_feedback_resolved` on affected stories, and trace nodes/edges. Default gates warn; strict mode blocks closure while open blocking feedback remains.

## Block E: Change Management

### Scenario E1: A Stakeholder Sends New Information

**Context:** The client, POD, or stakeholder sends an email, Slack message, demo comment, meeting note, architecture update, design update, QA observation, or delivery decision that changes scope, priority, or behavior.

**In VS Code chat, type:**

```text
/sync ACME_DASHBOARD --source input\interactions\demo-feedback.md --note "demo feedback"
```

For Codex:

```text
sentinel /sync ACME_DASHBOARD --source input\interactions\demo-feedback.md --note "demo feedback"
```

Plain-language option:

```text
The file input\interactions\demo-feedback.md contains new stakeholder feedback for ACME_DASHBOARD.
Register it as a change and summarize possible impact.
```

**Main outputs:**

- `07_changes/`
- impact report
- updated traceability graph
- updated local memory

**How to interpret it:** `/sync` does not magically patch every downstream artifact. It identifies impact and preserves evidence so the team can update brief, specs, backlog, or tests with control.

### Scenario E2: Autonomous Novelty Scan

**Context:** Several files were added or modified in known input or context folders. The team does not want to process each one manually.

**In VS Code chat, type:**

```text
/sync ACME_DASHBOARD
```

Plain-language option:

```text
Scan ACME_DASHBOARD for new or modified input and context files, register any changes, and tell me what was processed.
```

**How to interpret it:** This is useful for periodic scans. If a file is an answered `gaps.md`, use `/resolve-gaps` first to preserve structured gap closure.

### Scenario E3: A Meeting Changes The Shared Understanding

**Context:** A meeting clarifies scope, changes priority, introduces a constraint, or invalidates an assumption.

**In VS Code chat, type:**

```text
/sync ACME_DASHBOARD --source input\interactions\meeting-notes.md --note "scope clarification meeting"
/trace ACME_DASHBOARD
/health ACME_DASHBOARD
```

Plain-language option:

```text
The meeting notes at input\interactions\meeting-notes.md change the shared understanding for ACME_DASHBOARD.
Register them, refresh traceability, and check health.
```

**How to interpret it:** A meeting should not live only in human memory. If it changes understanding, it should become traceable evidence.

### Scenario E4: Metabolize An Unstructured Interaction Into A Proposed Digest

**Context:** You have an unstructured interaction — a meeting transcript, a client mail, a Slack thread — that probably contains answers to open gaps, decisions, new gaps, and assumption contradictions, but you do not want any of it to close or change anything automatically.

**What it is for:** `/sync --digest` extracts, with a verbatim citation per line, candidate signals from the interaction and routes them for BA review. It **proposes and routes, never applies**: it closes no gap and invalidates no assumption on its own. (For change traceability without extraction, use plain `/sync`; see E1–E3.)

**In VS Code chat, type:**

```text
/sync ACME_DASHBOARD --source input\interactions\meeting-notes.md --digest
```

For Codex:

```text
sentinel /sync ACME_DASHBOARD --source input\interactions\meeting-notes.md --digest
```

Plain-language option:

```text
These meeting notes for ACME_DASHBOARD are unstructured. Digest them into proposed gap
answers and decision candidates for my review — don't close anything automatically.
```

**What it needs:** An initialized project and a source file holding the unstructured interaction. The `--digest` flag is opt-in on top of `/sync`.

**What it produces:** `07_changes/.../interaction_digest.md` plus a `PROPOSED` gap-response file that does not close anything on its own — candidate answers to open gaps (each cited), `DEC-*` candidates, new gaps, and assumption contradictions. No signal means an explicit empty digest. Review the proposals, then apply the ones you accept through `/resolve-gaps` (structured closure) or a normal `/sync`.

## Block F: Retrieval And Memory

### Scenario F1: An Agent Needs Focused Context

**Context:** A person or agent needs to understand one topic, such as "SLA risk", "UX states", "endpoint inventory", or "US-003 regression evidence", without loading the whole workspace.

**In VS Code chat, type:**

```text
/retrieve ACME_DASHBOARD --query "SLA risk and queue triage" --workflow backlog --write-pack
```

For Codex:

```text
sentinel /retrieve ACME_DASHBOARD --query "SLA risk and queue triage" --workflow backlog --write-pack
```

Plain-language option:

```text
Retrieve focused backlog context for ACME_DASHBOARD about SLA risk and queue triage, and write a reusable context pack.
```

**Main output:**

- `08_context_packs/backlog.json` or workflow-specific context pack

**How to interpret it:** Retrieval is progressive disclosure. It helps manage context and tokens, but source workspace files remain authoritative.

### Scenario F2: Manual Edits Made Memory Stale

**Context:** Someone manually edited a Markdown artifact or domain context file. Local memory may be stale.

**In VS Code chat, type:**

```text
/reindex ACME_DASHBOARD
```

Plain-language option:

```text
I manually edited workspace files for ACME_DASHBOARD.
Rebuild local retrieval memory so future agents see fresh context.
```

**How to interpret it:** Reindexing does not change the source of truth. It only refreshes retrieval indexes.

### Scenario F3: Export A Controlled Artifact Copy

**Context:** The team wants to share a brief, gap document, or context request outside the workspace.

**In VS Code chat, type:**

```text
/export ACME_DASHBOARD --artifact brief --format md
```

Plain-language option:

```text
Export the ACME_DASHBOARD project brief as Markdown so I can share a controlled copy.
```

**How to interpret it:** The export is a controlled copy. The workspace remains the source of truth.

### Scenario F4: Export Gaps As An Interview Script Or A FAQ

**Context:** You are preparing for an elicitation meeting and want the open gaps as a running script; or discovery has matured and you want the closed gaps written up as an answered FAQ.

**What it is for:** `/export --artifact gaps --format interview` writes a meeting script from the **open** gaps; `--format faq` writes the mirror FAQ from the **closed** gaps. Both are read-only derived views — they never replace `01_discovery/gaps.md`, close no gap, and are regenerated rather than hand-edited. (For a plain shareable copy of an artifact, see F3.)

**In VS Code chat, type:**

```text
/export ACME_DASHBOARD --artifact gaps --format interview
/export ACME_DASHBOARD --artifact gaps --format faq
```

For Codex prefix with `sentinel`.

Plain-language option:

```text
Export the open ACME_DASHBOARD gaps as an interview script for tomorrow's meeting.
```

**What it needs:** A project with `gaps.md`. The `interview` and `faq` formats apply to the `gaps` artifact only. When a stakeholder registry exists (see A10) the interview script groups questions **by owner** instead of by lens.

**What it produces:** `08_context_packs/exports/gaps-interview.md` — open gaps ordered as a meeting script (blocking first, grouped by lens or owner), each with cited context, the question to ask, and 1–2 probing questions derived from cited candidate options (never invented). Or `08_context_packs/exports/gaps-faq.md` — only confirmed/closed gaps, each answer quoted verbatim from the seed/decision tables and cited to the gap id; open gaps never appear as answered, and with no confirmed gaps the FAQ is an explicit empty marker.

### Scenario F5: Open A Read-Only HTML View Of One Artifact

**Context:** A reviewer wants to read a generated artifact — gaps, brief, PRD, specs, or backlog — in a browser, with navigation, citation chips, and pending/assumption markers, without touching the source.

**What it is for:** `/view` renders one artifact as a self-contained, read-only HTML review surface derived from the Markdown source of truth. It is a rebuildable review view, not a second source of truth, and it never mutates the artifact.

**In VS Code chat, type:**

```text
/view ACME_DASHBOARD --artifact prd
/view ACME_DASHBOARD --artifact backlog --open
```

For Codex prefix with `sentinel`.

Plain-language option:

```text
Open the ACME_DASHBOARD PRD as an HTML view I can read in the browser.
```

**What it needs:** The chosen `--artifact` (`gaps`, `brief`, `prd`, `specs`, or `backlog`) already generated. Optional `--open` opens it in the default browser.

**What it produces:** `workspaces/ACME_DASHBOARD/08_context_packs/views/ARTIFACT.html` — self-contained, git-ignored, with section navigation, search, source-line anchors, pending/gap/assumption markers, citation chips resolving against the local traceability graph, and a one-hop mini trace graph. Feedback typed into the view stays in browser `localStorage`; to act on it, `GAP-*` comments use the `/resolve-gaps` answer shape and other comments go through `/sync --source PATH --note "Artifact review feedback"`.

## Block G: Audit And Framework Maintenance

### Scenario G1: Before Handoff Or Review

**Context:** The team wants to confirm that artifacts are structurally healthy before human approval, agent implementation, or repository changes.

**In VS Code chat, type:**

```text
/trace ACME_DASHBOARD
/health ACME_DASHBOARD
/validate ACME_DASHBOARD
```

Plain-language option:

```text
Prepare ACME_DASHBOARD for handoff.
Refresh traceability, run health, run validation, and summarize any remaining risks.
```

**How to interpret it:** `VALID` and `CLEAN` mean the workspace is structurally sound. They do not mean final functional approval.

### Scenario G2: A Blocker Appears Late

**Context:** A late dependency, compliance issue, architectural decision, design constraint, or QA risk invalidates existing assumptions.

**In VS Code chat, type:**

```text
/sync ACME_DASHBOARD --source input\interactions\blocker.md --note "late blocker"
/health ACME_DASHBOARD
```

Plain-language option:

```text
There is a late blocker documented at input\interactions\blocker.md.
Register it for ACME_DASHBOARD and check whether the project should become dirty.
```

**How to interpret it:** A blocker should not be resolved by silently editing the backlog. It should become traceable evidence and, when appropriate, degrade readiness until resolved. If the change triggers a gap that had already been `CLOSED`, the impact report lists it under `Reopened Closed Gaps` and `/status` surfaces the aggregate in `maturation_telemetry.reopened_by_sync_*`; the BA decides whether to reopen, resolve again, or reject the change as out of scope.

### Scenario G3: Validate The Framework Itself

**Context:** Someone changed Sentinel runtime code, skills, Kilo agents, docs, tests, or command behavior.

**For most users:** Ask Codex or the maintainer to run the framework verification.

```text
Run the Sentinel framework verification suite and doctor check, then summarize failures or warnings.
```

**For maintainers in a terminal:** the recommended one-step verification resolves the Python interpreter on its own and runs tests, `/doctor`, and evals:

```powershell
.\verify.ps1
```

Equivalent manual steps (use `py` instead of `python` if `python` opens the Microsoft Store on Windows):

```powershell
python -m unittest discover -s tests
python -m sentinel /doctor
python tests\evals\run_discovery_evals.py
```

If a change added or modified a command or skill, run `python -m sentinel.adapters` first to regenerate the Kilo/Claude command files and skill mirrors, then verify.

**How to interpret it:** Do not push framework changes if tests or `/doctor` fail. If `sentence_transformers` is missing, `/doctor` may warn while JSON fallback remains usable.

### Scenario G4: A New User Clones Or Downloads The Repo

**Context:** A person clones the repository or downloads a ZIP, opens the root in VS Code, and wants to use the framework with Kilo Code, Codex, local memory, and LanceDB.

**In VS Code chat, type:**

```text
/doctor
```

For Codex:

```text
sentinel /doctor
```

Plain-language option:

```text
I just opened this repository in VS Code.
Check whether Ignite Sentinel is ready to use on this machine and tell me what to fix if anything fails.
```

**How to interpret it:** If LanceDB fails, Sentinel still works in `json-hybrid` mode; install `python -m pip install -e .[memory]` only when the environment allows vector memory. Semantic embeddings are a separate optional layer (`.[memory-semantic]`) and must use local model files or cache. If `python` is unavailable or points to an invalid Windows alias, use `.\installers\sentinel.ps1 /doctor`. If Kilo does not see commands, confirm VS Code opened the repository root, not a subfolder.

### Scenario G5: See The Whole Portfolio At A Glance

**Context:** You are running several Sentinel projects and want one portfolio overview — phase, health, gaps, backlog rollups — instead of checking each workspace separately.

**What it is for:** `/dashboard` generates a local, read-only HTML portfolio dashboard for every workspace. Unlike project commands it takes no `PROJECT_ID`; it scans all workspaces with a `state.json`, skips `_template`, and never mutates anything or runs follow-up commands. The `sentinel-dashboard` skill maps plain-language status requests to it.

**In VS Code chat, type:**

```text
/dashboard
/dashboard --open
```

For Codex:

```text
sentinel /dashboard
```

Plain-language option:

```text
Show me the portfolio dashboard for all my Ignite workspaces.
```

**What it needs:** One or more workspaces under `workspaces/`. Optional `--root PATH` and `--open`.

**What it produces:** A single `dashboard.html` in the repository root — self-contained, offline, git-ignored, and rebuildable (not a source of truth). It shows portfolio KPIs, per-workspace phase/health, the lifecycle pipeline, copyable client-response gaps, generated documents in a modal view, backlog rollups, DoR/DoD gates, warnings, and suggested prompts.

### Scenario G6: Generate Synthetic Sample Data For The Developer Handoff

**Context:** Specs and stories exist and a developer handoff needs realistic sample data to exercise the flows — seed a local database, write example requests — before any real data exists.

**What it is for:** The `sentinel-handoff-datasets` skill generates synthetic CSV/JSON/SQL fixtures whose *shape* comes from the governed data models but whose *values* are invented. This data is synthetic by design and therefore **outside governance**: never evidence, never cited, never traced. There is no CLI command for it.

**In chat, plain language (recommended):**

```text
Generate synthetic sample data for the ACME_DASHBOARD developer handoff from the specs
and stories — CSV/JSON fixtures, clearly marked as synthetic, disposable.
```

**What it needs:** Governed specs (`03_specs/`) and user stories (`04_backlog/`) to take the schema from — only the values are invented; the skill never fabricates fields the specs never declared.

**What it produces:** Files under `08_context_packs/synthetic/` — the datasets, a `README.md` manifest carrying the `SYNTHETIC — not evidence` marker and listing which specs/stories each dataset exercises, and a self-ignoring `.gitignore` (`*` + `!.gitignore`) so the area is never committed. No governed artifact may reference it; `/validate`'s `no_synthetic_citation` guard catches any slip. It is disposable scaffolding, regenerated whenever specs change.

## Choosing Between `/resolve-gaps` And `/sync`

Use `/resolve-gaps` when:

- the file has `### GAP-ID` sections;
- the client or domain owner answered structured response fields;
- the goal is to close, partially close, or keep open known discovery gaps.

Use `/sync` when:

- information is new or not mapped to existing gaps;
- the source is a meeting note, email, Slack message, design update, technical update, QA observation, delivery note, or scope change;
- the goal is change traceability and impact analysis.

In many cases, use both: `/resolve-gaps` first for structured closure, then `/sync` for new information that exceeds the existing gaps.

## Terminal Fallback

If chat commands are unavailable because of environment policy or extension limitations, every chat command maps to:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

On Windows, the portable launcher maps to the same CLI while resolving the Python runtime:

```powershell
.\installers\sentinel.ps1 /COMMAND PROJECT_ID [OPTIONS]
```

Example:

```powershell
python -m sentinel /status ACME_DASHBOARD
```
