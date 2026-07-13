# Ignite Sentinel Codex Skills Guide

Ignite Sentinel includes repo-local Codex skills under:

```text
.codex/skills/
```

Skills provide progressive disclosure. The agent sees the skill metadata first and loads the body only when the workflow applies.

`.codex/skills/` is the canonical source. The same skills are mirrored byte-for-byte to `.agents/skills/` (Agent Skills standard readers) and `.claude/skills/` (Claude Code) by `python -m sentinel.adapters`; every skill carries validated `name`/`description` frontmatter (checked by `/doctor`), so agents can auto-trigger them from the description alone.

Skills delegate deterministic work to the same local CLI used by Kilo Code and terminal workflows. The normal command is `python -m sentinel ...`; if `python` is unavailable in Codex Desktop or VS Code, use the repo-local launcher `.\installers\sentinel.ps1 ...` from the repository root.

## Available Skills

All 24 canonical skills, grouped by lifecycle activity:

| Skill | Use When |
| --- | --- |
| `sentinel-intake-triage` | Triaging a pile of unstructured intake (mails/RFQs/chats) into candidate projects **before** `/init` |
| `sentinel-discovery` | Ingesting raw client/stakeholder requirements |
| `sentinel-brownfield-harvest` | Harvesting cited technical context from an existing local codebase (`[OBSERVED]`/`[INFERRED]`) |
| `sentinel-annotate` | Contributing semantic gaps the lexical checklist missed (agent proposal) |
| `sentinel-challenge` | Stress-testing what is not being said with the 7 registry elicitation techniques |
| `sentinel-scrutiny` | Systematic multi-lens scrutiny; `--mode implementability-probe` pre-flight per `RU-*` |
| `sentinel-assume` | Registering governed BA-owned assumptions (risk × uncertainty priority signal) |
| `sentinel-gap-response` | Processing answered discovery gaps and reporting the knowledge metabolism |
| `sentinel-maturity` | Checking readiness before specs/backlog (metrics + development readiness matrix) |
| `sentinel-project-brief` | Generating or refreshing the mature project brief (per-section readiness + gates) |
| `sentinel-domain-request` | Asking domains for deeper context packs |
| `sentinel-specs` | Generating PRD and AI-friendly specs |
| `sentinel-compose` | Proposing cited PRD narrative through `/compose` (never hand-edits) |
| `sentinel-self-review` | Adversarial pass over PRD/specs: cited findings + hard-to-reverse decisions |
| `sentinel-backlog` | Generating and operating the governed backlog (lifecycle, AC freeze, board) |
| `sentinel-backlog-refine` | Proposing cited backlog refinements through `/refine-backlog` |
| `sentinel-implementation-feedback` | Downstream agents reporting blockers as governed feedback |
| `sentinel-quality` | Generating quality/test coverage |
| `sentinel-handoff-datasets` | Generating disposable synthetic datasets for the developer handoff (never governed, never cited) |
| `sentinel-sync` | Processing feedback, meetings, or changes |
| `sentinel-health` | Auditing health, traceability, and indexing |
| `sentinel-dashboard` | Generating and interpreting the portfolio dashboard |
| `sentinel-command-router` | Executing `/COMMAND` chat commands and routing to the right skill |
| `sentinel-privacy-local-first` | Enforcing local-only privacy rules |

## How To Ask Codex

Examples:

```text
Use sentinel-discovery to ingest this client note for project ACME_DASHBOARD.
```

```text
Use sentinel-maturity and tell me why the project is blocked.
```

```text
Use sentinel-sync to ingest this follow-up and generate an impact report.
```

```text
Use sentinel-gap-response to process this answered gaps file.
```

```text
Use sentinel-domain-request to ask Technology for a context pack.
```

```text
Use sentinel-health to audit ACME_DASHBOARD before handoff.
```

## Skill Responsibilities

### `sentinel-discovery`

Creates:

- raw copy
- digest
- requirement
- gaps
- decisions
- initial traceability
- local LanceDB memory entries for generated artifacts and workspace context folders

Can regenerate the human-friendly gap response contract with:

```powershell
python -m sentinel /gaps PROJECT_ID
```

Uses the maturity gap checklist:

```text
.codex/skills/sentinel-discovery/references/requirement-maturity-gap-checklist.md
```

This checklist helps agents decide whether unclear product, design/prototype, technology, frontend, backend, or quality information should be marked as a gap.

Before deeper analysis, use:

```powershell
python -m sentinel /retrieve PROJECT_ID --query "discovery topic" --workflow discovery --write-pack
```

### `sentinel-maturity`

Reads:

- gaps
- requirements
- `sentinel.config.yaml`

Creates:

- maturity report
- project brief when readiness reaches `READY_FOR_SPECS`

### `sentinel-gap-response`

Runs:

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source PATH
```

Creates:

- copied client response
- gap resolution report
- gap resolution log
- confirmed seeds and decisions for structurally confirmed answers
- trace links from `CHG` to `GAP`, `SEED`, and `DEC`

### `sentinel-project-brief`

Runs:

```powershell
python -m sentinel /brief PROJECT_ID
```

Creates or refreshes:

- `02_requirements/project-brief.md`

### `sentinel-domain-request`

Runs:

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
```

