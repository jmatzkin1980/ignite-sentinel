# Claude Code Plugin

Ignite Sentinel installs as a Claude Code plugin, so you do not need a clone of the repository. The repository is also the marketplace that lists the plugin.

## Install

In Claude Code, from any project:

```text
/plugin marketplace add jmatzkin1980/ignite-sentinel
/plugin install ignite-sentinel@ignite-sentinel
```

From a shell, the same two steps are:

```bash
claude plugin marketplace add jmatzkin1980/ignite-sentinel
claude plugin install ignite-sentinel@ignite-sentinel
```

The plugin needs Python 3.10 or newer on `PATH` as `python`. It has no other dependency.

## What you get

| Component | What it does |
|-----------|--------------|
| 24 skills | The same `sentinel-*` skills as the clone, prefixed with the plugin name: `/ignite-sentinel:sentinel-views`, `/ignite-sentinel:sentinel-discovery`, and so on. |
| 1 hook | Read-only `PreToolUse` guard: a hand `Write`/`Edit` of a governed artifact (`workspaces/<id>/02_requirements/project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) is denied with the command that owns it. Nothing outside `workspaces/<id>/` is affected. |
| `launcher.py` + `lib/sentinel/` | The runtime, in source form, so it can be audited. The launcher locates `lib/` by its own path. |

Workspaces, views and the dashboard are written in the project you have open, never in the plugin folder.

The plugin has no `bin/`, monitors, LSP servers or telemetry. It makes no network calls (`/doctor` → `network_isolation_check`).

## MCP server (optional)

The MCP server is a second plugin, `ignite-sentinel-mcp`. It installs **disabled**, because it needs the third-party `mcp` package:

```bash
python -m pip install "mcp>=1.2,<3"
claude plugin install ignite-sentinel-mcp@ignite-sentinel
claude plugin enable ignite-sentinel-mcp@ignite-sentinel
```

It starts in the project directory and exposes the same tools as the clone's MCP server ([Claude adapter](13-claude-adapter.md#local-mcp-server-optional)).

## Clone and plugin together

In a clone, `.claude/skills` and `.claude/settings.json` already provide the skills and the hook. Installing the plugin as well loads the skills twice (once with the `ignite-sentinel:` prefix). Use one or the other.

## For maintainers

`plugins/` and `.claude-plugin/marketplace.json` are generated. Never edit them by hand:

```bash
python -m sentinel.adapters            # commands, skill mirrors and plugin
python -m sentinel.adapters --plugin   # plugin only
```

The skills are rendered from `.codex/skills` with the `claude-plugin` overlay, which only changes the runtime invocation (IMP-278). The version comes from `pyproject.toml`. `lib/sentinel/` is a byte-for-byte copy of `sentinel/`.

Two checks keep it honest:

- `/doctor` → `claude_plugin_check` (offline): it fails on drift, and on the manifest mistakes `claude plugin validate` rejects (`..` in a source, entry name different from manifest name, version in the entry, `homepage` that is not a URL, reserved names, top-level `bin/`, `hooks.json` without its `"hooks"` wrapper).
- CI → `plugin-validate`: runs Claude Code's own `claude plugin validate --strict` on the marketplace and both plugins.
