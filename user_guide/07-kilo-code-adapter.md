# Kilo Code Adapter

Ignite Sentinel includes a repo-local Kilo Code adapter under:

```text
.kilo/agents/
```

These 7 agents are Kilo's mode layer (each declares its own model, mode and permissions) and call the same portable CLI:

```powershell
python -m sentinel ...
```

They are **not** Kilo's only model-facing depth: the 24 Sentinel skills also load in Kilo — see [Skills in Kilo](#skills-in-kilo) below.

Before relying on Kilo chat commands in a freshly cloned repository, run the setup check from Kilo chat:

```text
/doctor
```

If LanceDB or another dependency is missing:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Agents

| Agent | Purpose |
| --- | --- |
| `sentinel-discovery` | Ingest raw input and create requirements, gaps, decisions |
| `sentinel-maturity` | Evaluate readiness |
| `sentinel-specs` | Generate AI-friendly specs |
| `sentinel-backlog` | Generate epics, stories, acceptance criteria, retrieval plans, and implementation readiness pack |
| `sentinel-quality` | Generate test coverage |
| `sentinel-sync` | Process changes and impact |
| `sentinel-health` | Run health, validation, traceability checks, including stale domain context detection |

Kilo agents use the same local LanceDB memory layer as Codex. `/ingest`, `/sync`, and `/reindex` keep `workspaces/[PROJECT_ID]/memory.lancedb/` populated, while `/retrieve` builds focused context packs for the active workflow.

