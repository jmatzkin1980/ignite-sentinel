# Skills catalog

Skills are short, written playbooks that tell an AI agent how to do one Sentinel job well: how to read the evidence, which command to run, what the command accepts, and what to report back. This page lists all 27 skills, grouped by the stage of the project where you need them. Read it if you want to know what the agent is doing behind a chat request, or which skill to ask for by name.

You do not need to memorise skill names. In Claude Code, Codex and Kilo Code the agent loads the right skill from the wording of your request ("the client answered the gaps" loads `sentinel-gap-response`). The names matter when you want to be explicit, and when you read a log.

## How skills work

- **One source, three generated copies.** The 27 skills are written once under `.codex/skills/`. That folder is the canonical source, not a place any agent reads. `python -m sentinel.adapters` copies it into the folders the surfaces actually load. `.agents/skills/` and `.claude/skills/` are byte-for-byte copies. The plugin's copy (`plugins/ignite-sentinel/skills/`) changes one thing: each line that runs `python -m sentinel` is rewritten to run the plugin's own launcher through its Python finder. The rest of the skill text is identical everywhere.
- **Skills never edit governed artifacts.** The gaps, brief, specs and backlog files change only through Sentinel commands. A skill prepares the input (often a small JSON file with verbatim quotes from your evidence), runs the command, and reports what the command accepted and rejected. If the command rejects a citation, the agent shortens it to the exact quote or drops the finding; it never paraphrases to get past the check.
- **The runtime is the judge.** The agent proposes, the command validates and records, and you decide. Nothing a skill produces closes a gap or approves a decision by itself.
- **Skills drive the same commands you can type.** Every command a skill runs is documented in the [command reference](01-command-reference.md).

### Where skills appear on each surface

| Surface | Where the skills load from | How you use them |
| --- | --- | --- |
| Claude Code, clone | `.claude/skills/` | The agent auto-triggers a skill from your request. Ask for one by name if you like. |
| Claude Code, plugin | The plugin's skills, prefixed with the plugin name (for example `ignite-sentinel:sentinel-views`) | Same behaviour. Use the plugin or the clone, not both, or skills load twice. |
| Codex | `.agents/skills/` | Auto-trigger, or name the skill: "Use sentinel-maturity and tell me why the project is blocked." |
| Kilo Code | `.agents/skills/` | Auto-trigger, or name the skill in chat. |
| Plain terminal | None | Skills are agent playbooks. In a terminal you run the commands yourself, and you write the JSON inputs by hand or with any agent. |

Setup and daily use per surface: [Kilo Code](07-kilo-code-adapter.md), [Codex](08-codex-adapter.md), [Claude Code](13-claude-adapter.md). The plugin channel is in [Claude plugin](18-claude-plugin.md).

### Human-only skill

One skill, `sentinel-privacy-local-first`, is marked human-only (`disable-model-invocation: true`). The agent does not load it on its own; you invoke it deliberately. That marker is a Claude Code feature. In Codex and Kilo Code the skill can still trigger by itself, which is harmless. In a clone the privacy rules are always on, because `AGENTS.md` and `CLAUDE.md` carry them. The plugin ships neither file, so a plugin user does not get those always-on instructions. What a plugin user gets instead: the runtime enforces the core rules itself (memory stays local to the workspace, export goes only through audited commands, the backlog privacy scan runs), and the skills that touch client material carry a short local-first rule of their own (for example `sentinel-command-router`, `sentinel-intake-triage` and `sentinel-brownfield-harvest`). The other 26 skills are model-invocable.

### The proposal pattern

Seven skills share one shape, the proposal channel: `sentinel-annotate`, `sentinel-challenge`, `sentinel-scrutiny`, `sentinel-assume`, `sentinel-compose`, `sentinel-backlog-refine` and `sentinel-self-review`. The agent writes a JSON file in which every item carries a verbatim quote from your evidence. The matching command checks every quote against the files, merges what passes with an `origin` tag (so you can see who proposed it), and lists what it rejected and why. You review and decide.

