# Changelog

All notable changes to Ignite Sentinel vNext are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Brief v2 schema as data (IMP-252). `sentinel/templates/brief_v2.json` defines the brief v2: §0–§9, 55 numbered subsections, 2 annexes and their sub-blocks.
  - **Each entry:** a stable id, en/es titles, its applicability (required ●, conditional ◐ or N/A —) per profile (`UI`, `API`, `BAT`, `INT`, `MIG`, `REG`, `MT`), how the genesis changes it, and a writing contract (inputs, what it produces, what it must include, what it must not invent, and the class of pending mark).
  - **Applicability:** `sentinel/brief_schema.py` combines the marks. The strongest profile wins. A genesis ● raises an entry and a genesis — lowers it. A Δ reshapes how the entry is filled. An N/A sub-block never switches its parent off. `MIG` implies `brownfield-replacement`. The N/A entries are grouped with their literal counterfactuals.
  - **Vocabulary as data:** the closed vocabulary of empty places and the two pending classes (`⏳ PENDIENTE` blocks; `⏳ PENDIENTE DOMINIO` is deferrable).
  - **Id golden:** `brief_v2_ids.lock.json` is append-only. `/doctor` fails if an id disappears without a tombstone, a tombstone is reused, or a new id is not appended.
  - **Settings:** `/brief --profile ... --genesis ... --validation-direction ...` records what the BA confirmed. Until then, `/brief` shows a proposal and the blocking gap `GAP-BRIEF-PROFILE`.
  - **Validation direction:** the confirmed one now drives the interim mark of a contradiction (`⏳` or `⚠`).
  - v1 briefs are unchanged.
- Dual read of the brief (IMP-254). `sentinel/brief_model.py` reads a v1 or a v2 brief into the six canonical lenses the readers already use, so no reader parses section numbers itself.
  - **Lens map:** v1 maps one to one. In v2, §1–§4 feed their lens, §5 feeds lens 5 except §5.11, and §5.11 plus §6 feed lens 6; §0 and §7–§9 feed none. A test pins the map against the schema.
  - **Readers:**
    - Brief readiness (and so `/maturity`, `/status` and the brief→PRD check) reads `⏳` marks and `[[…]]` citations in a v2 brief.
    - The specs retrieval answers its v1 heading terms through an alias table.
    - `/view` counts structured citations.
  - **Backlog anchor:** an anchor into a v2 brief is its section id (`§ 5.11`), not a line range, because v2 is rewritten in place.
  - **Guard:** the v1 compiler never overwrites a v2 brief; `/brief` and `/specs` keep it until the v2 compiler lands.
  - v1 output is unchanged: the goldens are identical, and a characterization test pins the readiness reader against the previous algorithm.
- Brief v2 compiler, core (IMP-253a). `/brief --brief-version 2` opts a project in. It compiles only with a confirmed profile and genesis; until then `GAP-BRIEF-PROFILE` opens in `gaps.md` and the v1 brief stays.
  - **Body:** `sentinel/compilers/brief_v2.py` writes §0–§9 and the annexes, in en or es. Every place is one of three things:
    - a quoted fact with a `[[sources § … # F-NN]]` citation of its source row (a confirmed gap answer cites the response that closed it and names the gap);
    - a pending mark: `⏳ PENDING (GAP-X)`, or `⏳ PENDING DOMAIN (GAP-X)` for domain context and for conditional places with no evidence;
    - an N/A with its counterfactual, grouped as the schema says.
  - **Routing:** gap answers reach their subsection through `brief_model.V2_GAP_ROUTES`.
  - **Counts:** §0.2 (certainty per section, reliability warning) and §7 (seeded marks, open gaps) count the same places.
  - **Assumptions and build list:** §8 lists the assumptions. §9 lists build items with their dependencies.
  - **Changes:** §6.3 lists changes against the previous v2 brief with the closed delta vocabulary. A re-run is byte-identical.
  - **Report:** `02_requirements/brief_compile_report.json` lists every place, the `fill_sites` still to fill and the `unused_sources`.
  - **Citations:** `sources` is a citation document (`07_changes/source_log.md`), so `/validate` resolves the brief's citations.
- Brief v2: in-place rewrite, inferences, `built` marks and transcription rules (IMP-253b).
  - **In-place rewrite** (inverts IMP-145). A confirmed answer replaces what the raw input said about the same place, and the replaced statement moves to the provenance annex and to the report's `replaced` list. In a v2 project, `/resolve-gaps` recompiles the brief right away: only the answered places change, and the output lists them as `brief_v2.rewritten_places`. The self-correction gate checks each answer inside its own place with its gap id.
  - **Inferences:** an assumption that closes a gap appears in that gap's place as `(inferred) … (ASM-X)`, next to the `⏳` it waits on. It is counted in the report, listed in provenance, and kept as an `INFERRED` unit in `knowledge_state.json` that survives the ledger's re-materialization.
  - **Contradictions:** an open contradiction's interim value goes in its place, routed by scope.
    - With `to-build`, it is followed by its `⏳` mark.
    - With `validation_direction: built`, it gets `⚠` inline, §7.2 lists the divergences, and §9 carries only Debt and Defect items.
    - An unresolved contradiction is only a pending mark.
  - **Transcription rules:**
    - Quotes stay verbatim, including contracted enumerations and capped values.
    - A source `TBD` stays `TBD` and keeps its place pending.
    - A doubled word is marked `[sic]`.
  - The `sentinel-project-brief` skill is rewritten for the brief v2: settings, the four kinds of place, these rules, the compile report and the v2 self-correction gate.
