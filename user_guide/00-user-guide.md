# Ignite Sentinel User Guide

Ignite Sentinel vNext is a local-first framework for maturing business and product requirements inside AI PODs. It does not replace Product, Technology, Design, Quality, Delivery, or Compliance judgment. It organizes the work so raw requirements do not jump straight into implementation without context, traceability, explicit questions, and verifiable handoffs.

The core idea is simple: clients and stakeholders usually bring needs in an incomplete form. The input may be a short Markdown note, screenshots, diagrams, emails, meeting notes, technical references, or a mixed bundle of partial evidence. Sentinel treats that material as initial evidence, pressure-tests it, detects gaps, records decisions, and builds mature understanding until it can produce a `project-brief.md`.

That brief becomes the bridge between discovery and downstream artifacts: PRD, specs, backlog, acceptance criteria, quality artifacts, domain context requests, and execution-ready context packs for AI agents.

This guide is written for people who are new to the framework. If you are a BA, Product Owner, Product Manager, Tech Lead, UX/UI designer, QA, Delivery lead, or someone working with AI agents, it answers three questions:

- What problem Sentinel solves.
- What to do at each moment of the lifecycle.
- Which artifacts are generated and how to use them without losing traceability.

## One Sentence Summary

Sentinel turns raw information into mature requirements through discovery, gap resolution, traceability, health checks, specs, backlog readiness, and local retrieval. Versionable workspace files are always the source of truth; local memory is only a context retrieval aid.

## What Sentinel Does

At a high level:

1. A project workspace is created.
2. Initial client or stakeholder documentation is ingested.
3. Product, Technology, Design, Quality, Delivery, and Compliance lenses review the input critically.
4. Initial requirements, identity seeds, decisions, gaps, and traceability are generated.
5. `gaps.md` is shared with the client or domain owners to capture missing information.
6. Structured gap responses are processed.
7. A mature `project-brief.md` is generated when the requirement is ready.
8. PRD and specs are generated from the mature brief and supporting context.
9. Backlog artifacts are generated only when the project is healthy enough to proceed.
10. Backlog generation produces both human-readable epics/stories and machine-friendly implementation readiness packs.
11. Quality artifacts and test coverage are generated from user stories.
12. Health, validation, and traceability are audited before downstream handoffs.

Sentinel does not assume that a stakeholder sentence is automatically final truth. It treats input as evidence. When evidence is strong enough, it can become a seed or decision. When information is missing or risky, Sentinel turns it into a gap.

## Workspace Model

Each project lives in:

```text
workspaces/[PROJECT_ID]/
```

That directory contains raw input, discovery artifacts, requirements, specs, backlog, quality artifacts, traceability, changes, context packs, and local memory. Project separation prevents mixing information from different clients or initiatives.

The source of truth is the versionable workspace files. Local memory, including LanceDB and JSON fallback indexes, is only a retrieval index. If memory disagrees with a Markdown artifact in the workspace, the workspace artifact wins.

## Seeds

A seed is an atomic statement that captures known or pending truth. Examples:

- "The first value slice is an authorized user seeing one high-risk item."
- "Monthly historical exports are out of MVP scope."
- "The source of truth for SLA risk is Case Management."

Seeds help agents avoid reinterpreting the full raw input every time they work on the project.

## Gaps

A gap is missing, ambiguous, risky, or unverifiable information. A gap is not a failure. It is a healthy way to avoid invention.

If the team does not know which user uses a screen, which endpoint exists, which metric has a baseline, which UX states are required, or which quality evidence proves completion, Sentinel marks that uncertainty as a gap.

Discovery is inquisitive about what the input mentions but does not explain: naming a screen, portal, API, or integration does not answer the questions about its journey, UI states, contracts, or failure behavior. Those gaps stay open and cite the exact mention that triggered the question, so the client sees why it is being asked.

Common gap statuses:

- `OPEN`: still missing or unresolved.
- `ANSWERED`: a substantive answer exists with decision still pending confirmation; severe gaps in this state keep blocking specs/backlog.
- `PARTIALLY_CLOSED`: some information arrived but it is not enough — including vague answers (`TBD`, deferrals) even when marked as confirmed; the resolution report explains why with a note.
- `CLOSED`: structured evidence is sufficient to close the gap.

This matters because downstream artifacts should not hide uncertainty. A PRD, spec, backlog, or test plan should expose unresolved assumptions rather than inventing them away.

## Domain Context

Technology, Design, Quality, Delivery, Business, and other domain owners can keep enriching the workspace throughout the lifecycle.

Typical domain context includes:

- Technology: architecture notes, as-is/to-be context, affected services, endpoints, data contracts, commands, engineering practices, deployment constraints, security and observability notes.
- Design: user journeys, prototypes, screens, states, design tokens, interaction rules, accessibility constraints, copy and validation behavior.
- Quality: test strategy, regression suites, test data, automation conventions, quality gates, fail-to-pass and pass-to-pass expectations.
- Delivery: dependencies, release constraints, environment readiness, rollout notes, ownership and timing.
- Product or Business: current state, target state, personas, business rules, exclusions, KPIs, and decision rationale.