## Catalog at a glance

| Stage | Skills |
| --- | --- |
| Before a project exists | `sentinel-intake-triage` |
| Discovery | `sentinel-discovery`, `sentinel-brownfield-harvest`, `sentinel-annotate`, `sentinel-challenge`, `sentinel-scrutiny`, `sentinel-assume`, `sentinel-gap-response`, `sentinel-sync`, `sentinel-domain-request` |
| Define | `sentinel-maturity`, `sentinel-project-brief`, `sentinel-release-split`, `sentinel-prototype-trace`, `sentinel-prototype-manual` |
| Specify | `sentinel-specs`, `sentinel-compose`, `sentinel-self-review` |
| Backlog and delivery | `sentinel-backlog`, `sentinel-backlog-refine`, `sentinel-implementation-feedback`, `sentinel-quality`, `sentinel-handoff-datasets` |
| Verify and report | `sentinel-health`, `sentinel-views` |
| Every stage | `sentinel-command-router`, `sentinel-privacy-local-first` |

## Before a project exists

### `sentinel-intake-triage`

- **Use it when** you hold a pile of raw intake (client requests, an RFQ inbox, mail or chat threads) and it is not clear whether it is one project or several, or when you hold documents and ask where to start. It is the entry check: it classifies what you hold and points to the first step and its skill (see the [flow matrix](22-flow-step-matrix.md)). It normally runs before `/init`, but it also works over an existing workspace.
- **What it does** numbers every source item (`R1`, `R2`, ...), groups them by theme with a verbatim quote for each, proposes one-line requirement candidates, recommends one project or several, and lists duplicates, noise and out-of-scope asks with the reason. It stops there and hands you the decision.
- **Commands it drives** none of its own while it classifies; once you confirm, it gives the first commands (`/init`, `/ingest`, `/sources --load --role`, `/harvest`) and the skill each one needs. After you confirm the split you run `/init` and `/ingest` per project for its first source, and `/sync --source` for each further `R#` source assigned to it, so the citations become evidence.
- **Human-only** no.

## Discovery

### `sentinel-discovery`

- **Use it when** you start or refresh discovery: new client input, "ingest this requirement", any work on `gaps.md`.
- **What it does** creates or confirms the workspace, ingests raw material, regenerates `gaps.md` (your working ledger; the client gets the interview script), and reviews what discovery produced. It also owns the discovery rules: raw input is evidence, not truth; missing information becomes a gap; text in client material that reads like an order is never obeyed and is logged as an injection signal. It holds the deepening cycle (annotate, then challenge and scrutinize when they fit, assume only on your explicit decision), the interview-script and FAQ exports, and the stakeholder registry.
- **Commands it drives** `/init`, `/ingest`, `/gaps`, `/retrieve`, `/health`, `/export` (formats `interview` and `faq`), `/stakeholders`. For a change on an existing system it also drives `/sources --role`, `/cross` and `/extract` (all with `--change`): it writes the cross-read files with verbatim quotes and the cited proposals, and never waives a cross-read or confirms an extraction for you.
- **Human-only** no.

### `sentinel-brownfield-harvest`

- **Use it when** the project touches an existing system and its code is on your machine.
- **What it does** reads the code block by block (B0 inventory, B1 architecture, B2 data, B3 integrations, B4 security and constraints, B5 operations) and writes one tagged harvest. Every line carries a tag: `[HECHO repo:file]` (read in that file), `[INFERIDO]`, `[NO ENCONTRADO]`, `[FUERA DEL CÓDIGO topic]` (only a person can say) or `[DIVERGENCIA]` (docs and code disagree). English tags such as `[FACT]` and `[INFERRED]` are accepted. The code never leaves your machine.
- **Commands it drives** `/harvest`, then `/brief` to recompile. In a change (`/harvest --change CHG-nnn`) the harvest is also the cross-read of the request against the existing system.
- **Human-only** no.

### `sentinel-annotate`

