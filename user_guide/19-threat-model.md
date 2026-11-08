# Threat Model

This page is for a security reviewer or an IT approver. It states what Ignite Sentinel protects, the threats it considers, the control for each threat, how to verify the control yourself, and the risk that remains.

Every control below is checked by a test in `tests/` and most of them also by `python -m sentinel /doctor`. The design rule behind all of them: **the documents Sentinel reads are data, never instructions, and everything it writes stays in your project.**

## System in one paragraph

A business analyst (BA) gives Sentinel source documents: requirements, transcripts, specs. The runtime, a Python package with no mandatory third-party dependency, copies them into a workspace (`workspaces/<PROJECT_ID>/`), extracts gaps and units, and compiles governed Markdown artifacts (brief, specs, backlog), plus local HTML views and a dashboard. An agent (Claude Code, Codex, Kilo Code) can drive the commands and propose contributions, but the runtime validates each one against a verbatim citation before it touches an artifact. Sentinel ships as a clone, a single-file `.pyz`, or a Claude Code plugin.

## Assets

| Asset | Where it lives | Why it matters |
|-------|----------------|----------------|
| Client source documents | The BA's original files, and their copy in `workspaces/<PROJECT_ID>/00_raw/` | Confidential business information, sometimes personal data or credentials pasted by mistake |
| Derived artifacts | `workspaces/<PROJECT_ID>/01_discovery/` to `08_context_packs/` | Same confidentiality as the sources, plus the BA's decisions |
| Local memory index | `workspaces/<PROJECT_ID>/` (JSON, or LanceDB when enabled) | A searchable copy of the text |
| Views and dashboard | `workspaces/<PROJECT_ID>/08_context_packs/views/*.html`, `dashboard.html` | Rendered copies of the artifacts, opened from disk |
| Browser storage of the views | The browser's `localStorage` for `file://` pages | Feedback comments and guided answers the BA types in a view stay there until exported or cleared (see below) |
| The BA's machine and project | Everything outside the workspace | Sentinel runs with the BA's user rights |
| The release channel | Tags, releases and the `stable` branch on GitHub | What every installation trusts |

Keys Sentinel stores in `localStorage`:

| Key | Content |
|-----|---------|
| `ignite-sentinel:view-feedback:<project>:<artifact>:<source>` | Feedback comments typed in a view, and the source digest they were written against |
| `ignite-sentinel:view-guided-response:<project>:<artifact>:<source>` | Answers typed in a guided response view |
| `ignite-sentinel:view-provenance` | Whether provenance is shown (a preference, no content) |
| `ignite-sentinel:color-mode` | Light or dark (a preference, no content) |