- Brief v2 integrity (IMP-255). It applies only to a v2 brief.
  - `/validate` reports:
    - a `⏳` that points to a gap missing from `gaps.md` or already closed;
    - an inline `⚠` without an open contradiction gap;
    - a mark without its `fill_site` in the compile report, or the reverse;
    - an `(inferred)` line without its `INFERRED` ledger row;
    - a forbidden value used as a value: an empty cell, `-`, `—`, a bare `N/A`, the brief's own `TBD`, `ninguno`;
    - an edit residue.
  - **Umbrella gaps:** the compiler points every pending mark at an open gap. A place with none gets its section's non-blocking umbrella gap `GAP-BRIEF-S<n>`, which the compiler opens and closes as needed.
  - **`/doctor`:** checks that skills and mirrors write the v2 marker and the pending marks only in their canonical form.
  - v1 briefs are never checked.
- Gaps as elicitation (IMP-257).
  - **Table:** the gap table gains two columns at the end, `Kind` (`client`, `domain` deferrable, `synthesis`, `template`) and `Closure` (a closed vocabulary of 13 reasons plus `reopened_false_premise`). Older `gaps.md` files still read.
  - **Closure rules:**
    - Every closure needs a citation, otherwise `closure_findings`.
    - `by_decision` cites a `DEC-*`; `resolved_by_inference` cites an `ASM-*` and stays partially closed.
    - A confirmed TBD is partial, and example data never closes.
    - `reopened_false_premise` reopens a gap and keeps the previous closure.
  - **Reopening:** invalidating an assumption reopens the gaps it held up.
  - **Elicitation:** the recommended option is marked as an inference, the response section shows the "meanwhile" value from an active assumption with where it appears in the brief v2, and `01_discovery/gap_elicitation.json` keeps it all.
  - **Topic dedup:** agentic channels, self-review and contradictions extend an open gap on the same topic instead of opening a duplicate.
  - **Rounds:** `/gaps --top N` plans the next round (scope > security > UX > technical, recommended first, "leave pending") into `01_discovery/gap_round.md`.
  - **Schema:** `gap.schema.json` is aligned with the table.
  - **Bug fix:** an empty response field no longer reads the next line as its value.
- Golden snapshots of the brief v2 in English and Spanish, with its compile report (`tests/fixtures/golden/brief_v2/`). This closes H16a. The v1 goldens are unchanged across the horizon.

## [0.4.0] — 2026-11-10

### Added
- `CTX-NNN` lifecycle and `/next` (IMP-294). A context request moves `active` -> `answered` -> `closed`, or `obsolete`: `/sync` marks it `answered` when a change cites its id, and `/context-request --id CTX-NNN --status ... [--reason]` moves it by hand (`closed` and `obsolete` need a reason and are final; regenerating reopens). Transitions are kept in `08_context_packs/requests/ctx_lifecycle.json`. `/next` prints only the next step, the same decision as `next_action` in `/status`, in the CLI, MCP (`sentinel_next`) and the Claude Code and Kilo commands.
- Sweep protocol for agentic channels and F7 (IMP-271). `sentinel/templates/agent_sweep_protocol.md` is the guide `/annotate`, `/challenge`, `/scrutinize`, the implementability probe and `/self-review` follow, with a worked example. On top of the verbatim evidence check, the runtime rejects a payload with a malformed `AUSENTE: <what> en <where>`, an absence that is actually in the source, a bad `untouched` or `blocks`, or figures written by the agent; it counts what it accepted in `01_discovery/agent_sweep_log.md`. F7: `/gaps --id GAP-X --disposition accepted|rejected|irrelevant` records the BA's disposition on agentic gaps, and `/maturity` reports the false-alarm rate per channel (`maturation_telemetry.agent_channel_dispositions`).
- Central registry of id families and a structured-citation validator (IMP-249). `sentinel/templates/id_families.json` lists every family with its pattern and status: kept (`GAP`, `ASM`, `DEC`, `US`, `SPEC-U`, `CTX`...), new for v2 artifacts (`RN`, `CA`, `HU`, `SC`, `I`, `P`, `E`, `C`, `R`, `PDef`) or a view (`D-N.M` of `DEC`). It also holds the `r<N>` release prefix (only `RN`, `CA`, `HU`), the catalog keys for error codes, events, flags and routes, and the edges `HU → SPEC-U → US`. Retired ids go to `06_traceability/retired_ids.json` and are never reused. In a v2 artifact (`<!-- sentinel-artifact: v2 -->`), `/validate` resolves each `[[doc § section › subblock # ID — sostiene: ...]]` inside the cited section and flags line-number citations; v1 artifacts are unchanged.
- `.docx` ingestion in three layers (IMP-270), standard library only. `/ingest` and `/sync` turn a `.docx` into Markdown (headings, lists, tables), copy its images from `word/media/` and `media/` to `NAME_media/`, and list its comments with author, date and anchor. The extraction is dated, carries the sha256 of the original, is redacted like any source and registers as an F-NN row. The autonomous `/sync` scan picks `.docx` up.
- Contradictions, echo, disguised proposals and cited-but-undelivered sources (IMP-251). `/ingest` and `/sync` anchor each source's short statements to its F-NN row in `01_discovery/statement_ledger.json` and render `01_discovery/contradictions.md`.
  - **Contradiction:** two sources with different values for the same subject keep both anchors and open a blocking gap `origin: contradiction`, without choosing. Silence is not a contradiction.
  - **Interim value:** the IMP-250b precedence says which version governs while the gap is open, marked `⏳` (`⚠` with `validation_direction: built`); an unsettled clash has none.
  - **Echo:** a file Sentinel wrote is an `own_artifact`; it adds no facts and never closes a gap.
  - **Disguised proposal:** a source that declares itself not validated only adds proposals and cannot close a gap; proposal cues and new technical names are proposals until ratified.
  - **Cited, never delivered:** a cited document missing from the registry opens a gap `origin: cited_not_delivered` with what to ask for and to whom.
  - The gap schema `origin` enum now lists every origin the code writes.