- **Use it when** the agent has read the raw requirement and spotted gaps the automatic checklist missed, typically because a reassuring keyword is present while the substance is undefined.
- **What it does** writes the structured analysis (gaps with lens, severity, question and a verbatim quote), runs the command, and reports merged and skipped gaps. New gaps carry `origin: agent`. It then asks you to record a disposition on each new gap.
- **Commands it drives** `/annotate`; follow-up `/gaps --id GAP-X --disposition accepted|rejected|irrelevant`.
- **Human-only** no.

### `sentinel-challenge`

- **Use it when** the requirement looks complete and you want to stress-test what nobody said.
- **What it does** runs elicitation techniques per lens: four by default (pre-mortem, role-play, assumption inversion, jobs-to-be-done forces) and three opt-in (red/blue team, first principles, stakeholder round-robin). The pre-mortem classifies imagined failures as Tiger, Paper Tiger or Elephant so you spend effort where it matters. Findings merge with `origin: challenge` and a `challenge_report.md` is written.
- **Commands it drives** `/challenge`.
- **Human-only** no.

### `sentinel-scrutiny`

- **Use it when** you want a systematic pass across the lenses against the raw input plus domain context, or a pre-flight check of what a coding agent would be missing.
- **What it does** three modes. Default scrutiny finds unstated assumptions, contradictions, mentions without detail and domain conflicts. `--mode implementability-probe` is a per-requirement-unit pass (every finding anchors to an `RU-*`) that says what is missing to implement it. `--mode anchors` reviews a brief v2 line by line, checking that each cited source really supports the sentence (holds, says less, says the opposite) and opens `GAP-ANC-*` gaps.
- **Commands it drives** `/scrutinize` (optional `--lens`).
- **Human-only** no.

### `sentinel-assume`

- **Use it when** you decide to move forward over a gray area on purpose, with an owner and a risk attached. The agent never proposes this on its own initiative.
- **What it does** registers governed assumptions: each has a lens, a human owner, a risk, an optional uncertainty and a verbatim basis. High risk with high uncertainty shows "test before advancing" (a signal, not a block), and the runtime may suggest the cheapest test. An assumption is never evidence.
- **Commands it drives** `/assume`.
- **Human-only** no.

### `sentinel-gap-response`

- **Use it when** a client or domain owner returns answers to the gaps, or when you want to work gaps live in chat.
- **What it does** runs the closure and explains the result: only a substantive answer with a confirmed (or not-applicable) decision closes a gap; a vague answer such as "TBD" stays partially closed. It reports what the closure moved (assumptions validated or invalidated, artifacts now stale) and plans question rounds with `/gaps --top N`. Its grill mode asks one gap per turn, drafts the response file, and closes everything with one `/resolve-gaps` at the end. A cited candidate option is never an answer.
- **Commands it drives** `/resolve-gaps`, `/gaps` (`--top`), `/maturity`, `/status`, `/export` (interview).
- **Human-only** no.

### `sentinel-sync`

- **Use it when** new information arrives after discovery (meeting notes, a client mail, a design update, a late blocker, a new version of a document) and must become a traceable change instead of silent scope creep.
- **What it does** registers the change with an impact report, detects new or modified sources by content hash, and, with `--digest`, extracts proposed answers, decision candidates, new gaps and assumption contradictions from unstructured text. The digest proposes and routes; it applies nothing. It also manages the source registry: when a known file arrives with new content it asks you which version governs, and never assumes the newest one does.
- **Commands it drives** `/sync` (with `--digest`), `/sources`, `/retrieve`, `/reindex`, `/health`.
- **Human-only** no.

### `sentinel-domain-request`

- **Use it when** Technology, Design, Quality, Frontend or Backend must deepen the analysis from the brief.
- **What it does** generates a cited request per domain that tells the domain team what to document. It does not do their analysis. It also manages a request's life (`active`, `answered`, `closed`, `obsolete`), and reminds you that delivered packs should carry `when_to_read:` frontmatter and one owner per fact.
- **Commands it drives** `/context-request` (`--domain`, or `--id CTX-NNN --status ...`).
- **Human-only** no.