If the VS Code environment cannot resolve `python`, use the repo-local launcher from the terminal or from the generic `/sentinel` workflow when allowed:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /status PROJECT_ID
```

The launcher preserves the same CLI contract and only changes how the Python runtime is found.

When Kilo generates backlog, review both:

```text
workspaces/[PROJECT_ID]/08_context_packs/backlog_generation.json
workspaces/[PROJECT_ID]/08_context_packs/implementation_readiness.json
```

If `/health` reports that domain context changed after backlog generation, run `/reindex PROJECT_ID` and retrieve focused context before handing work to implementation or test agents. Rerun `/backlog PROJECT_ID` only when the change materially affects story scope, sequencing, acceptance criteria, dependencies, or execution contracts.

## Skills in Kilo

Kilo Code supports the Agent Skills standard, so the 24 Sentinel skills are **not** Codex- or Claude-only. Per Kilo's documentation, it discovers skills in:

```text
.kilo/skills/           project-level
~/.kilo/skills/         global
.agents/skills/         compatibility directory, loaded by default
.claude/skills/         compatibility directory, only when "Claude Code Compatibility" is enabled
```

plus any extra location declared through `skills.paths` / `skills.urls` in `kilo.jsonc`.

This repository generates `.agents/skills/` from the canonical `.codex/skills/` (`python -m sentinel.adapters`), so **the 24 skills are available in Kilo on a fresh clone with no extra configuration** — that is the directory Kilo loads by default. Nothing needs to be copied into `.kilo/skills/`.

How to use them:

- Name the skill in chat when you want a specific one: *"Use `sentinel-backlog` to generate the backlog for ACME_DASHBOARD."*
- Otherwise describe the situation. Skills follow progressive disclosure: the agent sees `name` + `description` first and loads the body only when the workflow applies, so the description is what makes a skill selectable.
- The deeper `references/*.md` layer of a skill is read on demand, and it needs no configuration: Kilo allows reads by default, so a skill can open its own references without an extra permission prompt. Confirmed live on Kilo Code 7.4.16.

> **Leave "Claude Code Compatibility" off.** With it enabled Kilo loads `.agents/skills/` **and** `.claude/skills/` — in this repo those are byte-identical mirrors, so the same 24 skills are registered twice under the same `name`. Kilo's documentation defines precedence only between project and global scope, not between two compatibility directories holding the same skill, so the outcome of that collision is unspecified. `.agents/skills/` alone covers this repo.

The 7 agents in `.kilo/agents/` and the skills coexist. What each agent actually declares today is `name`, `description` and `mode: primary` — Kilo *supports* per-agent model and permission choices, but this repo does not use them. The practical difference is that an agent body is always in context once you pick that mode, whereas a skill loads when the agent judges it relevant; and 17 of the 24 skills have no agent counterpart.

## Plugin: use the clone

Kilo Code, including the VS Code extension, runs Sentinel from the clone: `.agents/skills`, `.kilo/agents` and `.kilo/commands`. There is no Sentinel plugin for Kilo, and none is planned while Kilo's plugin format stays as documented today (IMP-281):

- A Kilo plugin is a JavaScript/TypeScript module. A marketplace entry (`PLUGIN.yaml`) points at an npm package, or at a git repo whose `package.json` exports `./server` or `./tui`. Kilo documents no skills-only plugin, and Sentinel's runtime is Python with no JS (`sentinel/` is stdlib-only).
- Kilo's marketplace has a separate item type for skills, but it is a catalogue curated by Kilo. Sentinel's 24 skills drive one Python runtime and only make sense together, so they are not suited to it.
- Kilo exposes no plugin path variable to skills, so the Claude Code plugin's `${CLAUDE_PLUGIN_ROOT}` invocation would not resolve there either.

Sources: the Kilo marketplace README (`Kilo-Org/kilo-marketplace`, `plugins/README.md`) and kilo.ai's plugin and skills docs, read on 2026-11-07 for Kilo Code 7.8.27.

If you want the skills available outside this repository, add the clone's `.agents/skills` folder to `skills.paths` in your **user-level** Kilo config. Kilo does not trust paths that only a project config declares outside that project.

## Slash Workflows

Kilo Code supports repo-local workflows in `.kilo/commands/`. In this repo, those workflows let you type short Ignite commands directly in Kilo chat.

Non-technical users can also describe the situation in plain language. Kilo should use the matching Sentinel agent or command workflow and then summarize the generated artifacts and next step.

Examples:

```text
/doctor
/init ACME_DASHBOARD
/ingest ACME_DASHBOARD --source input\client_requirement\sync-guide.md
/gaps ACME_DASHBOARD
/resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
/maturity ACME_DASHBOARD
/brief ACME_DASHBOARD
/context-request ACME_DASHBOARD --domain technology
/status ACME_DASHBOARD
/sync ACME_DASHBOARD --source input\interactions\client-answer.md --note "client follow-up"
/retrieve ACME_DASHBOARD --query "client gap response" --workflow sync
/specs ACME_DASHBOARD
/backlog ACME_DASHBOARD
/quality ACME_DASHBOARD
/trace ACME_DASHBOARD
/health ACME_DASHBOARD
/validate ACME_DASHBOARD
```

If a command name conflicts with the chat surface, use the generic fallback:

```text
/sentinel /init ACME_DASHBOARD
```

## Suggested Prompt

```text
Use the sentinel-discovery agent to ingest input/client-note.md for project ACME_DASHBOARD.
```

Other plain-language examples:

```text
The client answered gaps in input\interactions\answered-gaps.md.
Process them for ACME_DASHBOARD and tell me whether discovery is ready for a brief.
```

```text
Generate backlog for ACME_DASHBOARD and tell me whether any story still needs Technology, Design, or Quality context.
```

## Permissions

The repo includes:

```text
kilo.jsonc
.kilocodeignore
```

`kilo.jsonc` follows the schema Kilo publishes at `https://app.kilo.ai/config.json`, declared in the file's own `$schema` line so VS Code validates it as you edit. Permissions live under the top-level `permission` key, as a map of pattern to `allow` / `ask` / `deny` per tool:

- `permission.edit` allows edits generally and **denies** the governed artifacts (`project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`), plus `.git/**`, secrets, env files and build output. Governed artifacts are regenerated through their owning command, never typed over.
- `permission.read` leaves reads open and holds back only local secrets. Skills and their `references/*.md` need no entry.
- `permission.bash` pre-authorizes the Sentinel CLI with a single `python -m sentinel *` pattern, so adding a command later cannot leave the config behind. Anything not listed falls to Kilo's own default rather than to a stricter rule invented here.

> **A caveat worth keeping.** These rules are vendor configuration, not code this project runs. The published schema documents the *shape* but not the matching semantics — glob syntax, relative versus absolute paths, precedence between rules. `/doctor` therefore checks that the rules are declared correctly, which is not the same as proving Kilo honours them. If you depend on the governed-artifact deny, confirm it in Kilo with auto-approve off: try to edit a `04_backlog/*.md` and check you are stopped. The two surfaces with deterministic enforcement are Claude Code and Codex, and the CLI gate is what all three share.

If a new Sentinel command is added later, `.kilo/commands/` still needs the new workflow file; `kilo.jsonc` does not, because the CLI is pre-authorized by pattern.

## In Restricted Environments

If Kilo cannot execute commands, use the VS Code terminal manually:

```powershell
python -m sentinel /doctor
python -m sentinel /retrieve PROJECT_ID --query "topic" --workflow sync --write-pack
python -m sentinel /health PROJECT_ID
```

If `python` is unavailable in that terminal, use:

```powershell
.\installers\sentinel.ps1 /doctor
.\installers\sentinel.ps1 /health PROJECT_ID
```

