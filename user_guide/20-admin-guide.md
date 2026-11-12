# Admin Guide: Claude Code Plugin Under Managed Settings

This guide is for the administrator who approves Ignite Sentinel for an organization's Claude Code users. It covers a restrictive managed settings policy, pinning the plugin to a release or a commit, how to confirm the policy is in force, what to review before approving a version, retention, and the audit trail.

For what Sentinel protects and how, read the [threat model](19-threat-model.md) first. For installing the plugin as a user, see the [Claude Code plugin guide](18-claude-plugin.md).

The managed settings keys below are Claude Code's, documented in [Manage plugins for your organization](https://code.claude.com/docs/en/plugins/org) and [Deploy managed settings](https://code.claude.com/docs/en/managed-settings). Users cannot override a managed key.

## What the plugin needs on each machine

- Claude Code with plugin support. The `archive` source (install without git) needs v2.1.224 or later.
- Python 3.10 or newer. It does not have to be on `PATH`: the plugin's `python.sh` also looks in the usual Windows install folders, and `SENTINEL_PYTHON` can name the interpreter ([plugin guide](18-claude-plugin.md#install)). No package installs: the runtime is standard library only.
- Read access to `github.com/jmatzkin1980/ignite-sentinel` over git, or to the release assets over HTTPS for the `archive` source.
- No other network access. Sentinel makes no network calls (`network_isolation_check`).

## 1. A restrictive policy

This policy allows only the Ignite Sentinel marketplace at one release, registers it on every machine, installs the plugin, keeps the MCP plugin off, and closes the side doors. The same file is in [`references/managed-settings.json`](references/managed-settings.json).

```json
{
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "jmatzkin1980/ignite-sentinel", "ref": "v0.8.0" }
  ],
  "extraKnownMarketplaces": {
    "ignite-sentinel": {
      "source": { "source": "github", "repo": "jmatzkin1980/ignite-sentinel", "ref": "v0.8.0" },
      "autoUpdate": false
    }
  },
  "enabledPlugins": {
    "ignite-sentinel@ignite-sentinel": true,
    "ignite-sentinel-mcp@ignite-sentinel": false
  },
  "disableSideloadFlags": true,
  "allowManagedHooksOnly": true,
  "disableCommandPluginSources": true,
  "pluginTrustMessage": "Ignite Sentinel is approved by IT at the pinned release only."
}
```

| Key | Effect |
|-----|--------|
| `strictKnownMarketplaces` | Allowlist of marketplace sources. Repo, `ref` and `path` must match exactly, so the entry must be identical to the registered source. Any other marketplace, including Anthropic's official one, is refused. Add entries for the other marketplaces you approve. |
| `extraKnownMarketplaces` | Registers the marketplace on every machine at session start. |
| `"autoUpdate": false` | No background refresh of this marketplace. Users cannot turn it back on. |
| `enabledPlugins` | Force-installs `ignite-sentinel`. `ignite-sentinel-mcp` is blocked and hidden; it already installs disabled, and this keeps users from enabling it. |
| `disableSideloadFlags` | Rejects `--plugin-dir`, `--plugin-url`, `--agents` and `--mcp-config`, which would bypass the allowlist for one run. |
| `allowManagedHooksOnly` | Only managed hooks and hooks of force-enabled plugins run. The plugin's read-only hook keeps working; user and project hooks stop. |
| `disableCommandPluginSources` | No plugin installed by running a command on the machine. |
| `pluginTrustMessage` | Your text, appended to the trust warning before install. |

`allowManagedHooksOnly` affects more than this plugin: user, project and other plugins' hooks stop running, and `/goal` is unavailable. Drop it if your users rely on their own hooks.

The policy names release `v0.8.0`. Use the release you approved.

### Where to deploy it

| Mechanism | Location |
|-----------|----------|
| Managed settings file, Windows | `C:\Program Files\ClaudeCode\managed-settings.json` |
| Managed settings file, macOS | `/Library/Application Support/ClaudeCode/managed-settings.json` |
| Managed settings file, Linux and WSL | `/etc/claude-code/managed-settings.json` |
| Windows Group Policy or Intune | The JSON as a `REG_SZ` value named `Settings` under `HKLM\SOFTWARE\Policies\ClaudeCode` |
| macOS MDM | A configuration profile whose top-level keys are the settings keys |
| claude.ai admin console | **Organization settings › Claude Code › Managed settings** (Teams or Enterprise, Owner role) |

The file locations need administrator rights to write. A managed file that is not valid JSON stops Claude Code from starting, so validate it before you deploy (`python -m json.tool managed-settings.json`).