## Define

### `sentinel-maturity`

- **Use it when** you ask "is this ready for specs?" or a downstream command was blocked by maturity.
- **What it does** runs the check and reads the report: gap closure rate, maturity score and trend, requirement quality, where maturation stalls, and the development readiness matrix (16 areas and a per-unit table of what is confirmed, deferred to a domain pack, or open). It offers the next move as options, not one directive: chase blocking gaps, raise a context request, validate an assumption first, or proceed.
- **Commands it drives** `/maturity`, with `/resolve-gaps` and `/context-request` as remedies. In a workspace that only holds changes it refuses, writes nothing and points to `/status --change` and `/next --change`.
- **Human-only** no.

### `sentinel-project-brief`

- **Use it when** discovery is stable and you generate or refresh the project brief, or when a pending place or a gate needs explaining.
- **What it does** confirms the brief settings with you (profile, genesis, validation direction, brief version), runs `/brief`, and reads the result: the per-section readiness, the compile report (which places are waiting on a client gap and which on domain context), and the three gates (brief coverage, unit implementability, specification self-correction). It never applies the settings proposal on its own and never writes the brief body. New projects use brief v2, so until profile and genesis are confirmed the blocking `GAP-BRIEF-PROFILE` stays open and `/specs` refuses.
- **Commands it drives** `/status`, `/maturity`, `/brief`, `/validate`.
- **Human-only** no.

### `sentinel-release-split`

- **Use it when** a brief v2 may be too big for one release and you want a release series.
- **What it does** reads the assessment, walks the release split model (criteria written before cutting, core and variations, the shared base, contracts as named nodes, releases with a closing check, sketches, inheritance of open gaps) and writes the proposal JSON. It helps you get the partition green, and then guides derivation per release, moving a unit between releases, and closing a release. Confirming, moving and closing need the names of the BA and the technical team; the agent never supplies them.
- **Commands it drives** `/split` (`--assess`, `--propose`, `--confirm`, `--move`, `--close`), then `/specs`, `/backlog`, `/status` with `--release rN`.
- **Human-only** no.

### `sentinel-prototype-trace`

- **Use it when** an HTML prototype is ingested and inventoried and you want to know what each screen element stands on.
- **What it does** walks one screen per pass, in the surface's browser when there is one, and traces each element to its data, contract and rule against the brief. Each element is graded established, inferred, unsupported or demo. It checks the four states (ideal, empty, loading, error) and common prototype defects, and asks at most four questions per pass. If it cannot open the screen it says so (`executed: false`) and traces only what the inventory and the brief state.
- **Commands it drives** `/prototype --inventory` (first), then `/prototype --trace`.
- **Human-only** no.

### `sentinel-prototype-manual`

- **Use it when** you want the user manual of an ingested prototype.
- **What it does** writes, screen by screen, what the user does, citing interface elements as placeholders such as `{{S2-E06}}` so the runtime injects the real words. A screen it cannot describe from the inventory stays without a manual and shows as a hole in the view.
- **Commands it drives** `/prototype --inventory`, `/prototype --manual`, `/view --artifact prototype-manual`.
- **Human-only** no.

## Specify

### `sentinel-specs`

- **Use it when** a mature brief is ready and you generate or review the PRD and the specification layer.
- **What it does** runs `/specs` and reads what it produced: the human PRD, the compact `specs.md` index and the bounded `SPEC-U-*` execution units. It explains foundation-drift warnings and summarises the per-unit delta report after a regeneration. PRD content is quoted from raw input; with no signal a section stays pending. A non-goal is added by closing a gap as not applicable, never by editing the PRD.
- **Commands it drives** `/maturity`, `/specs` (and `--release rN` for a series), `/trace`.
- **Human-only** no.

### `sentinel-compose`

