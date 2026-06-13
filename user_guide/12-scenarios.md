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

## Block A: Discovery Start

### Scenario A1: A Client Sends The First Requirement Package

**Context:** The client sends the first set of information. It may be a Markdown file, business note, screenshots, diagrams, system references, or an incomplete bundle of all of those. No project workspace exists yet.

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

**What Sentinel does:** The agent runs three techniques per lens — pre-mortem, role-play (operator, auditor, attacker...), and assumption inversion. Each finding is validated against the raw input exactly like `/annotate`, merged as a gap tagged `origin: challenge`, and summarized in a versionable report.

**Main outputs:**

- updated `01_discovery/gaps.md` (gaps with `origin: challenge`)
- `01_discovery/challenge_report.md` (findings grouped by lens and technique, plus imagined failures and inverted assumptions)

**How to interpret it:** This is how you surface the risks a client never states. The findings enter the normal `/resolve-gaps` → `/maturity` flow, so the challenge becomes traceable evidence, not a lost conversation.

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

**How to interpret it:** If `/health` reports that domain context changed after backlog generation, rerun `/backlog` before implementation handoff. The backlog depends on living domain context.

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
