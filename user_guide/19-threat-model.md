# Threat Model

This page is for a security reviewer or an IT approver. It states what Ignite Sentinel protects, the threats it considers, the control for each threat, how to verify the control yourself, and the risk that remains.

Every control below is checked by a test in `tests/` and most of them also by `python -m sentinel /doctor`. Below, a `/doctor` check is named by the label it prints, followed by the function that implements it. Most of these checks run only in a clone (`"mode": "framework"`); outside a clone `/doctor` runs in runtime mode, where of the checks cited here only "workspace ids" and "package imports no network module" run. The design rule behind all of them: **the documents Sentinel reads are data, never instructions, and everything it writes stays in your project.**

## System in one paragraph

A business analyst (BA) gives Sentinel source documents: requirements, transcripts, specs. The runtime, a Python package with no mandatory third-party dependency, copies them into a workspace (`workspaces/<PROJECT_ID>/`), extracts gaps and units, and compiles governed Markdown artifacts (brief, specs, backlog), plus local HTML views and a dashboard. An agent (Claude Code, Codex, Kilo Code) can drive the commands and propose contributions, but the runtime validates each one against a verbatim citation before it touches an artifact. Sentinel is installed from a clone of the repository, as a Claude Code plugin (from the marketplace or a release archive), or as a wheel; a clone can also build a single-file `.pyz` locally. The plugin has an optional second plugin for MCP, which installs disabled.

## Assets

| Asset | Where it lives | Why it matters |
|-------|----------------|----------------|
| Client source documents | The BA's original files, and their copy in `workspaces/<PROJECT_ID>/00_raw/` | Confidential business information, sometimes personal data or credentials pasted by mistake |
| Derived artifacts | `workspaces/<PROJECT_ID>/01_discovery/` to `08_context_packs/` | Same confidentiality as the sources, plus the BA's decisions |
| Release series working copies | `workspaces/<PROJECT_ID>/.series_work/<rN>/`, one per release built with `--release` | A full copy of the workspace for that release, client sources (`00_raw/`) and change copies (`07_changes/`) included |
| Local memory index | `workspaces/<PROJECT_ID>/` (JSON, or LanceDB when enabled) | A searchable copy of the text |
| Views and dashboard | `workspaces/<PROJECT_ID>/08_context_packs/views/*.html`, release views in `08_context_packs/<rN>/views/*.html`, `dashboard.html` | Rendered copies of the artifacts, opened from disk |
| Browser storage of the views | The browser's `localStorage` for `file://` pages | Feedback comments, guided answers and readiness marks the BA enters in a view stay there until cleared (see below) |
| The BA's machine and project | Everything outside the workspace | Sentinel runs with the BA's user rights |
| The release channel | Tags, releases and the `stable` branch on GitHub | What every installation trusts |

Keys Sentinel stores in `localStorage`:

| Key | Content |
|-----|---------|
| `ignite-sentinel:view-feedback:<project>:<artifact>:<source>` | Feedback comments typed in a view |
| `ignite-sentinel:view-feedback:<project>:<artifact>:<source>:source-sha` | The sha256 of the source the comments and guided answers were written against (no content) |
| `ignite-sentinel:view-guided-response:<project>:<artifact>:<source>` | Answers typed in a guided response view |
| `ignite-sentinel:readiness:<project>` | The sent/answered marks of the readiness view: the ids of the marked requests, no text (**Clear** in the view empties it) |
| `ignite-sentinel:view-provenance` | Whether provenance is shown (a preference, no content) |
| `ignite-sentinel:color-mode` | Light or dark (a preference, no content) |

