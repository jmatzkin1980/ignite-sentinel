---
name: sentinel-brownfield-harvest
description: "Use on a brownfield project when an existing system's codebase is available locally and Ignite needs technical context about it — observed architecture, surfaces and integrations, data models, constraints — as discovery evidence: read the code and write cited docs into 00_raw/02_technology_context/, marking every claim [OBSERVED] or [INFERRED]. Trigger on 'harvest the existing system', 'read the current codebase for context', or brownfield technical-context needs before or alongside /ingest."
---

# Sentinel Brownfield Harvest

Use this skill on a **brownfield** project: there is an existing system whose repository is available **on the machine**, and Ignite needs technical context about it as evidence. It guides you to read that code and produce cited, consumable technical-context docs under `00_raw/02_technology_context/`, so discovery, gaps, and downstream artifacts ground on the real system instead of on assumptions. The existing ingest consumes these docs as technical domain evidence with **no runtime change**.

## When to use / when not

- **Use** when the project touches or extends a system that already exists in code, that code is local, and you need its architecture, integrations, data models, or constraints as grounded evidence.
- **Do not use** on a greenfield project (nothing to harvest). And do not use this to *ask a domain team* for analysis — that is `/context-request --domain technology` (`sentinel-domain-request`). This skill reads **code**, it does not interview people; product/business intent stays with the client requirement and discovery.

## Workflow

1. **Confirm local access and scope.** Identify which repo(s)/paths of the existing system are on the machine and in scope. Nothing leaves the machine (see Rules). If the code is not local, stop — do not fetch it through an external service.
2. **Survey, don't guess.** Read the code to *observe* four areas: **architecture** (modules/services/components and how they relate), **surfaces & integrations** (endpoints, events, external systems, auth boundaries), **data models** (entities, schemas, key tables/collections), and **constraints** (runtime/versions, NFRs, limits visible in config/CI/build).
3. **Write one doc per area** into `00_raw/02_technology_context/` — e.g. `architecture.md`, `surfaces-integrations.md`, `data-models.md`, `constraints.md`. Use Markdown/txt/html so the existing ingest picks them up unchanged. Optional frontmatter `respondent_profile: technical`.
4. **Mark every claim `[OBSERVED]` or `[INFERRED]`.** `[OBSERVED]` = you read it directly in a specific file (cite the path, and symbol/line when useful). `[INFERRED]` = a reasonable deduction the code does not state outright — mark it and name what it rests on. If you can neither observe nor safely infer, write `[PENDING DOMAIN CONTEXT]` and let discovery raise the gap. Never present a guess as fact.
5. **Cite the code.** Every `[OBSERVED]` claim points to `path/to/file` (plus symbol/line when it helps a reader verify). Citations reference the existing system's files; you do **not** copy the source wholesale into the workspace — harvest structure and patterns, not a proprietary source dump.
6. **Hand to ingest.** Once the docs are written, `/ingest PROJECT_ID --source ...` (or `/sync` for later updates) consumes them as technical domain evidence with no runtime change. Discovery, `/gaps`, and specs can then cite the harvested context.

## Output

One or more Markdown docs under `00_raw/02_technology_context/`. Each is a set of headings (by area) whose every bullet is a single claim tagged `[OBSERVED]` or `[INFERRED]` with its code citation, and any unknown left as `[PENDING DOMAIN CONTEXT]`. These are ordinary domain-context inputs — not a governed artifact of their own — so they flow through ingest like any other technical-context file.

## Rules

- **Privacy, local-first — non-negotiable.** The existing system's code never leaves the machine: no external service, no remote embeddings, no remote MCP, no pasting proprietary source into an external tool to "summarize the repo". See `sentinel-privacy-local-first`.
- **No client-identifiable persistence.** Per AGENTS.md, only genericized patterns/structure go into versioned artifacts — never persist client names, system names, endpoints, credentials, or identifiable data.
- **Observed-vs-inferred is a contract, not a nicety.** No unmarked claim: an unmarked line reads as established fact and silently pollutes discovery. `[OBSERVED]` requires reading the code that proves it; a name-based or convention-based deduction is `[INFERRED]` at best.
- **Don't invent.** A missing fact is `[PENDING DOMAIN CONTEXT]` (or a `GAP-*` once ingested), never a plausible-sounding fill.
- **Cite the code for every `[OBSERVED]` claim**, and reference files by path — do not dump the source tree into the workspace.
- **Feeds existing ingest.** Write into `00_raw/02_technology_context/` in a consumable format; there is no new command and no runtime change, and generated downstream artifacts are still mutated only via Sentinel commands.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Unmarked claim presented as fact** — a technical-context line with no `[OBSERVED]`/`[INFERRED]` tag. → Tag every claim; an untagged line is indistinguishable from an invented one downstream.
- **Calling an inference "observed"** — deducing architecture from folder names or naming conventions and stamping it `[OBSERVED]`. → `[OBSERVED]` needs the code that proves it; a convention-based deduction is `[INFERRED]`.
- **Copying the whole source tree in** — pasting proprietary code into the workspace as "context". → Cite by path; harvest structure and patterns, not a source dump (privacy + SSoT).
- **Sending code to an external tool** — uploading the repo to an outside service to summarize it. → Local-first is non-negotiable; the harvest runs on the machine.
- **Filling an unknown with a guess** — writing a plausible endpoint or schema you never actually saw. → `[PENDING DOMAIN CONTEXT]`; let discovery raise the gap.
