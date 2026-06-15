# Ignite Sentinel Workflows

This document describes the main workflows and when to use them. It is more procedural than the command reference: the goal is to show how commands connect into a real delivery rhythm, from a raw client request to a mature brief, then to specs, backlog, quality, changes, and health checks.

If you are new to Sentinel, read this page together with [Escenarios Operativos](12-scenarios.md). Workflows describe the usual path; scenarios describe what to do when a concrete situation appears.

The examples use `python -m sentinel` for terminal clarity. In Kilo Code chat, use `/command`; in Codex or Codex Desktop, use `sentinel /command` when a slash command is intercepted. If a laptop does not expose a valid `python`, run the same command through `.\installers\sentinel.ps1` on Windows or `sh installers/sentinel.sh` on Unix-like shells.

## Workflow 1: New Requirement

This workflow starts when the team receives the first meaningful input from a client or stakeholder. The input is usually incomplete. That is expected. The point of this workflow is not to force completeness on day one, but to make incompleteness visible, structured, and actionable.

Use when a client provides the initial project package: synchronization guide, architecture or repository references, UX/UI references, sketches, snapshots, design system files, quality context, or delivery constraints.

Recommended source organization before ingestion:

```text
input/
  client_requirement/
  business_context/
  technology_context/
  design_context/
  quality_context/
  interactions/
```

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /gaps PROJECT_ID
python -m sentinel /maturity PROJECT_ID
```

Optionally, deepen discovery beyond the deterministic checklist before resolving gaps. The agent operating the framework can propose semantic gaps it read in the raw input, or stress-test the requirement, and the runtime validates each finding against a verbatim quote before merging:

```powershell
python -m sentinel /annotate PROJECT_ID --source input\interactions\analysis.json
python -m sentinel /challenge PROJECT_ID --source input\interactions\findings.json
python -m sentinel /scrutinize PROJECT_ID --source input\interactions\scrutiny.json
```

`/annotate` merges gaps the keyword checklist suppressed (`origin: agent`); `/challenge` runs pre-mortem, per-lens role-play, and assumption inversion, writing `01_discovery/challenge_report.md` (`origin: challenge`); `/scrutinize` crosses raw input with local domain context and writes `01_discovery/scrutiny_report.md` (`origin: scrutiny`) while refreshing the discovery ledger. All three keep the runtime as the authority — the agent cites, it never invents — and the merged gaps flow through `/resolve-gaps` like any other.

If maturity is `BLOCKED`, review:

```text
workspaces/PROJECT_ID/01_discovery/gaps.md
workspaces/PROJECT_ID/01_discovery/requirement_maturity_report.md
```

Then ask stakeholders for missing information. The gap document is designed as a conversation artifact: it should be understandable by a client or domain owner, while still preserving the `GAP-ID` structure Sentinel needs to process the answer later.

When the answered gap document returns:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

For functional or business-rule gaps, the expected format now points stakeholders toward EARS-shaped answers. A confirmed EARS answer is accumulated into `02_requirements/requirements.md` as `REQ-EARS-*`. A confirmed prose answer still closes the gap when it is substantive, but Sentinel marks it `EARS-eligible, not normalized` and `/status` counts it so the BA or agent can propose a separate EARS rewrite for confirmation.

When maturity reaches `READY_FOR_SPECS`, Sentinel also materializes:

```text
workspaces/PROJECT_ID/02_requirements/project-brief.md
```

You can also refresh the brief explicitly:

```powershell
python -m sentinel /brief PROJECT_ID
```

The brief is the closing artifact for discovery. It consolidates the iterated requirement across business/product, technology, design, quality, governance, decisions, seeds, inferences, and open uncertainty radar. Downstream PRD/spec/backlog generation should treat it as the mature requirement handoff.

Discovery maturity does not mean every domain artifact is fully designed. The brief should provide enough signal for domain agents to deepen their work in context packs:

- Design gets affected journeys, users, screens, states, copy constraints, and visual evidence references.
- Technology gets system boundaries, endpoint/event inventory, create/modify/reuse decisions, source-of-truth ownership, constraints, and risks.
- Frontend and Backend get enough behavior, surface, integration, validation, and failure-mode context to split implementation responsibly.
- Quality gets acceptance strategy, critical flows, edge cases, test data needs, and trace expectations.

Generate domain requests when the brief is ready for deeper analysis:

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
python -m sentinel /context-request PROJECT_ID --domain design
python -m sentinel /context-request PROJECT_ID --domain quality
```

Typical gaps to surface include:

- missing user access or navigation path;
- undefined data source, calculation logic, metric owner, or refresh frequency;
- missing UX behavior, empty/error/loading states, or design-system constraints;
- missing non-functional expectations, permissions, auditability, or compliance constraints;
- acceptance criteria that are not measurable or testable.

## Workflow 2: Specs Generation

Use this workflow only after discovery has produced enough confirmed evidence. Specs created too early tend to hide uncertainty inside polished language, which is exactly what Sentinel tries to prevent.