Feedback and guided answers are client content. Nothing here leaves the browser: the views have no network access (T5's CSP). Exporting them as Markdown removes nothing. **Clear Comments** in a view empties its feedback comments only, and **Clear** in the readiness view empties its marks. Guided answers have no clear control: they stay until the BA empties each field or clears the browser's site data for local files, which removes every key above.

## Trust boundaries

1. **Source documents → runtime.** Untrusted. A document can be written by anyone, including someone who wants to steer the outputs or exfiltrate data.
2. **Agent → runtime.** Semi-trusted. An agent proposes; the runtime validates every contribution against a citation from the sources.
3. **Runtime → file system.** Writes are confined to the project (T2).
4. **Runtime → network.** None (T5).
5. **GitHub → installation.** Releases, tags and the plugin are trusted once verified (T4, T6).

## Threats

### T1 — Prompt injection through sources

A source contains text written as an instruction ("ignore the previous rules", "you are now the admin", "run this command", "send the file to…") hoping an agent or a compiler acts on it.

**Control:** `/ingest` and `/sync` flag instruction-shaped passages as findings with `origin: injection_signal` in `01_discovery/injection_signals.md`, with source, line and excerpt. Detected, in English and Spanish:

- **override**: "ignore / disregard / forget the previous instructions, rules or prompts";
- **role impersonation**: a line starting `system:`, `assistant:` or `developer:`, chat-template tokens, "you are now", "act as", "pretend to be";
- **command execution**: "run / execute the following command", `curl … | sh`, `wget … | sh`, `rm -rf`;
- **exfiltration**: "send / upload / post / forward / share the data, files, secrets, credentials… to …", including a file name or address with dots in it (`state.json`, `evil.example`);
- **governance tampering**: "close / approve / skip all gaps, gates, maturity, readiness", "do not report / flag / log".

The same phrasings are also found where a reader does not see them:

- **html_comment**: inside an HTML comment (`<!-- … -->`), also when the phrase is split across the comment's lines or the comment opens with `system:`. One finding covers the whole comment (its line range) and all its lines are blanked;
- **encoded**: a run of base64 (also URL-safe), hex or percent-encoding (`%20`) that decodes to UTF-8 text with one of these phrasings. The register shows the decoded excerpt, with any secret in it redacted;
- **obfuscated**: a line that only matches once zero-width characters are removed and look-alike forms such as fullwidth letters are folded (Unicode NFKC).

Comments, data URIs, hashes and tokens without such a phrase are not flagged.

Not detected: an unclosed `<!--`, text hidden by markup or CSS (`display:none`, white text), an encoded run split across lines, encoded twice or in another scheme (ROT13, gzip), letters from another script that look Latin (Cyrillic `о` for `o`), other languages, and paraphrases that avoid these phrasings.

The flagged lines are blanked from the text the compilers analyze, so an embedded order cannot change gaps, units or downstream artifacts. Memory applies the same shield: whenever it indexes a client copy (the `/ingest` raw copy, a `/sync` or `/resolve-gaps` change copy, any file in the `00_raw/` context folders or `07_changes/` that Sentinel did not write itself), flagged lines are blanked, also on `/sync` and on `/reindex`, so `/retrieve` and the context packs never serve them. The raw copy keeps them verbatim for the BA to review. When a view shows that raw copy as a source fragment (the brief view cites `RAW-…`), each flagged line appears as `<NEUTRALIZADO:type>`. The views escape all text they render and keep their embedded data inside its `<script type="application/json">` block, so markup or a script in a source shows as text and does not run.

Agent and BA payloads get the same check: `/annotate`, `/challenge`, `/scrutinize` (every mode), `/self-review` (every mode), `/compose`, `/assume`, `/refine-backlog`, `/implementation-feedback`, and `--override` on `/validate`, `/quality` and `/backlog-status`. Flagged lines are listed in `injection_signals.md` and stay verbatim only in the payload copy the command keeps. `/scrutinize --mode anchors`, `/self-review --crosses` and `/self-review --sufficiency` keep no payload copy, so there the flagged lines are only listed. In everything else the command writes from the payload (artifacts, reports, registers, `state.json`), each flagged line becomes `<NEUTRALIZADO:type>`; in a rejection report, only the quoted payload text is neutralized, not Sentinel's own message. Citations are checked against the sources first, on the text as the agent wrote it. So an `/annotate`, `/challenge` or `/scrutinize` gap may quote a flagged line of the raw input: the quote passes, and `gaps.md` and the report show it neutralized. The `absent` entries of the sweep protocol are also checked on the payload as written; `agent_sweep_log.md` stores them sanitized, and its figures are still counted by the runtime. `/compose` checks its citations again each time the PRD is regenerated, so it keeps them as written in `accepted_blocks.json` and neutralizes them only in `prd.md`.

Every agentic surface (AGENTS.md, CLAUDE.md, the MCP server instructions, the Kilo agents, the source-reading skills) declares that sources are data. Agent contributions only land after the runtime finds their verbatim citation in the sources.

**Evidence:** `tests/test_injection_signals.py`: seeded patterns produce one finding each, and a compiler's output is identical with and without an embedded instruction. `tests/test_privacy_imp336.py`: flagged lines stay out of memory and `/retrieve` after `/ingest`, `/sync` and `/reindex --full`. `tests/test_payload_hygiene_imp342.py`: for each payload command, a flagged line stays only in the payload copy, and a `/compose` citation of a flagged source line still passes when the PRD is regenerated. `tests/test_payload_hygiene_imp347.py`: the same for `/annotate`, `/challenge`, `/scrutinize` (every mode), `/self-review --crosses` and `/self-review --sufficiency`, and a gap that quotes a flagged raw line is accepted but shown neutralized. `tests/test_hidden_injection_imp351.py`: hidden, encoded and obfuscated instructions are flagged and stay out of memory and `/retrieve`, ordinary comments and encoded data are not flagged, and the brief view shows a flagged raw line neutralized with source markup kept as data.

**Residual risk:** detection is pattern-based. A novel phrasing can pass unflagged; the citation rule still keeps an agent from inventing content, but an agent that reads the raw source directly is protected only by its own harness and by the BA's review.

### T2 — Path traversal and unconfined writes

A crafted project id, artifact name or source path (`..`, an absolute path, a symlink or junction) makes Sentinel write outside the project, or a crash halfway leaves a truncated artifact.

**Control:** every file the runtime writes goes through `sentinel/core/io.py`. The destination must resolve inside its root, so `..`, foreign absolute paths and links that leave the root raise `UnconfinedWrite`; both spellings of a Windows folder (8.3 short names) compare equal. Writes land in a temporary file, are fsynced and swapped in with `os.replace`. Project ids are validated before any path is built. An AST guard keeps the rest of `sentinel/` from writing any other way.

**Evidence:** `tests/test_safe_writer.py` (escapes, links, interrupted writes, the AST guard); "workspace ids" (`project_ids_check`) in `/doctor`.

**Residual risk:** an attacker who can already create links inside the project folder can redirect reads. Writes stay confined.

### T3 — Secret leakage

A source contains a private key, cloud key, token, JWT, URL with credentials, connection string or a plain credential, and it reaches an artifact, a view, an export, the memory index or the repository.

**Control:** `/ingest`, `/sync --source`, `/resolve-gaps` and `/harvest` run every incoming file through the same sanitizer. So do the commands that take an agent or BA payload (`/annotate`, `/challenge`, `/scrutinize` and `/self-review` in every mode, `/compose`, `/assume`, `/refine-backlog`, `/implementation-feedback`, and `--override` on `/validate`, `/quality` and `/backlog-status`): the payload copy they keep and everything they write from it carry `<SECRETO:type>`. Detected:

- `private_key`: PEM private key blocks;
- `connection_string`: `Server=…;…Password=…`, `AccountKey=`, `SharedAccessKey=`;
- `url_credentials`: a URL that carries a user and a password before the host;
- `cloud_key`: AWS access key ids (`AKIA…`, `ASIA…`), Google API keys (`AIza…`), `aws_secret_access_key = …`;
- `jwt`: three-part `eyJ…` tokens;
- `token`: GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), GitLab (`glpat-`), Slack (`xoxb-`, `xoxp-` and similar), OpenAI / Anthropic style `sk-…`, Stripe secret and restricted keys (`sk_live_`, `sk_test_`, `rk_live_`, `rk_test_`), Stripe webhook secrets (`whsec_`), npm (`npm_`), SendGrid (`SG.…`), and `Bearer` tokens of 24 characters or more;
- `credential`: a key-value line whose key is `password`, `passwd`, `pwd`, `secret`, `client_secret`, `api_key` / `apikey`, `access_key`, `secret_key`, `token` or `access_token` / `auth_token` / `api_token` / `refresh_token` (also with a prefix such as `DB_PASSWORD`, and quoted as in JSON or YAML), followed by `=` or `:` and a value. Only the value is redacted. The value must look like a secret: at least 6 characters with a letter and a digit, or at least 20 characters of key-like charset. Placeholders (`<your password>`, `***`, `xxxx`, `${VAR}`, `{{VAR}}`, `%VAR%`, `your-…`, `example…`) and prose (`Password: required`) are not redacted.

