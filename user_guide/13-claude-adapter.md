# Using Sentinel on Claude Code

This page explains how Ignite Sentinel appears in Claude Code, how the commands and skills work there, what the hook enforces, and the limits. Read it after [installing](06-installation-vscode.md) if Claude Code is your surface.

There are two ways to have Sentinel in Claude Code. Use **one**, not both:

| | Clone | Plugin |
|---|-------|--------|
| Install | [Path B](06-installation-vscode.md#path-b-claude-code-clone) | [Path A](06-installation-vscode.md#path-a-claude-code-plugin-from-the-marketplace), details in the [plugin guide](18-claude-plugin.md) |
| Slash commands | Yes, one per command (`/ingest`, `/gaps`, ...) | No: ask in chat, or use the skills with the `ignite-sentinel:` prefix |
| Skills | 27, from `.claude/skills/` | The same 27, prefixed `ignite-sentinel:` |
| Hook that protects governed files | Yes, `.claude/settings.json` | Yes, shipped in the plugin |
| Needs a copy of the repository | Yes | No |
| Updates | `git pull` | Marketplace channel or pinned version |

The same Claude Code works in the terminal and in the VS Code extension. A chat-only Claude Desktop session has no shell and so cannot run Sentinel by itself; `CLAUDE.md` carries routing rules for it, but only Claude Code has been checked live.

## First 10 minutes (clone)

1. Open the repository folder in Claude Code.
2. `/doctor` should end with `PASS`.
3. Create a project, ingest a source, and ask for the next step:

   ```text
   /init ACME_PORTAL
   /ingest ACME_PORTAL --source input/client_requirement/request.md
   /next ACME_PORTAL
   ```

   Claude Code has a built-in `/init` of its own. If it answers instead of Sentinel, send `/sentinel /init ACME_PORTAL`.
4. A new project uses brief v2: confirm its profile and genesis once with `/brief ACME_PORTAL --profile UI,API --genesis greenfield`. Until then `GAP-BRIEF-PROFILE` is open and `/specs` refuses. See [Workflows](03-workflows.md).

With the plugin the steps are the same, spelled `sentinel /init ACME_PORTAL`, and `/doctor` runs in runtime mode, checking the runtime but not the clone's files (see the [plugin guide](18-claude-plugin.md#first-run)).

## Commands

In a clone, `.claude/commands/` holds one file per Sentinel command plus the `/sentinel /COMMAND ...` fallback. They are generated from one manifest, the same one that generates the Kilo Code commands. The commands, their options and the gates are in the [command reference](01-command-reference.md).

You can also describe the situation and let Claude choose. `CLAUDE.md` and the router skill map intent to commands:

| You say | Claude runs |
|---------|-------------|
| "New requirement in this file; create the project, ingest it and tell me what is missing." | `/init`, `/ingest`, `/next` |
| "The client answered the gaps in this document." | `/resolve-gaps`, `/maturity`, `/next` |
| "Technology updated its architecture notes." | `/sync`, `/reindex`, `/health` |

The full map is in [Driving Sentinel from chat](11-chat-commands.md).

## Skills

The 27 canonical skills are mirrored to `.claude/skills/`. Claude Code registers 26 as model-invocable; the 27th, `sentinel-privacy-local-first`, is human-only and runs only when you ask for it. Every skill has a name and a description, and Claude loads the one that matches the conversation: "the client answered the gaps" loads `sentinel-gap-response`; "this acceptance criterion cannot hold" loads `sentinel-implementation-feedback`. The catalog is in [Skills catalog](04-codex-skills-guide.md).

## What the hook enforces

Governed artifacts are written only by their command. A `PreToolUse` hook denies a hand `Write` or `Edit` of:

- `workspaces/<id>/02_requirements/project-brief.md`
- `workspaces/<id>/03_specs/*.md`
- `workspaces/<id>/04_backlog/*.md`

When it denies, it names the command that owns the file (`/brief`, `/specs`, `/backlog`). Reads are never blocked, and neither is the CLI, which is how those files are regenerated. If you need a different result in one of them, answer the gap, ingest new evidence or sync a change, then run the command again ([Workflows](03-workflows.md)).

The hook was watched refusing a write in Claude Code. It covers Claude's editor tools only: a write through some other channel is not seen by the hook, so `/health` also flags a hand edit of any hash-tracked file. Other rules Claude follows are in `CLAUDE.md`: gates are respected, missing information stays a visible `GAP-*`, and nothing is sent to external services.

> [!NOTE]
> In a clone and in the plugin alike, the hook finds Python by itself through `python.sh` (`.claude/hooks/python.sh` in a clone): `SENTINEL_PYTHON` first, then `python3`, `python` or `py -3` on `PATH` (the Microsoft Store alias is skipped), then the usual Windows install folders. If the hook seems to do nothing, set `SENTINEL_PYTHON` to the full path of `python.exe`.

### Optional: verify edits with a subagent

The clone ships a read-only subagent, `ignite-verifier`, and an opt-in hook example. When you copy the example into `.claude/settings.local.json`, a write to a governed artifact starts the verifier in an isolated context with read-only tools. It checks the change against cited evidence and reports `VERIFIED` or `BLOCKED`; it never fixes anything. Setup is in `.claude/hooks/README.md`. Nothing activates by default, and `/self-review` gives the same check through the governed channel.

## Memory

Claude uses the same local memory as the other surfaces: `/ingest`, `/sync` and `/reindex` keep `workspaces/<id>/memory.lancedb/` populated (or the JSON fallback when LanceDB is absent), and `/retrieve` builds focused context packs. The workspace files remain the source of truth. See [Traceability and memory](05-traceability-and-memory.md).

## Local MCP server (optional)

Sentinel can expose its lifecycle as 38 MCP tools over a local stdio channel, so any MCP client can call them without parsing chat. It makes no network calls and applies the same gates. A failed command returns an error result with the exit `code`, an `error` and a `next_step`.

In a clone: install the extra (`python -m pip install --require-hashes -r constraints/mcp.txt`, then `python -m pip install --no-deps -e .`), list the tools with `python -m sentinel.mcp --describe`, and start the server with `python -m sentinel.mcp`. In Claude Code, the supported route is the MCP plugin. Both are in the [plugin guide](18-claude-plugin.md#mcp-server-optional).

## Limits to know

- The plugin has no slash commands of its own; a clone has them.
- The MCP plugin and the clone's MCP setup have not been watched running in a session.
- Claude Code's own settings, models and data handling are out of Sentinel's control; for organization policy see the [admin guide](20-admin-guide.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/init` does something else | Use `/sentinel /init ACME_PORTAL`. |
| A hand edit was denied | That is the hook working. Use the command it names. |
| A command is refused (exit code 4) | A gate stopped it. Read the `next step:` line or run `/next ACME_PORTAL`. |
| Skills appear twice | The clone and the plugin are both installed. Remove one. |
| The project's commands are missing after adding a folder | Claude Code reads commands when a session starts; restart the session. |

## Next

- [Claude Code plugin guide](18-claude-plugin.md)
- [Command reference](01-command-reference.md)
- [Workflows by situation](03-workflows.md)
- [Driving Sentinel from chat](11-chat-commands.md)
