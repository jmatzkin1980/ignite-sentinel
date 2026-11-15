# Install: choose your path

This page helps you pick how to install Ignite Sentinel and walks you through it, step by step, until you have run your first command. Read it if you have not installed Sentinel yet, whether you are a business analyst, a product manager or a developer.

Sentinel runs on your machine and needs only Python. What changes between the paths is **where you talk to it** (Claude Code, Codex, Kilo Code or a plain terminal) and **how the files get to your machine** (marketplace, clone, archive or wheel).

## Words used on this page

| Term | One-line meaning |
|------|------------------|
| Surface | The tool you chat with: Claude Code, Codex, Kilo Code, or a terminal. |
| Clone | A copy of the Sentinel repository on your disk (`git clone`, or the ZIP download from GitHub). |
| Plugin | A package Claude Code installs for you, so you do not need a clone. |
| Marketplace | A catalog Claude Code reads to find plugins. This repository is one: `jmatzkin1980/ignite-sentinel`. |
| MCP | Model Context Protocol, a standard way for an AI tool to call a program's functions. Sentinel can expose its commands this way. Optional. |
| VDI | A virtual desktop, often locked down: no admin rights, little or no internet. |
| Zipapp (`.pyz`) | Python's single-file program format. Sentinel can build one. |
| Wheel | A Python package file you install with `pip`. |

## Which path is mine?

Pick the first row that matches how you work.