Not detected: a credential with no key in front of it, a value that is a single plain word (`changeme`), a credential in a table cell or prose ("the password is …"), and provider formats not listed above. The BA's original file is only read; the workspace copy and everything extracted from it carry `<SECRETO:type>` instead. Each redaction is logged in `01_discovery/secret_alerts.md` with type, line and a SHA-256 fingerprint, never the value. False positives are allowlisted by fingerprint. Memory redacts everything it indexes. `/view` and the exports refuse to write an output that carries a secret or a reference to another workspace. Personal data is reported only, opt-in, in `01_discovery/pii_report.md`. In a clone, `/doctor` runs "tracked files carry no secrets" (`tracked_secrets_check`) over `git ls-files` and "workspaces/ is ignored by git" (`workspaces_ignored_check`), which fails when a new workspace would be committable.

**Evidence:** `tests/test_secrets_ingest.py`: six seeded secrets, six redactions, none in any output. `tests/test_privacy_imp336.py`: each credential and provider kind is redacted, placeholders are not, and nothing reaches the workspace, memory or `/retrieve` after `/ingest`, `/sync --source`, `/resolve-gaps` or `/harvest`. `tests/test_payload_hygiene_imp342.py`: no secret from a payload reaches any workspace file, and each one is logged in `secret_alerts.md`, for each payload command. `tests/test_payload_hygiene_imp347.py`: the same for `/annotate`, `/challenge`, `/scrutinize` (every mode), `/self-review --crosses` and `/self-review --sufficiency`.

