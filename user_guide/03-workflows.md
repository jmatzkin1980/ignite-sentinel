# Ignite Sentinel Workflows

This document describes the main workflows and when to use them. It is more procedural than the command reference: the goal is to show how commands connect into a real delivery rhythm, from a raw client request to a mature brief, then to specs, backlog, quality, changes, and health checks.

If you are new to Sentinel, read this page together with [Escenarios Operativos](12-scenarios.md). Workflows describe the usual path; scenarios describe what to do when a concrete situation appears.

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
workspaces/PROJECT_ID/08_context_packs/specs_generation.json
```

`prd.md` is the complete what/why narrative for humans and business reviewers, including personas, FRs with ACs, NFRs, KPIs, JTBD traceability, execution planning, and governance. `specs.md` is the compact agent contract: it keeps trace IDs, retrieved context signals, backlog seeds, and the retrieval plan that backlog agents should use before slicing epics and stories. `specs_generation.json` shows the local memory context used to draft each major PRD/spec section.

## Workflow 3: Backlog Generation

Backlog generation should happen after the spec has a stable source. A user story should be traceable back to the requirement, brief, spec, acceptance criteria, and eventually tests. If the project is still `DIRTY`, fix the discovery or traceability problem first.

Use when specs are ready to become execution-oriented backlog.

```powershell
python -m sentinel /backlog PROJECT_ID
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
```

The primary backlog output is one Markdown file per epic, starting with:

```text
workspaces/PROJECT_ID/04_backlog/EPIC-001.md
```

That epic file contains the domain context coverage, story map, agent execution contracts, retrieval plans, and the user stories. Sentinel also creates `US-00x.md` mirrors so traceability and quality tooling can link to each story as an individual node.

Backlog generation uses progressive disclosure. Before writing the epic, Sentinel retrieves focused local context for business value, functional slicing, technical dependencies, execution commands, critical surfaces, engineering practices, UX states, design match, quality risks, regression contract, and open uncertainty. The retrieval audit is stored in `08_context_packs/backlog_generation.json`; source workspace files remain authoritative if memory disagrees.

Sentinel also writes `08_context_packs/implementation_readiness.json`. This pack is the handoff contract for agents that will plan, implement, or test the backlog. It lists each story's required domains, pending context, dependencies, validation contract, retrieval queries, trace IDs, blast radius, and a snapshot of the live domain context used at generation time.

Technology, Design, Quality, Delivery and other domains can keep enriching their context files throughout the lifecycle. After those files are ingested, synced, or reindexed, downstream backlog generation can cite them. If a domain contract is missing, Sentinel keeps `[PENDING DOMAIN CONTEXT]` visible instead of inventing commands, files, design tokens, regression suites, or blast-radius boundaries.

If domain context changes after backlog generation, `/health` reports the backlog as potentially stale. Rerun:

```powershell
python -m sentinel /reindex PROJECT_ID
python -m sentinel /backlog PROJECT_ID
```

Then continue with quality, trace, health, and validation.

When reviewing the backlog, check:

- every story cites `REQ-001`, `PRD-001`, `SPEC-001`, and an FR/JTBD;
- stories are vertical value slices, not isolated frontend/backend/data tasks;
- `Small` means small but still valuable: avoid micro-stories that cannot be accepted independently;
- domain context coverage makes Technology, Design, Quality and Delivery evidence visible or explicitly pending;
- agent execution contracts include autonomy limits, blast radius, validation contract, and sequencing notes without inventing missing domain context;
- each story includes a retrieval plan for downstream execution agents;
- `implementation_readiness.json` is present and does not hide missing domain context;
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

Use when Codex or Kilo needs focused context without loading the entire workspace. This is a read-only progressive disclosure step; it queries local LanceDB memory and can write a reusable context pack.

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