- **Use it when** the generated PRD is accurate but thin and you want better narrative that is still backed by evidence.
- **What it does** writes agent-authored paragraphs, each with verbatim citations, and merges them into the PRD as an `Agent Composition` block tagged `origin: agent`. Blocks aimed at a still-pending section, or with citations that are not verbatim, are rejected. On a later `/specs` regeneration only still-valid blocks are reapplied.
- **Commands it drives** `/compose` (after `/specs`), and `/compose --change CHG-NNN` onto the PRD of a change.
- **Human-only** no.

### `sentinel-self-review`

- **Use it when** you want an adversarial pass before handoff. It has three modes.
- **What it does** the default mode reviews the PRD and specs: cited skeptical gaps (`origin: self-review`) and hard-to-reverse `DEC-*` decisions, registered for your review without rewriting anything. `--sufficiency` runs on a brief v2 alone, from a clean context, and answers "could a builder start tomorrow?" place by place, opening `GAP-SUF-*` gaps; repeat the round after answers arrive. `--crosses` checks that the lenses of the brief agree and opens `GAP-XRV-*` gaps.
- **Commands it drives** `/self-review` (`--sufficiency`, `--crosses`).
- **Human-only** no.

## Backlog and delivery

### `sentinel-backlog`

- **Use it when** you turn specs into the backlog and operate it: generate, order, change story status, rebuild the board.
- **What it does** runs `/backlog` and explains the result: one vertical story per confirmed spec unit, concrete enabler epics only when justified, the slice plan (enablers first, then waves), the readiness pack for downstream agents, and the acceptance-criteria freeze that happens when a story becomes Ready. It governs the story lifecycle and the board, and reminds you that a status change is made only with `/story-status`.
- **Commands it drives** `/maturity`, `/backlog` (`--with-task-seeds`, `--story-format`, `--release rN`), `/backlog-status`, `/story-status`, `/implementation-feedback`, `/quality`, `/trace`, `/health`.
- **Human-only** no.

### `sentinel-backlog-refine`

- **Use it when** a story is too big, two should merge, one is missing, or an enabler candidate appeared.
- **What it does** writes cited refinement proposals (`reslice`, `split-story`, `merge-stories`, `missing-story`, `enabler-candidate`) and merges them as an agent overlay for you to review. Nothing is rewritten automatically.
- **Commands it drives** `/refine-backlog`, and `/refine-backlog --change CHG-NNN` over the stories of a change.
- **Human-only** no.

### `sentinel-implementation-feedback`

- **Use it when** a planning, implementation or testing agent hits a blocker in a story: a new dependency, a gap, an acceptance criterion that cannot hold, or a surface no story covers.
- **What it does** gives that agent a small contract: report the finding with evidence through the command, never patch the story. Accepted findings are traced, a gap-type finding opens `GAP-FEEDBACK-*`, affected stories may be marked Stale, and open findings can block a story's Done.
- **Commands it drives** `/implementation-feedback` (a story of a change needs no flag: its units are checked against that change).
- **Human-only** no.

### `sentinel-quality`

- **Use it when** the backlog exists and you want test cases and a readiness audit.
- **What it does** generates test cases traced to stories and the backlog readiness audit (INVEST, slicing, acceptance coverage, dependencies). Findings are Definition-of-Ready warnings by default; strict gates are an opt-in.
- **Commands it drives** `/quality` (and `--override` with cited decisions when you proceed on purpose), `/quality --change CHG-NNN` for the stories of one change (its own folder and verdict), `/trace`, `/health`.
- **Human-only** no.

### `sentinel-handoff-datasets`

- **Use it when** a developer handoff needs realistic sample data to exercise the specs and stories.
- **What it does** generates synthetic CSV, JSON or SQL files whose shape comes from the governed specs and whose values are invented. Everything lands under `08_context_packs/synthetic/`, is marked `SYNTHETIC — not evidence`, and is git-ignored and disposable. It is never cited and never traced, and `/validate` flags any citation to it.
- **Commands it drives** none. It is skill-only.
- **Human-only** no.