This context is ingested and reindexed locally. Agents use `/retrieve` for progressive disclosure, pulling only the focused evidence needed for the active workflow.

## Traceability

Every important artifact has an ID:

- `RAW`: raw input.
- `SEED`: identity or product truth seed.
- `DISC`: discovery log or lens review.
- `GAP`: gap report.
- `DEC`: decision or impact report.
- `REQ`: requirement.
- `PRD`: product requirements document.
- `SPEC`: agent-oriented spec.
- `EPIC`: epic.
- `US`: user story.
- `AC`: acceptance criteria.
- `TC`: test case.
- `CHG`: change event.
- `CTX`: context request.

Traceability lets the team answer questions such as:

- Where did this user story come from?
- Which decision closed this gap?
- Which change may affect this spec?
- Which test covers this acceptance criterion?
- Which domain context was used before handing work to an implementation agent?

## Health And Validation

`/health` does not replace human approval. It is a deterministic control that checks structural signals such as blocking gaps, metrics without sources, orphan trace nodes, missing memory indexing, stale domain context, and story-to-epic linkage.

A project can be:

- `CLEAN`: no structural findings were detected.
- `DIRTY`: unresolved findings exist.

`CLEAN` means "structurally ready to continue." It does not mean "approved by the client."

`/validate` checks semantic completeness: required artifacts, expected sections, trace IDs, specs context packs, backlog readiness audit, story execution contracts, retrieval plans, and `implementation_readiness.json`.

## Backlog And Implementation Readiness

Backlog generation is intentionally strict because downstream AI agents may use the backlog to plan, implement, and test.

`/backlog` generates:

```text
04_backlog/EPIC-001.md
04_backlog/US-001.md
08_context_packs/backlog_generation.json
08_context_packs/implementation_readiness.json
```

It may also create:

```text
04_backlog/EPIC-002-cross-cutting-enablers.md
```

Backlog rules:

- Epics are the primary human review artifacts.
- Story mirrors exist for traceability and quality tooling.
- Stories should be vertical, value-oriented slices.
- INVEST is applied pragmatically: `Small` means small but still independently valuable, testable, and useful.
- Missing domain context remains visible as `[PENDING DOMAIN CONTEXT]`.
- Each story includes `Domain Context Coverage`, `Agent Execution Contract`, and `Retrieval Plan For Execution Agents`.
- Acceptance criteria are declarative Given/When/Then scenarios and classify fail-to-pass, pass-to-pass, and evidence expectations.
- Cross-cutting enablers are valid only when concrete implementation work must be built in advance to support confirmed functionality across stories, epics, FRs, or implementation surfaces.
- Generic setup, broad hardening, environment availability, or vague operability work is a precondition or external task unless tied to this project's confirmed functionality and objective completion evidence.

`implementation_readiness.json` is the machine-friendly handoff pack. It records story readiness, required domains, pending context, retrieval queries, validation expectations, dependencies, trace IDs, blast radius, and the domain context snapshot used during backlog generation.

If domain context changes after backlog generation, `/health` marks the backlog as stale. From chat, run:

```text
/reindex PROJECT_ID
/backlog PROJECT_ID
```

For Codex, prefix each line with `sentinel` if needed.

Then rerun quality, trace, health, and validation before implementation handoff.

## Basic Flow

Use VS Code chat as the primary interface when Kilo Code or Codex is available.

- In Kilo Code, type the slash command directly.
- In Codex, prefix the same command with `sentinel` if the slash command is intercepted.
- If you do not know the exact command, explain the situation in plain language and ask the agent to run the appropriate Sentinel workflow.

### 1. Initialize A Project

```text
/init PROJECT_ID
```

Codex-safe form:

```text
sentinel /init PROJECT_ID
```

This creates folders, `state.json`, `sentinel.config.yaml`, an empty traceability graph, source manifest, and local memory area.

### 2. Ingest Initial Input

```text
/ingest PROJECT_ID --source input\client_requirement\request.md
```

Sentinel copies the input to the workspace, creates initial requirements, gaps, seeds, decisions, and multi-lens review artifacts. It also indexes generated artifacts and domain context folders into local memory.

### 3. Review Gaps

```text
/gaps PROJECT_ID
```

`01_discovery/gaps.md` is designed for humans. Each gap is framed as elicitation (IMP-022): besides the question, it states why it matters (the risk if left open), what answering it unblocks (the downstream brief/PRD/spec section that consumes the answer), the expected response format, an example answer, owner/source fields, evidence fields, and decision status. It can be shared with a client or domain owner without requiring them to understand the framework internals.

### 3b. (Optional) Deepen Discovery With The Agent

Beyond the deterministic checklist, the agent operating the framework can contribute gaps it reads semantically — gaps a reassuring keyword would otherwise suppress:

```text
/annotate PROJECT_ID --source analysis.json
/challenge PROJECT_ID --source findings.json
```