- Source precedence, impact matrix and closing report (IMP-250b), on top of the F-NN registry. The routing data lives in `sentinel/templates/source_routing.json`.
  - **Authority:** each new row gets one (minutes, API contract, prototype, example...), defaulted from its bucket or from a file named like an example; `/sources --authority` corrects it.
  - **Impact matrix, document x section:** each new row gets the cells its authority routes to, with what to look for. `/sync --digest` shows it as section (e). `/sources --cell DOCUMENT/SECTION --mark updated|reviewed` closes a cell (reviewed needs a reason). A retired source cascades to every document. Pending cells appear in `/status`.
  - **Precedence by scope:** `/sources --precedence SCOPE --between F-NN,F-MM` says which row governs. The default table is overridable per scope with `precedence:` in `sentinel.config.yaml`. An own artifact is never an authority, and an unsettled clash is `unresolved`: the newest source never wins by default.
  - **An example never closes a rule:** `/resolve-gaps` leaves a confirmed answer from an example `ANSWERED`.
  - **Closing report:** `/sources --report` writes `07_changes/closing_report.md` by recipient, with ADDED / MODIFIED / REMOVED per row and the originals ready to delete. It never deletes.
- Source registry (IMP-250a): each source content is one `F-NN` row in `00_raw/source_manifest.json`, rendered as `07_changes/source_log.md`. `/sources PROJECT_ID` lists the rows, and `--id F-NN` changes one.
  - **Novelty by hash, never by date:** the same document under a second path is the same row, and two `/sync` runs over one file do not duplicate it. A known path with new content is a candidate new version until a person says which one governs (`--superseded-by` or `--current`).
  - **Row lifecycle:** `/ingest`, `/sync` and `/resolve-gaps` open the row when they start and close it when the cross finishes. A row left open is a `/status` warning.
  - **Validity:** current, superseded, retired (with its reason and replacement) or expired by a cut-off date, optionally for one topic.
  - `/status` and the verdict gain a non-blocking `sources` gate. Existing manifests are migrated on first read, and the counter never restarts.
- Build-readiness view (IMP-247): `/view PROJECT_ID --artifact readiness` shows what is missing and from whom.
  - **Items:** one card for the workspace, one per backlog story and one per SLICE-PLAN wave. Each card carries its governed verdict from IMP-248. A wave takes the most severe verdict of its stories, and a wave without stories is never green.
  - **Requests:** every open gap and every missing Definition of Ready item is a request, marked by whether it blocks the start, the slice or nothing.
  - **Recipients:** requests are grouped by recipient from the stakeholder registry. Unregistered owners are shown as unassigned, never invented. **Copy request** turns each group into a message ready to send.
  - **Local marks:** you can tick requests in the browser (`ignite-sentinel:readiness:…`), and export or import the marks. An open request degrades a `READY` item, and marks never upgrade a governed verdict.
  - It renders through the same shell, themes and CSP as the other views, with EN/ES goldens.
- Ready-to-build verdict by counts (IMP-248). `build_readiness_verdict(project_id, release=None)` (`sentinel/readiness_verdict.py`) is the single source of the verdict (`READY`, `READY_WITH_WARNINGS`, `NOT_READY`), the gap counts, the gate matrix and the next step for `/status`, `/dashboard` and the MCP `sentinel_status` tool, which now agree.
  - Never `READY` with a blocking gap open.
  - A check that could not run (no brief, no requirement units, no knowledge units, no backlog) is listed in `partial_coverage` and never shows green.
  - `DEFERRED_TO_CONTEXT` units and "test before advancing" assumptions are warnings.
  - `release` is accepted and reported as not scoped yet; scoping arrives with the release series.
  - The maturity score stays published next to the verdict, and the maturity gates do not change.
- `/status` prints a summary by default: the verdict, gap counts, gate matrix, maturity score and next step. `--full` (MCP: `full=true`) prints the detailed dump, where `development_readiness` now appears once instead of twice.

