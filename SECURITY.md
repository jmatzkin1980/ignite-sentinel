# Security Policy

Ignite Sentinel is a local-first tool that reads your clients' business and product documents. This page tells you how to report a vulnerability, which versions receive fixes, and where the security design is described.

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/jmatzkin1980/ignite-sentinel/security/advisories/new)**, or **Security › Report a vulnerability** on the repository page.

Do not open a public issue, pull request or discussion for a vulnerability.

Include what you can:
- the version (`python -c "import sentinel; print(sentinel.__version__)"`, or `version` in the plugin's `plugin.json`) and the surface (clone, Claude Code plugin, `.pyz`);
- the steps or a minimal source document that reproduces it;
- what an attacker gains: a write outside the project, a secret reaching an artifact, an instruction in a source steering an output, a network call.

Never attach real client documents. Reproduce with invented data.

What to expect:
- an acknowledgement within 7 days;
- an assessment, and either a fix plan or a reasoned decline, within 30 days;
- a fix released as a new version within 90 days of your report, sooner for a severe issue, with a GitHub security advisory that credits you unless you prefer otherwise;
- coordinated disclosure: please keep the details private until the fix is released or 90 days have passed, whichever comes first. If a fix needs longer, we agree on a new date with you.

This is maintained by one person, so these are targets, not guarantees.

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest release (the `stable` channel) | Yes |
| `main` | Fixes land here first; it is not a release |
| Any older release | No: upgrade to the latest release |

Releases are tagged `vX.Y.Z` and listed under [Releases](https://github.com/jmatzkin1980/ignite-sentinel/releases). Each release carries its wheel, its plugin archives, a CycloneDX SBOM and build provenance attestations ([Claude Code plugin guide](user_guide/18-claude-plugin.md#without-git-the-release-archive)).

## Scope

In scope:
- the runtime (`sentinel/`), the generated plugins (`plugins/`) and their hook;
- the views and the dashboard that the runtime writes;
- the release and CI workflows (`.github/workflows/`).

Out of scope:
- the agent or harness you run Sentinel from (Claude Code, Codex, Kilo Code, VS Code). Report those to their vendors;
- findings that need an attacker who can already write to your project folder or your user profile;
- the content Sentinel generates being wrong. Correctness issues are ordinary bugs; open an issue.

## Security design

- [Threat model](user_guide/19-threat-model.md): what Sentinel protects, the threats it considers, each control and how to verify it.
- [Admin guide](user_guide/20-admin-guide.md): enabling the Claude Code plugin under restrictive managed settings, pinning it, what to review before approval, retention and the audit trail.
- [IT portability note](PORTABILITY.md): the short note for an IT approval.