Do not use the user-writable `HKCU\SOFTWARE\Policies\ClaudeCode` registry key for this policy. Claude Code reads it as a fallback, but because the user can write it, `true` entries in `enabledPlugins` are ignored there: `/status` says so, and the plugin is not installed. Test the policy from the managed settings file or HKLM, as the rollout will use.

Observed with Claude Code 2.1.305:

| Key | Source | Result |
|-----|--------|--------|
| `strictKnownMarketplaces` | HKCU | Enforced. Anthropic's directory and any other marketplace are refused: `is blocked by enterprise policy. Allowed sources: github:jmatzkin1980/ignite-sentinel@<ref>` |
| `extraKnownMarketplaces` | HKCU, file | Enforced. The marketplace is registered at the pinned ref with `"autoUpdate": false`. |
| `enabledPlugins` | HKCU | Ignored for `true` entries. |
| `enabledPlugins` | File | Enforced. The plugin installs in the background at session start (`Scope: managed`), and the user cannot disable it. The first session may report `not cached` until the download finishes; the next session is clean. |
| `disableSideloadFlags` | File | Enforced. `claude --plugin-dir .` exits with `--plugin-dir is disabled by your organization's managed settings (disableSideloadFlags)`. |

## 2. Pin the plugin

Pick one of three pins. All of them stop a new version from reaching users until you change the policy.

### To a release tag (the policy above)

The marketplace source carries `"ref": "v0.8.0"`. Releases are cut only by CI, from a tag that matches the version, with attestations. A tag can still be moved by someone with push rights to the repository.

### To a commit SHA

A marketplace source accepts a `ref` but not a `sha`. To pin a commit, declare the catalog inline in managed settings (a `settings` marketplace source) and point its one entry at the plugin directory with `git-subdir`, which takes a `sha`:

```json
{
  "strictKnownMarketplaces": [
    {
      "source": "settings",
      "name": "ignite-sentinel",
      "plugins": [
        {
          "name": "ignite-sentinel",
          "source": {
            "source": "git-subdir",
            "url": "https://github.com/jmatzkin1980/ignite-sentinel.git",
            "path": "plugins/ignite-sentinel",
            "ref": "v0.8.0",
            "sha": "<40-character commit SHA of v0.8.0>"
          }
        }
      ]
    }
  ],
  "extraKnownMarketplaces": {
    "ignite-sentinel": {
      "source": {
        "source": "settings",
        "name": "ignite-sentinel",
        "plugins": [
          {
            "name": "ignite-sentinel",
            "source": {
              "source": "git-subdir",
              "url": "https://github.com/jmatzkin1980/ignite-sentinel.git",
              "path": "plugins/ignite-sentinel",
              "ref": "v0.8.0",
              "sha": "<40-character commit SHA of v0.8.0>"
            }
          }
        ]
      },
      "autoUpdate": false
    }
  },
  "enabledPlugins": {
    "ignite-sentinel@ignite-sentinel": true
  },
  "disableSideloadFlags": true,
  "allowManagedHooksOnly": true,
  "disableCommandPluginSources": true
}
```

Get the SHA of a release with:

```bash
gh api repos/jmatzkin1980/ignite-sentinel/commits/v0.8.0 --jq .sha
```

Claude Code checks out the `sha` even if the tag moves. The allowlist entry for a `settings` source must carry the same `name` and identical `plugins`. This catalog lists only `ignite-sentinel`, so the MCP plugin cannot be installed at all.

### Without git: the release archive

Each release carries `ignite-sentinel-vX.Y.Z.zip` and a `SHA256SUMS` file. An `archive` entry in an inline catalog installs over HTTPS and refuses a download whose digest differs. Use this plugin entry in place of the `git-subdir` one above:

```json
{
  "name": "ignite-sentinel",
  "source": {
    "source": "archive",
    "url": "https://github.com/jmatzkin1980/ignite-sentinel/releases/download/v0.8.0/ignite-sentinel-v0.8.0.zip",
    "sha256": "<64-hex digest from SHA256SUMS>"
  }
}
```

You can also host the zip on an internal server and point `url` there.

## 3. Confirm the policy is in force

On one machine, before the rollout:

