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
/dashboard
/init PROJECT_ID
/ingest PROJECT_ID --source PATH
/gaps PROJECT_ID
/annotate PROJECT_ID --source PATH
/challenge PROJECT_ID --source PATH
/scrutinize PROJECT_ID --source PATH [--mode implementability-probe]
/assume PROJECT_ID --source PATH
/resolve-gaps PROJECT_ID --source PATH
/maturity PROJECT_ID
/brief PROJECT_ID
/context-request PROJECT_ID --domain DOMAIN
/stakeholders PROJECT_ID [--add --id ID --name NAME --domain DOMAIN]
/status PROJECT_ID
/export PROJECT_ID --artifact ARTIFACT --format md
/export PROJECT_ID --artifact prd --format mdx
/export PROJECT_ID --artifact ARTIFACT --format interview|faq
/sync PROJECT_ID [--source PATH --note "NOTE" --digest]
/retrieve PROJECT_ID --query "TEXT" --workflow WORKFLOW
/reindex PROJECT_ID
/specs PROJECT_ID
/self-review PROJECT_ID --source PATH
/compose PROJECT_ID --source PATH
/view PROJECT_ID --artifact ARTIFACT [--open]
/backlog PROJECT_ID [--with-task-seeds --story-format user|job]
/backlog-status PROJECT_ID
/story-status PROJECT_ID --story US-NNN --set STATE [--owner NAME --evidence PATH]
/refine-backlog PROJECT_ID --source PATH
/implementation-feedback PROJECT_ID --source PATH
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

## Skills (model-invoked)

The 24 canonical skills under `.codex/skills/` are mirrored byte-for-byte to `.claude/skills/`, so Claude Code registers the 23 model-invocable ones (the human-only `sentinel-privacy-local-first`, marked `disable-model-invocation: true`, is invoked deliberately and never auto-triggered): every skill carries validated `name`/`description` frontmatter (enforced by `/doctor` and the repo test suite), and Claude auto-triggers the right one from the description when the conversation matches — "the client answered the gaps" loads `sentinel-gap-response`, "this AC can't hold" loads `sentinel-implementation-feedback`, and so on, without the user naming the skill.

Full catalog and per-skill responsibilities: [Codex Skills Guide](04-codex-skills-guide.md) (same skills, same contracts — only the mirror directory differs). The seven agentic proposal skills close with an identical Agentic Spirit block (verbatim-citation discipline, lifecycle-based severity, project language, focus-first retrieval); a drift guard keeps skill content aligned with the runtime (technique registry, command manifest, assumption schema).

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
python -m sentinel.mcp --describe   # list the 32 tools
python -m sentinel.mcp              # start the stdio server
```

**Structured gap elicitation (IMP-143).** Among the tools, `sentinel_gap_elicitation` (`project_id`, `gap_id`) returns a structured MCP *elicitation request* for a single `GAP-*` — the cited candidate options (IMP-113) presented as a schema-typed prompt — **only when the connected client declares elicitation capability**. If the client does not support elicitation, the tool degrades gracefully to the exact behavior of `sentinel_gaps` (plain text). It never depends on the capability and stays fully local (no remote MCP).

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

## Governed-Artifact Verifier Hook (Optional, IMP-146)

The repo ships a read-only verifier subagent, `.claude/agents/ignite-verifier.md`, plus an **opt-in** `PostToolUse` hook example under `.claude/hooks/`. When enabled (by copying the example block into your local `.claude/settings.local.json`), any `Write`/`Edit` that touches a governed artifact (`project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) spawns the verifier with an isolated context and tools restricted to `Read, Grep, Glob` (explicit denylist of `Write/Edit/Bash/Agent`). It checks the change against local cited evidence — no invention, criterion continuity, governed mutation channel — and reports `VERIFIED` or `BLOCKED` with cited findings; it never auto-corrects, and the BA/main agent decides.

Nothing activates by default: adopters without Claude Code (or without Agent-hook support) are unaffected and can run the same verification through the governed `/self-review` channel. Hooks can be bypassed by writes outside the editor tools, so this is one enforcement layer; the runtime-side complements are the brief phase-close self-correction (IMP-145) and the generated-artifact checksum check (IMP-147). Setup and the manual smoke test live in `.claude/hooks/README.md`.