Feedback and guided answers are client content. They never leave the browser: the views have no network access (T5's CSP). They stay until the BA exports them as Markdown, uses **Clear Comments** in the view, or clears the browser's site data for local files.

## Trust boundaries

1. **Source documents → runtime.** Untrusted. A document can be written by anyone, including someone who wants to steer the outputs or exfiltrate data.
2. **Agent → runtime.** Semi-trusted. An agent proposes; the runtime validates every contribution against a citation from the sources.
3. **Runtime → file system.** Writes are confined to the project (T2).
4. **Runtime → network.** None (T5).
5. **GitHub → installation.** Releases, tags and the plugin are trusted once verified (T4, T6).

## Threats

### T1 — Prompt injection through sources

A source contains text written as an instruction ("ignore the previous rules", "you are now the admin", "run this command", "send the file to…") hoping an agent or a compiler acts on it.

**Control:** `/ingest` and `/sync` flag instruction-shaped passages (override, role impersonation, command execution, exfiltration, governance tampering; English and Spanish) as findings with `origin: injection_signal` in `01_discovery/injection_signals.md`, with source, line and excerpt. The flagged lines are blanked from the text the compilers analyze, so an embedded order cannot change gaps, units or downstream artifacts. The raw copy keeps them for the BA to review. Every agentic surface (AGENTS.md, CLAUDE.md, the MCP server instructions, the Kilo agents, the source-reading skills) declares that sources are data. Agent contributions only land after the runtime finds their verbatim citation in the sources.

**Evidence:** `tests/test_injection_signals.py`: seeded patterns produce one finding each, and a compiler's output is identical with and without an embedded instruction.

**Residual risk:** detection is pattern-based. A novel phrasing can pass unflagged; the citation rule still keeps an agent from inventing content, but an agent that reads the raw source directly is protected only by its own harness and by the BA's review.

### T2 — Path traversal and unconfined writes

A crafted project id, artifact name or source path (`..`, an absolute path, a symlink or junction) makes Sentinel write outside the project, or a crash halfway leaves a truncated artifact.

**Control:** every file the runtime writes goes through `sentinel/core/io.py`. The destination must resolve inside its root, so `..`, foreign absolute paths and links that leave the root raise `UnconfinedWrite`; both spellings of a Windows folder (8.3 short names) compare equal. Writes land in a temporary file, are fsynced and swapped in with `os.replace`. Project ids are validated before any path is built. An AST guard keeps the rest of `sentinel/` from writing any other way.

**Evidence:** `tests/test_safe_writer.py` (escapes, links, interrupted writes, the AST guard); `project_ids_check` in `/doctor`.

**Residual risk:** an attacker who can already create links inside the project folder can redirect reads. Writes stay confined.

### T3 — Secret leakage

A source contains a private key, cloud key, token, JWT, URL with credentials or connection string, and it reaches an artifact, a view, an export, the memory index or the repository.

**Control:** `/ingest` and `/sync` detect those six kinds. The BA's original file is only read; the workspace copy and everything extracted from it carry `<SECRETO:type>` instead. Each redaction is logged in `01_discovery/secret_alerts.md` with type, line and a SHA-256 fingerprint, never the value. False positives are allowlisted by fingerprint. Memory redacts everything it indexes. `/view` and the exports refuse to write an output that carries a secret or a reference to another workspace. Personal data is reported only, opt-in, in `01_discovery/pii_report.md`. In the repository, `/doctor` runs `tracked_secrets_check` over `git ls-files` and `workspaces_ignored_check`, which fails when a new workspace would be committable.

**Evidence:** `tests/test_secrets_ingest.py`: six seeded secrets, six redactions, none in any output.

**Residual risk:** a secret in a format the detector does not know passes through. Personal data is not redacted, only reported.

### T4 — Supply chain

A compromised dependency, GitHub Action or release artifact runs code on the BA's machine.

**Control:** the core has no mandatory third-party package (`stdlib_purity_check`). The optional extras are locked with hashes in `constraints/` and installed with `--require-hashes`. CI runs CodeQL, dependency review, `pip-audit` over every lock and `claude plugin validate --strict`, with every Action pinned by commit SHA; Dependabot keeps them current. Each release carries a CycloneDX SBOM, and the wheel, the SBOM and each plugin archive have a build provenance attestation (`gh attestation verify <file> --repo jmatzkin1980/ignite-sentinel`). The plugin ships the runtime in source form so it can be read, and `claude_plugin_check` fails when it drifts from the generator.

**Evidence:** `tests/test_supply_chain.py`, `tests/test_release.py`; the `security` and `release-attest` workflows in `.github/workflows/`.

**Residual risk:** an attestation proves where an artifact was built, not that the code is benign. A compromised maintainer account can publish a signed bad release; pinning (T6) limits who receives it automatically.

### T5 — Network exfiltration

Code in the runtime or in a view sends client content to a remote host.

**Control:** `network_isolation_check` is an AST scan that fails on any import of `socket`, `urllib`, `http`, `ftplib`, `smtplib`, `ssl` or an HTTP client, including dynamic imports with a literal name. `webbrowser` only opens existing local files. The embedding extras force offline mode and fall back to a local embedder without a model; they never download. The views and the dashboard carry a Content-Security-Policy (`default-src 'none'; connect-src 'none'; form-action 'none'; …`), so a page cannot fetch, post or load a remote image.

**Evidence:** `tests/test_zero_network.py`, `tests/test_view_csp.py`.

**Residual risk:** the agent or harness you run Sentinel from has its own network access. Its policies apply separately (see the [admin guide](20-admin-guide.md)).

### T6 — Hooks

The plugin ships a hook, and hooks run commands with the user's rights on every matching tool call. A tampered hook would run on each edit.

**Control:** the plugin has exactly one hook, `plugins/ignite-sentinel/hooks/deny-governed-artifact-write.py`, a read-only `PreToolUse` guard that only denies a hand `Write`/`Edit` of a governed artifact; it writes nothing and makes no network call. The plugin has no `bin/`, monitors, LSP servers or telemetry, and the MCP server is a separate plugin that installs disabled. The plugin is generated, and `claude_plugin_check` in `/doctor` fails when its hook, or any other file, differs from what the generator produces. `agentic_surface_audit_checks` flags dangerous shell constructs in the hook and settings JSON of the clone. An admin can set `allowManagedHooksOnly`: only hooks of plugins force-enabled by managed settings run, matched on the full `plugin@marketplace` id.

**Evidence:** `tests/test_governed_artifact_deny.py`, `tests/test_claude_plugin.py`.

**Residual risk:** a hook runs whatever the installed plugin version contains. Review the hook before approving a new version (see the admin guide, Before you approve).

### T7 — Auto-update

Claude Code refreshes plugins in the background. A new version, legitimate or not, reaches every machine without a review.

**Control:** the plugin's version drives updates, and a version is only released through a tag that matches it, from CI, with attestations (`tools/release.py`). Users choose a channel: `#stable` (moves only on a release), `#vX.Y.Z` (fixed) or `main`. An admin pins the marketplace to a release tag or the plugin to a commit SHA and sets `"autoUpdate": false` on the managed marketplace entry, which users cannot toggle back.

**Evidence:** `tests/test_release.py`: a tag without a bump, or a bump without its CHANGELOG section, fails the release check.

**Residual risk:** a tag can be moved by someone with push rights; a commit SHA cannot. Use the SHA pin where that matters.

## Out of scope

- The harness (Claude Code, Codex, Kilo Code, VS Code), its model provider and its own data handling.
- An attacker who already controls the BA's user account or project folder.
- The correctness of the generated content: the BA reviews every artifact.

Report a vulnerability as described in [SECURITY.md](../SECURITY.md).