## Verify and report

### `sentinel-health`

- **Use it when** you ask whether the workspace is healthy, a verdict is `DIRTY`, validation warns, or before handoff.
- **What it does** runs the checks and explains the remedy as a ladder: regenerate through the owning command, add context upstream and reindex, or record a cited override when you proceed on purpose. It detects hand edits of governed files and never "fixes" them by editing back. The non-blocking blocks (semantic quality, cross-artifact consistency, question quality, standards coverage) are maturity lenses, not gates.
- **Commands it drives** `/health`, `/trace`, `/validate` (`--override`), `/doctor`.
- **Human-only** no.

### `sentinel-views`

- **Use it when** you ask for project or portfolio status in plain words, "show me the dashboard", or "open the PRD view".
- **What it does** generates and explains the read-only HTML pages: the portfolio dashboard and the per-artifact views (gaps, brief, PRD, specs, backlog, readiness, release guide, diagrams, and the prototype views). The readiness view answers "what is missing, and from whom?". Views never change a workspace; corrections go through `/sync` or `/resolve-gaps`. It suggests where to start across workspaces and runs no follow-up command without asking.
- **Commands it drives** `/dashboard` (`--theme`, `--open`), `/view`.
- **Human-only** no.

## Every stage

### `sentinel-command-router`

- **Use it when** you type a chat command such as `/init PROJECT_ID`, `sentinel /health PROJECT_ID` or `ignite /status PROJECT_ID` and want it executed from chat.
- **What it does** parses the command, runs it with `python -m sentinel` (or the repo launcher when `python` is missing), summarises the result, and routes to the skill of that stage to interpret it. It leads `/status` with the verdict and never calls a workspace ready unless the verdict is `READY`. If the chat UI swallows a slash command, send it with the `sentinel` prefix.
- **Commands it drives** every command in the registry. See [Chat commands](11-chat-commands.md) for the intent map.
- **Human-only** no.

### `sentinel-privacy-local-first`

- **Use it when** you want the full local-first rule set or an export checklist: source of truth in versionable workspace files, retrieval memory local to the workspace, no remote MCP, vector database or embedding service for client content, and export only through audited commands.
- **What it does** is a deliberate reference. In a clone the non-negotiable rules are always on in `AGENTS.md` and `CLAUDE.md`; the plugin ships neither file (see [Human-only skill](#human-only-skill)).
- **Commands it drives** `/export` as the audited way out.
- **Human-only** yes. Invoke it on purpose; it does not auto-load.

## Which skill writes the input file

| Command | You or the agent | Skill |
| --- | --- | --- |
| `/annotate`, `/challenge`, `/scrutinize`, `/assume`, `/self-review`, `/compose`, `/refine-backlog`, `/implementation-feedback` | The agent writes the JSON from your evidence. You review the result. | the matching skill |
| `/harvest` | The agent writes the tagged Markdown from the code. | `sentinel-brownfield-harvest` |
| `/split --propose`, `/prototype --trace`, `/prototype --manual` | The agent writes the JSON. | `sentinel-release-split`, `sentinel-prototype-trace`, `sentinel-prototype-manual` |
| `/resolve-gaps` | The client answers `gaps.md`, or the agent drafts the answers you confirm. | `sentinel-gap-response` |
| `/split --confirm`, `--move`, `--close` | You supply the BA and technical-team names and the evidence. | `sentinel-release-split` |

## Next

- Worked examples that use these skills end to end: [Scenarios](12-scenarios.md).
- Every command and flag: [Command reference](01-command-reference.md).
- Typing commands in chat, and the intent map: [Chat commands](11-chat-commands.md).
- Per-surface setup: [Kilo Code](07-kilo-code-adapter.md), [Codex](08-codex-adapter.md), [Claude Code](13-claude-adapter.md).
- The writing conventions for skills (maintainers): [Skill authoring checklist](references/skill-authoring-checklist.md).
