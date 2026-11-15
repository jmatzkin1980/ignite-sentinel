# Claude Code plugin

This page covers installing Ignite Sentinel as a Claude Code plugin, so you do not need a copy of the repository: how to install it, which version you get, how to install without git, and the optional MCP plugin. Read it if you use Claude Code and want the least setup. For day-to-day use, see [Using Sentinel on Claude Code](13-claude-adapter.md).

The repository is also the marketplace (the catalog) that lists the plugin.

## Install

You need Python 3.10 or newer. The plugin has no other dependency. In Claude Code, from any project:

```text
/plugin marketplace add jmatzkin1980/ignite-sentinel
/plugin install ignite-sentinel@ignite-sentinel
```

From a shell, the same two steps are:

```bash
claude plugin marketplace add jmatzkin1980/ignite-sentinel
claude plugin install ignite-sentinel@ignite-sentinel
```

The plugin does not need `python` on `PATH`. Its hook and skills start Python through `python.sh`, which tries `SENTINEL_PYTHON`, then `python3`, `python` and `py -3` on `PATH` (skipping the Microsoft Store alias), then the usual Windows install folders. If it finds none it says so and how to fix it. To choose an interpreter yourself, set `SENTINEL_PYTHON` to its full path. `python.sh` is a plain shell script that Claude Code runs with the `sh` it uses for hooks (Git Bash on Windows).

Use the plugin **or** a clone, not both: a clone already provides the skills and the hook, and the plugin would load the skills a second time.

## First run

The plugin has no slash commands of its own: it ships skills and one hook. A skill is run with the plugin's name as a prefix, for example `/ignite-sentinel:sentinel-views`. To run Sentinel commands, send them in chat with the `sentinel` prefix, or describe what you want; the `sentinel-command-router` skill turns either into the CLI call.

1. Open the folder where your project data should live. Workspaces, views and the dashboard are written there, never in the plugin folder.
2. Start a project and ask for the next step:

   ```text
   sentinel /init ACME_PORTAL
   sentinel /next ACME_PORTAL
   ```

3. Ingest your first source: `sentinel /ingest ACME_PORTAL --source notes/request.md`.

**Check:** `claude plugin list` shows `ignite-sentinel` enabled and `workspaces/ACME_PORTAL/` appears in your folder.

> [!NOTE]
> Type `sentinel /doctor`, or ask "run the Ignite Sentinel doctor". The plugin has no slash commands of its own, so a bare `/doctor` runs Claude Code's built-in diagnostic, which can offer to change your Claude Code settings. Inside a plain project folder Sentinel's doctor runs in runtime mode (`"mode": "runtime"`): it checks the interpreter, the folder and the optional extras, and a `doctor mode` check says the clone's files were skipped. To check a clone, run `sentinel /doctor --root PATH_TO_THE_CLONE`.
>
> On Windows, Claude Code runs the plugin's commands through Git Bash, which rewrites a leading `/init` into a path such as `C:/Program Files/Git/init`; Sentinel reads that path back as the command. Observed on 2026-11-15 with 0.12.0, installed from the GitHub marketplace in the Claude desktop app on Windows: the skills autocomplete as `/ignite-sentinel:...`; `init`, `ingest`, `next` (it asks for the brief settings), `brief`, `view` and `dashboard` run from plain requests; `specs` is refused until the brief settings are confirmed; `sentinel /doctor` passes in runtime mode; and a hand write to `03_specs/` or a hand edit of `project-brief.md` is denied by the hook, which names the owning command.

The rest of the lifecycle is the same on every surface: see [Workflows](03-workflows.md) and the [command reference](01-command-reference.md).

## What you get

