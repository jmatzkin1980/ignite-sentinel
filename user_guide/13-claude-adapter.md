# Claude Adapter

Ignite Sentinel includes a repo-local adapter for Claude, covering three surfaces:

- **Claude Code in VS Code** (extension): native slash commands from `.claude/commands/`.
- **Claude Code CLI** (terminal): same slash commands, plus direct CLI usage.
- **Claude Desktop / Cowork**: no native slash commands, but `CLAUDE.md` provides routing rules so chat-style commands and natural-language requests map to the right Sentinel CLI sequence.

The adapter files are:

```text
CLAUDE.md            instructions loaded automatically by Claude sessions
.claude/commands/    one slash command per Sentinel command, plus /sentinel fallback
```

All commands call the same portable CLI as the Codex and Kilo adapters:

```powershell
python -m sentinel /COMMAND PROJECT_ID [OPTIONS]
```

## Setup check

Before relying on Claude chat commands in a freshly cloned repository, open the repo root in VS Code (or connect the folder in Claude Desktop) and run:

```text
/doctor
```

If LanceDB or another dependency is missing:

```powershell
python -m pip install -e .
python -m sentinel /doctor
```

## Slash commands

`.claude/commands/` mirrors `.kilo/commands/` one to one:

```text
/doctor
/init PROJECT_ID
/ingest PROJECT_ID --source PATH
/gaps PROJECT_ID
/annotate PROJECT_ID --source PATH
/challenge PROJECT_ID --source PATH
/resolve-gaps PROJECT_ID --source PATH
/maturity PROJECT_ID
/brief PROJECT_ID
/context-request PROJECT_ID --domain DOMAIN
/status PROJECT_ID
/export PROJECT_ID --artifact ARTIFACT --format md
/sync PROJECT_ID [--source PATH --note "NOTE"]
/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW
/reindex PROJECT_ID
/specs PROJECT_ID
/backlog PROJECT_ID
/quality PROJECT_ID
/trace PROJECT_ID
/health PROJECT_ID
/validate PROJECT_ID
/sentinel /COMMAND PROJECT_ID [OPTIONS]
```

If a slash command conflicts with a built-in Claude command on some surface, use the generic fallback:

```text
/sentinel /init PROJECT_ID
```

## Natural language usage

Claude sessions load `CLAUDE.md` automatically, so you can also describe the situation in plain language. Examples:

- "Tengo un nuevo requerimiento en este archivo, creá el proyecto, ingestalo y decime qué falta" → `/init` + `/ingest` + `/status`.
- "El cliente respondió los gaps en este documento" → `/resolve-gaps` + `/maturity` + `/status`.
- "Tecnología actualizó su contexto de arquitectura" → `/sync` + `/reindex` + `/health`.

Claude maps the intent to the right lifecycle sequence, runs the CLI, and summarizes generated artifacts, gaps, health, and the next recommended step.

## Rules Claude follows in this repo

- Generated artifacts are mutated only through Sentinel CLI commands, never by editing downstream outputs by hand.
- Lifecycle gates are respected: blocked maturity stops `/specs` and `/backlog`; `DIRTY` health stops `/backlog` and `/quality`. If a command is blocked, Claude explains why and recommends the prior step.
- Missing information stays visible as `GAP-*`, `[PENDING INPUT]`, or `[PENDING DOMAIN CONTEXT]`; nothing is invented.
- Local-first privacy applies: no client content, code, or embeddings are sent to external services.
- Framework changes go through a working branch and PR, never directly to `main`.

## Memory

Claude uses the same local memory layer as the other adapters. `/ingest`, `/sync`, and `/reindex` keep `workspaces/[PROJECT_ID]/memory.lancedb/` populated, while `/retrieve` builds focused context packs for the active workflow. Versionable workspace files remain the source of truth.

## Local MCP Server (Optional)

Sentinel can also expose the lifecycle as MCP tools over stdio, so Claude Desktop, Claude Code, or any MCP client can call commands directly (no chat-command parsing). It is 100% local: stdio transport, no network, same gates and command protocol.

Enable and run:

```powershell
python -m pip install -e .[mcp]
python -m sentinel.mcp --describe   # list the 18 tools
python -m sentinel.mcp              # start the stdio server
```

Claude Desktop / Claude Code configuration:

```json
{
  "mcpServers": {
    "ignite-sentinel": {
      "command": "python",
      "args": ["-m", "sentinel.mcp"],
      "cwd": "C:/path/to/ignite-sentinel"
    }
  }
}
```

Tools are named `sentinel_init`, `sentinel_ingest`, `sentinel_maturity`, etc. Gate violations return structured errors with the failing reason, so the client can recommend the right prior step. Without the optional `mcp` package, everything else (chat adapters, CLI) keeps working and `/doctor` reports a WARN.