Use when the requirement is mature enough to become an AI-friendly spec.

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/02_requirements/project-brief.md
workspaces/PROJECT_ID/03_specs/prd.md
workspaces/PROJECT_ID/03_specs/specs.md
workspaces/PROJECT_ID/03_specs/units/SPEC-U-NNN.md
workspaces/PROJECT_ID/08_context_packs/specs_generation.json
```

`prd.md` is the complete what/why narrative for humans and business reviewers, including personas, FRs with ACs, NFRs, KPIs, JTBD traceability, execution planning, and governance. `specs.md` is the compact agent contract and index: it keeps trace IDs, retrieved context signals, backlog seeds, and the retrieval plan that backlog agents should use before slicing epics and stories. When confirmed EARS rows exist, `03_specs/units/SPEC-U-NNN.md` files carry bounded execution context with source anchors. `specs_generation.json` shows the declarative retrieval plan section, focused local memory context, and `read_plan` anchors used to draft each major PRD/spec section.

## Workflow 3: Backlog Generation

Backlog generation should happen after the spec has a stable source. A user story should be traceable back to the requirement, brief, spec, acceptance criteria, and eventually tests. If the project is still `DIRTY`, fix the discovery or traceability problem first.

Use when specs are ready to become execution-oriented backlog.

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /backlog PROJECT_ID --with-task-seeds   # optional, only when downstream asks for task-seed intentions
python -m sentinel /quality PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
```

Review:

```text
workspaces/PROJECT_ID/04_backlog/
workspaces/PROJECT_ID/05_quality/
workspaces/PROJECT_ID/08_context_packs/backlog_generation.json
workspaces/PROJECT_ID/08_context_packs/implementation_readiness.json
workspaces/PROJECT_ID/08_context_packs/slice_plan.json
```

After `/quality`, review `05_quality/backlog_readiness_audit.md` for the story-level INVEST/SPIDR score. The audit checks the existing Ignite model only: vertical behavior or concrete enabler boundary, small-but-valuable scope, classified ACs, traceability, and explicit dependencies. Findings feed DoR warnings in `state.json#story_gates`; they do not block by default.

The primary backlog output is one Markdown file per epic, starting with:

```text
workspaces/PROJECT_ID/04_backlog/EPIC-001.md
```

That epic file contains the domain context coverage, story map, agent execution contracts, retrieval plans, and the user stories. Sentinel also creates `US-00x.md` mirrors so traceability and quality tooling can link to each story as an individual node.

Backlog value stories are derived from confirmed `SPEC-U-*` files produced by `/specs`. If six confirmed EARS statements create six Spec Units, `/backlog` creates six value stories. The story's slicing pattern and rationale are selected from `sentinel/slicing/backlog_slicing_model.json`, which preserves the existing INVEST, vertical slicing, SPIDR, Lawrence and enabler-boundary model. If `/specs` has no evidence-backed functional unit, `/backlog` keeps the missing evidence visible as a `[PENDING INPUT]` stub and points reviewers back to the blocking gaps rather than inventing a placeholder backlog.

Backlog generation uses progressive disclosure. Before writing the epic, Sentinel retrieves focused local context for business value, functional slicing, technical dependencies, execution commands, critical surfaces, engineering practices, UX states, design match, quality risks, regression contract, and open uncertainty. The retrieval audit is stored in `08_context_packs/backlog_generation.json`; its queries come from `sentinel/retrieval_plans/backlog_generation.json` and each result carries `read_plan` source anchors. The pack keeps the aggregate retrieval view and a `per_story.US-NNN` mini-context for each Spec Unit-derived story, so one story can cite a stale-data surface while another cites a metrics-outage surface. Confirmed execution signals in each story carry an `anchor` with `source_path`, `section_path`, `line_start`, and `line_end`, and the `US-NNN.md` render shows that pointer inline. Source workspace files remain authoritative if memory disagrees.

Sentinel also writes `08_context_packs/implementation_readiness.json`. This pack is the handoff contract for agents that will plan, implement, or test the backlog. It lists each story's required domains, pending context, dependencies, validation contract, execution contract, retrieval queries, trace IDs, blast radius, and a snapshot of the live domain context used at generation time. If specs were regenerated after backlog creation, `stale_spec_units` names changed `SPEC-U-*` units so reviewers can focus only on affected slices.

If downstream planning explicitly needs a task-seed contract, run `/backlog --with-task-seeds`. Sentinel adds optional seeds to each story and to `implementation_readiness.json`, grounded in AC and confirmed critical surfaces; the default command stays silent, and the opt-in contract still does not create task IDs, estimates, assignments, schedules, or managed implementation steps.

`04_backlog/SLICE-PLAN.md` and `08_context_packs/slice_plan.json` add the ordered handoff view: concrete `EPIC-002` enablers first, then implementation waves that can be planned in parallel after prerequisites, with checkpoints and per-story handoff packs. This is still backlog governance, not tasking; downstream agents consume the plan to decide what to retrieve and plan next.

Technology, Design, Quality, Delivery and other domains can keep enriching their context files throughout the lifecycle. After those files are ingested, synced, or reindexed, downstream backlog generation can cite them. If a domain contract is missing, Sentinel keeps `[PENDING DOMAIN CONTEXT]` visible instead of inventing commands, files, design tokens, regression suites, or blast-radius boundaries.