### Changed
- One gap counter (`gaps.count_gaps`) replaces the two that disagreed. `/status` used to fold `ANSWERED` into `partially_closed`, and both counters hardcoded `critical`/`high` as blocking. Blocking now follows `maturity.blocking_gap_severities`, and `/status` counts from `gaps.md` instead of a cached copy in `state.json`.
- One next-step decision replaces the separate ones in `/status` and `/dashboard`, which branched differently. It follows the stage, so a project at `READY_FOR_BACKLOG` with non-blocking gaps open is pointed at the backlog, not back at the gaps.

### Fixed
- The documentary schemas now say what the code writes (IMP-249): `decision.schema.json` accepts named decisions (`DEC-AUTH-TOKEN`), and the traceability node id pattern, built from the registry, accepts the `CTX`, `DISC`, `PRD`, `QA`, `SEED`, `EV`, `RU`, `SPEC-U` and `REQ-EARS` nodes the graph already holds.
- An unreadable source fails with a typed error (IMP-270). A corrupt `.docx` or a binary file that is not UTF-8 text raised a bare `UnicodeDecodeError`; it now raises `SourceFormatError` before any F-NN row opens. A UTF-8 file with an unknown extension is still stored as Markdown, but no longer silently: the output carries `source_format.warning`.
- Precedence: an authority no longer beats itself through an `over: "*"` rule; two minutes in `business` are `unresolved` (IMP-250b).
- A line-ending-only change is no longer drift, a new source or a hand edit (IMP-291). Sentinel writes with the OS line ending, and git or an editor can flip a file between CRLF and LF without touching its content; drift, the source manifest and the out-of-CLI-edit check hashed raw bytes, so that flip read as "source changed", "modified" and "edited outside the CLI". They now share one hash over the content with CRLF folded to LF (`sentinel/core/hashing.py`), and a hash recorded before this release still matches, so existing workspaces are not flagged on upgrade. `/health` also reports a derived artifact (`specs`, `backlog`) that has no recorded source fingerprint as "cannot be verified" instead of passing it silently.
- `/sync` no longer reads its own output back as client input (IMP-293). `/sync --digest` writes `*_interaction_digest.md` and `*_gap_response_proposed.md` into the `07_changes` bucket of the change, and never recorded them, so the next autonomous `/sync` ingested them as new sources. They are now recorded, and every file Sentinel writes into a scanned bucket (`*_impact_report.md`, `*_interaction_digest.md`, `*_gap_response_proposed.md`, `*_gap_resolution_report.md`) is excluded from the scan even after someone edits it: a PROPOSED gap response is applied only through an explicit `/resolve-gaps --source`.
- Touching gaps no longer moves a project back a stage (IMP-292). `/annotate`, `/challenge`, `/scrutinize`, `/self-review`, `/sync`, `/resolve-gaps` and `/gaps` recomputed `readiness_stage` from the gap counts alone, which tops out at `READY_FOR_PROJECT_BRIEF`, so a project at `READY_FOR_BACKLOG` fell back to the brief with nothing new blocking it. Now the stage only moves back when a blocking gap is open; a later stage, or a block set by `/brief`, is kept until the command that owns it runs again. `/dashboard` also knows `SELF_CORRECTION_FAILED` and `UNITS_NOT_IMPLEMENTABLE`, which `/brief` writes, instead of showing them as raw keys at the ingest step.

## [0.3.0] — 2026-11-08

### Added
- The Claude Code plugin finds Python without `python` on PATH (IMP-290): the hook and the skills now start Python through a generated `python.sh` (`sh "${CLAUDE_PLUGIN_ROOT}/python.sh" ...`), which tries `SENTINEL_PYTHON`, then `python3` / `python` / `py -3` on PATH (skipping the Microsoft Store alias), then the usual Windows install folders, checks for 3.10+, and otherwise exits 127 with how to fix it. Seen live: a Windows laptop with Python 3.14 installed but no `python` or `py` on PATH, where every plugin skill failed. `*.sh` is checked out with LF. The MCP plugin still starts `python` directly, since MCP servers are not run through a shell.
- Security policy, threat model and admin guide (IMP-283):
  - **`SECURITY.md`**: reports go through GitHub private vulnerability reporting; only the latest release is supported.
  - **Threat model** (`user_guide/19-threat-model.md`): the assets, including the feedback and guided answers that views keep in `localStorage`, and seven threats: prompt injection, path traversal, secret leakage, supply chain, network exfiltration, hooks and auto-update. Each one names its control, the test that proves it, and the residual risk.
  - **Admin guide** (`user_guide/20-admin-guide.md`):
    - a restrictive managed settings policy (`user_guide/references/managed-settings.json`) with `strictKnownMarketplaces`, managed `enabledPlugins` (MCP plugin blocked), `"autoUpdate": false`, `disableSideloadFlags`, `allowManagedHooksOnly` and `disableCommandPluginSources`;
    - pinning to a release tag, to a commit SHA (inline `settings` catalog with a `git-subdir` source) or to an archive digest;
    - how to confirm the policy is in force;
    - an approval checklist per release;
    - retention (workspaces, browser storage, transcripts, `tools/clean_local.py`) and the audit trail.
  - `tests/test_security_docs.py` keeps the documents true: every `/doctor` check, storage key, log file, path and cleanup flag they cite must exist, and the example policy must allowlist exactly what it registers.
