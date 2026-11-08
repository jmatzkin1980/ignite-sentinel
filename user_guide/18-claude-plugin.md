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

The plugin needs Python 3.10 or newer. It has no other dependency. It does not need `python` on `PATH`: the hook and the skills start Python through `python.sh`, which tries, in order, `SENTINEL_PYTHON`, `python3`, `python` and `py -3` on `PATH` (skipping the Microsoft Store alias), then the usual Windows install folders (`%LOCALAPPDATA%\Programs\Python\Python3*`, `%LOCALAPPDATA%\Python\pythoncore-3*`, `%ProgramFiles%\Python3*`). If none is found it says so and how to fix it. To pick an interpreter yourself, set `SENTINEL_PYTHON` to its full path.

## What you get

| Component | What it does |
|-----------|--------------|
| 24 skills | The same `sentinel-*` skills as the clone, prefixed with the plugin name: `/ignite-sentinel:sentinel-views`, `/ignite-sentinel:sentinel-discovery`, and so on. |
| 1 hook | Read-only `PreToolUse` guard: a hand `Write`/`Edit` of a governed artifact (`workspaces/<id>/02_requirements/project-brief.md`, `03_specs/*.md`, `04_backlog/*.md`) is denied with the command that owns it. Nothing outside `workspaces/<id>/` is affected. |
| `launcher.py` + `lib/sentinel/` | The runtime, in source form, so it can be audited. The launcher locates `lib/` by its own path. |
| `python.sh` | Finds Python 3.10+ for the hook and the skills (see above). A plain POSIX shell script; Claude Code runs it with the `sh` it uses for hooks (Git Bash on Windows). |

Workspaces, views and the dashboard are written in the project you have open, never in the plugin folder.

The plugin has no `bin/`, monitors, LSP servers or telemetry. It makes no network calls (`/doctor` → `network_isolation_check`).

## Versions and channels

The plugin carries the package version (`plugin.json` → `version`). Claude Code updates an installed plugin only when that version changes.

| Channel | Add the marketplace with | You get |
|---------|--------------------------|---------|
| `stable` | `/plugin marketplace add jmatzkin1980/ignite-sentinel#stable` | The latest release. The `stable` branch moves only when a release is cut. |
| One release | `/plugin marketplace add jmatzkin1980/ignite-sentinel#vX.Y.Z` | Exactly that release, until you add another ref. |
| `main` | `/plugin marketplace add jmatzkin1980/ignite-sentinel` | Everything merged, released or not. |

The first release that carries the plugin is `0.3.0`.

A marketplace name can be registered only once, so switch channels with `/plugin marketplace remove ignite-sentinel` and add it again with the new ref.

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

Claude Code refuses a download whose digest does not match (Claude Code 2.1.224 or newer).

## MCP server (optional)

The MCP server is a second plugin, `ignite-sentinel-mcp`. It installs **disabled**, because it needs the third-party `mcp` package. It starts `python` directly (MCP servers do not run through a shell), so it does need Python on `PATH` as `python`:

```bash
python -m pip install "mcp>=1.2,<3"
claude plugin install ignite-sentinel-mcp@ignite-sentinel
claude plugin enable ignite-sentinel-mcp@ignite-sentinel
```

It starts in the project directory and exposes the same tools as the clone's MCP server ([Claude adapter](13-claude-adapter.md#local-mcp-server-optional)).

## Codex and Kilo Code

The plugin targets Claude Code. In Codex and Kilo Code, use the clone: it is the supported path, and the plugin has not been observed running a skill there. See the [Codex adapter](08-codex-adapter.md#plugin-not-supported-yet).

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

### Cutting a release

The version lives in `pyproject.toml`. `sentinel/__init__.py` and both `plugin.json` repeat it, and `python tools/release.py check` fails when any of them differs (CI → `release-check`).

1. On a branch, bump `version` in `pyproject.toml` and `__version__` in `sentinel/__init__.py`. Run `python -m sentinel.adapters --plugin`.
2. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [X.Y.Z] — YYYY-MM-DD` and open a new, empty `## [Unreleased]` above it.
3. Merge the PR. Nobody tags by hand: `release-check` on `main` does it.
   - It tags `vX.Y.Z` on the merge commit that introduced the version.
   - It calls `release-attest`, which:
     - fails on a tag that is not the version ("tag without a bump") or that has no dated CHANGELOG section;
     - builds the wheel, the SBOM and the plugin zips, and validates each zip;
     - attests all of them and creates the GitHub release, with the CHANGELOG section as notes;
     - fast-forwards `stable` to the tag.

`release-check` on `main` fails when the version is untagged and CHANGELOG has no dated section for it. It also fails when the version sources disagree. When the commit that introduced an untagged version is older than the push, it is only tagged, with no release. This is how `v0.2.0` gets its tag, on the merge of #207.

A tag pushed by hand (`git push origin vX.Y.Z`) runs the same `release-attest`.

`python tools/release.py zip --out dist` builds the same zips locally. They are reproducible: same commit, same bytes (`SOURCE_DATE_EPOCH`, sorted entries, LF endings).