**Residual risk:** a secret in a format the detector does not know passes through (see "Not detected" above). Personal data is not redacted, only reported.

### T4 — Supply chain

A compromised dependency, GitHub Action or release artifact runs code on the BA's machine.

**Control:** the core has no mandatory third-party package ("stdlib purity", `stdlib_purity_check`, in a clone). The optional extras are locked with hashes in `constraints/`; the install guides give the `--require-hashes` command, and a plain `pip install` of an extra skips that protection. CI runs CodeQL, dependency review, `pip-audit` over every lock and `claude plugin validate --strict`, with every Action pinned by commit SHA; Dependabot keeps them current. Each release carries a CycloneDX SBOM, and the wheel, the SBOM and each plugin archive have a build provenance attestation (`gh attestation verify <file> --repo jmatzkin1980/ignite-sentinel`). The plugin ships the runtime in source form so it can be read, and in a clone "Claude Code plugin and marketplace" (`claude_plugin_check`) fails when it drifts from the generator. A `.pyz` built from a clone is not part of a release and carries no attestation: build it on a machine you trust.

**Evidence:** `tests/test_supply_chain.py`, `tests/test_release.py`; the `security` and `release-attest` workflows in `.github/workflows/`.

**Residual risk:** an attestation proves where an artifact was built, not that the code is benign. A compromised maintainer account can publish a signed bad release; pinning (T6) limits who receives it automatically.

### T5 — Network exfiltration

Code in the runtime or in a view sends client content to a remote host.

**Control:** "package imports no network module" (`network_isolation_check`, in a clone and in runtime mode) is an AST scan that fails on any import of `socket`, `urllib`, `http`, `ftplib`, `smtplib`, `ssl` or an HTTP client, including dynamic imports with a literal name. `webbrowser` only opens existing local files. The embedding extras force offline mode and fall back to a local embedder without a model; they never download. The one permitted house is `sentinel/setup_download.py` (`network_import_violations` allows only that file), reached only by `/setup --semantic-memory`: https only, hosts `huggingface.co` and `.hf.co` subdomains, a pinned revision, and every file's sha256 and size verified before activation. Sentinel never downloads, except /setup --semantic-memory, which runs only when you ask for it (you, or your agent at your request in chat) and which checks every file's sha256 before using it. The views and the dashboard carry a Content-Security-Policy (`default-src 'none'; connect-src 'none'; form-action 'none'; …`), so a page cannot fetch, post or load a remote image.

**Evidence:** `tests/test_zero_network.py`, `tests/test_view_csp.py`.

**Residual risk:** the agent or harness you run Sentinel from has its own network access. Its policies apply separately (see the [admin guide](20-admin-guide.md)).

### T6 — Hooks

The plugin ships a hook, and hooks run commands with the user's rights on every matching tool call. A tampered hook would run on each edit.

**Control:** the plugin has exactly one hook, `plugins/ignite-sentinel/hooks/deny-governed-artifact-write.py`, a read-only `PreToolUse` guard that only denies a hand `Write`/`Edit` of a governed artifact; it writes nothing and makes no network call. The plugin has no `bin/`, monitors, LSP servers or telemetry, and the MCP server is a separate plugin that installs disabled. The plugin is generated, and in a clone "Claude Code plugin and marketplace" (`claude_plugin_check`) in `/doctor` fails when its hook, or any other file, differs from what the generator produces. The "agentic surface audit: ..." checks (`agentic_surface_audit_checks`) flag dangerous shell constructs in the hook and settings JSON of the clone. An admin can set `allowManagedHooksOnly`: only hooks of plugins force-enabled by managed settings run, matched on the full `plugin@marketplace` id. In a clone, the same rule (no hand write of a governed artifact) is applied by a Claude Code hook, a Codex policy script and Kilo Code's `permission.edit` rules, the first two sharing one decision in `sentinel/hooks_logic.py`; "kilo.jsonc denies editing governed artifacts" (`kilo_governed_deny_check`) verifies the Kilo rules. The list of governed files comes from `sentinel/governed_artifacts.py`, the same list `/health` uses for hand-edit detection. Only the Claude Code hook and the Kilo rules have been watched refusing a write, and only for the brief, specs and backlog; the refusal for `gaps.md` and `requirements.md` has not been watched on any surface yet. The Codex script has not been watched at all, so for that surface the command gates and `/health`'s hand-edit detection are the control.

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
