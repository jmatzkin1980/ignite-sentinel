# Portability modes and the IT note

This page lists the ways Ignite Sentinel can run on machines you do not control, says which one fits which environment, explains where the single-file `.pyz` fits, and gives you a note you can adapt and send to IT to ask for approval. Read it if you are a BA or PM who needs to get Sentinel approved, or the person reviewing that request. What to do when a piece is blocked, and how data is handled, is in [Secure environments](09-secure-environments.md).

## The principle

Sentinel does not ask for more permissions. It reduces its footprint:

- it uses a Python 3.10+ that the organization already approves;
- it has no mandatory third-party package for the core lifecycle;
- client content stays local, in plain text files that can be audited;
- it has no network code (a check in `/doctor` enforces that).

## Portability modes

| Situation | Minimum | Command | What a good result looks like |
|-----------|---------|---------|-------------------------------|
| Your own or unrestricted laptop | Python 3.10+ | `python -m sentinel /doctor` | `PASS`; LanceDB may be a `WARN` if you did not install the extra |
| Corporate laptop with approved Python | Python 3.10+, a writable folder | `python -m sentinel /doctor` | `PASS`, no required package |
| VDI without `pip` or admin rights | Python 3.10+ | `python -m sentinel /doctor` | `PASS` in `json-hybrid` memory mode; LanceDB shows as an optional `WARN` |
| Restricted PowerShell | Python 3.10+ | `python -m sentinel /doctor` | Call Python directly; the launcher script is not needed |
| Claude Code approved, git blocked | Claude Code 2.1.224+ and Python 3.10+ | install the [release archive](18-claude-plugin.md#without-git-the-release-archive) | The plugin installs over HTTPS with a pinned digest |
| Prefer to move one file | Python 3.10+ and a `.pyz` built earlier | [see below](#the-single-file-pyz) | `PASS` on a machine that also has the framework folder |
| An agent surface already approved | VS Code, Codex, Kilo Code or Claude Code | `/doctor` or `sentinel /doctor` in chat | The agent routes to the local CLI; the tool's own policies still apply |
| No approved Python | Approval for Python 3.10+ or an equivalent runtime | not applicable yet | Asking for Python is usually easier to approve than an unsigned binary |

For the install steps of each surface, use the [install page](06-installation-vscode.md).

## The single-file `.pyz`

A `.pyz` is Python's single-file program format. A clone builds one with `python -m sentinel.build` (output `dist/sentinel.pyz`). It is for moving the runtime as one file when installing a package is not possible.

- It is **not** part of a GitHub release and has no attestation. You build it yourself, on an approved machine.
- It carries the runtime and its schemas, templates, lenses, retrieval plans and slicing model. It leaves out the vendored diagram library (about 3.5 MB), so `/view` shows each diagram as code instead of a picture.
- It still needs Python 3.10+; it avoids installing the package on the target machine.
- It runs every command from the folder where it is used, for example `python sentinel.pyz /init ACME_PORTAL`.
- **`/doctor` needs the framework folder.** The check looks for `AGENTS.md`, `.agents/skills`, `.kilo/` and similar files that the `.pyz` does not contain. Run `python sentinel.pyz /doctor --root PATH_TO_FRAMEWORK_FOLDER`; without a framework folder it reports `FAIL` on those files, which does not mean the `.pyz` is broken.

If you only need the commands and not the agent files, the [wheel](06-installation-vscode.md#path-g-wheel) from a release is the better single artifact: it is attested.

## A note for IT

Copy and adapt:

```text
I need to use Ignite Sentinel vNext to mature business requirements in a local project.

Technical requirements:
- Python 3.10 or newer, approved by the organization.
- A local folder with read and write permission.
- No mandatory Python package for the core lifecycle.
- No cloud services, remote MCP, external vector databases or external embedding
  services for client content.

How it works:
- Project artifacts stay in local files under workspaces/[PROJECT_ID]/.
- The local memory is a rebuildable index, not the source of truth.
- Without LanceDB the framework runs in a deterministic json-hybrid mode; its
  health check reports a warning for the optional piece and still passes.
- The code is plain text and can be audited in the repository.

Validation command:
python -m sentinel /doctor
```

To give IT more to review, add the [threat model](19-threat-model.md) (what is protected and how to check each control), the [admin guide](20-admin-guide.md) (a managed settings policy for Claude Code, pinning a version, retention) and [SECURITY.md](../SECURITY.md). If you will install the plugin, say that it comes from GitHub (git, or HTTPS for the release archive).

The same text in Spanish is in [PORTABILITY.md](../PORTABILITY.md) at the repository root.

## What not to promise

To avoid misunderstandings with Security:

- Do not promise that GitHub, VS Code, Codex, Claude Code or Kilo Code use no network. Those tools have their own approvals and policies.
- Do not promise that the user will never install an extra. LanceDB and semantic embeddings are optional and should be installed only if IT allows it.
- Do not treat `workspaces/` as public. It holds project material and is ignored by git in the framework repository.

## Next

- [Secure environments](09-secure-environments.md)
- [Install: choose your path](06-installation-vscode.md)
- [Threat model](19-threat-model.md) and [admin guide](20-admin-guide.md)
- [Command reference](01-command-reference.md#doctor)