- Versioning and releases (IMP-282):
  - **One version.** It lives in `pyproject.toml`. `sentinel.__version__` was stuck at `0.1.0` and is now `0.2.0`. `tools/release.py check` fails when `sentinel/__init__.py` or a `plugin.json` differs from `pyproject.toml` (CI → `release-check`).
  - **The tag must match the version.** A `vX.Y.Z` tag runs `release-attest`, which fails when the tag is not the version ("tag without a bump") or CHANGELOG has no dated section for it.
  - **No bump stays untagged.** On `main`, `release-check` tags `vX.Y.Z` on the merge commit that introduced the version and calls `release-attest`. A version that already carried its tag is left alone. A version introduced by an older commit is only tagged: that is how `v0.2.0` gets its tag, on the merge of #207. An untagged version without a dated CHANGELOG section fails.
  - **What a release publishes.** The workflow builds the wheel, the SBOM and one reproducible `.zip` per plugin, plus `SHA256SUMS`. Each zip passes `claude plugin validate --strict`, and all of them are attested.
  - **Where it lands.** The workflow creates the GitHub release, with the CHANGELOG section as notes, and fast-forwards the `stable` branch.
  - **Channels.** `jmatzkin1980/ignite-sentinel#stable` (latest release), `#vX.Y.Z` (one release) or no ref (`main`).
  - **Installing without git.** The zip feeds an `archive` plugin source (`url` + `sha256`).
- Claude Code plugin and marketplace (IMP-279): the repo is a marketplace (`.claude-plugin/marketplace.json`) with two plugins generated by `python -m sentinel.adapters --plugin` under `plugins/`. `ignite-sentinel` ships the 24 skills (rendered with the `claude-plugin` overlay), the read-only governed-artifact hook, a `launcher.py` that finds `lib/` by its own path, and the runtime in source form; workspaces land in the open project. `ignite-sentinel-mcp` carries the MCP server and installs disabled (`defaultEnabled: false`). No `bin/`, monitors or telemetry. `/doctor` adds `claude_plugin_check` (drift guard plus an offline subset of `claude plugin validate`) and CI runs `claude plugin validate --strict`. Install: `/plugin marketplace add jmatzkin1980/ignite-sentinel`, `/plugin install ignite-sentinel@ignite-sentinel` (guide: `user_guide/18-claude-plugin.md`).
- Supply chain and security CI (IMP-289): the optional extras are locked with hashes in `constraints/*.txt` and `tools/check_constraints.py` fails on any dependency without `==` or a hash. A `security` workflow runs dependency review on PRs, CodeQL (Python), `pip-audit` over every lock and a `--require-hashes` install. `tools/sbom.py` builds a CycloneDX SBOM (stdlib) from `pyproject.toml` and the locks; on `v*` tags `release-attest` builds the wheel and the SBOM with a build provenance attestation. Dependabot keeps the SHA-pinned actions current.
- Content-Security-Policy in views and the dashboard (IMP-288): the shell emits `default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'` as a `<meta http-equiv>` before any style or script, since the pages open from disk. HTML goldens regenerated (one line each). Observed live: dashboard (drawer, filters), `/view` (TOC, provenance toggle, local notes, Markdown export via `blob:`) and a local theme with an embedded woff2 font all work with no violation, while `fetch` and a remote image are blocked.
- Prompt-injection hygiene (IMP-286): source content is data, never instructions. `/ingest` and `/sync` flag instruction-shaped passages (override, role impersonation, command execution, exfiltration, governance tampering; English and Spanish) as findings with `origin: injection_signal` in `01_discovery/injection_signals.md` (`INJ-NNN`, source, line, excerpt). The flagged lines are blanked from the text the compilers analyze, so an embedded order cannot steer gaps, units or downstream artifacts. The workspace raw copy keeps them and the BA reviews them. AGENTS.md, CLAUDE.md, the MCP server instructions, the Kilo agents and the source-reading skills now declare the rule.
- Secrets and sensitive data at ingestion (IMP-285): `/ingest` and `/sync` detect private keys, cloud keys, JWTs, tokens, credentials in URLs and connection strings (`sentinel/secrets_scan.py`). The user's original file is only read. The workspace copy and everything extracted from it carry `<SECRETO:type>` instead, and each redaction is logged in `01_discovery/secret_alerts.md` with type, line and a SHA-256 fingerprint, never the value. False positives are allowlisted by fingerprint in `secrets_allowlist.txt`. Memory redacts every text it indexes, and `/view` and exports refuse to write an output that carries a secret or a reference to another workspace. Personal data is reported only, opt-in with `pii_report: true` (`01_discovery/pii_report.md`). `/doctor` adds `tracked_secrets_check` (scans `git ls-files`) and `workspaces_ignored_check` (new workspaces must be ignored; a deliberately versioned workspace is a WARN, see IMP-212).
- Verifiable zero network (IMP-284): `/doctor` runs `network_isolation_check`, an AST scan of the package that fails on any import of `socket`, `urllib`, `http`, `ftplib`, `smtplib`, `ssl` or an HTTP client library, including `importlib.import_module` / `__import__` with a literal name. `webbrowser` is only imported in `core/local_browser.py`, whose `open_local_file` opens existing local files (`file://`) and refuses URLs. The embedding extras force `HF_HUB_OFFLINE=1` (plus `TRANSFORMERS_OFFLINE` / `HF_DATASETS_OFFLINE`) before loading a model library; without a local model they fall back to the hash embedder with a message and never download.
- Single confined, atomic writer (IMP-287): every file the runtime writes goes through `sentinel.core.io` (`write_text`, `write_bytes`, `append_text`, `append_bytes`, `copy_file`, `write_json`). The destination must resolve inside its root — the project workspace it lives in, or an explicit root for repo-level outputs — so `..`, foreign absolute paths and links or junctions that leave the root raise `UnconfinedWrite`; both spellings of a folder (8.3 short names) compare equal. Writes land in a temporary file, are fsynced and swapped in with `os.replace`, so a failure halfway never truncates the previous content. The 85 direct writes and 10 `shutil.copyfile` calls were migrated, and an AST guard keeps `sentinel/` from writing any other way.
- CI in GitHub Actions (IMP-246):
  - `ci-fast` runs on every push: unit suite without the slow modules, `/doctor`, faithfulness eval.
  - `ci-full` runs on every pull request: whole suite, evals, wheel in a clean venv, and a Windows/Linux × Python 3.10/3.13 × LanceDB × `mcp` 1/2 matrix.
  - Actions are pinned by SHA and run with read-only permissions.
  - New tools: `verify.sh` (POSIX twin of `verify.ps1`), `tools/run_tests.py --tier fast|full` and `tools/time_tests.py`.
  - `.github/workflows` is registered as a surface contract, and the app's `.claude/worktrees` scratch folder is exempt.