If domain context changes after backlog generation, `/health` reports a freshness warning. Refresh memory and retrieve focused context before handoff:

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /retrieve PROJECT_ID --query "implementation context for affected story" --workflow implementation
```

Rerun `/backlog` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts. Then continue with quality, trace, health, and validation.

When reviewing the backlog, check:

- every value story cites `REQ-001`, `PRD-001`, `SPEC-001`, and a `SPEC-U-*` unit or remains explicitly pending;
- stories are vertical value slices, not isolated frontend/backend/data tasks;
- `Small` means small but still valuable: avoid micro-stories that cannot be accepted independently;
- domain context coverage makes Technology, Design, Quality and Delivery evidence visible or explicitly pending;
- agent execution contracts include autonomy limits, blast radius, validation contract, and sequencing notes without inventing missing domain context;
- each story includes a retrieval plan for downstream execution agents;
- `implementation_readiness.json` is present and does not hide missing domain context;
- `SLICE-PLAN.md` and `slice_plan.json` sequence enablers, waves, checkpoints and per-story handoff packs without creating task IDs;
- acceptance criteria separate `fail-to-pass`, `pass-to-pass`, and evidence expectations;
- `EPIC-002-cross-cutting-enablers.md` appears only when concrete frontend/backend/architecture/auth/data/integration/audit/observability work must be built in advance to support confirmed functionality inside the project boundary;
- generic setup or phrases like "make an internal tool accessible" are treated as preconditions/external tasks, not backlog enablers;
- acceptance criteria are declarative Given/When/Then scenarios;
- dependencies and `[PENDING INPUT]` markers are visible;
- no confidential raw details leaked into the generated backlog.

## Workflow 4: Change Or Meeting Sync

Once a project has artifacts, new information should not be pasted silently into whichever document seems closest. Treat meaningful feedback as an event. This keeps the project history explainable: what changed, why it changed, and which artifacts may be affected.

Use when the client, POD, or stakeholder introduces new information that is not a structured gap response: email or Slack content, meeting transcripts, architecture notes, design updates, QA observations, delivery decisions, or new requirement signals.

For answered `gaps.md`, prefer:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
```

Autonomous mode:

```powershell
python -m sentinel /sync PROJECT_ID
```

Sentinel scans known input and workspace context folders, compares file hashes against `00_raw/source_manifest.json`, and processes new or modified files as change events.

Explicit mode:

```powershell
python -m sentinel /sync PROJECT_ID --source input\change.md --note "source and intent"
python -m sentinel /retrieve PROJECT_ID --query "main change topic" --workflow sync --write-pack
```

Review:

```text
workspaces/PROJECT_ID/07_changes/
workspaces/PROJECT_ID/08_context_packs/
```

Then patch affected artifacts and rerun:

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

Use this loop until the shared understanding is stable enough to generate or refresh specs and backlog. For major changes, rerun maturity and consider refreshing the project brief before touching downstream artifacts.

## Workflow 4B: Project Branch Execution

Use this when running a real client/project execution, as opposed to improving the framework itself. It protects `main` from client artifacts and makes it easier to decide what should be merged back.

Use a dedicated Git branch for real project execution or workflow tests.

```powershell
git switch main
git pull
git switch -c project/PROJECT_ID
```

Run Ignite commands in that branch:

```powershell
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\sync-guide.md
```

Do not merge project branches into `main` when they contain client documents, generated workspaces, or test artifacts. Merge back only isolated improvements to the framework itself.

## Workflow 5: Health Audit

Health audit is the system's immune check. It does not approve business content, but it can detect structural problems before another team or agent builds on top of them.

Use before handing artifacts to another domain or agent.

```powershell
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
python -m sentinel /trace PROJECT_ID
```

Hand off only when:

- health is `CLEAN`
- validation is `VALID`
- traceability matrix is understandable
- known business uncertainties are represented as gaps

## Workflow 6: Context Retrieval

Use retrieval when the workspace has more context than an agent should load at once. This is Sentinel's progressive disclosure mechanism: retrieve the smallest useful slice, keep source hashes, and preserve why each result was returned.

Use when Codex or Kilo needs focused context without loading the entire workspace. This is a read-only progressive disclosure step; it queries local retrieval memory (`lancedb-hybrid` when available, deterministic `json-hybrid` otherwise) and can write a reusable context pack.

```powershell
python -m sentinel /retrieve PROJECT_ID --query "acceptance criteria and SLA risk" --workflow backlog --limit 5
```

Use filters when possible:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --artifact-type change --domain product
```

Add filters and budgets to keep context tight:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "scope" --workflow discovery --language es --sensitivity internal --max-chars 2000 --summary-only
```

Create a context pack:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk" --workflow sync --write-pack
```

## Recommended Handoff Checklist

Before sharing with another domain:

- Product: requirement and gaps are clear.
- Technology: scope and constraints are visible.
- Design: user journey implications are explicit or flagged.
- Quality: acceptance criteria and test cases exist.
- Delivery: open gaps, risks, and change impacts are visible.
- Agents: trace IDs and source artifacts are present.
