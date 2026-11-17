# Using Sentinel on Kilo Code

This page explains how Ignite Sentinel appears inside Kilo Code (the VS Code extension): the slash commands, the agents, the skills, what Kilo itself refuses to do, and what to do when something does not work. Read it after [installing](06-installation-vscode.md#path-d-kilo-code-clone) if Kilo Code is your surface.

Sentinel on Kilo Code runs from a **clone** of the repository. Kilo has no Sentinel plugin and none is supported (see [Why a clone](#why-a-clone-and-not-a-plugin)).

## What you get

| Piece | Where it lives | What it does |
|-------|----------------|--------------|
| Slash commands | `.kilo/commands/` | One file per Sentinel command. Typing `/ingest ACME_PORTAL --source input/note.md` runs the CLI from the repository root. `/sentinel /COMMAND ...` is the fallback when a name clashes with a Kilo command. |
| 7 agents | `.kilo/agents/` | Modes for the main stages: `sentinel-discovery`, `sentinel-maturity`, `sentinel-specs`, `sentinel-backlog`, `sentinel-quality`, `sentinel-sync`, `sentinel-health`. |
| 27 skills | `.agents/skills/` (generated) | The model-facing guidance behind each stage. Kilo loads this folder by default. |
| Permission rules | `kilo.jsonc`, `.kilocodeignore` | Protect governed artifacts and pre-approve the Sentinel CLI. |

All of it calls the same CLI as every other surface: `python -m sentinel /command ...`. Everything below the chat is identical on Claude Code, Codex and a terminal.

## First 10 minutes

1. Open the repository folder in VS Code and Kilo Code chat.
2. `/doctor` should end with `PASS`.
3. Create a project and ingest a source:

   ```text
   /init ACME_PORTAL
   /ingest ACME_PORTAL --source input/client_requirement/request.md
   /next ACME_PORTAL
   ```
4. A new project uses brief v2, so confirm its profile and genesis once before specs: `/brief ACME_PORTAL --profile UI,API --genesis greenfield`. Until you do, `GAP-BRIEF-PROFILE` is open and `/specs` refuses. [The workflow guide](03-workflows.md) walks through this.

You can also describe what you need: "The client answered the gaps in input/interactions/answers.md, process them for ACME_PORTAL." Kilo picks the matching command or agent, runs it and summarizes the result and the next step.

## Commands in Kilo

Every command in the [command reference](01-command-reference.md) has a file in `.kilo/commands/`. If Kilo intercepts a name, write it as `/sentinel /init ACME_PORTAL`. If a command cannot run in chat at all, use the VS Code terminal: `python -m sentinel /health ACME_PORTAL`.

When Windows cannot resolve `python`, the launcher finds one: `.\installers\sentinel.ps1 /health ACME_PORTAL`.

## Agents

| Agent | Purpose |
|-------|---------|
| `sentinel-discovery` | Ingest raw input and create requirements, gaps and decisions |
| `sentinel-maturity` | Evaluate readiness |
| `sentinel-specs` | Generate specs |
| `sentinel-backlog` | Generate epics, stories, acceptance criteria and the readiness pack |
| `sentinel-quality` | Generate test coverage |
| `sentinel-sync` | Process changes and their impact |
| `sentinel-health` | Run health, validation and traceability checks |

Select one when you want its focus, for example: "Use the sentinel-discovery agent to ingest input/note.md for ACME_PORTAL." Each agent file declares only a name, a description and `mode: primary`; the repository does not set a model or per-agent permissions. Twenty of the 27 skills have no agent of the same name: they are used whenever the situation matches.

## Skills in Kilo

Kilo Code supports the Agent Skills standard and loads `.agents/skills/` by default, so the 27 skills work on a fresh clone with no configuration. Name one in chat ("Use `sentinel-backlog` to generate the backlog for ACME_PORTAL"), or describe the situation: the agent sees each skill's name and description first and loads the full text when it applies. The list is in the [skills catalog](04-codex-skills-guide.md).

> [!WARNING]
> Leave Kilo's "Claude Code Compatibility" setting **off**. With it on, Kilo also loads `.claude/skills/`, a byte-identical copy, and registers every skill twice under the same name.

To make the skills available outside this repository, add the clone's `.agents/skills` folder to `skills.paths` in your user-level Kilo config. Kilo does not trust paths that only a project config declares outside that project.

## What Kilo enforces

`kilo.jsonc` follows the schema Kilo publishes, and its rules were checked by hand in Kilo with auto-approve off:

| Rule | Effect |
|------|--------|
| `permission.edit` | Editing is allowed, except for the governed artifacts (`gaps.md`, `requirements.md`, `project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`), `.git/`, secrets, env files and build output. A hand edit of a governed artifact is stopped. The `gaps.md` and `requirements.md` rules were added later and have not been checked in Kilo yet. |
| `permission.read` | Reads stay open; local secrets ask first. |
| `permission.bash` | The Sentinel CLI (`python -m sentinel *`) and the clone launchers are pre-approved. Anything else follows Kilo's defaults. |

The point of the first rule is that governed artifacts are written only by their command (`/ingest`, `/gaps`, `/resolve-gaps`, `/brief`, `/specs`, `/backlog`). When you need a change in one of them, edit its inputs or answer the gap, then regenerate: see [Workflows](03-workflows.md). `/doctor` checks that `kilo.jsonc` denies the same files as the Claude Code and Codex hook, and `/health` also flags a hand edit of a hash-tracked file.

> [!NOTE]
> These are Kilo settings, not code Sentinel runs. `/doctor` verifies that the file is well formed and declares the rules, which is not proof that Kilo honours them. To confirm, try to edit a `04_backlog/*.md` with auto-approve off: Kilo should stop you.

## Limits to know

- The slash command files in `.kilo/commands/` and `.kilocodeignore` have not been watched live in Kilo; the agents, the skills and `kilo.jsonc` have.
- Skills that need the agent to write a JSON proposal (`/annotate`, `/challenge`, `/scrutinize`, `/assume`, `/compose`, `/self-review`) rely on Kilo's model; the runtime checks every quote before accepting a contribution, so a bad proposal is refused, not applied.
- If Kilo cannot run commands in your environment, use the terminal as above. Nothing in Sentinel depends on Kilo.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| A command does nothing | Open the repository root, not a subfolder, and check that `kilo.jsonc`, `.kilo/agents/` and `.kilo/commands/` are visible. |
| Kilo prompts for every command | The call differs from the approved pattern (`py -m sentinel`, a `.venv` path). Approve once or use `python -m sentinel`. |
| Warning naming `kilo.jsonc` at startup | The file does not match Kilo's schema and Kilo ignores the bad block. Run `python -m sentinel /doctor`, which checks it. |
| A command is refused (exit code 4) | A gate stopped it and printed a `next step:` line. `/next ACME_PORTAL` prints it again. |

## Why a clone and not a plugin

A Kilo plugin is a JavaScript or TypeScript module, and Kilo documents no skills-only plugin; Sentinel's runtime is Python. Kilo's marketplace for skills is curated by Kilo, and Sentinel's skills only make sense together with its runtime. Kilo also gives skills no variable for a plugin folder. So use the clone.

## Next

- [Command reference](01-command-reference.md)
- [Workflows by situation](03-workflows.md)
- [Skills catalog](04-codex-skills-guide.md)
- [Driving Sentinel from chat](11-chat-commands.md)