- User-local themes (IMP-241): a theme name is looked up in `<workspace>/.sentinel/themes/` (`/view` only), then in `~/.ignite/themes/` (`IGNITE_THEMES_DIR`). Built-in names always win; `.sentinel/` is git-ignored per workspace. User themes may embed licensed `.woff2` fonts as `data:` URIs (no network). `/doctor` warns about local themes that are invalid, lack `procedencia` or shadow a built-in. Guide: `user_guide/17-themes.md`.
- Visual theme model (`sentinel/themes.py`): validated JSON themes with light/dark tokens, a semantics map that generates the colour legend, and the built-in `neutral` theme (WCAG AA in both modes). `/doctor` checks that `neutral` is the only theme shipped in the repo. Not yet used by views (IMP-239).
- Common view shell (`sentinel/shell.py`, templates in `sentinel/themes/templates/`): skip link, sticky top bar with a persisted light/dark toggle, sticky sidebar that becomes a hamburger menu below 900 px, print rules.
- `/dashboard --theme NAME_OR_PATH` (default `neutral`); also on the MCP `sentinel_dashboard` tool.
- `tools/clean_local.py`: maintainer cleanup that dry-runs by default and, with `--apply`, removes only git-ignored caches and build output, eval reports beyond retention, and leftover test tempdirs; workspaces need `--include-workspaces` plus a per-workspace confirmation.
- `tests/test_evals_faithfulness.py` runs the faithfulness claim eval (no-invention trap) in the unit suite, and `verify.ps1` runs `run_faithfulness_claim_evals.py` in the evals step.