1. Start Claude Code and run `/status`. The `Setting sources` line shows `Enterprise managed settings (file)`, or `(HKLM)`, `(plist)`, `(remote)` for the other mechanisms.
2. Run `/plugin`. `ignite-sentinel` is installed and enabled; `ignite-sentinel-mcp` is not listed.
3. Try another marketplace: `/plugin marketplace add anthropics/claude-plugins-official`. It fails with a message that contains `is blocked by enterprise policy`.
4. From a shell, run `claude --plugin-dir .`. It exits with an error that names `disableSideloadFlags`.
5. In an empty project, run `/ignite-sentinel:sentinel-views`. The skill runs, and anything it writes lands in that project.
6. From the same project, ask Claude to edit `workspaces/<id>/03_specs/<file>.md` by hand: the plugin's hook denies it and names the command that owns the file.

## 4. Upgrade

1. Review the new release (next section).
2. Change the `ref` (and the `sha` or `sha256`, if you pin those) in both the allowlist and the registered source. They must stay identical.
3. Deploy. Claude Code installs the new version at the next session start.

## Before you approve

For each release you approve:

1. **Provenance.** Download the release assets and verify each one:

   ```bash
   gh release download v0.8.0 --repo jmatzkin1980/ignite-sentinel
   gh attestation verify ignite-sentinel-v0.8.0.zip --repo jmatzkin1980/ignite-sentinel
   sha256sum --check SHA256SUMS
   ```

2. **What changed.** Read the release's `CHANGELOG.md` section, then the diff of what runs on the machine:

   ```bash
   git diff v0.7.0 v0.8.0 --stat -- plugins/ignite-sentinel
   git diff v0.7.0 v0.8.0 -- plugins/ignite-sentinel/hooks plugins/ignite-sentinel/.claude-plugin plugins/ignite-sentinel/launcher.py plugins/ignite-sentinel/python.sh
   ```

3. **Hooks.** `plugins/ignite-sentinel/hooks/hooks.json` declares one `PreToolUse` hook on `Write|Edit` that runs `deny-governed-artifact-write.py` through `python.sh`, the script that finds Python. Read the hook script and `python.sh`; `python.sh` only looks for an interpreter and runs it. Any new hook, matcher or command is a reason to stop and ask.
4. **Surface.** The plugin still has no `bin/`, monitors, LSP servers or MCP servers (those live only in `ignite-sentinel-mcp`).
5. **No network.** In a clone at the tag, `python -m sentinel /doctor` passes `network_isolation_check`, `stdlib_purity_check` and `claude_plugin_check`.
6. **Dependencies.** The SBOM (`ignite-sentinel-vX.Y.Z.cdx.json`) lists only the optional extras; the plugin itself uses none of them.

## Retention and cleanup

Sentinel keeps client content in four places. None of them is in the plugin folder.

| Where | What | How to clean it |
|-------|------|-----------------|
| `workspaces/<PROJECT_ID>/` in the user's project | Source copies, artifacts, views, the memory index | Delete the workspace folder when the engagement ends. `workspaces/` is git-ignored by default (`workspaces_ignored_check`). |
| Browser `localStorage` for local files | Feedback comments and guided answers typed in views | **Clear Comments** in each view, or clear the browser's site data for local files. |
| Claude Code transcripts | Whatever the agent read or wrote in a session | Claude Code deletes them after `cleanupPeriodDays` (default 30). Set a lower value in managed settings. |
| A maintainer's clone | Caches, build output, old eval reports, leftover test folders | `python tools/clean_local.py` lists them (dry run); `python tools/clean_local.py --apply` deletes them. It never touches tracked files; workspaces only with `--include-workspaces` and a typed confirmation per workspace. |

The memory index is rebuildable from the artifacts (`/reindex`); deleting it loses nothing.

## Audit trail

What happened in a project is recorded in append-only files in its workspace:

| File | Records |
|------|---------|
| `01_discovery/secret_alerts.md` | Each redacted secret: source, line, type and fingerprint, never the value |
| `01_discovery/injection_signals.md` | Each instruction-shaped passage flagged in a source |
| `01_discovery/agent_annotation_log.md` | Each agent contribution, merged or skipped, with its citation |
| `01_discovery/decisions.md` | The BA's decisions on gaps |
| `01_discovery/gap_resolution_log.md` | Each gap resolution run and its result |
| `07_changes/metabolism_log.md` | Each change to the sources and the artifacts it impacts |

Version the workspace on a project branch to get a full history of every artifact ([Repo & Branching Strategy](10-repo-and-branching-strategy.md)).

On the Claude Code side:
- OpenTelemetry events `claude_code.plugin_installed` and `claude_code.plugin_loaded` record installs and loads per machine (set `OTEL_LOG_TOOL_DETAILS=1` to keep the plugin name).
- On the Enterprise plan, the Analytics API reports installs and invocations per plugin.
