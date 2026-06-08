# Scenarios

This document describes concrete situations that can happen while using Ignite Sentinel vNext. A new user should be able to find a scenario, recognize their case, run the right command, inspect the generated artifacts, and understand the result.

All scenarios share the same rule: the source of truth lives in `workspaces/[PROJECT_ID]/`. Local memory is a retrieval aid, not final authority.

## Block A: Discovery Start

### Scenario A1: A Client Sends The First Requirement Package

**Context:** The client sends the first set of information. It may be a Markdown file, business note, screenshots, diagrams, system references, or an incomplete bundle of all of those. No project workspace exists yet.

**Run:**

```powershell
python -m sentinel /init ACME_DASHBOARD
python -m sentinel /ingest ACME_DASHBOARD --source input\client_requirement\initial-request.md
python -m sentinel /status ACME_DASHBOARD
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

**Recommended placement:**

```text
workspaces/ACME_DASHBOARD/00_raw/02_technology_context/
workspaces/ACME_DASHBOARD/00_raw/03_design_context/
workspaces/ACME_DASHBOARD/00_raw/04_quality_context/
workspaces/ACME_DASHBOARD/07_changes/03_domain_updates/
```

**Run:**

```powershell
python -m sentinel /reindex ACME_DASHBOARD
python -m sentinel /retrieve ACME_DASHBOARD --query "endpoint inventory and affected surfaces" --workflow discovery --write-pack
```

**What Sentinel does:** Indexes domain context locally and makes it available through focused retrieval.

**Main outputs:**

- updated `memory.lancedb/`
- optional `08_context_packs/discovery.json`

**How to interpret it:** Domain context helps close ambiguity, but it does not automatically turn an assumption into confirmed truth. If something remains unsupported or undecided, keep it as a gap.

### Scenario A3: The Team Needs A Client-Friendly Gap Document

**Context:** The initial analysis detected missing information. The team needs a clear document the client can answer without knowing Sentinel internals.

**Run:**

```powershell
python -m sentinel /gaps ACME_DASHBOARD
```

**What Sentinel does:** Regenerates `01_discovery/gaps.md` in the project language. The document includes metadata, instructions, one section per gap, answer examples, owner/source fields, evidence fields, and decision status.

**Main output:**

- `01_discovery/gaps.md`

**How to interpret it:** This file is both human-friendly and machine-processable. A stakeholder can answer under each `### GAP-ID`, and Sentinel can later process those answers with `/resolve-gaps`.

## Block B: Gap Resolution And Maturity

### Scenario B1: The Client Returns Answered Gaps

**Context:** The client or a domain owner returns the answered `gaps.md`. Some answers are confirmed, some partial, and some still pending.

**Run:**

```powershell
python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /status ACME_DASHBOARD
```

**What Sentinel does:** Reads `### GAP-ID` sections, extracts answers, owner/source, evidence, and decision status. It closes a gap automatically only when there is a non-empty answer with a confirmed or not-applicable decision status.

**Main outputs:**

- `01_discovery/gap_resolution_log.md`
- `07_changes/00_client_responses/`
- updated `01_discovery/gaps.md`
- updated `01_discovery/requirement_maturity_report.md`

**How to interpret it:** `CLOSED` means the answer can be used as confirmed truth. `PARTIALLY_CLOSED` means useful information arrived, but not enough to unblock maturity if the gap is critical or high severity.

### Scenario B2: The Gap Response Adds New Scope

**Context:** The client answers a gap but also introduces something new, such as a new export, a new user type, or a behavior not covered by existing gaps.

**Run:**

