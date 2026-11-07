# Changelog

All notable changes to Ignite Sentinel vNext are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Prompt-injection hygiene (IMP-286): source content is data, never instructions. `/ingest` and `/sync` flag instruction-shaped passages (override, role impersonation, command execution, exfiltration, governance tampering; English and Spanish) as findings with `origin: injection_signal` in `01_discovery/injection_signals.md` (`INJ-NNN`, source, line, excerpt). The flagged lines are blanked from the text the compilers analyze, so an embedded order cannot steer gaps, units or downstream artifacts. The workspace raw copy keeps them and the BA reviews them. AGENTS.md, CLAUDE.md, the MCP server instructions, the Kilo agents and the source-reading skills now declare the rule.
- Secrets and sensitive data at ingestion (IMP-285): `/ingest` and `/sync` detect private keys, cloud keys, JWTs, tokens, credentials in URLs and connection strings (`sentinel/secrets_scan.py`). The user's original file is only read. The workspace copy and everything extracted from it carry `<SECRETO:type>` instead, and each redaction is logged in `01_discovery/secret_alerts.md` with type, line and a SHA-256 fingerprint, never the value. False positives are allowlisted by fingerprint in `secrets_allowlist.txt`. Memory redacts every text it indexes, and `/view` and exports refuse to write an output that carries a secret or a reference to another workspace. Personal data is reported only, opt-in with `pii_report: true` (`01_discovery/pii_report.md`). `/doctor` adds `tracked_secrets_check` (scans `git ls-files`) and `workspaces_ignored_check` (new workspaces must be ignored; a deliberately versioned workspace is a WARN, see IMP-212).
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