### Changed
- Kilo Code plugin not pursued (IMP-281): a Kilo plugin is a JS/TS module (`PLUGIN.yaml` pointing at an npm package or a git repo whose `package.json` exports `./server` or `./tui`). Kilo documents no skills-only plugin and exposes no plugin path variable, so the clone (`.agents/skills`, `.kilo/`) stays the supported Kilo path, VS Code extension included. `user_guide/07-kilo-code-adapter.md` documents it, with the sources and the user-level `skills.paths` option.
- Codex plugin deferred (IMP-280): Codex CLI 0.142.4 reads `.claude-plugin/marketplace.json` and installs `ignite-sentinel` as is, but no plugin skill has been run in Codex (no account to observe it), and Codex documents `${CLAUDE_PLUGIN_ROOT}` only for hooks. The clone stays the supported Codex path. The surface-contract registry now names Codex on the marketplace entry, and `user_guide/08-codex-adapter.md` documents the plugin as unsupported, with the evidence and how to settle it.
- Per-surface skill rendering (IMP-278): `render_skill` / `render_skills` in `sentinel.adapters` apply a distribution overlay that rewrites only the runtime invocation (`python -m sentinel` in the clone, the plugin's `launcher.py` in `claude-plugin`); submodule commands such as `python -m sentinel.adapters` are left alone. The clone overlay is the identity, so the mirrors stay byte-identical, and `skills_out_of_sync` rejects a canonical skill that already carries an overlay invocation.
- Skill naming convention (IMP-277): every skill is `sentinel-<object>[-<action>]` and its description opens with the trigger (`Use when` / `Use on` / `Use before`) and ends with a `Not for ...` clause pointing to the neighbouring skill. `/doctor` enforces it (`skill_naming_check`), and `skills_out_of_sync` also reports a skill left behind in a mirror. **`sentinel-dashboard` is renamed `sentinel-views`** and now also covers the per-artifact `/view` pages.
- `/stakeholders` runs inside the command protocol (IMP-244): it leaves a `command_protocol_log.md` entry and refreshes the governed-artifact snapshot like every other writer. A test requires every CLI command to be read-only, mutating or explicitly exempt (`doctor`, `dashboard`, `init`, each with its reason), so a new command can no longer skip the protocol.
- The MCP server supports `mcp` 1.x (`FastMCP`) and 2.x (`MCPServer`, from `mcp.server.mcpserver` or `mcp.server`), passes everything but the name by keyword (2.x changed the positional order), and runs with an explicit `transport="stdio"` (IMP-245). The `[mcp]` extra is bounded to `mcp>=1.2,<3`.
- `/view` runs on the common shell and themes (IMP-240), with `--theme` (CLI and MCP) and the workspace config `theme:` as fallback.
  - The embedded model no longer carries `blocks`; trace nodes and source fragments live in shared tables. View goldens drop from 3.2 MB to 1.8 MB.
  - No wall clock and no absolute paths (provenance: source cut-off and 12-char sha256). `generate_artifact_view` returns `cutoff`, `source_sha256` and `theme` instead of `generated_at`.
  - Reader edition hides inline provenance behind a toggle.
  - Notes warn when the source changed and mark orphaned targets.
  - The feedback export is unchanged.
- `/dashboard` runs model -> validate -> render: the HTML is byte-for-byte reproducible (no build time, no absolute root), uses only theme tokens, shows the theme legend and a provenance section (source cut-off, `state.json` fingerprints, regeneration command). `generate_dashboard` returns `cutoff` and `theme` instead of `generated_at`.
- Eval reports keep the newest 5 per kind (`SENTINEL_EVAL_KEEP_REPORTS`); `SENTINEL_EVAL_REPORTS=0` disables writing them. The retrieval eval test uses the same retention.

### Fixed
- A non-editable install (`pip install .`) now ships every `sentinel` subpackage; it previously failed with `ModuleNotFoundError: sentinel.core`.
- `tests/test_momtest.py` no longer leaves temporary directories behind on every run.
- `/resolve-gaps` no longer classifies a client answer as `domain` or `inference` because of the folder the answer file sits in: only the owner, the evidence and the file's own name count, and keywords must start a word (`QA lead`, not `Aqua`). This was the intermittent `test_closed_split_by_client_domain_and_inference_source` failure on Linux CI, where a random `/tmp/tmpqa…` directory tipped the split.

### Security
- `PROJECT_ID` is validated at the CLI boundary, which MCP tools also go through (IMP-243):
  - 1-64 letters, digits, `_` or `-`, starting with a letter or digit;
  - it must resolve inside `workspaces/`.

  Ids like `../x`, `a/b` or `C:\x` now fail before anything is written. `/doctor` lists existing workspaces with invalid ids.

## [0.2.0] — 2026-07-17

### Added
- `/dashboard` generates a local, read-only, self-contained `dashboard.html` portfolio view for all workspaces, with lifecycle pipeline, gaps copy flow, embedded markdown documents, backlog rollup, gates, warnings, and suggested prompts/commands.
- `sentinel-dashboard` skill and user guide page document natural-language dashboard generation, interpretation, and the section/stage registry contract for safe dashboard evolution.
- `/ingest` now materializes a discovery knowledge ledger (`01_discovery/knowledge_state.md` and `.json`) with lens-scoped `CONFIRMED`/`ASSUMED`/`OPEN`/`INFERRED` units, evidence or `[PENDING INPUT]`, traceability links, local memory indexing, and a `/status` summary.
- `/scrutinize` adds governed multi-lens discovery scrutiny: cited findings from raw input or domain context become `origin: scrutiny` gaps, `scrutiny_report.md`, traceability edges, and refreshed ledger units.
- `/self-review` adds a skeptical PRD/spec review channel: cited findings become `origin: self-review` gaps, hard-to-reverse decisions are registered under `03_specs/self_review/`, and generated PRD/spec artifacts are not auto-edited.
- `/assume` registers governed BA-owned assumptions with human owner, risk, verbatim local basis, optional provisional gap link, `assumptions.md`, traceability, maturity/status risk summary, and `ASSUMED` ledger units.
- `/maturity` now persists `01_discovery/development_readiness.json`, a 16-area lens readiness matrix with `CONFIRMED`/`ASSUMED`/`OPEN` cells, evidence, scores, and a Crystallization Gate verdict exposed through `/status` and the dashboard.
- `/resolve-gaps` and `/sync` now metabolize governed knowledge into the ledger: confirmed answers can validate assumptions, explicit `ASM-*` invalidations open linked ledger units, development readiness is recalculated, impact reports name affected `KLU-*` units, and `/health` flags stale downstream artifacts.
- `/view` generates a local, read-only, self-contained HTML view for one artifact (`gaps`, `brief`, `prd`, `specs`, or `backlog`) with section navigation, markers, citations, and trace-node context. Its marker panel now enriches gaps and governed assumptions with lens/severity/status, why/unblocks/expected-format, owner/risk, inline `#marker-*` anchors, filtering, and section certainty badges.
- `/view` evidence chips now resolve trace IDs against the real local graph, embed bounded source fragments, and render one-hop mini trace graphs without network or external libraries.
- `/view` now includes a local feedback loop: reviewers can save section or marker comments in `localStorage` and export Markdown shaped for existing `/resolve-gaps` and `/sync` flows, without the HTML writing to source artifacts or introducing a new parser format.
- `/view` now includes guided response mode: gap and assumption markers are classified as client, domain, or BA/assumption items, client questions are shown by default, and local draft progress is tracked in `localStorage`.
- Artifact views now derive sections from a governed Markdown-to-blocks interlingua with a closed catalog (`section`, `requirement-table`, `persona`, `ears-statement`, `decision`, `traceability`, `pending`, `assumption`) and fixture-tested Markdown round trips. Markdown remains the source of truth.
- `/export PROJECT_ID --artifact prd --format mdx` writes an optional local MDX export folder derived from the artifact block model, for teams that already have an offline renderer. It does not install a renderer, call hosted services, or replace Markdown as source of truth.
- `/stakeholders` registers and lists project stakeholders and routes discovery gaps to the owning domain lens; an interview-script export groups open gaps by owner.
- `/sync --digest` metabolizes unstructured interactions (meeting notes, mail/Slack transcripts) into per-channel change events without inventing scope.
- `/export --format interview|faq` produces an interview script (open gaps grouped by owner) and an FAQ export derived from governed artifacts.
- `/backlog --story-format user|job` (and a `story_format` config option) emits JTBD job stories when the input gives no persona, without inventing one; user stories remain the default and the acceptance criteria, slicing, and traceability are unchanged.
- Discovery entry-edge skills: intake triage for unstructured initial requests, brownfield harvest for cited technical context from an existing codebase, and synthetic handoff datasets (disposable sample data, never governed or cited).
- `/doctor` now self-audits the framework's own agentic surface: `agentic_surface_audit` checks committed hook/settings config against a shell denylist, and `skill_invocation_checks` verifies human-only skill invocation flags stay consistent across the Claude/Codex/Kilo mirrors.
- Skill-authoring checklist (`user_guide/references/skill-authoring-checklist.md`) documenting leading-words, split-by-sequence, and human-only invocation guidance.

### Changed
- Backlog privacy scan is now configurable through `privacy_scan.mode` (`off`, `warn`, `block`) and defaults to non-blocking `warn`; `block` preserves the previous hard gate as opt-in.
- Governed artifacts (`project-brief.md`, specs, backlog) are protected from out-of-band hand edits across every surface — Claude (PreToolUse deny), Codex (hook), and Kilo (write deny) — so changes flow only through the owning command.
- Backlog execution-contract retrieval is now deterministic: critical surfaces and commands are selected by pure relevance instead of wall-clock recency, eliminating nondeterministic ordering in cold runs.

## [0.1.0] — 2026-06-14

First consolidated release of the governed requirement-maturation lifecycle (Discovery → Specs → Backlog), local-first and fully reconstructible from versionable workspace files.

### Discovery → Brief
- Inquisitive, lens-based gap detection with an externalized lens registry (`sentinel/lenses/`).
- Sanctioned agentic channels validated against verbatim citations: `/annotate` (semantic gaps) and `/challenge` (pre-mortem + per-lens role-play).
- EARS normalization of confirmed functional answers into testable `REQ-EARS-*` statements.
- Evidence-compiled project brief with per-section readiness and maturation telemetry; reopened-gap tracking on `/sync`.

### Specs
- `/specs` emits a human PRD, a compact spec index, and bounded `SPEC-U-*` units derived from confirmed evidence.
- `/compose` merges cited agent-authored PRD narrative (`Origin: agent`); unsupported citations rejected.
- Unit-level deltas and stale-unit propagation on regeneration.

### Backlog — Horizon 8 (governed backlog)
- Stories derived from confirmed Spec Units instead of a fixed seed list; `[PENDING INPUT]` stubs instead of invented scope.
- Externalized slicing model (`sentinel/slicing/`) preserving INVEST ("small but valuable"), vertical slicing, SPIDR and Lawrence, with one explained pattern per story.
- Bounded cross-cutting enabler epic (`EPIC-002`) with strict acceptance.
- Per-story progressive-disclosure context (`per_story.US-NNN`) with `read_plan` anchors propagated into story execution signals.
- `SLICE-PLAN.md` + `slice_plan.json` deterministic handoff with a pre-handoff DoR gate (soft by default, strict opt-in); optional `--with-task-seeds` that never execute, estimate, assign, or schedule.
- Governed story lifecycle and BA rollup board: `/story-status`, `/backlog-status`.
- `/quality` INVEST/SPIDR/Lawrence scoring with a dynamic `backlog_readiness_audit.md` feeding DoR warnings.
- Agentic `/refine-backlog` (cited proposals) and downstream `/implementation-feedback` loop (`GAP-FEEDBACK-*`, DoD gating).
- Backlog answer-key evals; deterministic local privacy scan over `04_backlog/`.

### Memory & platform
- Layered local retrieval: optional semantic embeddings and LanceDB hybrid (vector + FTS + reciprocal rank fusion), with a first-class deterministic `json-hybrid` fallback.
- Heading-aware chunking with `section_path` and line anchors; incremental reindex by `source_hash` / `embedding_version` / `chunking_version`.
- Single command manifest drives Kilo / Claude / Codex / MCP adapters and skill mirrors; local stdio MCP server.
- `verify.ps1` runs the unit suite, `/doctor`, and the eval harness (discovery, brief, PRD, specs, backlog, retrieval).