```powershell
python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
python -m sentinel /sync ACME_DASHBOARD --source input\interactions\answered-gaps.md --note "gap response includes new scope"
python -m sentinel /trace ACME_DASHBOARD
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

**Run:**

```powershell
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /brief ACME_DASHBOARD
```

**What Sentinel does:** Evaluates gap status and materializes or refreshes `02_requirements/project-brief.md` from requirements, gaps, seeds, decisions, lens review, and available domain context.

**Main outputs:**

- `01_discovery/requirement_maturity_report.md`
- `02_requirements/project-brief.md`

**How to interpret it:** The brief closes discovery. It should be clear enough for PRD/specs/backlog and for Technology or Design to deepen their own context packs. It should not pretend to contain every implementation-level contract.

## Block C: Domain Context Requests

### Scenario C1: Technology Needs A Focused Context Request

**Context:** The product requirement is mature enough for Technology to analyze affected systems, architecture, data, integration, commands, risks, and implementation surfaces.

**Run:**

```powershell
python -m sentinel /context-request ACME_DASHBOARD --domain technology
```

**What Sentinel does:** Generates a focused request under `08_context_packs/requests/`.

**Main output:**

- `08_context_packs/requests/technology_context_request.md`

**How to interpret it:** This does not replace technical analysis. It tells Technology what to deepen and which brief/gap references should guide the work.

### Scenario C2: Design Needs A Focused Context Request

**Context:** The requirement is mature enough for Design to analyze journeys, screens, states, prototypes, copy, accessibility, and validation behavior.

**Run:**

```powershell
python -m sentinel /context-request ACME_DASHBOARD --domain design
```

**Main output:**

- `08_context_packs/requests/design_context_request.md`

**How to interpret it:** Sentinel does not produce the final prototype. It makes the request to Design concrete, traceable, and based on mature discovery.

### Scenario C3: Domain Owners Update Their Context Files

**Context:** Technology, Design, Quality, or Delivery adds new context after PRD, specs, or backlog were generated.

**Run:**

```powershell
python -m sentinel /reindex ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
```

**What Sentinel does:** Rebuilds local memory and checks whether downstream artifacts may be stale.

**How to interpret it:** If `/health` reports that domain context changed after backlog generation, rerun `/backlog` before implementation handoff. The backlog depends on living domain context.

## Block D: Specs, Backlog, And Quality

### Scenario D1: Generate PRD And Specs

**Context:** A mature `project-brief.md` exists. The team needs a PRD for humans and a compact, agent-friendly spec.

**Run:**

```powershell
python -m sentinel /specs ACME_DASHBOARD
```

**What Sentinel does:** Generates `03_specs/prd.md` and `03_specs/specs.md`, preserving traceability from requirement/brief to PRD and from PRD to specs. The spec includes backlog-relevant contract, progressive disclosure context map, retrieval plan, backlog seeds, and traceability.

**Main outputs:**

- `03_specs/prd.md`
- `03_specs/specs.md`
- `08_context_packs/specs_generation.json`

**How to interpret it:** The PRD explains what should be built and why. The spec acts as an operational contract for agents and a traceable bridge into backlog.

### Scenario D2: Generate Backlog With Execution Readiness

**Context:** Specs exist and health allows downstream generation.

**Run:**

```powershell
python -m sentinel /backlog ACME_DASHBOARD
```

**What Sentinel does:** Generates epic Markdown files, story mirrors, acceptance criteria, domain context coverage, agent execution contracts, retrieval plans, backlog retrieval evidence, and implementation readiness pack.

**Main outputs:**

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- optional `04_backlog/EPIC-002-cross-cutting-enablers.md`
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`

**How to interpret it:** This is an initial traceable backlog, not the final sprint plan. Review whether stories are vertical, valuable, testable, and correctly bounded. Check that missing domain context remains visible instead of invented.

### Scenario D3: A Cross-Cutting Enabler Is Needed

**Context:** The project needs concrete implementation work in advance, such as shared auth rules, an API contract, a persistence/query capability, an integration contract, audit logging, or a UI shell that supports multiple confirmed stories.

**Run:**

```powershell
python -m sentinel /backlog ACME_DASHBOARD
```

**What Sentinel does:** If evidence is specific enough, creates `EPIC-002-cross-cutting-enablers.md`.

**How to interpret it:** Valid enablers support confirmed functionality across stories, epics, FRs, or implementation surfaces. Generic environment setup, broad hardening, or vague "make this accessible" work should not become backlog enablers unless tied to project-specific functionality and objective completion evidence.

### Scenario D4: Generate Quality Artifacts

**Context:** User stories and acceptance criteria exist.

**Run:**

```powershell
python -m sentinel /quality ACME_DASHBOARD
python -m sentinel /trace ACME_DASHBOARD
```

**What Sentinel does:** Generates test cases and backlog readiness audit. Links `US -> AC -> TC` in traceability.

**Main outputs:**

- `05_quality/TC-001.md`
- `05_quality/backlog_readiness_audit.md`
- updated traceability graph and matrix

**How to interpret it:** Quality artifacts should preserve fail-to-pass, pass-to-pass, and evidence expectations. They are a test-planning handoff, not proof that implementation has already been tested.

### Scenario D5: Backlog Or Quality Is Blocked

**Context:** Someone tries to generate backlog or quality while health is `DIRTY`.

**Run:**

