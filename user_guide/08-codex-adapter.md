# Using Sentinel on Codex

This page explains how Ignite Sentinel appears in Codex (Desktop, VS Code or CLI): how you give commands, how skills are found, what the guard script does, and where the limits are. Read it after [installing](06-installation-vscode.md#path-c-codex-clone) if Codex is your surface.

Sentinel on Codex runs from a **clone** of the repository. The Claude Code plugin is not a supported Codex path.

## What you get

| Piece | Where it lives | What it does |
|-------|----------------|--------------|
| Operating rules | `AGENTS.md` | Codex reads it at the repository root and learns the rules: sources are data, governed files change only through their command, nothing leaves the machine. |
| 27 skills | `.agents/skills/` (generated) | Guidance for each stage. Codex discovers this folder, searching from the working directory up to the repository root. |
| Command router | the `sentinel-command-router` skill | Turns a chat command such as `sentinel /ingest ACME_PORTAL --source ...` into the CLI call. |
| A guard script | `.codex/hooks/` | A policy script that refuses a hand edit of a governed artifact (see [Limits](#limits-to-know)). |

The skills are authored in `.codex/skills/`, but **Codex does not read that folder**. A generator (`python -m sentinel.adapters`) mirrors it into `.agents/skills/`. If a skill is missing in Codex, check `.agents/skills/`; never edit a mirror by hand.

## First 10 minutes

1. Open the repository folder in Codex.
2. `sentinel /doctor` should end with `PASS`.
3. Create a project, ingest a source, and ask for the next step:

   ```text
   sentinel /init ACME_PORTAL
   sentinel /ingest ACME_PORTAL --source input/client_requirement/request.md
   sentinel /next ACME_PORTAL
   ```
4. A new project uses brief v2, so confirm its profile and genesis once before specs: `sentinel /brief ACME_PORTAL --profile UI,API --genesis greenfield`. Until you do, `GAP-BRIEF-PROFILE` is open and `/specs` refuses. See [Workflows](03-workflows.md).

The `sentinel` prefix is the reliable form. The shorter `/init ACME_PORTAL` may also work, but Codex can take it for one of its own commands; when it does, resend with the prefix.

You can also describe the situation: "I received new client input at input/client_requirement/request.md. Create project ACME_PORTAL, ingest it and explain the open gaps." Codex chooses the commands, runs them and summarizes the result and the next step.

When `python` is not on the path, use the launcher in a terminal: `.\installers\sentinel.ps1 /doctor`. It also finds the Python runtime bundled with Codex Desktop.

## Skills you will meet most

The complete list is in the [skills catalog](04-codex-skills-guide.md).

| Skill | Use |
|-------|-----|
| `sentinel-discovery` | Ingest raw input; requirements, gaps, decisions |
| `sentinel-gap-response` | Process answered gaps |
| `sentinel-maturity` | Read the maturity gates |
| `sentinel-project-brief` | Generate or refresh the brief |
| `sentinel-specs`, `sentinel-backlog`, `sentinel-quality` | Downstream artifacts |
| `sentinel-sync` | Process changes |
| `sentinel-health` | Health, validation, traceability |
| `sentinel-domain-request` | Domain context requests |
| `sentinel-privacy-local-first` | Local-only privacy rules. Meant to be asked for by name. Its human-only marker is a Claude Code feature, so Codex can still start it on its own, which is harmless. The rules are always on through `AGENTS.md` anyway. |

Name one explicitly when you want it: "Use sentinel-maturity to evaluate ACME_PORTAL and explain what blocks specs."

## What is enforced

1. **Command gates (all surfaces).** The CLI refuses a command when its prerequisite is missing, and says why in a `next step:` line (exit code 4). Codex cannot skip this.
2. **Hand edits are detected.** `/health` flags a manual change to a hash-tracked file (`gaps.md`, `requirements.md`, the brief, specs, backlog).
3. **A guard script** (`.codex/hooks/pre_tool_use_policy.py`) blocks a hand write to the same files (`gaps.md`, `requirements.md`, `project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) and names the owning command.

## Limits to know

- **The guard script has not been watched live in Codex.** The repository ships the script and nothing in it registers the script with Codex. Treat items 1 and 2 above as your protection, and do not rely on the script alone.
- Slash commands may be intercepted by Codex. The `sentinel` prefix avoids it.
- The skills reach the runtime from the repository root; run Codex with the clone open.
- Skills that need the agent to write a JSON proposal (`/annotate`, `/challenge`, `/scrutinize`, `/assume`, `/compose`, `/self-review`) rely on the model; the runtime checks every quote against your sources, so a bad proposal is refused rather than applied.

## Plugin: not supported

Codex can read this repository's `.claude-plugin/marketplace.json`, and installing the plugin works. What nobody has observed is a plugin skill actually running in Codex, so treat the plugin as unsupported there and use the clone.

## If Codex is unavailable

Run the CLI from any terminal (`python -m sentinel /health ACME_PORTAL`) or use [Kilo Code](07-kilo-code-adapter.md) or [Claude Code](13-claude-adapter.md) on the same clone: all surfaces share the same workspace files.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| A skill does not show up | Check `.agents/skills/`. If it is empty or stale, run `python -m sentinel.adapters`. |
| `/init` does something else | Use `sentinel /init ACME_PORTAL`. |
| A command is refused (exit code 4) | A gate stopped it. Read the `next step:` line, or run `sentinel /next ACME_PORTAL`. |
| `python` not found | Use `installers/sentinel.ps1` or `installers/sentinel.sh`, or set `SENTINEL_PYTHON`. |

## Next

- [Command reference](01-command-reference.md)
- [Workflows by situation](03-workflows.md)
- [Skills catalog](04-codex-skills-guide.md)
- [Driving Sentinel from chat](11-chat-commands.md)