| Component | What it does |
|-----------|--------------|
| 27 skills | The same `sentinel-*` skills as the clone, prefixed with the plugin name: `/ignite-sentinel:sentinel-views`, `/ignite-sentinel:sentinel-discovery`, and so on. |
| 1 hook | A read-only `PreToolUse` guard: a hand `Write` or `Edit` of a governed artifact (`workspaces/<id>/02_requirements/project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) is denied with the command that owns it. Nothing outside `workspaces/<id>/` is affected. |
| `launcher.py` and `lib/sentinel/` | The runtime in source form, so it can be audited. |
| `python.sh` | Finds Python 3.10+ for the hook and the skills. |

The plugin has no `bin/` folder, monitors, LSP servers or telemetry, and makes no network call (`/doctor` runs `network_isolation_check` for that).

## Versions and channels

The plugin carries the package version (`plugin.json` field `version`). Claude Code updates an installed plugin only when that version changes.

| Channel | Add the marketplace with | You get |
|---------|--------------------------|---------|
| `stable` | `/plugin marketplace add jmatzkin1980/ignite-sentinel#stable` | The latest release. The `stable` branch moves only when a release is cut. |
| One release | `/plugin marketplace add jmatzkin1980/ignite-sentinel#vX.Y.Z` | Exactly that release, until you add another ref. |
| `main` | `/plugin marketplace add jmatzkin1980/ignite-sentinel` | Everything merged, released or not. |

A marketplace name can be registered only once, so switch channels with `/plugin marketplace remove ignite-sentinel` and add it again with the new ref. An organization that wants one approved version on every machine pins it with managed settings: see the [admin guide](20-admin-guide.md).

### Updating the plugin

Claude Code does not update a marketplace you added yourself unless you turn auto-update on, and a new version arrives only when a release changes the plugin's `version`.

| You added the marketplace with | To get a newer release |
|---|---|
| `#stable` or no ref (`main`) | In a session: `/plugin`, tab **Marketplaces**, select `ignite-sentinel`, **Update marketplace**. In a terminal: `claude plugin update ignite-sentinel@ignite-sentinel`. |
| `#vX.Y.Z` | The tag does not move, so an update finds nothing. Remove the marketplace and add the new tag: `/plugin marketplace remove ignite-sentinel`, then `/plugin marketplace add jmatzkin1980/ignite-sentinel#vX.Y.Z` and `/plugin install ignite-sentinel@ignite-sentinel`. |

- **Automatic updates:** `/plugin`, tab **Marketplaces**, select `ignite-sentinel`, **Enable auto-update**. Claude Code then checks in the background during a session; the new version loads at the next start or after `/reload-plugins`. It makes sense only on `#stable`.
- **Removing the marketplace uninstalls the plugin** and its settings. Your workspaces are not touched: they live in your project folder, not in the plugin.
- **Check the version** you run in `/plugin`, tab **Installed**; **Update now** there updates that plugin alone. What changed in each release is in the [CHANGELOG](../CHANGELOG.md).
- An organization that pins a version with managed settings moves everyone by changing the `ref` in its policy: see the [admin guide](20-admin-guide.md).

### Without git: the release archive

Each GitHub release carries one `.zip` per plugin (`ignite-sentinel-vX.Y.Z.zip`, `ignite-sentinel-mcp-vX.Y.Z.zip`) and a `SHA256SUMS` file. Every file has a build provenance attestation:

```bash
gh attestation verify ignite-sentinel-vX.Y.Z.zip --repo jmatzkin1980/ignite-sentinel
```

The zip is the input of an `archive` plugin source, which installs over HTTPS with no git. An organization that hosts its own catalog can point an entry at the release asset and pin its digest from `SHA256SUMS`:

```json
{
  "name": "ignite-sentinel",
  "source": {
    "source": "archive",
    "url": "https://github.com/jmatzkin1980/ignite-sentinel/releases/download/vX.Y.Z/ignite-sentinel-vX.Y.Z.zip",
    "sha256": "<digest from SHA256SUMS>"
  }
}
```

Claude Code refuses a download whose digest does not match (Claude Code 2.1.224 or newer). The administrator's version, with the review checklist, is in the [admin guide](20-admin-guide.md#without-git-the-release-archive).

## MCP server (optional)

MCP (Model Context Protocol) lets an AI tool call a program's functions directly. Sentinel's MCP server exposes its lifecycle as 38 tools over a local stdio channel, with the same gates, and makes no network call. Everything else works without it.

It is a second plugin, `ignite-sentinel-mcp`. It installs **disabled** because it needs the third-party `mcp` package. Unlike the main plugin, it starts the command `python` directly, so a `python` on `PATH` must have `mcp` installed:

```bash
python -m pip install "mcp>=1.2,<3"
claude plugin install ignite-sentinel-mcp@ignite-sentinel
claude plugin enable ignite-sentinel-mcp@ignite-sentinel
```

For a reproducible install with pinned versions and hashes, take `constraints/mcp.txt` from the release you use and run `python -m pip install --require-hashes -r mcp.txt` instead of the first line.

The server starts in your project folder. In Claude Code, `/mcp` should list `ignite-sentinel`. A failed command returns an error result whose text carries the exit `code`, the `error` and the `next_step`. This plugin has not yet been watched enabled in a session.

**From a clone,** install the extra with the hashed lock (`python -m pip install --require-hashes -r constraints/mcp.txt`, then `python -m pip install --no-deps -e .`), list the tools with `python -m sentinel.mcp --describe`, and register the server in the project's `.mcp.json`:

```json
{
  "mcpServers": {
    "ignite-sentinel": { "command": "python", "args": ["-m", "sentinel.mcp"] }
  }
}
```

Claude Code starts it from the folder you opened, so open the repository root. Among the tools, `sentinel_gap_elicitation` returns a structured question for one gap when the connected client supports elicitation, and falls back to the plain `sentinel_gaps` text when it does not.

## Codex and Kilo Code

The plugin targets Claude Code. In Codex and Kilo Code use the clone: see [Codex](08-codex-adapter.md#plugin-not-supported) and [Kilo Code](07-kilo-code-adapter.md#why-a-clone-and-not-a-plugin).

## Do not edit the plugin by hand

`plugins/` and `.claude-plugin/marketplace.json` are generated from the repository's sources. Do not edit them; a check in `/doctor` (`claude_plugin_check`) fails on any difference.

## Next

- [Using Sentinel on Claude Code](13-claude-adapter.md)
- [Start here: concepts and your first run](00-user-guide.md)
- [Admin guide: managed settings and pinning](20-admin-guide.md)
- [Threat model](19-threat-model.md)