```powershell
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

**What Sentinel does:** The command protocol blocks downstream generation when project health is not safe.

**How to interpret it:** This protects the team from generating documentary debt or stories based on unresolved assumptions. Fix gaps, context, traceability, or stale artifacts first.

## Block E: Change Management

### Scenario E1: A Stakeholder Sends New Information

**Context:** The client, POD, or stakeholder sends an email, Slack message, demo comment, meeting note, architecture update, design update, QA observation, or delivery decision that changes scope, priority, or behavior.

**Run:**

```powershell
python -m sentinel /sync ACME_DASHBOARD --source input\interactions\demo-feedback.md --note "demo feedback"
```

**What Sentinel does:** Copies the input into `07_changes/`, creates a `CHG` node, generates an impact report, and links the change to potentially affected artifacts.

**Main outputs:**

- `07_changes/`
- impact report
- updated traceability graph
- updated local memory

**How to interpret it:** `/sync` does not magically patch every downstream artifact. It identifies impact and preserves evidence so the team can update brief, specs, backlog, or tests with control.

### Scenario E2: Autonomous Novelty Scan

**Context:** Several files were added or modified in known input or context folders. The team does not want to process each one manually.

**Run:**

```powershell
python -m sentinel /sync ACME_DASHBOARD
```

**What Sentinel does:** Reads `00_raw/source_manifest.json`, compares hashes, detects new or modified files, and processes each novelty as a change event.

**How to interpret it:** This is useful for periodic scans. If a file is an answered `gaps.md`, use `/resolve-gaps` first to preserve structured gap closure.

### Scenario E3: A Meeting Changes The Shared Understanding

**Context:** A meeting clarifies scope, changes priority, introduces a constraint, or invalidates an assumption.

**Run:**

```powershell
python -m sentinel /sync ACME_DASHBOARD --source input\interactions\meeting-notes.md --note "scope clarification meeting"
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
```

**How to interpret it:** A meeting should not live only in human memory. If it changes understanding, it should become traceable evidence.

## Block F: Retrieval And Memory

### Scenario F1: An Agent Needs Focused Context

**Context:** A person or agent needs to understand one topic, such as "SLA risk", "UX states", "endpoint inventory", or "US-003 regression evidence", without loading the whole workspace.

**Run:**

```powershell
python -m sentinel /retrieve ACME_DASHBOARD --query "SLA risk and queue triage" --workflow backlog --write-pack
```

**What Sentinel does:** Queries local memory, applies filters, returns results with `why_retrieved`, and can write a reusable context pack.

**Main output:**

- `08_context_packs/backlog.json` or workflow-specific context pack

**How to interpret it:** Retrieval is progressive disclosure. It helps manage context and tokens, but source workspace files remain authoritative.

### Scenario F2: Manual Edits Made Memory Stale

**Context:** Someone manually edited a Markdown artifact or domain context file. Local memory may be stale.

**Run:**

```powershell
python -m sentinel /reindex ACME_DASHBOARD
```

**What Sentinel does:** Rebuilds local LanceDB and JSON fallback memory from versionable artifacts, traceability graph, and context folders.

**How to interpret it:** Reindexing does not change the source of truth. It only refreshes retrieval indexes.

### Scenario F3: Export A Controlled Artifact Copy

**Context:** The team wants to share a brief, gap document, or context request outside the workspace.

**Run:**

```powershell
python -m sentinel /export ACME_DASHBOARD --artifact brief --format md
```

**What Sentinel does:** Copies the selected artifact into `08_context_packs/exports/`.

**How to interpret it:** The export is a controlled copy. The workspace remains the source of truth.

## Block G: Audit And Framework Maintenance

### Scenario G1: Before Handoff Or Review

**Context:** The team wants to confirm that artifacts are structurally healthy before human approval, agent implementation, or repository changes.

**Run:**

```powershell
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

**What Sentinel does:** Materializes traceability views, checks health signals, and validates semantic artifact completeness.

**How to interpret it:** `VALID` and `CLEAN` mean the workspace is structurally sound. They do not mean final functional approval.

### Scenario G2: A Blocker Appears Late

**Context:** A late dependency, compliance issue, architectural decision, design constraint, or QA risk invalidates existing assumptions.

**Run:**

```powershell
python -m sentinel /sync ACME_DASHBOARD --source input\interactions\blocker.md --note "late blocker"
python -m sentinel /health ACME_DASHBOARD
```

**How to interpret it:** A blocker should not be resolved by silently editing the backlog. It should become traceable evidence and, when appropriate, degrade readiness until resolved.

### Scenario G3: Validate The Framework Itself

**Context:** Someone changed Sentinel runtime code, skills, Kilo agents, docs, tests, or command behavior.

**Run:**

```powershell
python -m unittest discover -s tests
python -m sentinel /doctor
```

**What Sentinel does:** The unit suite checks core lifecycle flows. `/doctor` verifies local runtime, repo structure, Codex/Kilo adapters, write access, required dependencies, LanceDB local probe, commands, and optional dependencies.

**How to interpret it:** Do not push framework changes if tests or `/doctor` fail. If `sentence_transformers` is missing, `/doctor` may warn while JSON fallback remains usable.

### Scenario G4: A New User Clones Or Downloads The Repo

**Context:** A person clones the repository or downloads a ZIP, opens the root in VS Code, and wants to use the framework with CLI, Kilo Code, Codex, local memory, and LanceDB.

**Run:**

```powershell
python -m sentinel /doctor
```

**What Sentinel does:** Checks Python, repo structure, Kilo/Codex adapter files, write access, LanceDB, command availability, and optional dependencies.

**How to interpret it:** If LanceDB fails, install dependencies with `python -m pip install -e .` in the active environment. If Kilo does not see commands, confirm VS Code opened the repository root, not a subfolder.

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