Creates:

- `08_context_packs/requests/[domain]_context_request.md`

### `sentinel-privacy-local-first`

Use this when handling project data, memory, retrieval, or exports.

Rules:

- no remote MCP for client/project content;
- no external embedding APIs;
- no external vector database;
- LanceDB and JSON fallback stay under the project workspace;
- source files remain the source of truth.

### `sentinel-specs`

Creates:

- `03_specs/prd.md` for the human/business narrative
- `03_specs/specs.md` for agent progressive disclosure
- `REQ/project_brief -> PRD -> SPEC` traceability

### `sentinel-backlog`

Creates:

- one Markdown file per epic as the primary human review artifact
- `US-00x.md` story mirrors for traceability and quality tooling
- one value story per confirmed `SPEC-U-*` unit, or a `[PENDING INPUT]` stub when no evidence-backed unit exists
- user stories with domain context coverage, agent execution contracts, and retrieval plans
- story-level `Slicing Pattern` and `Slicing Rationale` selected from `sentinel/slicing/backlog_slicing_model.json`
- acceptance criteria with fail-to-pass, pass-to-pass, and evidence classifications
- `08_context_packs/backlog_generation.json`
- `08_context_packs/implementation_readiness.json`
- `SPEC-U -> EPIC -> US -> AC` traceability, with `SPEC-001` retained as the index contract

Rules:

- prefer vertical, value-oriented stories;
- derive story scope from confirmed `03_specs/units/SPEC-U-NNN.md` files; do not expand a fixed placeholder story list;
- preserve the declarative INVEST/SPIDR/Lawrence slicing model and the separate cross-cutting enabler boundary;
- keep `[PENDING DOMAIN CONTEXT]` visible instead of inventing missing implementation detail;
- create a cross-cutting enabler epic only for concrete implementation work that must be built in advance to support confirmed project functionality;
- rerun `/reindex` and use focused retrieval if domain context changes after backlog generation; rerun `/backlog` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

### `sentinel-quality`

Creates:

- test case set
- `US -> TC` traceability
- dynamic `backlog_readiness_audit.md` with INVEST/SPIDR story quality scores and DoR warnings

### `sentinel-sync`

Creates:

- change node
- impact report
- `CHG -> impacted artifact` traceability
- local LanceDB memory entries for the change

### `sentinel-health`

Creates:

- health reports
- traceability findings
- memory indexing findings
- stale domain context findings when backlog was generated from an older domain snapshot

## Guardrail Hooks

Optional hooks live in:

```text
.codex/hooks/
```

They are reminders and guardrails, not the primary enforcement mechanism. The deterministic CLI commands remain the source of validation:

```powershell
python -m sentinel /validate PROJECT_ID
python -m sentinel /health PROJECT_ID
```

The post-tool hook also attempts to index edited workspace `.md` and `.txt` artifacts into local memory. Run `/reindex PROJECT_ID` if a workflow depends on fresh context.

### Agentic proposal channels

`sentinel-annotate`, `sentinel-challenge`, `sentinel-scrutiny`, `sentinel-assume`, `sentinel-compose`, `sentinel-backlog-refine`, and `sentinel-self-review` share the same shape: the agent authors a JSON payload with verbatim local citations, the matching command validates and merges it with a typed `origin`, and the runtime never lets the agent edit artifacts directly. Each skill documents its exact payload contract (field names, enums, and what the runtime rejects). All seven close with an identical **Agentic Spirit** block: never paraphrase a rejected citation (shorten to the exact verbatim substring or drop the finding), assign severity for the lifecycle (critical/high block maturity), write client-facing text in the workspace's `project_language`, and prefer `/retrieve --write-pack` focus packs over reading all of `00_raw/`.

### `sentinel-self-review`

Adversarial pass over generated PRD/specs before handoff: cited skeptical gaps (`origin: self-review`) plus hard-to-reverse `DEC-*` decisions with risk and reversibility, registered under `03_specs/self_review/` for BA review. The runtime never rewrites PRD/specs.

### `sentinel-implementation-feedback`

Lightweight contract for downstream planners/implementers/testers hitting a blocker in a story: finding types `new-dependency | gap | ac-challenge | surface-not-covered`, mandatory evidence, and what acceptance triggers (`GAP-FEEDBACK-*`, scoped `Stale`, the `implementation_feedback_resolved` DoD gate). Written for agents that do not carry the BA context.

### `sentinel-command-router`

Maps `/COMMAND PROJECT_ID [OPTIONS]` chat messages (also `sentinel /COMMAND` and `ignite /COMMAND` forms) to CLI executions for every manifest command, then routes to the matching skill for interpretation. A drift guard keeps it complete against the command manifest.

### `sentinel-dashboard`

Generates the local, read-only portfolio dashboard (`/dashboard`) and interprets its sections for status questions that do not name an exact command.