`/annotate` merges semantic gaps the agent found while reading the raw input; `/challenge` runs advanced elicitation (pre-mortem, per-lens role-play, assumption inversion) and writes a `challenge_report.md`. Both validate every finding against a verbatim quote from the raw input before merging (the agent proposes with evidence; the runtime never invents), tagging them `origin: agent` / `origin: challenge`. The merged gaps then flow through `/resolve-gaps` like any other.

### 4. Resolve Structured Gap Answers

```text
/resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
```

Sentinel automatically closes only gaps with confirmed structured answers. If an answer exists but the decision is still pending, the gap remains partially closed. When a confirmed answer is written in EARS syntax ("When <trigger>, the system shall <response>." and the other four patterns, EN or ES), it is also accumulated into `requirements.md` as a testable `REQ-EARS-*` statement (IMP-026).

### 5. Check Maturity

```text
/maturity PROJECT_ID
```

If critical or high gaps remain open or partial, the project stays blocked. If maturity reaches `READY_FOR_SPECS`, Sentinel can generate or refresh the project brief. `/maturity` and `/status` also report per-section brief readiness and maturation telemetry (how many resolve rounds ran, how gaps closed by provenance, the oldest blocking gap) so you can see where maturation is stalling (IMP-025, IMP-028).

### 6. Generate The Project Brief

```text
/brief PROJECT_ID
```

The brief is the closure of discovery. It should be clear enough for PRD/specs/backlog and for Technology or Design to deepen their own context packs, without pretending to include every low-level implementation contract.

### 7. Request Domain Context

```text
/context-request PROJECT_ID --domain technology
/context-request PROJECT_ID --domain design
/context-request PROJECT_ID --domain quality
```

Domain requests are focused, traceable prompts for domain owners. They should enrich the relevant workspace context folders and then be ingested, synced, or reindexed.

### 8. Generate Specs, Backlog, And Quality Artifacts

```text
/specs PROJECT_ID
/backlog PROJECT_ID
/quality PROJECT_ID
```

Run these only when project maturity and health allow it. `/backlog` and `/quality` are blocked while project health is `DIRTY`.

### 9. Audit Traceability And Health

```text
/trace PROJECT_ID
/health PROJECT_ID
/validate PROJECT_ID
```

Use these before human review, agent handoff, or repository changes.

Terminal fallback:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

Portable launcher fallback when a laptop does not expose a valid `python` command:

```powershell
.\installers\sentinel.ps1 /COMMAND PROJECT_ID [OPTIONS]
```

On Unix-like shells:

```sh
sh installers/sentinel.sh /COMMAND PROJECT_ID [OPTIONS]
```

## Workspace Shape

```text
workspaces/[PROJECT_ID]/
  00_raw/             Original evidence and domain context
  01_discovery/       Gaps, decisions, seeds, lens review, maturity report
  02_requirements/    Requirements and project brief
  03_specs/           PRD and agent-oriented specs
  04_backlog/         Epics, user stories, acceptance criteria
  05_quality/         Test cases and backlog readiness audit
  06_traceability/    Graph, matrix, health reports, command protocol log
  07_changes/         Changes, client responses, meeting notes, domain updates
  08_context_packs/   Retrieval packs, exports, domain requests, readiness packs
  memory.lancedb/     Rebuildable local retrieval index
```

## Privacy Model

Sentinel is designed for environments where client information or code should not travel through external channels by default.

By default:

- Client and project content stays in local files.
- LanceDB memory is local.
- JSON fallback indexes are local.
- Remote MCP, external vector databases, and external embeddings are not used for client/project content unless explicitly approved.
- Versionable workspace files remain the source of truth.

## How To Read The Rest Of The Guide

- [Command Reference](01-command-reference.md): what each command does.
- [Artifact Reference](02-artifact-reference.md): what each generated file is for.
- [Workflows](03-workflows.md): recommended lifecycle flows.
- [Codex Skills Guide](04-codex-skills-guide.md): how Codex skills map to Sentinel workflows.
- [Traceability And Memory](05-traceability-and-memory.md): how local memory and progressive disclosure work.
- [Installation And VS Code](06-installation-vscode.md): how to use Sentinel after cloning or downloading the repo.
- [Kilo Code Adapter](07-kilo-code-adapter.md): how Kilo Code reads repo-local agents and commands.
- [Codex Adapter](08-codex-adapter.md): how Codex reads skills and `AGENTS.md`.
- [Claude Adapter](13-claude-adapter.md): how Claude Code and Claude Desktop read `.claude/commands/` and `CLAUDE.md`.
- [Secure Environments](09-secure-environments.md): privacy-first operation.
- [Repo And Branching Strategy](10-repo-and-branching-strategy.md): how to maintain the framework.
- [Chat Commands](11-chat-commands.md): how chat commands map to CLI commands.
- [Scenarios](12-scenarios.md): concrete examples of common situations.

## Practical Advice

- Do not hide uncertainty. Convert doubt into a gap.
- Do not treat generated artifacts as magical truth. Review them.
- Do not let memory override source files.
- Use `/retrieve` for focused context instead of loading the whole workspace.
- Rerun `/reindex` after manual edits to workspace artifacts or domain context.
- Rerun `/health` and `/validate` before handoff.
- Keep examples and framework rules agnostic: never 