| I use... | And I can... | Do this | What you get | What you need |
|----------|--------------|---------|--------------|---------------|
| Claude Code | install plugins from GitHub | [Path A: Claude Code plugin](#path-a-claude-code-plugin-from-the-marketplace) | The 27 skills and the hook that protects governed files. No slash commands of its own: you ask in chat. | Python 3.10+ and Claude Code |
| Claude Code | clone a repository | [Path B: Claude Code clone](#path-b-claude-code-clone) | Native slash commands (`/ingest`, `/gaps`, ...), skills, hook, everything in one folder | Python 3.10+, git or the ZIP download |
| Codex | clone a repository | [Path C: Codex clone](#path-c-codex-clone) | Skills and chat routing through `AGENTS.md`, guard script | Python 3.10+, git or ZIP |
| Kilo Code (VS Code) | clone a repository | [Path D: Kilo Code clone](#path-d-kilo-code-clone) | Slash commands, 7 agents, skills, edit protection in `kilo.jsonc` | Python 3.10+, git or ZIP |
| nothing but a terminal | clone, or install a wheel | [Path E: terminal only](#path-e-terminal-only-no-agent) | Every command through `python -m sentinel /command` | Python 3.10+ |
| Claude Code, and git is blocked | download a file from GitHub Releases | [Path F: release archive](#path-f-release-archive-no-git) | The same plugin as Path A, installed over HTTPS | Python 3.10+, Claude Code 2.1.224+ |
| a managed machine, and the install must be reviewable | read a list of approved files | [Path G: wheel](#path-g-wheel) or [the secure environments guide](09-secure-environments.md) | The `sentinel` command, without agent files | Python 3.10+, pip |

> [!TIP]
> Unsure? A Claude Code user who wants the least setup should take Path A. Someone who wants every command typed as `/command` in chat should take Path B, C or D, whichever agent they use.

Use **one** Claude Code path, not both: in a clone the skills and the hook are already present, and the plugin would load the skills a second time.

## Prerequisites

1. **Python 3.10 or newer.** Check with `python --version`. On Windows, `py --version` also works. If `python` opens the Microsoft Store, Python is not installed: install it from [python.org](https://www.python.org/downloads/) and tick "Add python.exe to PATH". The plugin and the clone launchers can also find Python on their own (see [How Sentinel finds Python](#how-sentinel-finds-python)).
2. **git**, only for clone paths. Without git, download the repository ZIP from GitHub and extract it to a writable folder.
3. **A writable folder.** Sentinel writes your projects to `workspaces/` in the folder where you run it.
4. **Nothing else.** The core uses only the Python standard library. `pip install -e .` installs no extra package, so you do not need it.

### Optional extras

Install an extra only if your environment allows it. Without them Sentinel works fully; retrieval simply uses its deterministic fallback.

| Extra | Adds | Without it |
|-------|------|------------|
| `.[memory]` | LanceDB, a local vector index for `/retrieve` | `json-hybrid` mode: lexical retrieval, same traceability. `/doctor` shows a `WARN`, which is healthy. |
| `.[memory-semantic]` | Local multilingual embeddings (needs a model you place on disk; Sentinel never downloads one) | A deterministic hash embedding. |
| `.[mcp]` | The `mcp` package, to run Sentinel as an MCP server | Everything else keeps working. |

Each extra has a lock file with pinned versions and hashes in `constraints/`. In a clone, install reproducibly with:

```powershell
python -m pip install --require-hashes -r constraints/memory.txt
python -m pip install --no-deps -e .
```

Swap `memory.txt` for `memory-semantic.txt` or `mcp.txt` as needed. Details and air-gapped use are in the [secure environments guide](09-secure-environments.md).

## Path A: Claude Code plugin from the marketplace

1. Install Python 3.10+ (see prerequisites).
2. In Claude Code, from any project folder:

   ```text
   /plugin marketplace add jmatzkin1980/ignite-sentinel
   /plugin install ignite-sentinel@ignite-sentinel
   ```

   Or from a shell: `claude plugin marketplace add jmatzkin1980/ignite-sentinel`, then `claude plugin install ignite-sentinel@ignite-sentinel`.
3. Open the folder where your project data should live and ask Claude to start a project:

   ```text
   sentinel /init ACME_PORTAL
   ```

   Or in plain words: "Create a Sentinel project called ACME_PORTAL."
4. Run `sentinel /next ACME_PORTAL`. It prints the next step alone.

**Check:** `claude plugin list` shows `ignite-sentinel` enabled, and `workspaces/ACME_PORTAL/` appears in your project folder. `/doctor` also works here: in a plain project folder it runs in runtime mode (`"mode": "runtime"`), checking the interpreter, the folder and the optional extras, and skips the clone's files.

Channels, pinning and the optional MCP plugin are in the [Claude Code plugin guide](18-claude-plugin.md).

## Path B: Claude Code clone

1. Install Python 3.10+ and git.
2. Clone and open the folder in Claude Code (CLI or the VS Code extension):

   ```powershell
   git clone https://github.com/jmatzkin1980/ignite-sentinel.git
   cd ignite-sentinel
   claude
   ```
3. Check the setup:

   ```text
   /doctor
   ```
4. Start a project and run your first command:

   ```text
   /init ACME_PORTAL
   ```

   If Claude Code answers `/init` with its own built-in command, send `/sentinel /init ACME_PORTAL` instead.
5. Run `/next ACME_PORTAL`.

**Check:** `/doctor` ends with verdict `PASS`. See [what a `/doctor` result means](#reading-a-doctor-result). Using Sentinel from Claude Code is covered in the [Claude Code guide](13-claude-adapter.md).

## Path C: Codex clone

1. Install Python 3.10+ and git, and clone as in Path B.
2. Open the folder in Codex (Desktop or VS Code).
3. Check the setup:

   ```text
   sentinel /doctor
   ```
4. Start a project:

   ```text
   sentinel /init ACME_PORTAL
   ```
5. Run `sentinel /next ACME_PORTAL`.

**Check:** `/doctor` ends with `PASS`. The `sentinel` prefix keeps Codex from taking `/init` for one of its own commands. More in the [Codex guide](08-codex-adapter.md).

## Path D: Kilo Code clone

1. Install Python 3.10+, git and the Kilo Code extension for VS Code.
2. Clone, then open the **folder itself** in VS Code (not a subfolder):

   ```powershell
   git clone https://github.com/jmatzkin1980/ignite-sentinel.git
   cd ignite-sentinel
   code .
   ```
3. In Kilo Code chat: `/doctor`.
4. Then `/init ACME_PORTAL` and `/next ACME_PORTAL`.

**Check:** `/doctor` ends with `PASS`, and Kilo shows no "Configuration is invalid at kilo.jsonc" warning when VS Code opens. More in the [Kilo Code guide](07-kilo-code-adapter.md).

## Path E: terminal only, no agent

Works from a clone or after a [wheel install](#path-g-wheel). Every command is the same as in chat, prefixed with `python -m sentinel`.

```powershell
python -m sentinel --help
python -m sentinel /doctor
python -m sentinel /init ACME_PORTAL
python -m sentinel /next ACME_PORTAL
```

Run these from the folder that should hold `workspaces/`: Sentinel anchors its files to the current folder.

On Windows without a working `python`, the launcher in a clone finds one for you:

```powershell
.\installers\sentinel.ps1 /doctor
```

If PowerShell refuses with an execution-policy error, run it for this one call only (it changes no setting):

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\sentinel.ps1 /doctor
```

On macOS and Linux: `sh installers/sentinel.sh /doctor`.

**Check:** `/doctor` says `PASS` in a clone (`"mode": "framework"`, every check runs).

## Path F: release archive (no git)

Each GitHub release carries the plugin as a `.zip` and a `SHA256SUMS` file, installed over HTTPS with no git. It is usually set up by whoever manages your Claude Code, because it goes in a plugin catalog entry. The steps, the checksum and the verification are in the [Claude Code plugin guide](18-claude-plugin.md#without-git-the-release-archive); an administrator can also enforce it with [managed settings](20-admin-guide.md). Afterwards, continue from Path A, step 3.

## Path G: wheel

The release also carries a Python wheel (`ignite_sentinel-X.Y.Z-py3-none-any.whl`) that installs the `sentinel` command and nothing else: no skills, no slash commands, no hook.

```powershell
python -m pip install .\ignite_sentinel-0.11.0-py3-none-any.whl
sentinel /init ACME_PORTAL
sentinel /next ACME_PORTAL
```

Run these in the folder that should hold `workspaces/`. Inside a plain project folder `/doctor` runs in runtime mode: it checks the interpreter, command parity, the folder and the optional extras, and a `doctor mode` check says the clone's files were skipped. It is a useful check after installing the plugin, the wheel or a `.pyz`.

Verify the download with `gh attestation verify <file> --repo jmatzkin1980/ignite-sentinel`.

### The single-file `.pyz`

A clone can build a one-file copy with `python -m sentinel.build` (output `dist/sentinel.pyz`, ignored by git, not part of releases). It carries the runtime without the vendored diagram library, so `/view` shows diagrams as code. It runs every command, for example `python sentinel.pyz /init ACME_PORTAL`. `python sentinel.pyz /doctor` runs in runtime mode; to check a clone, use `python sentinel.pyz /doctor --root PATH_TO_THE_CLONE`. The [portability guide](16-portability.md) explains when to use it.

## Reading a `/doctor` result

`/doctor` has two modes, shown as `"mode"` in the result. In a framework clone (a folder with `sentinel/__init__.py` or `.codex/skills`) it is `framework` and checks Python, the repository files, the skills, the agent adapters, write access, optional extras and more. Anywhere else (a project folder with the plugin, the wheel or a `.pyz`) it is `runtime` and checks only the interpreter, command parity, that the package imports no network module, workspace ids and portability, write access and the optional extras; a `doctor mode` check says the clone checks were skipped.

| Result | Meaning | What to do |
|--------|---------|------------|
| `PASS` | No check failed. | Go on. |
| `WARN` | An optional piece is missing, for example LanceDB. Healthy; the verdict stays `PASS`. | Nothing, unless you want that feature. |
| `FAIL` | A required file or condition is missing. The verdict is `FAIL` and the exit code is 5. | Read the failing line: it names the path or the condition. |

## How Sentinel finds Python

| Launcher | Looks for Python in this order |
|----------|-------------------------------|
| Plugin (`python.sh`) | `SENTINEL_PYTHON`, then `python3`, `python`, `py -3` on `PATH` (skipping the Microsoft Store alias), then the usual Windows install folders. |
| Clone launcher (`installers/sentinel.ps1`) | `SENTINEL_PYTHON`, a `.venv` in the folder, `python`, `py`, the Codex Desktop bundled runtime. |
| Clone launcher (`installers/sentinel.sh`) | `SENTINEL_PYTHON`, `.venv/bin/python`, `python3`, `python`. |
| MCP plugin and the clone's Claude hook | The command `python` on `PATH`. |

Set `SENTINEL_PYTHON` to the full path of an approved interpreter to pin one.

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `python` is not recognized, or opens the Microsoft Store | Use `py -m sentinel /doctor`, the launcher in `installers/`, or set `SENTINEL_PYTHON`. |
| `No module named lancedb` | Not an error. Install `.[memory]` if you want vector retrieval, then run `/reindex PROJECT_ID`. |
| Kilo asks permission for every command | The invocation differs from the pre-approved `python -m sentinel *`, for example `py -m sentinel`. Approve once or use the documented form. |
| Claude Code's clone hook does nothing | The hook starts Python through `.claude/hooks/python.sh`, which tries `SENTINEL_PYTHON`, then `python3`/`python`/`py -3` on `PATH` (skipping the Microsoft Store alias), then the usual Windows install folders. If none is found, set `SENTINEL_PYTHON` to the full path of `python.exe`. |
| A command exits with 6 | Another command holds the workspace. See the [admin guide](20-admin-guide.md#the-workspace-lock). |

## Next

- [Start here: concepts and your first run](00-user-guide.md)
- Your surface: [Claude Code](13-claude-adapter.md), [Codex](08-codex-adapter.md), [Kilo Code](07-kilo-code-adapter.md)
- [Secure, offline and VDI use](09-secure-environments.md) and [portability modes](16-portability.md)
- [Command reference](01-command-reference.md)
