# Changelog

All notable changes to Ignite Sentinel vNext are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.38.0] — 2026-11-26

### Added

- **`/quality PROJECT_ID --change CHG-NNN` and the `quality` step of `/next --change` (IMP-431, H27 inc 8a).** The stories of a change have their own quality audit: test cases and the readiness audit in `05_quality/CHG-nnn/` (in the change's language, over every derived release of a series), a verdict kept in the change's record (never the project's phase or health), current until a story of the change is edited. `/next --change` asks for it between the backlog and the validation, and asks again after an edit; `/status --change` shows the verdict.
- **`/specs|/backlog PROJECT_ID --change CHG-NNN --release rN` and `/split --change --close|--move` (IMP-429, H27 inc 7d).** The confirmed series of a change is derived release by release: `rN` gets the `SPEC-U` units it owns (same ids) in `03_specs/CHG-nnn/rN/` and its stories in `04_backlog/CHG-nnn/rN/` (canonical `US-nnn.md`; `EPIC-CHG-nnn` lists every derived release). A unit owned by two releases or by none stops the derivation before anything is written. `--close rN` needs the stories Done and turns what `rN` delivered into preserved behavior ("entregado en rN") of the later releases; `--move` moves a unit inside the series, never touching a closed release, and the derivations it makes old are asked for again. `/validate --change` reports a stale series and a unit with two owners or none, and a confirmed series follows the text of its change (`refresh_series_if_stale`).

### Changed

- `/quality` of the project audits only the stories no change wrote; in a workspace that only holds changes it refuses and names `/quality P --change CHG-001`.
- `/next --change` walks the series: `specs`, `backlog` and `done` name the release (`--release rN`, then `--close rN`), one open release after another, and never ask twice for what is done.

### Fixed

- `/maturity` in a workspace that only holds changes refuses without writing a BLOCKED report or marking the project DIRTY (IMP-431).
- T2-D2 (second part): what a release of a change delivered is preserved behavior of the next ones, not new units built again.

## [0.37.0] — 2026-11-26

### Added

- **`/split PROJECT_ID --change CHG-NNN --assess|--propose|--confirm` and `/view|/export --change --artifact release-guide` (IMP-427, H27 inc 7c).** A change too big for one release is split inside the change: the assessment, the proposal and the confirmation read the brief of the change (no project brief needed) and write under it (`01_discovery/CHG-nnn/split_assessment.*`, `02_requirements/CHG-nnn/series/`, `02_requirements/CHG-nnn/rN/project-brief.md`), with the series guide in the change's language and `GAP-SPLIT-CLIENT` in the change's gaps. `--close`, `--move` and `--release` with `--change` are refused until the sub-releases of a change are derived. `/split` of the project does not change.

### Changed

- The escalation notice of a change offers `/split P --change CHG --propose`, or keeping it as one change, instead of moving to the project path.

### Fixed

- T2-D2 (first part): a change that is too big can be split into releases without a project brief.

## [0.36.0] — 2026-11-26

### Added

- **`/setup --semantic-memory`, `--offline-from DIR` and `--status` (IMP-425, H27 inc 7b).** Turns on semantic memory in one step: installs the pinned model `minishlab/potion-multilingual-128M` (revision pinned in `templates/semantic_models.json`), verifying every file's sha256 and size before activation, https only, hosts `huggingface.co` and `.hf.co` subdomains. `--offline-from` installs from a local folder with the same checks; `--status` verifies without network. It runs only when asked, by the person or by their agent at their request in chat; it is never automatic and not an MCP tool. The guide, admin guide, `sentinel-health` and `sentinel-command-router` say so, in the same words: Sentinel never downloads, except `/setup --semantic-memory`.

### Changed

- `/doctor` and its recommendation name `/setup --semantic-memory`; `network_import_violations` allows only `setup_download.py`. The verified model path is used after the environment variables: both `SENTINEL_MODEL2VEC_MODEL` and `SENTINEL_SENTENCE_TRANSFORMERS_MODEL` override it, and `semantic.json` counts only when it names the manifest's pinned model and revision (otherwise it is ignored and `/doctor` warns).

### Fixed

- `/setup --semantic-memory` final review (IMP-425): works from the `.pyz` (the downloader is extracted to a private temporary folder), reindexes each workspace under its IMP-299 lock (a busy one is skipped with a warning naming `sentinel /reindex ID --full`), activates atomically (the previous install is set aside and restored on any failure; staging is always cleaned), stops downloading past the manifest size, validates manifest names, checks `--offline-from` size first and hashes in a stream, exits 1 on `--status` mismatch and names the pip command for the install kind.
- T2-D4 and T2-18: a missing semantic model no longer leaves the user without a way to install it.

## [0.35.0] — 2026-11-26

### Added

- **Derived sources, partial baselines and the deliverables of a change's prototype (IMP-423, H27 inc 7a).** `/sources --load FILE --role diseno_nuevo --change CHG-nnn --derived-from F-NN` loads a readable render or transcript of a prototype with no visible text as a derived source: citations verify word for word against it, and `crosses.md` and the brief of the change show `(derived from F-NN)`. `/sources --load FILE --role linea_de_base --reliability documental|codigo|mixta` declares how complete the baseline is: against a partial one a NOT FOUND reads "not found in a partial baseline: confirm" and is asked once. `/prototype PROJECT_ID --change CHG-nnn --inventory|--manual|--trace` works the prototype of one change (files under `02_requirements/CHG-nnn/prototype/`), and `/view PROJECT_ID --change CHG-nnn --artifact diagrams|prototype|prototype-manual|prototype-trace` shows it (`CHG-nnn-diagrams.html`: the to-be with the as-is, a component's status only from the notation of section 5.1, else `sin dato registrado`). Skills, commands and the guide say so, and the flow matrix rows D and F no longer promise inc 7.

### Changed

- The new-surface candidates of a change are deduplicated: the same absence read in two harvests is one candidate (the first is kept), a decision already taken is not offered again, and the id of the dropped duplicate resolves to the kept candidate in `/cross --accept-new` and `--decline-new`.

### Fixed

- T2-12 and casuistry D: a prototype the extraction cannot read no longer ends in a cross against nothing, and a baseline that is only documentation no longer asserts absences.

## [0.34.0] — 2026-11-25

### Added

- **Cross-reads and element-by-element extraction on the project request (IMP-420, H27 inc 6b).** `/extract PROJECT_ID` and `/cross PROJECT_ID` work without `--change` on the request of the project when it writes rules, criteria, stories or decisions with an id (RN-, CA-, HU-, PD-; a section titled Acceptance criteria or a loose "Regla 3" does not count), the project has no specs yet and its brief is v2 (a project already at specs, backlog or quality, or on the brief v1, keeps its step unless an inventory or a cross-read exists): casuistry B of the forensic report, a mature brief for a new project. The files are `02_requirements/extraction/` and `01_discovery/crosses/`; every statement is ADDED, with no `Superficie` check and no `Afecta`. `/next PROJECT_ID` gains six steps after `resolve_blocking`, offered with or without a compiled brief and only when the request has ids or an inventory or a cross-read exists: `crosses`, `extract_inventory`, `extract_proposals`, `extract_confirm`, `extract_orphans` and `extract_verify`. A request without ids sees no new step, file or brief change.

### Changed

- The rows confirmed in the extraction of the project enter the EARS table of `02_requirements/requirements.md` with `EXT:<element>` and the global numbering (a retired row goes to `extraction/retired_ears.md`, so no id is reused); the brief v2 of the project transcribes the confirmed sections and rows, lists the discarded elements under 6.2 as "Fuera del alcance" ("Out of scope") and is asked to be compiled again when the extraction changed after it; the questions of the project cross-reads go to `01_discovery/gaps.md` with their exact id. A project without ids does not change.

### Fixed

- Final review of IMP-420 (6b): the offer counts only ids written in the request, not the synthetic elements of an itemized heading nor loose mentions; it no longer sends a project past the brief (specs, backlog, quality) into crosses and extraction, nor a brief v1 project, which the extraction never reaches; `run_cross` and `run_extract` without change apply the same guard as the CLI; the MCP tools list `change` as optional for extract and cross; the project extraction flags read only the project's harvests; a later topic merge never folds a question into an exact cross gap.
- Casuistry B: a mature brief of a new project is no longer reduced to mentions ("mentioned is not resolved"): each rule, criterion, story and decision is extracted with a literal quote and counted in the coverage before the brief transcribes it.

## [0.33.0] — 2026-11-25

### Added

- **A new source in the middle of a change: `/sync --change`, re-cross of what it touched and adversarial review of the change (IMP-418, H27 inc 6a).** `/sync PROJECT_ID --change CHG-nnn --source PATH --role ROLE [--supersedes F-NN]` loads the new document of a change by role, detects whether it is a new version (same path, or same role and file name) and confirms it only with the BA's `--supersedes`; without `--source` it scans the shared role folders for files not yet registered (it skips those of another change). `01_discovery/CHG-nnn/sync_report.md` says what was carried and what to read again, with the commands. `/cross --delta` records only the touched claims; the others keep their questions and answers. `--change` on `/challenge`, `/scrutinize` and `/annotate` reviews the request, the brief and the gaps of the change, opens its questions in `01_discovery/CHG-nnn/gaps.md` and writes `challenge_report.md`, `scrutiny_report.md` and `agent_annotation_log.md` under `01_discovery/CHG-nnn/` (the probe and anchors modes refuse with `--change`).

### Changed

- Confirming a version with `/sources --superseded-by` (or `--current`) on a row of a change re-crosses only what it touched: the claims whose quote stays literal are carried with their gap and their answer. `/next --change`, the verdict and `/status --change` show a new version nobody confirmed once (a warning, never a blocker). A baseline loaded after the harvest asks for `/harvest --change` again. In a workspace that only has changes, `/challenge`, `/scrutinize` and `/annotate` without `--change` refuse naming `--change`.

### Fixed

- Final review of IMP-418: a request edited in place and confirmed as a new version re-crosses its new elements (the previous text is gone, so every element counts as new); the refusals of `/scrutinize --change` (probe, anchors), `/cross --delta` and the project form in a change-only workspace follow the language of the change; `/sync --change --supersedes` with the content already loaded says nothing new; a design claim is no longer carried onto another change's prototype; the cross report lists the answered questions of replaced claims as replaced, not withdrawn; `/status --change` no longer repeats the unconfirmed-version note in its `warnings`.
- T2-22 and casuistry G of the forensic report: the cross-read and harvest files sent again are no longer left as "candidate new version, not confirmed", and a new version of the request no longer forces crossing everything again.

## [0.32.0] — 2026-11-25

### Added

- **The change specification by functionality and the change backlog by slices (IMP-416, H27 inc 5b).** `03_specs/CHG-nnn/specs.md` has one `FUN-nn` section per functionality with eight blocks of registered data only (`sin dato registrado` when there is none) and a traceability table Unidad / REQ-EARS / Elemento / Cita / Superficie / GAP; the units of the change cite `ruta:Lnn-Lmm` and their headings follow the language of the change. `story_size.max_units` (5) in the slicing model; enablers for the new surfaces of the change; `04_backlog/CHG-nnn/SLICE-PLAN.md`; `source_units` in the stories of the change. The skills `sentinel-specs` (with the validated `change-functionality` example) and `sentinel-backlog`, and the guide, describe it.

### Changed

- `/backlog --change` builds vertical slices by functionality and delta, starts SPIDR above 5 units and no longer generates one story per unit; INVEST Small measures a story of the change by its units; a specs report of 0.31 is read as `old` and `/next --change` asks to regenerate specs and backlog.

### Fixed

- `/backlog --change` at scale (T2-38: one retrieval per story, not per unit); the specs of the change with origin and line citation (T2-34, T2-35), grouped (T2-36) and in the language of the change (T2-37); the command `specs.md` no longer says that `prd.md` is not written.
- `/backlog --change` after the final review of IMP-416: an enabler of a new surface is judged INVEST Small by its own rule, not by the units of the stories it enables; a regroup (0.31 upgrade, or a slice crossing the size limit) never deletes a change story that is `In Progress`, `In Review`, `Blocked` or `Done` (it keeps its id and units, only the rest regroup); with `backlog_gate.strict` the command refuses before writing anything; a REMOVED unit with no `Afecta` keeps its story (only the units that retire not-implemented stories are dropped, per unit); the Objetivo of the change specs cites the lines and GAP decisions of the consolidated text it quotes; the English change document and the slice plan of a change use the change language, a new surface has no as-is facts of other screens, and an enabler no longer borrows the requirements of the first story it enables.

## [0.31.0] — 2026-11-25

### Added

- **The consolidated final brief and the change PRD (IMP-414, H27 inc 5a).** `/extract --change --consolidate PATH`, `--confirm-replacement ID` (with `--delegated`) and `--keep-text ID --gap GAP --reason`; the internal table `01_discovery/CHG-nnn/consolidation_control.md|json`; the step `consolidate` in `/next --change` and `consolidation` in `/status --change`; the annex `A.decisions` "Registro de decisiones"; and `03_specs/CHG-nnn/prd.md` in `/specs --change`.

### Changed

- `/export --change --final` delivers the consolidated text (decisions applied with the GAP reference, the literal text of the requirements without EARS rows, what was discarded only in 6.2 "No entra", the v2 structure of the request respected) and is refused while an element is not consolidated; the working export does not change.

### Fixed

- Answering a `GAP-CHQ` the other way round leaves a single winner; a `GAP-CHQ` whose pair no longer clashes is retired, also after validating an assumption or accepting an earlier decision (M2 of inc 4); the final brief no longer mixes the original request with the decisions (T2-30 to T2-33, T2-39).
- Consolidation (IMP-414 final review): a replacement sentence that is a cut of the element or of an answer no longer skips the number and negation guards; an added `no` is refused too; the element id is not a source of numbers; a replacement whose decision was re-answered goes back to pending (and the final export is refused until it is confirmed again); a retired `GAP-CHQ` reopens when the same pair clashes again; the change PRD shows `sin dato registrado` instead of the project placeholders (ASM-01/02, static traceability rows, gap ids not in the change); running the same consolidation file twice leaves `consolidation.json` untouched; the guide no longer teaches `--keep-text` for an option that already keeps the request.

## [0.30.0] — 2026-11-24

### Added

- **The BA delegates and reviews (IMP-412, H27 inc 4).** `/assume --change` and `--id --validate|--invalidate --reason`; the answer `Estado de decisión: supuesto` with `Valida:` (`gap_counts["assumed"]`); `--delegated`/`--note` in `/extract` and `Confirmado por:` in the answers; `Tipo: aplica|extension` and `Decisión:` in the proposals; `a_confirmar` marks; `GAP-CHQ-*` questions when two decisions clash; `/export --artifact borde|decisiones --change`, `--format faq --change` and `/view --change` of those views; `/sources --change --keep-single --reason`.

### Changed

- The several-processes warning uses a threshold relative to the size of the request (a single integration no longer warns); `/assume` without `--source` answers with an input error (exit 3); `/extract --reason` also goes with `--confirm-item`.

### Fixed

- Final review of H27 inc 4: a rerun of an answer file never closes again an assumption the BA invalidated nor downgrades one they validated (C1, I1); a `supuesto` needs a quoted literal of at least 4 words that is not in an answer file the runtime saved (I2, I3), and `/assume --change` cannot close `GAP-SCOPE` (M6); `--keep-single` covers only the size the BA saw (I4) and refuses `--no-baseline` (M7); `decisiones` shows who decided and the delegation even without `Owner / fuente` (I5); a delegated question is ratified by answering again and is not listed once reopened (I6); a `GAP-CHQ` answered with `Opción: A|B` replaces the losing decision, which stops being a fact in the brief, the export and `decisiones` (I7); a question closed as assumed is no longer printed as a fact in the brief or the export (P1); the "a confirmar" mark follows the request on existing EARS rows (P2) and shows in the border view (P3) and in confirmed sections (M5); contradiction letters are not compared across questions (M1).
- The assumptions of a change are no longer closed as confirmed by dodging the detector (T2-14, T2-15); a clash between decisions is no longer resolved by the agent (T2-26); the speculative marks of the request are no longer taken as firm (T2-28); the escalation warning stops repeating once the BA decided (T2-05).

## [0.29.0] — 2026-11-24

### Added

- **Decisions not asked twice and coherence of the change (IMP-410, H27 inc 3).** The decisions of a change in the memory (`change_decision`, `change_border`, `change_cross`, `change_cross_report`, `change_coherence`); `PRE_DECIDED` questions with the earlier answer loaded and `/gaps --change --id --accept-prior`; divergences already requested from Design shown with their `PD-nn`; lens coherence of the change with `/self-review --crosses --change` and the `coherence` step of `/next --change`.

### Changed

- A question is `PRE_DECIDED` only when the earlier decision covers it (same quoted statement, or same rule/criterion/story, never a mere shared line); `critical` ones keep blocking; `--accept-prior` only on those direct links, with the live answer and the option; a reopened or re-answered earlier decision updates its dependents (`prior_reopened`, `prior_changed`); a `PRE_DECIDED` section sent back untouched stays pending; `/status`, `/next` and the verdict no longer render the lens view of the change when its inputs did not move; the decision documents take the lens of the question as their memory domain.
- `/self-review` without `--source` answers with an input error (exit 3); the change verdict adds the `coherence` gate; a workspace with its cross-reads done goes back to the `coherence` step before the extraction.

### Fixed

- Sentinel no longer asks again a contradiction that a divergence already decided (T2-19); the design cross-read recognizes the requests to Design that the request already holds (T2-13); `gaps.md`, the cross-reads, `crosses.md` and the border can be searched with `/retrieve` (T2-17).

## [0.28.0] — 2026-11-24

### Added

- **The agent works alone (IMP-408, H27 inc 2).** `Opción:` field in the answers (`Option:` in English); `Redactado por:` and who decides in the report (`owners`); the skill of the next step in `/next`, `/status`, `/ingest --change`, `/resolve-gaps --change` and in the `next step:` line; real formats in the skills, tested against the parsers; entry skill in `sentinel-intake-triage`; flow × step matrix (`user_guide/22-flow-step-matrix.md`); `tools/trial_audit.py`.

### Changed

- A confirmed answer that names several options, in its text or in the `Opción:` field (`A y B`), does not close (T2-09); a project gap whose question carries `(A)`/`(B)` marks now shows `_(option X)_` in its resolution row and stores `option` (project path, additive); the request of `/ingest --change` is stored in `00_raw/09_request/` (T2-02); the findings of `/resolve-gaps --change` come out in the language of the change.

### Fixed

- `GAP-VER` when the request cites an earlier version of itself offers option (D) or does not open (T2-01); the misplaced border and the word that marks a file as not validated are named in the refusal (T2-03, T2-04); a new run of the same answers file no longer stays as a "possible new version" (T2-22).

## [0.27.0] — 2026-11-24

### Added

- **Reliable change brief (IMP-406, H27 inc 1).** Fine inventory (`SEC-x.pN` parts with a range of lines); coverage by lines with `Líneas:` and `Lectura: parcial`; reading plan in batches; `/extract --verify` and `--verify-result`; change verdict in `/status --change`; `/gaps --change --id --impact construccion|operativo`; change export in brief v2 format with a seal; `export_final` step.

### Changed

- IMP-406 final review: an element that starts with its id and one very long line are split into parts too (a quote and a line range now measure a reading); parts keep their id while their text does not change; a reopened `difiere` is confirmed again only with a corrected proposal; `/next` adds `extract_verify` for extractions of more than 100 elements and the default sample is 5 % of the confirmed (at least 10); `/export --change --final` refuses while the change verdict is `NOT_READY` or the v2 text has pending marks, and `/next` points to `/gaps --impact`; the final export goes stale when the seal inputs change; the change verdict is `NOT_READY` while its brief is stale or it has no requirement rows; items confirmed without a line check are listed as `legacy_confirmed` and keep the verdict from `READY`.
- `Líneas:` is required on every proposal (the unconfirmed proposals of 0.26 are proposed again); a section is confirmed with its literal text and the brief shows it (`Texto:` becomes `Resumen:`); `--confirm-item` does not take a partial reading.

### Fixed

- Registering a cross-read again closes the questions of the claims that disappear (T2-16); a workspace that only has changes no longer stays `health: DIRTY` forever and `/status --change` says why it is dirty (T2-30).

## [0.26.0] — 2026-11-23

### Added

- **`/cross --change` (IMP-404).** Cross-reads of the request against the new design and against itself, with a verbatim quote validated by role; divergences and contradictions open blocking questions; what has no support flags its element of the extraction; candidates for a `nuevo` surface from the `NO ENCONTRADO` of the change's harvest (`--accept-new`, `--decline-new`); a `crosses` block in `/status --change` and a "Cruces" line in the brief. A cross-read with nothing found is one `[SIN HALLAZGOS]` claim; `--skip` also waives a stale cross-read; a cross-read goes stale when a request or prototype is added after it; `--accept-new` also takes a `GAP-SED-…` question ("only in the design"); a claim line that does not follow the format is an error, not ignored; quotes accept `«…»` and inner `"`, and HTML prototypes match inline tags and attribute text (`placeholder`, `title`, ...); with no prototype the design cross-read does not apply.

### Changed

- **`/next --change` (IMP-404).** It asks for the three cross-reads (or their waiver) and for the new surfaces before the request is inventoried; `/harvest --change` is recorded as the cross-read with the baseline; `/export --final` with a pending extraction sends the BA to `/extract`; what is preserved with no elements or questions sends the BA to load a note with the role `pedido`.

## [0.25.0] — 2026-11-23

### Added

- **`/extract --change` (IMP-402).** Inventory of the request element by element, proposals with a verbatim citation, confirmation by section except what is flagged, EARS rows with Delta and Superficie per statement, the sections of the brief filled, coverage in `/status`, `/next` and the brief, and what is preserved covered with an UNCHANGED row.

### Changed

- **`/next --change` (IMP-402).** It replaces `pending_extraction` with the extraction steps (`extract_inventory`, `extract_proposals`, `extract_confirm`, `preserved`), and `done` requires full coverage and what is preserved covered; the `requirements` step no longer depends on an open question.
- **Extraction review fixes (IMP-402).** The inventory keeps indented lines inside their list item, takes id-led paragraphs, treats several `#` headings as sections and splits the criteria inside a story heading. New steps `extract_unreadable` (a request file Sentinel cannot read never counts as covered), `extract_orphans` (an element that left the request but keeps EARS rows, taken out with `--reject-item`) and a `--confirm-item` step when only flagged proposals are left. A re-submitted proposal identical to its confirmed version stays confirmed (`unchanged`). The change lens round takes an itemized acceptance-criteria heading or CA-/AC- ids as the acceptance signal. The workspace-only verdict no longer warns that coverage is not measured.

## [0.24.0] — 2026-11-22

### Added

- **Sources by role in a change (IMP-400).** `/sources PROJECT_ID --load PATH --role pedido|linea_de_base|plan_previo|diseno_nuevo [--change CHG-NNN]` registers a document with the role it plays (folders `00_raw/06_baseline`, `07_prior_plan`, `08_new_design`, `09_request`); `--id F-NN --role ROLE` corrects a role and `--change CHG-NNN --no-baseline --reason TEXT` waives the baseline. The MCP tool `sentinel_sources` takes `load`, `role`, `change` and `no_baseline`.
  - A request that cites a document by name or sha while another version of it is loaded opens a blocking `GAP-VER-xxxxxx` in the change (one per citation). A cited document that was never loaded is only a warning of `/status --change`.
  - `/status --change` shows the sources by role; `/next --change` has a `baseline` step between the scope and the lenses.

### Changed

- **`by_baseline` needs a registered baseline (IMP-400).** A question closes `by_baseline` only when the quote is in a current source registered as `linea_de_base`; a hand copy in `00_raw/`, the harvest, a prior plan, the design of what is new or a replaced source is rejected, and the message names the cause and how to register it. The example of the change guide cites `00_raw/06_baseline/sad-compras.md`. Scenario 11, the workflows, the command reference and the skills now load the documents with `--load`. The project path is unchanged.
  - A change created with 0.23.0 whose baseline was copied into `00_raw/` by hand and never registered now shows the "Registrar la línea de base" (`baseline`) step in `/next --change`. Remedy: `/sources PROJECT_ID --load <that path> --role linea_de_base --change CHG-NNN` (registers it in place) or `/sources PROJECT_ID --change CHG-NNN --no-baseline --reason TEXT`.

## [0.23.0] — 2026-11-22

### Fixed

- **Honest signals on the change path, and spot defects (IMP-398).** The change path stops promising what Sentinel does not measure.
  - The brief of a change no longer says "the change note covers it". A topic the request covers and the brief does not hold shows `⏳ PENDING EXTRACTION` (`⏳ PENDIENTE DE EXTRACCIÓN`), a deferred mark. `/export --final` refuses while any exists and the draft banner and `extraction_pending` list the sections.
  - `/next` for a change gets a `pending_extraction` step before `done`. The text of `done` says that coverage of the request is not measured; the texts of `lenses` and `requirements` no longer send the BA to `gaps.md` or to a gap that does not exist.
  - A mature request cannot produce a final change-brief export until the extraction increment: the `⏳ PENDING EXTRACTION` mark clears only when a question of that section is answered, and a change with no such open question stays at its step (`requirements` or `pending_extraction`) with `--final` refused; the BA checks the request by hand. In a draft export `pending_marks` stays the blocking count, extraction sections are reported apart (`extraction_pending`), and the change-only verdict's `gaps` gate is `NOT_APPLICABLE` (non-blocking).
  - The verdict of a workspace that only has changes lists each change's blockers and never "Discovery has not run". When every change is done it is `READY_WITH_WARNINGS`, with a request-coverage warning.
  - A divergence closed by the baseline shows the answer and "Baseline support: «quote»" in the change brief. The harvest's B1 facts go to §1 and B5 to §5 (technical). In a change harvest, the divergence description and question speak the change's language and offer "build or fix it in this change"; harvests of the project keep their wording.
  - `/gaps --change` guide explains that answers go in a separate file, processed with `/resolve-gaps --change`.
  - Deliberate changes that also reach the project path:
    1. Injection detection (`sentinel/injection.py`): Spanish phrases such as "omite reglas vigentes" are no longer flagged; post-nominal instruction phrases ("las instrucciones del sistema") and usted/ustedes imperatives are now flagged. It is an advisory signal and may flag some narrative text.
    2. `/doctor` install hints for a missing runtime dependency use the interpreter that is running (`& "<python>" -m pip install ...` on Windows, `"<python>" -m pip install ...` elsewhere), not a bare `python`.
    3. The `/export --final` refusal wording says "deferred marks" instead of "deferred domain marks" (it now also counts the pending-extraction marks of a change).

### Added

- **Optional alias for a border surface (IMP-398).** A border line may be `zone | type | name | alias` (up to 40 characters, no `;` or `|`, no accents, unique in the border). `Superficie` accepts the name or the alias and always stores the canonical name. Scenario 11 (the request that already says everything, and the new marks and steps), the command reference, the router and the harvest skill cover it; the harvest skill now also covers verifying a request or brief against what is built inside a change.

## [0.22.0] — 2026-11-22

### Added

- **Changes to an existing system, increment 5 (IMP-396).** A change is validated against its border, warns when it may be too big, and has its own next step.
  - Every confirmed EARS answer of a change except `GAP-SCOPE` carries `- Superficie: <border name>[; <name>]` (`Surface` in English files). The runtime proposes candidates and validates each name against the border (`surface_findings`); the BA decides. The surfaces travel into the requirement rows, the units and the stories.
  - Escalation warnings (`several_processes`, `new_actors`, `third_party_contract`) are computed on the fly from the border and the rows. They never block: the BA decides whether to split the change or move to the project path. They show in `/next`, `/status` and `/validate --change`.
  - `/validate PROJECT --change CHG-nnn` runs four checks (`unit_citations`, `preserved_pass_to_pass`, `rows_have_surfaces`, `stories_inside_border`), each of which can `SKIP`, and gives `VALID` or `INVALID` (exit 5). A plain `/validate` in a workspace that only has changes exits 4 and names the change.
  - `/next` and `/status` know about changes: a `changes` list when they exist, the first pending change in a change-only workspace, and `--change CHG-nnn` for one. The sequence is scope, lenses, brief, requirements, specs, backlog, validate, done; it never reaches the PRD, and `--change` with `--release` exits 3.
  - On the "save draft" fixture, the finished change validates `VALID`, `/next --change` answers `done` and there are no warnings; a border with a new `rol` raises `new_actors`. Scenario 11 (step 12 and an escalation example), the command reference and the skills cover it.

## [0.21.0] — 2026-11-22

### Added

- **Changes to an existing system, increment 4b (IMP-393).** A change gets its backlog, and what it affects in the backlog that already exists is traced.
  - `/backlog PROJECT --change CHG-nnn` writes the epic `04_backlog/EPIC-CHG-nnn.md` and one story per ADDED, MODIFIED or REMOVED unit (`change`, `source_unit` and `delta` in the frontmatter; trace CHG, SPEC-U, REQ-EARS), plus `08_context_packs/CHG-nnn/backlog_generation.json` and `backlog_report.json`. Each UNCHANGED row is a pass-to-pass criterion (`AC-NNN-06` onward) of every story. The gate is scoped to the change: no blocking gaps and specs current with the REQ-EARS rows (exit 4); `--change` with `--release` exits 3; a plain `/backlog` in a workspace that only has changes exits 4. The project's epic, stories and phase are not touched, and the project `/backlog` keeps the stories of changes.
  - The answer of a MODIFIED or REMOVED requirement names the stories it affects with `- Afecta: US-nnn | ninguna` (`Affects` / `none`), required when the workspace already has stories; candidates are proposed. Draft, Ready and Blocked stories become Stale; In Progress and In Review stay and get a warning; Done stories stay Done with `modificada_por`. The new story of a change over a Done or in-progress story is a change request (`type: change_request`, `modifica`, graph edge `modifies`). A REMOVED row over stories that are all not implemented makes no story.
  - Story ids stay stable once a workspace has changes. On the "save draft" fixture, `/backlog --change` gives 3 stories (`US-001` to `US-003`) under `EPIC-CHG-001`, each with one pass-to-pass criterion, no change request and nothing Stale. Scenario 11 (step 11 and a mixed-workspace variant) and the command reference cover it. The `next_step` of `/specs --change` now points to `/backlog --change`.

## [0.20.1] — 2026-11-22

### Fixed

- **A file that only mentions "borrador" or "draft" is no longer read as an unvalidated source (IMP-390).** A source counts as unvalidated only when it declares itself so: a validation-state phrase ("sin validar", "not yet validated"...), a heading, a metadata line (`Estado: borrador`, `status: draft`, frontmatter), a line that is only the mark (`BORRADOR`, `[DRAFT]`), or a self-declaration ("Este documento es un borrador"). A feature called "Guardar borrador" in the first lines no longer keeps `/resolve-gaps` answers from closing, and `/sync` no longer flags the note. A title mark in the first three lines (`BORRADOR - Requerimientos`, `Requerimientos (Borrador)`, `Borrador v0.2`), `Estado del documento:` style keys, a `| Estado | Borrador |` table row and wordings like "Esto es un primer borrador" also count, and a leading BOM no longer hides a heading or metadata line. The words and keys live in `source_routing.json`.

## [0.20.0] — 2026-11-21

### Added

- **Changes to an existing system, increment 4a (IMP-388).** A change gets its requirements and its specification units, without a PRD.
  - A gap answer of a change can declare `- Delta: ADDED | MODIFIED | REMOVED | UNCHANGED`. Only the BA fixes it (the runtime may propose one); an EARS answer of a change without a valid Delta does not close the gap. Confirmed EARS answers become `REQ-EARS-nnn` rows, with their Delta, in `02_requirements/CHG-nnn/requirements.md`, one per sentence.
  - `/specs PROJECT --change CHG-nnn` writes `03_specs/CHG-nnn/specs.md`, `units/` and `change_specs_report.json`: one `SPEC-U-nnn` per ADDED, MODIFIED or REMOVED requirement; UNCHANGED rows are listed as preserved behavior, not units. Unit ids come from a per-project registry, so a later change never reuses one. It writes no PRD and refuses without the change brief, with blocking gaps open, or with no ADDED/MODIFIED/REMOVED row.
  - On the "save draft" fixture, after the EARS answers: 0 blocking gaps, 3 units (all ADDED) and 1 preserved row. The skills and Scenario 11 (steps 9 and 10) of the user guide cover it. A response file that mentions "borrador" or "draft" in its first lines is still read as an unvalidated draft.
  - A change still has no backlog; it comes in a later increment.

## [0.19.0] — 2026-11-21

### Added

- **Changes to an existing system, increment 3 (IMP-386).** A change gets its own brief, which you can view and export.
  - `/brief PROJECT --change CHG-nnn` compiles `02_requirements/CHG-nnn/project-brief.md` and `change_brief_report.json`: nine sections (context and baseline, problem and result, border, as-is to to-be process, per lens, preserved behavior, rules and acceptance, blast radius and impact, pending). Every content line cites its origin. An open question is `⏳ PENDIENTE (GAP-X)` when it blocks and `⏳ PENDIENTE DOMINIO (GAP-X)` when it is deferred; nothing is invented. It takes no project setting (`--profile`, `--genesis`, `--validation-direction`, `--brief-version`: exit 3) and writes nothing of the project's.
  - `/view PROJECT --artifact brief|gaps --change CHG-nnn` writes `08_context_packs/views/CHG-nnn-*.html`. `/export PROJECT --artifact brief|gaps --change CHG-nnn [--format md|interview] [--final]` writes `08_context_packs/exports/CHG-nnn-*`; a draft carries a banner, and `--final` refuses while blocking marks remain.
  - A workspace that only has changes refuses `/brief`, `/view` and `/export` without `--change` and names the change to use. A project with its own requirement is unchanged, and the project path is byte-identical without the flag.
  - On the "save draft" fixture the brief has 9 sections and 3 blocking marks (objective, users, acceptance), all listed in section 9.
  - A change still has no specs and no backlog; they come in a later increment. The skills, manifest, MCP descriptions and Scenario 11 of the user guide cover the brief.

## [0.18.0] — 2026-11-21

### Added

- **Changes to an existing system, increment 2 (IMP-384).** A change can close gaps by citing the baseline, and the harvest reaches functional detail.
  - `Motivo de cierre: by_baseline` closes a change gap only when the answer is confirmed and cites a backticked `00_raw/` path plus a literal quote of 20 or more characters found in that file (whitespace collapsed, case kept). The cited file cannot be a change note. Otherwise the gap stays ANSWERED with a finding. Outside a change it never closes.
  - `/harvest PROJECT --source FILE` accepts `- doc: name — path` in B0, cites `name:file`, and adds blocks B6 screens, B7 flows and B8 rules and roles. With `--change CHG-nnn` its gaps (GAP-HRV-*) go to the change; a change-only workspace refuses it without the flag.
  - Measured on the "save draft" fixture with a synthetic Compras baseline: loading it and confirming seven `by_baseline` answers takes the lens round from 19 open gaps to 12 (20 total, 8 closed, 3 blocking still open). The project path stays at 27, unchanged.
  - The lens round now reads the change note plus only the answer text of each response file. Before, the answer-form labels ("Owner / fuente", "Evidencia o referencia") counted as evidence and suppressed checks: `GAP-DELIVERY-READINESS` and `GAP-QUALITY-HANDOFF` never appeared, so the lens round had 18 gaps instead of 20.
  - A change opened on 0.17.0 gains `GAP-DELIVERY-READINESS` and `GAP-QUALITY-HANDOFF` on its next `/gaps --change`.
  - The skills, manifest, MCP descriptions and Scenario 11 of the user guide cover both.

## [0.17.0] — 2026-11-19

### Added

- **Changes to an existing system, increment 1 (IMP-382).** A change or new feature on a system already in production has its own gap rounds, apart from the project's.
  - `/ingest PROJECT --source NOTE --change` opens a `CHG-nnn` with only the scope round. `/gaps PROJECT --change CHG-nnn` regenerates its gaps.
  - `/resolve-gaps PROJECT --source ANSWERS --change CHG-nnn` confirms a structured `Borde:` (one `zone | type | name` line per surface) under GAP-SCOPE and opens the lens round scoped to the border. One bad line rejects the whole file and writes nothing.
  - Measured on the "save draft" fixture: the scope round has 4 gaps (3 blocking); with a border of pantalla, endpoint, dato and proceso the lens round has 18 (17 open, 1 closed, 3 blocking); the plain project path has 27 (4 blocking) for the same note.
  - The project path is unchanged, and the MCP tools, manifest, skills and user guide cover `--change`.

## [0.16.1] — 2026-11-18

H25: Workflows and Scenarios are written for a BA/PM who talks to the assistant in chat.

### Changed

- **Chat-first Workflows and Scenarios (IMP-380, IMP-381).** Every step now starts with what to tell the assistant in plain language ("Tell the assistant: …"), then what you will see and what it means. The equivalent terminal commands, exact messages and technical details are in a collapsed "In a terminal" block under each step. Scenarios keep their story: the situation, the steps, and what you have at the end.

## [0.16.0] — 2026-11-18

H24: a guide any BA/PM can follow, and no dead ends on a real project. An audit of the user guide against the 0.15.0 code found 106 mismatches and a `/backlog` deadlock; live runs of every documented sequence found more. All are fixed, the README and the BA/PM pages are rewritten in plain language, and the diagrams are images that render everywhere.

### Fixed

- **No DIRTY dead ends (IMP-360, IMP-369).**
  - After a change on a project with a backlog, `/backlog` runs again once the brief and specs are regenerated, and health returns to CLEAN. Before, it was refused forever.
  - A change of meaning ("now", "instead", "out of scope") is cleared by regenerating, or recorded with the new `/trace PROJECT --reviewed CHG-NNN`.
  - Every command indexes the graph nodes it adds (`/story-status`, Done evidence, `/stakeholders --add`).
  - Moving one story forward no longer marks its siblings Stale.
  - `/next` and the `/backlog` refusal name the concrete commands, numbered, one per finding.
  - `/backlog` no longer runs on specs older than the brief.
  - `/resolve-gaps` with only unknown ids no longer marks downstream stale.
  - A refused command no longer leaves a false hand-edit warning.
  - Answers routed to brief places 7.1, 9.1 and the glossary are kept, so GAP-BRIEF-S7 and S9 stay closed.
- **CLI edges (IMP-361):**
  - `/sync --source` with a folder is refused cleanly instead of crashing.
  - The dashboard suggests `/sync` for a changed requirement.
  - The workspace `.gitignore` excludes `.series_work/` and release views.
  - Focus packs are named `*_focus.json`.
- **Implementation feedback and smaller fixes (IMP-367, IMP-370):**
  - Implementation feedback keeps its history, numbers ids across runs, resolves a gap by finding id, and recomputes health when nothing is open.
  - `/sync` detects new gaps only in the new source.
  - `/stakeholders --domain` takes lens names.
  - A synced file gets its authority from its drop folder.
  - Release-scoped `/next` hints keep `--release`.
  - `/refine-backlog` is idempotent.
  - Several EARS sentences in one answer each become a requirement.
  - `/view diagrams` without a brief is a gate with a next step.
  - The dashboard regenerate command keeps `--root`.
  - The theme shadow check ignores letter case.
- **The reference pages match the code (IMP-362, IMP-363):** the 106 audit findings are fixed across the command, artifact, memory, chat, install, adapter, plugin, admin, security and recovery pages, including correct offline install steps.

### Changed

- **Plain-language guide (IMP-365, IMP-366, IMP-368):**
  - README and Start here are written for a first-time BA/PM.
  - Workflows has 13 new situations, from moving on with assumptions to picking up a project after weeks.
  - Scenarios are re-run live and add "the client changes scope after the backlog" and "development finds a hole".
- **Diagrams are SVG images (IMP-364)** with their Mermaid source next to them, so they render on GitHub web and in the GitHub app. `tools/render_doc_diagrams.py` renders them offline with the vendored Mermaid; a test fails when an image is stale.
- `PORTABILITY.md` is updated to the current install paths.

## [0.15.0] — 2026-11-17

H23: closing what earlier horizons left open. A retired source leaves memory, every agent payload is redacted and shielded, instructions hidden in comments or encodings are caught, the deny hook covers the same files as hand-edit detection, the client gets a plain interview, the dashboard speaks the project's language, and each command writes the graph once.

### Added
- `/dashboard` renders in the project language (IMP-350, H23). It used to be Spanish whatever the project language. Each workspace's card, drawer, prompts, lifecycle, summary and modals follow that workspace's language (any `es*` tag is Spanish, anything else English); the page frame (header, filters, menu, legend, section titles, provenance) follows the language most workspaces use, English on a tie. The result carries `language`.
- `/validate` warns when a brief build item has no story (IMP-344, H23). A brief v2 with several in-scope items could produce fewer stories with no warning. A non-blocking `build_items_to_stories` check in `cross_artifact_consistency` names each `C-NN` no value story covers and says that only confirmed answers written in EARS become stories.

### Fixed
- A retired source stops feeding memory (IMP-341, H23). `/sources --retire` used to change only the row: `/retrieve` kept returning the file and `/reindex` indexed it again. Now its rows leave the LanceDB table and `memory.json` on retire (`memory_removed`), `/reindex` and `/ingest` skip it (`retired_skipped`), and `/retrieve`, context packs and the change timeline filter it out. The copy stays on disk; `--current` plus `/reindex` brings it back.
- Agent and BA payloads are redacted and shielded (IMP-342, IMP-347, H23). `/assume`, `/self-review`, gate overrides, `/compose`, `/refine-backlog`, `/implementation-feedback`, `/annotate`, `/challenge` and every mode of `/scrutinize` stored the payload verbatim, so a pasted password or key stayed in the workspace and an injected line reached `prd.md` and `gaps.md`. Now the archived copy is redacted (injection lines kept verbatim for the BA and listed in `injection_signals.md`), and what is written to artifacts, state, logs and memory is redacted with flagged lines shown as `<NEUTRALIZADO:type>`. Validation still runs on the payload as written, and `/compose` citations, which are re-validated on every regeneration, are stored redacted but not neutralized.
- Instructions hidden in HTML comments, encoded runs and look-alike text are detected (IMP-351, H23). A comment with the phrase split across lines, a base64, hex or percent-encoded override, and a zero-width or fullwidth "ignore" passed unflagged. Three new kinds (`html_comment`, `encoded`, `obfuscated`) flow through the existing shields; ordinary comments, data URIs, digests and accented text are not flagged. The brief view no longer embeds a raw fragment's injection lines verbatim. The threat model lists what is and is not detected.
- The deny hook covers `gaps.md` and `requirements.md`, from one list (IMP-343, IMP-348, H23). The hook refused agent edits to the brief, specs and backlog only, so an agent could write answers straight into `gaps.md`. Now one list in `sentinel/governed_artifacts.py` drives the hook, the `/health` hand-edit hashes and the Kilo check, and the refusal names the owning commands. Raw drops, answer files and payload JSON stay allowed. The new coverage is not yet observed live.
- Brief v2 gaps no longer move under the BA (IMP-344, H23). Brief marks fell back to a lens default gap routed to another place, so answering it opened a section umbrella that had not existed, and the 5.0 opening reopened `GAP-BRIEF-S5` on every compile. A mark now points at a gap routed to its own place or at the section umbrella from the first compile, and the umbrella question lists each place by number and title. A new project's question round now shows mostly umbrella gaps.
- The sweep protocol is named where it exists on every install (IMP-340, H23). A refused agent payload and the sweep log pointed to `sentinel/templates/agent_sweep_protocol.md`, which exists only in a clone; they now name the package's `templates/agent_sweep_protocol.md`. The health skill describes the IMP-332 hand-edit copies and the recomputed `DIRTY` verdict.
- H23 close (IMP-34z): a sweep of the guide and the skills against the H23 changes.

### Changed
- The interview export is the client-ready list of questions (IMP-344, IMP-349, H23). The guide said to send `gaps.md`, the working ledger. Now it says to send `/export --artifact gaps --format interview`, which no longer shows lens, severity or internal labels, groups questions by topic or owner, keeps each `### GAP-…` reference so answers come back through `/resolve-gaps` (tested end to end), replaces the generic keyword-probe lines with one natural follow-up, and has a catalogue question in English and Spanish for every lens check.
- One graph write and one memory broker per command (IMP-345, H23). The graph was saved once per node or edge (34 times in `/ingest`, 38 in `/backlog`) and `/specs` and `/backlog` built 9 to 14 brokers. Now each command writes the graph once, after its artifacts and even when it fails, and `/specs` and `/backlog` share one broker; `/backlog` went from 11.7 s to 7.8 s on the golden fixture.
- One copy of each diverged helper (IMP-346, H23). `normalize_lens`, `compact_links`, `workspace_relative` and the provenance section had copies that behaved differently. Each has one implementation: `n/a` or `-` is the product lens and `frontend`/`backend` are technical; empty link targets are dropped instead of shown as `None`; export paths no longer raise on Windows letter case; and the provenance section of the dashboard and every `/view` page follows the page language (Spanish pages now read "Fuente", "fecha de corte", "Regenerar") and is labelled for screen readers.

## [0.14.0] — 2026-11-17

H22: robustness, from an independent review whose findings were each reproduced before the fix. Memory keeps what it indexes, a lost or broken state file is refused with a way back, a hand edit is never lost without a word, MCP tools behave like the CLI, secrets and injected instructions stay out of memory, and a late change written in prose can be turned into a gap the BA decides on.

### Added
- `/sync` surfaces changes written in prose, without applying them (IMP-337, H22). A note that reversed confirmed scope ("The board decided: …") used to be stored and nothing else: no contradiction, no reopened gap, the brief unchanged, while the sync skill claimed closed gaps "are reopened".
  - **Every `/sync --source` result** carries a `prose_review`: how many lines were read as answers, as statements, stored without interpretation, and as decisions. Decision lines are caught in English and Spanish, also in the third person ("the board decided:", "se resolvió"), and each one lists the closed gaps and live assumptions it shares words with, as a hint that applies nothing.
  - **`/sync PROJECT_ID --source NOTE.md --analysis FILE`** takes the candidates an agent writes (`reopen_gap`, `invalidate_assumption` or `contradiction`, each with a quote from the note and one from the target). Both quotes are checked verbatim. One invalid candidate refuses the whole run with exit 3 and writes nothing, not even the note; each valid one opens a blocking `GAP-CHG-*`, which `/next` names as *Confirm a late change*.
  - **The BA decides** with `/gaps PROJECT_ID --id GAP-CHG-x --disposition accepted|rejected`. `accepted` reopens the gap (keeping the earlier closure on record) or invalidates the assumption, which reopens its gaps and marks what depends on it stale; an accepted contradiction points to `/sources --precedence`. `rejected` closes it as a false alarm.

### Fixed
- Memory keeps its vector table (IMP-330, H22). With lancedb 0.33 every command wiped the LanceDB table and recreated it, because `list_tables()` returns a response object and the name check was always false; retrieval silently fell back to a full scan of the JSON store. The table is now opened when it exists and created only when it is missing, an incremental `/reindex` restores rows the table lost, and the graph and `memory.json` are saved only when something changed (on a synthetic project: 29 `memory.json` writes instead of 41, half the files under `lance/`).
- A deleted or corrupted `state.json` is refused, with a backup to restore (IMP-331, H22). A deleted state used to be rebuilt silently as `CLEAN`, losing the brief settings, the language and the story lifecycle; a JSON file that did not parse failed with a bare `Expecting value: line 324…`. Now every state update first copies the state to `.sentinel/state.json.bak`; every project command checks the state before writing, and a missing state on a workspace in use is exit 3 with the restore step (a new workspace still initializes); a JSON file that does not parse is exit 3 with its path and the fix for that file. `/doctor` warns for each workspace whose state is missing or unreadable.
- A hand edit is never absorbed silently (IMP-332, H22). `/health` flagged a hand edit of the brief, a story or `gaps.md`, and the next command erased the warning and could overwrite the edit with no copy. Now the edited file is copied to `.sentinel/hand_edits/<timestamp>-<command>/` before the command runs; the warning stays while the edit is there, an overwritten edit is named on stderr, and `/health` keeps warning until the copy is deleted. A command that leaves health `CLEAN` while the last report said `DIRTY` re-runs the health check, so `/maturity` or `/specs` no longer clear `DIRTY` without fixing anything. The raw-file metric finding clears once the `GAP-METRIC-SOURCE*` gaps are closed.
- MCP tools forward every option the CLI accepts (IMP-333, H22). `sentinel_sources`, `sentinel_stakeholders` and `sentinel_split` dropped arguments, `sentinel_retrieve` defaulted to the discovery workflow, and gap elicitation assumed a Spanish project. Now every set value is forwarded and the CLI accepts or refuses it as in a terminal; elicitation reads the project language and defaults to English. Two silent ignores of the CLI are exit 3: `/stakeholders` fields without `--add`, and `/sources --precedence --between` combined with other options. The chat-commands page lists the renames and the two deliberate default differences (`split` assesses, `prototype` inventories).
- One count of pending marks (IMP-334, H22). On the same brief `/validate` reported 0 pending marks and `/export --final` 75 (it counted the legend and the tables). `/validate`, `/export --final` and `/maturity` now share one rule, which for a brief v2 equals its "Ready to build" count. **Domain marks (`⏳ PENDING DOMAIN`) no longer block `/export --final`**: only client marks do, and domain marks are listed as `deferred_marks`, matching the rest of Sentinel, where what waits for domain context does not block.
- Common credentials are redacted and the injection shield lasts (IMP-336, H22). The scanner caught 3 of 7 seeded secrets: `password = …`, `api_key: …` and Stripe keys reached context packs, memory and `/retrieve`. A new `credential` kind replaces only the value after a secret-like key (`password`, `pwd`, `secret`, `api_key`, `token`, `DB_PASSWORD`, quoted keys in JSON or YAML), and Stripe, `whsec_`, `npm_` and SendGrid tokens are detected; placeholders, prose and code are left alone. `/resolve-gaps` and `/harvest` now redact what they store. Lines flagged as injection at `/ingest` lost their shield on `/sync` and `/reindex`; they now stay out of memory and `/retrieve` (the raw copy keeps them for the BA), and an exfiltration line with a dotted file name is detected. The threat model lists what is and is not detected.
- H22 close (IMP-33z): a sweep of the guide and the skills against the H22 changes. A test fixture that combined IMP-331 and IMP-333 turned `main` red after both merged (#351); only the tests changed.

### Changed
- Docs and skills debt (IMP-335, H22). `AGENTS.md` and `CLAUDE.md` list every command and all 11 `/view` artifacts; skills name paths that exist in a plugin project; the context-request and `/self-review` pages state the real rules; the command reference's exit codes match the runtime. A new **Recovery** page (`user_guide/21-recovery.md`) covers a wrong file ingested, a wrong answer applied, a hand edit, a deleted or corrupted file and a refused command.
- Code debt, without changing behaviour except where noted (IMP-338, H22). The move from `generation.py` to `compilers/` is finished, the shared helpers live once in `sentinel/core/text.py`, the seven flat compatibility modules (`backlog_*.py`, `knowledge_ledger.py`, `knowledge_metabolism.py`) are deleted, and `discovery/workflow.py` (3,737 lines) is split into four modules plus a `sentinel/gaps/` package.
  - **Tables:** every table cell escapes `|` as `\|`, which reads back as `|`. Some writers used to replace it with `/`, so a story title or summary with a `|` now shows `\|`.
  - **File names:** picking a free file name stops after 999 candidates with exit 3; before, some writers could loop forever.

## [0.13.0] — 2026-11-16

### Fixed
- H21 close (IMP-32z): a sweep of the guide and the skills against the H21 changes. Nine places still loaded a later file with a second `/ingest` or described a harvest as replaced per run: the intake-triage skill, the skills catalog, the prototype scenario (now `/sync --source`), the workflows, the artifact reference, the versioning page and the prototype command page. The versioning page also no longer says the hook denies hand edits of `gaps.md` and `requirements.md` (it covers the brief, the top-level specs and the backlog), and the command router says a brief v2 that is not ready to build makes the verdict `NOT_READY`.
- `/harvest` accumulates blocks delivered one at a time (IMP-326, H21). The harvest skill said each block could be delivered separately, but `/harvest` refused a file without B0 and overwrote `01_discovery/harvest.json`, so a second run silently replaced the first, which the brief v2 reads. Now a later file may name the repos of an earlier B0, its blocks are added to `harvest.json` (a block delivered again replaces that block only), coverage is counted over all harvests, and the result lists the blocks delivered and registered.
- One verdict of "ready", and a `/next` that never sends you in circles (IMP-325, H21). `/status` said `READY_WITH_WARNINGS` while the brief v2 said "Ready to build: no": the brief's own line now blocks the verdict, and `/status` returns it as `ready_to_build`. `/next` repeated `/quality` forever (it now says *Validate and hand off*), sent a `DIRTY` project to `/backlog` or `/quality`, which refuse it (now *Fix what makes the project unhealthy* with `/health`), ignored a deleted brief past `/brief` (now *Regenerate the project brief*), and kept saying "Waiting for client answers" when the BA had assumed the answer: the text now says the assumption never unblocks and how to confirm the answer yourself with `/resolve-gaps`. When only non-blocking gaps are left it names `/specs` as the way forward. The command reference lists every `/next` step; the assume skill and command page explain the exit.
- Generated stories speak the project's language (IMP-324, H21). In an English project a story read "As a target user, I want when a patient confirms ... so that la capacidad confirmada se puede planificar..." and its acceptance criteria were Spanish text with a doubled "When When": the slicing compiler had no language, and used the EARS statement (which starts with "When") as the goal and as the criterion's "when". Now the story description, benefit, the acceptance criteria of value stories, enablers and the pending story, and the enablers' titles come in English or Spanish from the project language; the leading EARS word is dropped from the goal and the "when"; a Spanish project's text is unchanged apart from that. The PRD language no longer defaults to Spanish when the project language is missing or `auto`, and two accented Spanish strings that were garbled (`SecciÃ³n`, and dead enabler match words) are fixed. The dashboard stays in Spanish (see 0.12.0).
- A refused command leaves nothing behind, and bad input is exit 3, not 1 (IMP-323, H21). `/compose`, `/refine-backlog` and `/implementation-feedback` used to archive the payload, write reports, state and graph nodes, and only then refuse when nothing was accepted; now they refuse first and write only the report of why each item was refused (also listed in the message); the PRD or backlog, the payload archive, state and the graph are untouched. A payload with the wrong shape (a list root, a block that is not an object) is exit 3 instead of a traceback. A folder passed as `--source` (except to `/sync`) and a text `--source` that is not UTF-8 (for example UTF-16 from PowerShell 5.1 `>`) are refused with exit 3 before anything is written; a refused `/resolve-gaps` with such a file used to leave a copy that made `/health`, `/reindex` and `/sync` fail until it was removed by hand. The gate matrix gains the `/ingest` refusal of IMP-320 and these two `--source` rows.
- An answer is never dropped without a word (IMP-322, H21). Three answers used to vanish with exit 0: one written as indented bullets under `- Answer:` (the format several gaps ask for), the first answer of a file saved with a UTF-8 BOM, and one under a gap id that is not in `gaps.md`. Now bullets are read as the answer, a BOM is ignored, and an unknown id is listed in `unknown_gap_ids` and in the findings. The findings (a closure without a citation, an unknown id) are also written to the stored resolution report under `## Findings`, not only to the command's output. The guide and the gap-response skill now state the real rules: a confirmed answer without evidence closes but is flagged, and a pending substantive answer is `ANSWERED`, not `PARTIALLY_CLOSED`.
- A newline or a `|` in a gap no longer loses it (IMP-321, H21). An `/annotate` gap whose question held a newline was dropped from `gaps.md`, and one with a `|` shifted every column after it (severity, origin, question), while the command exited 0; a pipe in an `/assume` statement did the same to the assumptions table. Writers escaped table cells three ways and the reader split on every pipe. Now one writer (`table_cell`) turns newlines into spaces and escapes pipes, and the one row reader (`split_table_row`) splits only on unescaped pipes and reads `\|` back as `|`; the gaps table, the brief integrity check, the EARS register and the release tombstones use them.
- A second `/ingest` no longer resets a project (IMP-320, H21). It used to rewrite the requirement register, `gaps.md`, the decision log and the identity seeds from the new file, so every answered gap opened again and the verdict fell back, with exit 0 and no warning, and the guide told users to load each further file that way. Now `/ingest` on a project that already has its primary requirement refuses with exit 4, changes nothing, and names `/sync PROJECT_ID --source PATH`, which adds a file and keeps every answer. `--replace` replaces the primary requirement on purpose and reports how many answered gaps open again and which saved answer files to re-apply with `/resolve-gaps`. The guide, the command router, the discovery and the intake-triage skills now send every later file through `/sync`.

### Changed
- The install instructions use the `stable` channel (IMP-319). The README, the install page and the plugin guide said `/plugin marketplace add jmatzkin1980/ignite-sentinel`, which follows `main` (merged but unreleased work); they now say `#stable` and explain the difference. They also show the install by clicks in the Claude desktop app, link to updating the plugin and to organizing folders by client, and the README gains a "Good to know" list (folders per client, updates, the closing choice).

## [0.12.2] — 2026-11-15

### Fixed
- `/doctor` outside a framework clone no longer suggests `pip install -e .[memory]` (IMP-317). That command installs the clone's own project, so it fails in a plugin, wheel or `.pyz` project folder. In runtime mode the hints now name the packages (`lancedb`; `model2vec sentence-transformers`; `"mcp>=1.2,<3"`) and say to use the Python that runs Sentinel. The MCP server's missing-package message gives both forms. Found in the live walkthrough of 0.12.1.
- The plugin guide explains how the Claude desktop app removes a marketplace (IMP-317): `/plugin marketplace remove` only opens the plugins screen, the marketplace is removed from the **⋯** menu of its label, and uninstalling the plugin alone leaves the marketplace registered. It also records the Git Bash fix as observed in 0.12.1.

### Changed
- The agent closes with a choice when something is waiting on you (IMP-316). The command router, `AGENTS.md` and `CLAUDE.md` ask for one short question with 2 to 4 options, the recommended one first, shown as choices in Claude Code (`AskUserQuestion`) and as a numbered list elsewhere. Picking an option never closes a gap or confirms anything for you. Found in a live walkthrough: the next action got lost in the answer's text.
- The guide explains how to organize folders and releases (IMP-318). **Start here** recommends one root folder per client with one workspace per project, shows what `/dashboard` then covers and why a framework clone is a poor fit for several clients, and draws the folders of a project split into releases with the `--release rN` commands. **Versioning** adds one private repository per client folder.
- The plugin guide explains how to update the plugin (IMP-316): per channel, the in-session and terminal commands, how to turn on auto-update, how to move from one release tag to another, and that removing the marketplace uninstalls the plugin but never touches your workspaces.

## [0.12.1] — 2026-11-15

### Fixed
- The Claude Code plugin on Windows, found in a live install from the marketplace (IMP-315).
  - **Git Bash rewrote the command name.** Claude Code runs the plugin's commands through Git Bash, which turns a leading `/init` into `C:/Program Files/Git/init` before Python starts, so every command failed unless the agent worked around it. The CLI now reads a drive path whose last segment is a command back as that command.
  - **`/doctor` with the plugin is Claude Code's own.** The plugin has no slash commands, so a bare `/doctor` ran Claude Code's diagnostic, which offers to change Claude Code settings. The README, install, Claude Code, plugin and chat-command pages and the command router now say to type `sentinel /doctor`.
  - **Observed live:** the plugin page and the surface contracts of the marketplace and the plugin record the walkthrough (install in the Claude desktop app, the skills, the gates, the views and the deny hook).

## [0.12.0] — 2026-11-15

### Fixed
- The one-time brief v2 settings step was neither asked for nor enforced (IMP-311, H20).
  - **Before:** `/next` and `/status` said "Waiting for client answers" on a new project and never mentioned `/brief --profile --genesis`. When the step was skipped, `/maturity` decided `READY_FOR_SPECS` before compiling, then compiled a provisional brief in the old v1 layout, and a first `/specs` generated the PRD from it.
  - **Now:** `/next` and `/status` ask for the settings first (*Confirm the brief settings*) with a suggested command whose profile and genesis come from the raw input. On a v2 project with unconfirmed settings, `/maturity` opens `GAP-BRIEF-PROFILE` before deciding and reports `BLOCKED` without compiling a brief, so `/specs` and `/backlog` refuse (exit 4). A brief v1 project is not asked.
  - `/split --assess` and `--propose` without a compiled brief now name `/brief --profile --genesis` instead of `/maturity`.
- The same situation exits with the same code on every command (IMP-312, H20).
  - **A missing `--source` file** is invalid input (exit 3) with the next step "check the path", on every command. It used to end with exit 1 and a traceback on `/ingest`, `/resolve-gaps`, `/sync` and others.
  - **`/view` of an artifact not generated yet** is a gate refusal (exit 4) that points to `/next`, instead of exit 1.
  - **Every missing prerequisite is exit 4**, as `sentinel/errors.py` defines it: `/assume` before `/ingest`, `/compose` before `/specs`, `/implementation-feedback` before `/backlog` wrote an epic, `/self-review --sufficiency`/`--crosses` without a brief, the `/split` steps out of order (no brief v2, no proposal, no confirmed series, a brief that changed, a release already closed or with stories not Done), `--release` without a series, and `/prototype` before its inventory or brief. A refused payload or a missing option stays exit 3, so exit 1 now means a bug.
- Small runtime, skill and launcher fixes (IMP-313, H20).
  - **The clone's deny hook** ran `python .claude/hooks/...`, which does nothing where `python` is missing or is the Microsoft Store alias. It now starts Python through `.claude/hooks/python.sh`, the same shim the plugin ships, generated by `python -m sentinel.adapters` and checked for drift. Its surface contract is marked as not yet observed with the new command.
  - **`/retrieve --write-pack`** writes a context pack while `/retrieve` is read-only: the read-only contract test now declares that pack as a derived output and checks it is written.
  - **Skills:** the brief skill still called v1 the default; it now says v2 is the default and that `/next` asks for the settings. The command router lists all 11 `/view` artifacts, `--theme`, `--release` and the append-only command log.
  - **Text:** the `/gaps --top` help no longer claims a default of 5 (without it, `/gaps` regenerates `gaps.md`); the `/doctor` live checks no longer hard-code "24 skills".
- `/doctor` outside a framework clone checks the runtime instead of failing on the clone's files (IMP-314, H20). A user of the Claude Code plugin, the wheel or a `.pyz` works in a project folder without `sentinel/`, `.codex/skills`, `AGENTS.md` or the installers, and `/doctor` reported FAIL on every one of them. Now, in a folder that is not a clone, it runs in `runtime` mode: the interpreter, command parity, no network imports, workspace ids and portability, a writable folder and the optional dependencies, plus a `doctor mode` line that says the clone checks were skipped and how to run them (`/doctor --root PATH_TO_THE_CLONE`). In a clone nothing changes; the result now carries `"mode": "framework"` or `"runtime"`.
- H20 close (IMP-32z): a final sweep of the docs and skills against the H20 changes. `/scrutinize --mode anchors` without a compiled brief now refuses with exit 4 like the other prerequisites, and the command reference's gate matrix, the `/maturity`, `/status`, `/next` and `/scrutinize` blocks, the views page and one scenario now match the runtime. The dashboard stays in Spanish whatever the project language: translating it is a feature, not a fix, and is proposed separately.

### Changed
- The README and the user guide are rewritten for business analysts, product managers and developers (IMP-310). They had fallen behind releases 0.6–0.11: the first run skipped the brief v2 settings, five commands and the release-split, prototype, brownfield and gate-refusal flows had no page, and several counts and paths were stale.
  - **README** is a landing page: what Sentinel is, who it is for, the flow as a diagram, a "choose your path" install table, a quick start to a first `gaps.md`, next steps by role, and all 37 commands.
  - **Start here (`00`)** adds a glossary and a full first run with what you get and the next step after each step. **Workflows (`03`)** has one section per situation, including what to do when a gate refuses, by exit code.
  - **Command reference (`01`)** uses one template per command (syntax, an options table that matches the registry, what it writes, when it refuses and with which exit code, next step), plus an exit-code table and a gate matrix.
  - **Artifact reference (`02`)** covers every folder, including release series, prototypes and `.sentinel/`, with an edit rule and the regenerating command for each artifact.
  - **Install (`06`)** is a single "choose your path" page; the surface pages (`07`, `08`, `13`), secure environments and portability (`09`, `16`) no longer repeat each other; the skills catalog (`04`) covers all 27 skills.
  - Maintainer material (generated surfaces, cutting a release, the clean-clone check, framework branches, the lens knowledge base) moved from the user guide to `MAINTAINERS.md`.
  - No file was renamed, so existing links keep working.

## [0.11.0] — 2026-11-15

H19: closing open topics. `verify.ps1` runs the suite in parallel and takes about 6 minutes; before the IMP-305 cleanup it took about 47. `/trace` and `/maturity` are registered as the writers they are, and a test keeps every read-only command from writing an artifact. The skill metadata check catches any surface named in a description. Generated artifacts cite paths as `workspaces/<id>/...` instead of the absolute folder, so a moved workspace regenerates the same Markdown.

### Added
- H19 closing check (IMP-31z), outside the suite, on `support-dashboard`:
  - **v1:** 12/12 phases green on this branch and on `v0.10.0`, with `/validate` VALID. 25 of 30 Markdown are identical. The 5 differences are the IMP-308 citations: `<absolute folder>/workspaces/SUPDASH/...` became `workspaces/SUPDASH/...` in the maturity report, the epic, one story, the traceability matrix and the gap-resolution report.
  - **Default v2 flow:** two runs are identical (30/30), compared without normalizing paths. Neither cites the absolute folder.
  - **Portability:** one workspace copied to two different folders and regenerated in each, from `/status` to `/validate`. 31 of 31 Markdown are identical without normalizing paths, there are 26 unique graph nodes, and no path is absolute.
  - **`--assess`:** gives `no_split`.
- A parallel test run (IMP-309, H19). `tools/run_tests.py --jobs N` (or `--jobs auto`, one process per CPU) runs whole test modules in worker processes and prints the same closing lines as unittest (`Ran N tests`, `OK` or `FAILED`), with every failure's traceback.
  - **The unit is the module:** a module's fixtures and its working-directory changes are process state. Inside one worker, modules run one after another, as in a serial run.
  - **Order:** the modules in `tests/slow_modules.txt` start first, so the longest ones do not start last.
  - **Output:** each worker's own stdout (the CLI output many tests print) is discarded.
  - **Effect:** `verify.ps1` and `verify.sh` now use `--jobs auto`. On a 16-CPU Windows machine the suite went from about 27 minutes to about 5. The slowest-modules list then measures time under load, so read its shares, not its seconds.
  - **CI:** the CI workflows keep running the suite serially.

### Fixed
- Path conversion slowed every command (IMP-304, a regression from IMP-301).
  - **The cause:** converting a stored path to or from workspace-relative form resolved the workspace folder each time, a filesystem call on Windows. It runs for every graph node and every memory chunk on every save, so it took a third of a whole flow.
  - **The fix:** the folder is resolved once per workspace root and process. The comparison is a string prefix, case-insensitive on Windows. `is_absolute_path` no longer builds two path objects per call.
  - **The result:** the 12-phase `support-dashboard` flow went from 11.3 s to 5.4 s, faster than before IMP-300 (6.5 s). Paths and artifacts are unchanged.
- `/trace` and `/maturity` were registered as read-only but write artifacts (IMP-306).
  - **The risk:** `/maturity` rewrites `02_requirements/project-brief.md`, a governed artifact, but the protocol only refreshes the governed-artifact checksums after a mutating command. A later `/health` could then report a brief that only Sentinel had written as edited by hand.
  - **The fix:** both are now `MUTATING`. The protocol refreshes the checksums after them and no longer special-cases `/trace` for the traceability refresh.
  - **The guard:** `tests/test_read_only_commands.py` runs every read-only command on a matured workspace and fails if it writes a file outside the protocol's bookkeeping, the memory cache and the reports it declares. `/health` keeps its report as a declared output and stays read-only: it audits those checksums, so refreshing them after it would hide a hand edit.
- The skill metadata check of `/doctor` caught only "codex" in a description (IMP-307). It now uses the same detector as the command descriptions, `surface_leaks()`: a skill description that names Kilo, Claude, Codex, Cursor, Gemini or VS Code gives a WARN that names the surface. A cited repo file such as `CLAUDE.md` is still not a leak. Every current skill is clean.
- Generated artifacts quoted the absolute workspace folder (IMP-308, the remainder of IMP-301).
  - **Where:** the backlog anchors, the traceability matrix, the maturity, context-request and gap-resolution reports, the MDX export and its README, and the context packs (`read_plan.source_path`). A moved or cloned workspace regenerated different bytes, and the files carried the machine's folder names.
  - **The fix:** `core/paths.workspace_citation` writes every such path as `workspaces/<id>/<path>`, relative to the repo root: the same wherever the workspace lives, and openable from the repo root, where agents and people work. A path outside the workspace is kept as it is.
  - **Goldens:** unchanged. Their normalization already collapsed the absolute prefix to `workspaces/[PROJECT_ID]`, which is the form the artifacts now write.
  - **The guard:** `tests/test_portable_citations.py` scans every generated text file for the absolute folder, then regenerates the same workspace in place and in another folder: every Markdown file comes out identical.

### Changed
- A leaner test suite (IMP-305). The suite had grown to about 40 minutes on Windows, and most of its cost sat in a few modules that rebuilt the same workspace for every test.
  - **One build per class:** `tests/helpers.py` adds `SnapshotWorkspaceCase`, which builds a workspace once per class and restores a fresh copy, at the same path, before each test. Six backlog modules now use it: story status, refinement, hooks, gate overrides, implementation feedback and story format.
  - **Series E2E:** the second full run, which only proves determinism, now runs for one case instead of three.
  - **Removed duplicates**, each covered by a stronger test that is still there:
    - the hardcoded command and MCP tool lists in `test_core_flow` (the registry pins both);
    - a `/doctor` command-list check that held by construction;
    - a second Kilo allowlist test;
    - five copies of the skill mirror check and three of the per-skill metadata check;
    - a second plugin-sync check;
    - the discovery-eval assertions repeated in `test_annotate`.
  - **Where the time goes:** `verify.ps1` and `verify.sh` run the suite through `tools/run_tests.py --tier full --slowest 10`, which ends with the 10 slowest modules. A jump in the suite's time now shows in the PR that causes it.

## [0.10.0] — 2026-11-14

H18: robustness. One command registry feeds the CLI, the MCP server and the docs. Failures exit with typed codes from 0 to 6 and name the next step. One command at a time per workspace, under an operating-system lock. `state.json` is durable and versioned, and a 0.9.0 workspace migrates itself once, after a backup. The graph and the memory store workspace-relative paths, so a workspace can be moved or cloned. The Markdown artifacts are unchanged: the H18 closing control found 30/30 identical on `support-dashboard`.

### Added
- H18 closing check (IMP-30z), outside the suite, on `support-dashboard`:
  - **v1:** 12/12 phases green and 30/30 Markdown identical to `v0.9.0`, with `/validate` VALID. Only `state.json` changes.
  - **Default v2 flow:** two runs are identical (30/30).
  - **`--assess`:** gives `no_split`.
  - **Portability:** a workspace generated by `v0.9.0` was moved to another folder, then migrated and regenerated from `/brief` to `/validate`. It matches the same regeneration done by `v0.9.0` in place:
    - 30 of 31 Markdown are identical, with the same 26 graph nodes and no duplicates;
    - `/validate` is VALID;
    - no absolute path is left in the graph or memory, and the backup is written.

    The one difference is the regeneration diff of `EPIC-001.md`, which counts one more changed line. That line is a retrieval citation whose absolute path now names the new folder.
  - **For comparison:** `v0.9.0` regenerating the same moved workspace crashes at `/backlog` and grows the graph from 26 to 34 nodes.
  - **In the suite:** the series and prototype E2E goldens are unchanged, and the two-process lock test runs on the Windows and Linux CI legs.

### Changed
- Portable workspaces (IMP-301, H18). The graph, the memory and the artifact pointers in `state.json` stored absolute paths. A moved or cloned workspace failed in silence: `/validate` reported missing artifacts, `/reindex` skipped them, and `/health` compared two equally stale paths and saw nothing.
  - **Storage:** paths are stored relative to the workspace, the same rule as the context artifact ids. This covers graph node paths, memory `source_path`/`file_path` (JSON, manifest and LanceDB), `state.artifacts` and `last_*_source`. Sentinel resolves them against the workspace's current folder when it reads them, so callers and Markdown artifacts are unchanged.
  - **Legacy paths:** an absolute path from another copy of the workspace (one with a `workspaces/<id>/` segment) is read against the current folder. The 0.9.0 migration and `/reindex` rewrite it on disk.
  - **`/health`** reports any graph path that does not exist or points outside the workspace.
  - **`/doctor`** reports workspaces with an old or newer `schema_version`, or with absolute paths in the graph or memory.
  - **Release mirrors:** they keep the input nodes' relative paths instead of re-rooting absolute ones.
- Typed errors and exit codes (IMP-302, H18). Every failure used to exit with 1. Now:
  - **Codes:**
    - 0: success;
    - 1: an unexpected error (a bug), now followed by its traceback;
    - 2: wrong usage;
    - 3: invalid input (an invalid project id, a missing file, a refused payload);
    - 4: a gate refusal (a prerequisite, the project's health or its phase);
    - 5: an unfavourable verdict (`/validate` not VALID, `/doctor` not PASS);
    - 6: workspace busy, reserved for the workspace lock (IMP-299).

    The table is in `user_guide/01`.
  - **The next step:** a failure prints `next step: ...` when the runtime knows it. Examples: `Run /init P first.` for a missing workspace, `Run /ingest first.` for a prerequisite.
  - **In the code:** `sentinel/errors.py` holds `SentinelError`, `InputError`, `GateRefusal` and `WorkspaceBusy`. `InputError` and `GateRefusal` are also `RuntimeError`, so existing handlers keep catching them. The deliberate `RuntimeError`s of the runtime now raise a typed error. A plain `ValueError` counts as invalid input; any other exception counts as a bug.
  - **MCP:** a failed command comes back as an error result (`isError`) whose text is JSON with `code`, `kind`, `error`, `next_step` and `output`. `run_cli` adds the same fields to its result.
  - **Scripts:** any failure is still non-zero. A script that compared the exit code to exactly 1 needs updating.
- A durable, versioned `state.json` (IMP-300, H18). It used to mix what cannot be rebuilt with counts and metrics the runtime recomputes, plus the command log, and had no version.
  - **`state.json`** keeps the durable state (phase, health, story lifecycle and gates, language, privacy, `artifact_hashes`…) and `schema_version: 1`.
  - **`.sentinel/derived/state.json`** keeps `gap_counts`, `maturity_metrics`, `prd_section_readiness` and `backlog_rollup`. Deleting it loses nothing: `/status` gives the same answer.
  - **`.sentinel/command_log.jsonl`** keeps one line per command, append-only. A line torn by a crash is skipped. `command_protocol_log.md` still shows the last 25.
  - **Migration:** the first command that opens a 0.9.0 workspace migrates it, once, after copying `state.json` to `.sentinel/state.json.bak-0.9.0`. `last_export` becomes relative to the workspace.
  - **A newer schema** (a workspace written by a later Sentinel) is refused with exit code 3 and left untouched.
  - **In the code:** `read_state` returns both halves merged and `update_state` splits them again, so callers see one dict. Code or scripts that read `state.json` directly for the derived keys should use `read_state` or `read_workspace_state`.
- One command at a time per workspace (IMP-299, H18). Two commands on one workspace (CLI and MCP, or two sessions) used to overwrite each other's `state.json` and traceability graph, and the later write won.
  - **The lock:** every command that names a project locks its workspace (`.sentinel/lock`) while it runs. The read-only commands lock it too, because each one records itself in `state.json`. The lock is the operating system's, so a crashed process never leaves it behind.
  - **Waiting:** a second command waits up to 10 seconds (`SENTINEL_LOCK_TIMEOUT`), then exits with code 6, naming the command that holds the workspace.
  - **Write conflicts:** a JSON file that changed on disk between a command's read and its write used to raise a warning and be overwritten. Now the command stops with code 6 and leaves the file as it is.
  - **MCP:** one MCP server runs one tool call at a time, so two overlapping calls no longer mix their output.
  - **Deletions:** files are now deleted through `core.io.remove`, confined like a write, and the single-writer test covers deletions.
  - **Admin guide:** `user_guide/20` explains the lock and what to do when a session holds it.

### Added
- A single command registry (IMP-303, H18), `sentinel/commands.py`. Each command is declared once: its name, its place in the command protocol, whether it takes `--release`, its MCP tool and its arguments.
  - **Built from it:** the CLI parser, `cli.COMMANDS`, the protocol sets (`READ_ONLY_COMMANDS`, `MUTATING_COMMANDS`, `PROTOCOL_EXEMPT_COMMANDS`), the release commands and the runtime list the adapters compare with the manifest. The parser is identical to 0.9.0's.
  - **Checked against it** (`tests/test_command_registry.py`): the CLI dispatch, the MCP tools and every parameter they take, the commands manifest, one section per command in `user_guide/01` and the artifacts the MCP `view` tool describes. A CLI option with no MCP parameter, or the other way round, fails the test unless the registry states why it is left out.
  - **MCP gains the options it lacked:** `sentinel_init` takes `brief_version`; `sentinel_retrieve` takes `limit`, `artifact_type`, `domain`, `trace_id`, `iteration_min`, `status`, `language`, `sensitivity`, `section`, `max_chars` and `summary_only`; `sentinel_backlog` takes `story_format`; `sentinel_export` takes `domain`; `sentinel_quality`, `sentinel_validate` and `sentinel_backlog_status` take `override`; `sentinel_reindex` takes `full`.

## [0.9.0] — 2026-11-13

H17b: the derived artifacts. The to-be diagrams of a brief v2 render offline with a vendored, pinned mermaid. An ingested HTML prototype gets its inventory, the trace of each screen against the brief, and a user manual that quotes the interface's own words. The release series end to end now covers all eight release types. A workspace without a prototype or a series compiles, validates and derives exactly as 0.8.0 did: the H17b closing control found 30/30 identical Markdown on `support-dashboard`.

### Added
- H17b closing check (IMP-27z).
  - **Without a prototype**, on `support-dashboard`:
    - v1 has 12/12 phases green and 30/30 Markdown identical to `v0.8.0`, with `/validate` VALID;
    - the default v2 flow gives two identical runs;
    - `--assess` gives `no_split`.
  - **With a prototype:** `tests/test_prototype_e2e.py` takes the synthetic prototype through inventory, the trace of one screen and the manual. Each view matches its golden (`tests/fixtures/golden/prototype/`), and two runs in fresh workspaces are identical.
  - **Diagrams:** golden per type, a pending section drawn dashed, and a view that opens offline under the CSP (`tests/test_diagrams.py`).
- The release series end to end with the three remaining release types (IMP-298, H17b).
  - **Fixture:** a new synthetic fixture `tests/fixtures/synthetic_series_more_types/` covers an already built release, an enabler, a functional release and a segment cutover. Each one derives (specs, backlog, quality) and gives `/validate` VALID, and two runs are identical (`tests/test_series_e2e.py`).
  - **Release brief:** §0.1 now carries what each type requires (`release_split_model.json#release_types`):
    - an enabler: `supports`, `reduces_risk`, `goes_first` and `does_not_add` (its negative list);
    - a segment cutover: `segment`, `eligibility` and `switch`;
    - an already built release: `validation_direction: built`, and its §0.2 says `built`. Only that release: the next ones keep `to-build`.
  - **Proposal contract:** new optional `enabler` and `cutover` objects on a release (`release_split_proposal.schema.json`).
- `/view PROJECT_ID --artifact diagrams` (IMP-273, H17b): the to-be diagrams, generated deterministically as Mermaid from the v2 brief, in `sentinel/diagrams.py`.
  - **Diagrams:**
    - §3.4 → `stateDiagram-v2`;
    - §3.3 → `sequenceDiagram`;
    - §5.1 and §5.6 → `flowchart`, with each component's status (new, extends, unchanged, retired), plus a compared As-Is when something already exists;
    - the confirmed series → `flowchart` with its waves.
  - **Nothing is inferred:** a diagram is drawn only from structured lines: `A → B: label`, `Component (new)` or a table whose header names its columns.
    - A pending section is a dashed placeholder with its GAP.
    - A populated section without that notation says how to write it.
    - Conditional and optional lines are dashed.
  - **Each card** says what changes and what is still to define, with pending and release chips. The legend appears once. A diagram over 24 edges is split.
  - **Render:** offline, under the views' CSP.
    - The page inlines a vendored mermaid `11.17.2` (MIT, `sentinel/vendor/mermaid`), pinned by sha256 and checked by the new `/doctor` check `vendored mermaid`.
    - The colours come from the theme's semantics, and the page re-renders on the light/dark toggle.
    - Without the library (the minimal `.pyz` leaves it out) or on a hash mismatch, each card shows its code, marked "not rendered".
  - **Surfaces:** CLI and MCP `view`, the manifest, the `sentinel-views` skill, `user_guide` 01 and 15, `VIEW_TEMPLATES` and package-data.
- `/prototype PROJECT_ID --manual --source manual.json` and the `sentinel-prototype-manual` skill (IMP-276, H17b), in `sentinel/prototype_manual.py`.
  - **A `/compose`-like channel:** the agent writes the prose of each screen (purpose, steps, notes) and cites the inventory as `{{S2-E06}}`. The generator injects the element's literal text, so the agent never types the interface's words or figures.
  - **Refusals:** a paragraph without a citation, a figure in the prose, an element outside the screen (JS literals allowed), an unknown screen and a duplicate. A refused manual stores nothing.
  - **Merging:** submissions merge by screen.
  - **Output:** `02_requirements/prototype/manual.md` (`/view --artifact prototype-manual`, printable) lists every screen in order. A screen without manual is a visible hole.
  - **Surfaces:** CLI, MCP (`sentinel_prototype` with `mode=manual`), the manifest, the router, the new skill (in `/doctor` required skills, mirrored) and `user_guide` 01.
- `/prototype PROJECT_ID --trace --source trace.json` and the `sentinel-prototype-trace` skill (IMP-275, H17b), in `sentinel/prototype_trace.py`.
  - **One screen per pass:** the agent walks it in the surface's browser and traces each element element → data → contract → rule. With no browser it declares `executed: false`, which is "not executed", never invented.
  - **What the runtime validates**, against the inventory and the brief v2:
    - the element exists in that screen (or is a `JS-NN` literal) and its `element_quote` is literal;
    - `established` cites the brief verbatim, `inferred` names its basis, `unsupported` names an open gap, and `demo` cites the source that says it is not built;
    - the four states are declared as shown, unreachable or not_built;
    - the checks name a known check and a side to fix;
    - there are at most four questions;
    - there are no figures in the agent's prose (ids are fine).
  - **Refusals:** a refused trace lists every finding and stores nothing.
  - **Storage:** a valid one goes to `02_requirements/prototype/trace/F-NN-SN.json`, and `trace.md` (`/view --artifact prototype-trace`) shows the screen verdict (`supported`, `has_gaps` or `not_executed`).
  - **Evals:** 11 seeded synthetic traces, tuning and held-out, with a no-regression floor. They run in `verify.ps1` and CI.
  - **Surfaces:** CLI, MCP (`sentinel_prototype` with `mode=trace`), the manifest, the router, the new skill (in `/doctor` required skills, mirrored) and `user_guide` 01.
- `/prototype PROJECT_ID --inventory` (IMP-274, H17b): the inventory of each ingested HTML prototype, in `sentinel/prototype.py`.
  - **Input:** the redacted, shielded copy in `00_raw`, so secrets (IMP-285) and injection (IMP-286) are handled as for any source.
  - **Screens:** by `data-screen`, else `<section id>`, else the page.
  - **Elements:**
    - every visible element with its literal text, line and whether it starts hidden;
    - its stable id (`S1-E01`).
  - **JavaScript copy literals** (`JS-01`): state texts and error messages, with code left out.
  - **Output:** `02_requirements/prototype/inventory.json` and `inventory.md` (`/view --artifact prototype`). It is deterministic and stdlib only.
  - **Surfaces:** CLI, MCP (`sentinel_prototype`, `mode=inventory`), the manifest, the router and `user_guide` 01.
  - **Fixture:** a synthetic prototype (`tests/fixtures/synthetic_prototype/`, labelled) with three screens, hidden states and JS copy. The test seeds a secret at run time and checks it is redacted.

### Security
- The `[mcp]` lock pins `opentelemetry-api` 1.45.2, which fixes CVE-2026-126360 reported by pip-audit in 1.45.1.

## [0.8.0] — 2026-11-12

H17a′: the living series. A confirmed series can be re-scoped with a dated, confirmed move, releases close with evidence and free their dependents, and a guide shows the series as a whole. It also fixes two defects: releases derived from the whole brief, and a brief's scope reduced to one sentence per source. A workspace without a series compiles, validates and derives exactly as 0.7.0 did; the H17a′ closing control found 30/30 identical Markdown on `support-dashboard`.

### Added
- H17a′ closing check (IMP-26w). No code change. The control without a series, on `support-dashboard`:
  - v1 has 12/12 phases green and 30/30 Markdown identical to `v0.7.0`;
  - the default v2 flow gives two identical runs;
  - `--assess` gives `no_split`.
- The series end to end with every release type (IMP-297, H17a′). `tests/test_series_e2e.py` runs a second synthetic fixture, labelled as such (`tests/fixtures/synthetic_series_types/`).
  - **The fixture:** one source with five scope sentences, which IMP-296 turns into five build items.
  - **The series:**
    - a measuring spike with its questions, time-box and DEC contract;
    - two functional releases;
    - an interleaved `r2.1` (change found in testing);
    - a conditional with its open gap;
    - an integrator with its consumption table.
  - **Checks:**
    - every release derives (`specs`, `backlog` with the slice plan, and `quality`) and validates VALID;
    - each brief keeps its type's series fields;
    - the guide sorts `r2.1` in natural order;
    - two full runs are identical.
- Series guide and closing a release (IMP-269, H17a′), in `sentinel/release_guide.py`.
  - **`/split PROJECT_ID --close rN --evidence PATH --ba NAME --tech TEAM`:** closes a release only when every story of it is Done (in the release's own lifecycle) and a local evidence file of its closing check exists, fingerprinted by sha256.
    - The close is recorded in `partition.json` and survives later confirmations and moves while the release exists.
    - The output names the releases it unblocks.
  - **NOT READY by inheritance** [A38]: within `--release rN`, a hard dependency on a release that is not closed is a verdict blocker, with a new `series_dependencies` gate.
  - **The guide:** `02_requirements/series/release-guide.md`, also as `/view --artifact release-guide`. It recompiles with the series and shows:
    - the waves;
    - each release with its type, goal, edges and status (closed, waiting on a dependency, or open with its own stage);
    - the frozen contracts;
    - the coverage matrix, with each §6.1 line, `C-NN` and `P-N` and its owner;
    - what has no source (`[NO SOURCE]`), counted against what is declared absent (sketches and §6.2).
  - **Release axis in the readiness view** (IMP-247): one item per release, with its inherited, closed or own verdict.
  - **Surfaces:** CLI, MCP (`sentinel_split` with `mode=close`, `release` and `evidence`; `/view` lists `release-guide`), the manifest, the router, the skill and `user_guide` 01.
- `/split PROJECT_ID --move` (IMP-268, H17a′): re-scope and cascade, in `sentinel/release_move.py`.
  - **What moves:** one unit (`C-NN`, `P-N` or a quote of the brief) between releases of a confirmed series, or to a sketch (`--to sketch:<name>`).
  - **Confirmation:** the partition must stay green, and the BA and the technical team confirm it again (`--ba`, `--tech`). The client's confirmation gap reopens if it was closed.
  - **Cascade:** the series recompiles, with both briefs, REATRIBUIDO tombstones in the neighbours and the index. The touched releases with derivations are listed as `stale_derivations`, and their mirror's drift shows them.
  - **Record:** every move is dated, with its reason, the finding that motivated it and who confirmed it, in `02_requirements/series/scope_changes.md` and its JSON.
  - **Excluded is not resolved:** moving to a sketch closes no gap.
  - **Round trip (A→B→A):** it means "cut criterion not written" [A42]. The move is refused and `GAP-SPLIT-CRITERION` opens, until `--criterion Cn` names the written criterion that decides it.
  - **Surfaces:** CLI, MCP (`sentinel_split` with `mode=move`), the manifest, the router, the `sentinel-release-split` skill and `user_guide` 01.

### Fixed
- Derivations by release used the whole project's brief (IMP-267b, shipped in 0.7.0; fixed in IMP-269).
  - **The defect:** inside a release's mirror, `/specs` runs the maturity evaluation, which recompiled the brief v2 from the mirror's sources. That replaced the release brief with the whole brief, so a release's PRD and specs were derived from the whole project, and its fresh derivations reported drift.
  - **The fix:** inside a release scope the brief is never compiled; the release brief comes only from the series.
  - **A test** checks that the mirror's brief is the release brief after deriving, and that fresh derivations show no drift.
  - Releases derived on 0.7.0 should be derived again with `--release`.
- The brief v2 keeps all the scope of each source (IMP-296, H17a′). §6.1 and §6.2 took only the first "in scope" and the first "out of scope" sentence of each source, so the rest of a source's scope was silently lost, together with its build items in §9.1.
  - Now every scope sentence lands in its place, with no duplicates across sources, and §9.1 gets one `C-NN` per §6.1 item, as before.
  - **Behaviour change:** a v2 brief whose sources state several scope sentences compiles more §6.1, §6.2 and §9.1 items than in 0.7.0. A source with a single scope sentence compiles exactly as before. The goldens and the `support-dashboard` control are unchanged.

## [0.7.0] — 2026-11-12

H17a: the release series. A brief v2 can be assessed, proposed, validated, confirmed and compiled into a series of self-contained release briefs, and every derivation runs per release. A workspace without a series compiles, validates and derives exactly as 0.6.0 did.

### Added
- H17a closing check (IMP-26v): `tests/test_series_e2e.py` runs the series end to end on a synthetic multi-release fixture, labelled as such (`tests/fixtures/synthetic_series/`).
  - The fixture is three sources (filing, approval, payment), their gap answers and the agent's proposal.
  - The test runs the v2 flow, then `/split --assess`, `--propose` and `--confirm`. That compiles the index and the release briefs.
  - Per release, `specs`, `backlog` (with the slice plan) and `quality` run, and `/validate` is VALID for each.
  - Two full runs give identical release artifacts.
- Derivations by release (IMP-267b, H17a): `--release rN`, in `sentinel/release_scope.py`.
  - **Commands:** `specs`, `backlog` (including the slice plan), `quality`, `story-status`, `view`, `validate`, `trace`, `status` and `next` accept a release of a confirmed series. They also take it from MCP, as `release`. `quality` was added at the H17a close.
  - **How it runs:** the pipeline runs unchanged inside a mirror workspace (`workspaces/<P>/.series_work/rN/`) whose brief is `02_requirements/rN/project-brief.md`.
  - **Outputs:** they land under `03_specs/rN/`, `04_backlog/rN/`, `05_quality/rN/`, `06_traceability/rN/` and `08_context_packs/rN/`, with the paths inside rewritten.
  - **Isolation:**
    - each release keeps its own lifecycle: phase, story states, gates and acceptance-criteria freezes when its stories go to construction;
    - the project's `state.json` and its own derived artifacts are not touched;
    - whole-project EARS rows are not carried into a release, because the release brief is the input.
  - **Readiness:** the verdict knows the release it covers.
  - **`/validate`:** with a confirmed series it also reports the series' sync findings and each release's integrity.
  - **Invariant:** without `--release` nothing changes.
- Series compilation (IMP-267a, H17a), in `sentinel/release_series.py`. `/split --confirm` compiles two outputs from the whole brief v2 and the confirmed partition:
  - `02_requirements/series/index.md`, with:
    - the project in one page;
    - the series table;
    - the waves;
    - the frozen contracts;
    - the id map;
    - the sketches;
    - the sync findings.
  - one self-contained `02_requirements/r<N>/project-brief.md` per release.
  - **Tombstones:** in each release brief, every unit another release owns becomes a tombstone ("➡ lives in rN" / "➡ vive en rN") in every section, and a unit that moved says REATRIBUIDO. Anchors treat tombstones as exempt.
  - **Ids and §0.1:** build items `C-NN` become local and are mapped in the index. §0.1 declares the release in the series.
  - **Not split:** the SAD and the prototype. Releases sort in natural order (`r2` < `r2.1` < `r10`).
  - **Checks:** integrity and anchors run on each release brief.
  - **Recompiling is the synchronization:**
    - a later mutating command that changes the brief recompiles the series;
    - a unit the brief gained is "not routed" until the series is proposed again;
    - a v1 brief blocks the series [A43].
  - **Invariant:** a workspace without a confirmed partition is never touched.
- `/split PROJECT_ID --confirm --ba NAME --tech TEAM` (IMP-266, H17a): deterministic validation of the partition, `sentinel/release_split.py`.
  - **Graph with contracts as nodes:** shared schemas, APIs, file formats, events, roles and spike DECs are `contracts` (`K<N>`). Each hard edge carries its why and the contract it consumes, created by its target. Edges come in symmetric `depends_on`/`enables` pairs.
  - **Cycles and waves:** a cycle over hard edges is a missing contract (a gap, with its path). A hard dependency points to an earlier wave, and the topological waves are reported. A committed release never hard-depends on a conditional one.
  - **Coverage n of n:** every §6.1 scope line, every `C-NN` of §9 and every screen `P-N` goes to exactly one release or sketch.
  - **Single owner:** one creator and one name per contract. Two or more siblings extending one carry a cross note and a merge order. A shared service exposes only operations with a consumer.
  - **Frozen contracts:** the confirmation freezes each contract by sha256, and a later change needs an audited `contract_deltas` row.
  - **Relaxed rules:** never legal, regulatory or Must, and always `restored_in` a later release.
  - **The model's six validated anti-patterns**, reported by key.
  - **Pending with tentacles**, two distinct signals:
    - a conditional's gap repeated in two or more siblings is a finding;
    - a gap holding back `UMBRAL_TRANSVERSAL` (75 %) or more of the releases is a transversal-readiness signal.
  - **The integrator's premise** is checked against its consumption table.
  - **Confirmation:**
    - It requires all of the above green, and the brief unchanged since the proposal.
    - It writes `02_requirements/series/partition.json` with who confirmed (the BA and the technical team), the waves, the coverage and the frozen contracts.
    - The client's confirmation opens `GAP-SPLIT-CLIENT`.
    - Nothing is compiled.
  - `--propose` now returns `partition_preview`. The proposal schema adds `contracts`, `relaxed_rules`, `contract_deltas`, edge `consumes`, sketch `contains` and `{item: P-N}` units.
  - **Evals:** 13 seeded partitions, tuning and held-out, with a no-regression floor. They run in `verify.ps1` and CI.
- `/split PROJECT_ID --propose --source proposal.json` and the `sentinel-release-split` skill (IMP-265, H17a). The agent walks the release split model and writes the series proposal:
  - core and variations;
  - criteria written before cutting;
  - the base with its negative list;
  - releases with type, wave, pattern, goal and the brief units they contain;
  - conditionals with their gap, spikes, interleaved releases and sketches;
  - inheritance of each open gap to the first release that needs it;
  - the integrator's consumption table.

  The runtime validates structure, anchors (verbatim in their place) and release contracts.
  - A refused proposal lists every finding with its code and stores nothing.
  - A valid one is stored in `02_requirements/series/proposal.json` as a proposal, next to the assessment. Nothing is compiled.
  - The contract is `schemas/release_split_proposal.schema.json`, guarded against the validator.
  - **Evals:** 10 seeded proposals, tuning and held-out, with a no-regression floor in `metric_baseline.json`. The seeded defects are a criterion without source, an empty release, a layer cut by name and by lens, a misplaced inheritance, spike and conditional contracts, and an integrator without consumption, plus clean proposals that must pass. They run in `verify.ps1` and CI.
- `/split PROJECT_ID --assess` (IMP-263, H17a): should this brief v2 be split into a release series?
  - **Signals:** each of the model's 7 split and 5 no-split signals gets a deterministic detector and comes out `lit` (with its anchor in the brief), `off`, `undetermined` (its places are pending) or `on_proposal` (checked on a proposed release).
  - **No numeric threshold:** keyword cues read only cited fact lines.
  - **Recommendation:** `split`, `no_split` or `cannot_decide`, each with its reasons, plus the step 0 questions.
  - **Output:** `01_discovery/split_assessment.md` and its JSON. The brief is never touched.
  - **Re-assessment:** a later command that changes the brief runs an existing assessment again.
  - **v1:** a v1 brief is rejected, because a series does not mix v1 and v2.
  - **Surfaces:** CLI, the MCP tool `sentinel_split`, the command manifest (Claude Code and Kilo) and the router.
  - **Control:** the support-dashboard, crm-billing-sync and portal-autogestion eval fixtures all come out `no_split`.
- The release split model as data (IMP-264, H17a). `sentinel/templates/release_split_model.json` holds the framework's knowledge on splitting a v2 brief into a series of releases. The coming `/split` command reads it; nothing changes for a workspace without a series.
  - **When to split:** 7 signals to split and 5 not to, with no numeric threshold.
  - **How to cut:** 14 cut criteria and 24 patterns. Each pattern has its question, what it contains and inherits, the contract the siblings share, parallel or chained, and when not to use it.
  - **How to walk it:** the flow (step 0 plus 12 steps), the stopping criterion and the cut evaluation.
  - **How to order:** the ordering rule in 5 steps, with MoSCoW (Must at most 60 %, about 20 % Could).
  - **What a release is:** release types and interleave subtypes, the series base vs. a backlog enabler, the spike contract (1–3 questions, a time-box and a DEC), release INVEST and the anti-patterns.
  - The loader validates the model (`sentinel.release_split_model.validate_model`); `schemas/release_split_model.schema.json` documents it and a drift guard keeps the two in step.
  - The enabler boundary stays in `slicing/backlog_slicing_model.json`: the model cites it, never copies it.
  - `brief_v2.json` activates its series fields (`series_fields`, formerly `series_reserved_fields`), each mapped to the model section that defines its vocabulary.

### Fixed
- `GAP-SPLIT-CLIENT` (IMP-266) opened as `high`, which blocks by default. A confirmed series froze `/specs` until the client confirmed. It now opens as `medium`: it stays visible and does not block what the BA and the technical team already confirmed (IMP-267b).
- Retrieval recency no longer depends on the wall-clock second (IMP-295). `indexed_at` has one-second resolution: two artifacts indexed in the same second tied, and two indexed across a second boundary did not. So the recency re-score (IMP-123) could pick a different top result between identical runs; the backlog's Product evidence row flipped between `REQ-002` and `PRD-001`.
  - Each indexed artifact now carries `index_seq`, the order of indexing, which is the same on every run. Recency ranks by iteration, then `index_seq`.
  - `indexed_at` still breaks ties, but only for chunks indexed before this change.

## [0.6.0] — 2026-11-11

### Fixed
- A confirmed answer now lands in the brief v2 for every gap a round asks (IMP-26u). The H16c close measured the first `/gaps --top 5` round of the support-dashboard fixture on a synthetic answered round: only 1 of 5 answers reached the brief.
  - **Umbrella gaps:** an answer to `GAP-BRIEF-S<n>` fills its places one line per place (`1.2: … 1.4: …`), and its question says so. Before, the gap closed and the next compile reopened it with the marks still in place.
  - **Counterpart answers** (`GAP-CTP-*`, IMP-256) complete their place (6.2, 2.5, 5.11, 4.2) next to what the source says, instead of going nowhere.
  - **Delivery answers** routed to §9.1 (slicing, readiness, enablers) are written under the build list.
  - With the same synthetic round, `⏳` client goes from 16 to 13, domain from 56 to 51, and covered places from 7 to 13. `tests/test_answered_round.py` keeps the circuit; the real drop is measured on the first real project.
- The §6.3 cascade of a recompiled brief v2 wrote `—` for places that propagate nowhere, a forbidden value (IMP-255), so `/validate` failed after any recompile that changed §0.2 or §7. It now says "no other document" / "ningún otro documento".
- The admin guide's upgrade diff compares the previous release with the new one.

### Added
- Brownfield harvest into the brief v2 (IMP-262). `/harvest PROJECT --source harvest.md` (CLI, MCP `sentinel_harvest`, Claude Code and Kilo commands) ingests a tagged harvest of the existing system's code, written with the rewritten `sentinel-brownfield-harvest` skill.
  - **Format:** blocks B0 (repository inventory) to B5, and one tag per claim: `[HECHO repo:file]`, `[INFERIDO]`, `[NO ENCONTRADO where]`, `[FUERA DEL CÓDIGO topic]` or `[DIVERGENCIA repo:file]` (English tags work too).
  - **Validation:** a fact names a repo of B0, "not found" says where, and "out of code" uses the closed topic list. A bad harvest is refused with every reason.
  - **Storage:** secrets are redacted (IMP-285), and the harvest is stored under `00_raw/02_technology_context/harvest/` as a governed F-NN row with direction `built`.
  - **Routing:** "out of code" opens a non-blocking domain gap (never asked of the code again), and a README/code divergence opens a high ⚠ gap.
  - **Brief v2:** facts feed §5 by block with a citation of the harvest row, inferences become `(inferred)` lines with ledger rows, and §0.2 lists the repositories and the coverage per tag.
- Semantic crosses of the brief v2 (IMP-260b).
  - **The review:** `/self-review PROJECT --crosses --source crosses.json` (MCP `sentinel_self_review(crosses=True)`) lets an agent report crosses against the rules of `templates/semantic_crosses.json`:
    - the four lens crosses A–D: scope against lenses, business against process, process against design, design against technical;
    - the six exit checks IMP-260 could not decide by rule: field origin, endpoint in a service, retention with its job, obligation with control and acceptance criterion, existing systems stated, story against acceptance criterion against §9 item.
  - **What the runtime checks:** the rule allows the kind (`conflict` needs both ends, `missing` names where the counterpart should be), each quote is verbatim at a place on the rule's side, and a finding and a question are present.
  - **What happens to the result:** accepted crosses open `GAP-XRV-*` gaps (`origin: cross-review`, a conflict is high), and each review goes to `01_discovery/cross_review_log.md`. The brief is never edited.
  - **Evals:** `tests/evals/run_cross_review_evals.py` runs seeded fixtures with a held-out split and a no-regression floor, in `verify.ps1` and CI.
- Anchors that hold, agentic part (IMP-258b).
  - **The review:** `/scrutinize PROJECT --mode anchors --source review.json` lets an agent say, for each anchor of the brief v2, whether the cited passage holds the sentence, says less, or says the opposite.
    - It also gives the inverted reading: what the source alone supports.
    - An adversarial pass can refute a "holds" with a verbatim quote, which turns it into "says less".
  - **What the runtime checks:** the sentence sits verbatim at its place on a line that cites that source, and the source passage sits verbatim in the source's text. Every finding needs the inverted reading and a question.
  - **What happens to the result:** accepted findings open `GAP-ANC-*` gaps (`origin: anchor-review`, says the opposite = high). The brief is never edited, and each review is appended to `01_discovery/anchor_review_log.md`.
  - **Evals:** `tests/evals/run_anchor_review_evals.py` runs seeded fixtures with a held-out split and a no-regression floor, in `verify.ps1` and CI.
- Sufficiency of the brief v2 (IMP-259). `/self-review PROJECT --sufficiency --source payload.json` (CLI, MCP `sentinel_self_review(sufficiency=True)`) runs on the brief alone, with no PRD needed.
  - **Who reads:** a clean-context reader, whose protocol the `sentinel-self-review` skill fixes. It asks of each place and each §9 build item what is missing to start tomorrow, and classifies each obstacle as covered, missing, ambiguous or contradictory.
  - **What the runtime checks:**
    - the place exists (a section, subsection or `C-NN`);
    - a `missing` obstacle brings text that is not already in the brief;
    - ambiguous and contradictory quotes are verbatim in their places (both ends for a contradiction);
    - every non-covered obstacle carries a question.
  - **What happens to the result:** accepted obstacles open `GAP-SUF-*` gaps (`origin: sufficiency`, topic dedup, BA disposition). Each round is appended to `01_discovery/sufficiency_log.md`, and the verdict is SUFFICIENT when a round reports only covered places and nothing was rejected.
  - **Evals:** `tests/evals/run_sufficiency_evals.py` runs seeded fixtures with a held-out split and a no-regression floor, in `verify.ps1` and CI.

## [0.5.0] — 2026-11-11

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
- The brief v2 is the default for new projects (IMP-26w).
  - **New projects:** `/init` records `brief_version: 2`, and `/init --brief-version 1` keeps v1. Workspaces created before this have no `brief_version` and stay on v1.
  - **Confirmation:** until the BA confirms profile and genesis, `/brief` opens the critical `GAP-BRIEF-PROFILE`, the project stays at `CLIENT_RESPONSE_NEEDED`, and `/specs` refuses. Confirming compiles the v2 brief and unblocks the flow.
  - **Bug fix:** `/brief` now counts blocking gaps after compiling, so a gap the compilation itself opens (such as `GAP-BRIEF-PROFILE`) blocks the stage instead of leaving it at `READY_FOR_SPECS`.
  - **Tests:** the test suite pins `--brief-version 1` where it exercises the v1 flow. The brief v2 golden now runs on the default flow.
- Work versus deliverable (IMP-272).
  - **Exports:** an `/export` of the brief, the PRD or a context request that still has pending marks comes out stamped as a draft (a banner under the title, `draft: true` in MDX metadata) and reports `deliverable: draft` with `pending_marks`. `/export --final` refuses until none remain (CLI, MCP `sentinel_export(final=…)`). Gap exports (`interview`, `faq`, `--artifact gaps`) are working documents.
  - **Domain request packs:** they now carry `when_to_read:` frontmatter and ask for one owner per fact. `/validate`'s cross-consistency warns when a delivered domain context file lacks `when_to_read:` or gives a fact more than one owner.
- Cross-consistency of the brief v2, deterministic part (IMP-260).
  - **Exit checks:** `sentinel/cross_checks.py` runs the contract's exit checks that cross catalogs and sections, declared in `templates/cross_checks.json`:
    - a role of 2.1 named in 4.1/5.11;
    - error codes of 4.2 and 3.5 present in 5.15;
    - every business rule with a step in 3.2;
    - flags of 6.1 declared in 5.3;
    - analytics events feeding a success metric;
    - build items within scope (9.1 ⊆ 6.1, 6.2 ∩ 9.1 = ∅, every 6.1 item built);
    - exclusions with a destination or decision;
    - priority only in 2.3;
    - assumptions with a use;
    - technical pieces and declared training with a build item.
  - **Reporting:** results are PASS, WARN or SKIP (nothing to cross yet) in `/validate`'s cross-consistency report. They are non-blocking, like the other cross-artifact checks.
  - **Compiler:** brief v2 §9.1 now derives build items only from §6.1, so every item traces to scope.
- Governed glossary (IMP-261).
  - **Glossary:** `sentinel/glossary.py` builds `01_discovery/glossary.json`. Each term has a definition, a canonical name (a backticked identifier in the source), a "do not confuse with" note and its source row.
  - **Where terms come from:** confirmed answers to `GAP-PRD-GLOSSARY-GOVERNANCE` (`Term: definition; ...`); definitions in the raw input ("X means Y", "X significa Y", "se define como", a "Glossary"/"Glosario" section); and acronym expansions ("Service Level Agreement (SLA)"), which are kept as `(inferred)` because an expansion is not a definition. Nothing else is inferred.
  - **Brief v2:** the annex `A.glossary` renders the glossary as a table with citations; inferred definitions also become `INFERRED` ledger rows. PRD section 13 is now the project glossary, not a fixed table of Sentinel's own terms. With no terms it is an explicit pending line.
  - **Gap split:** `GAP-PRD-GLOSSARY-GOVERNANCE` now covers only the glossary, and the new `GAP-PRD-GOVERNANCE` takes mandatory constraints, governance and audit (PRD section 11, brief v2 §5.11). Both carry their own en/es elicitation text.
- Anchors that hold, deterministic part (IMP-258).
  - **Findings:** for a brief v2, `/validate` now reports, line by line:
    - a statement with no citation, outside the closed list of exemptions (`templates/anchor_exempt.json`: places such as §0, §7, §8 and provenance; line kinds such as pending marks, N/A, inferences, pointers, tables and computed verdicts);
    - a `sources` citation whose F-NN row does not exist;
    - a source that is superseded, retired or expired;
    - an echo (an artifact Sentinel wrote);
    - a line that names two gaps while its anchors hold only one. One anchor per subject.
  - **Count:** `sentinel.anchors.anchor_report` also counts the sites (n of n anchors hold).
  - **Evals:** `tests/evals/run_anchor_evals.py` runs synthetic fixtures with seeded defects, correct symmetries, exempt distractors and a held-out split. It fails on a miss, an extra finding, or a drop below the floor in `metric_baseline.json`. It runs in `verify.ps1` and CI.
- Counterpart and cross-cutting scenarios (IMP-256).
  - **Proximity:** a mentioned surface needs its counterpart near the mention (the same sentence or one sentence around it), or in a domain context folder. Before, one counterpart word anywhere in the document suppressed the gap. With no mention, the document-wide test stays, and a check can opt out with `"counterpart_scope": "document"`.
  - **15 counterpart rows** as lens data (`GAP-CTP-*`, medium, never blocking by themselves): integration, state, exclusion, flag, event, batch job, alert, personal data, deadline, write endpoint (idempotency), SLO, regulation (article), error code, design exclusion and manual step. Each carries its own en/es title, question, expected format, why and example, and the gap lookups read them first.
  - **Brief v2:** §3.6 renders the referral table of the 16 cross-cutting scenarios (`templates/cross_cutting.json`), with each scenario's status read from the places that specify it. It refers and never repeats, so it adds no marks. The §4.1 screen-states mark lists the 8 fixed states and the two distinctions.
  - **Vague wording:** `weak_words` gains contracted enumerations ("etc.", "entre otros") and vagueness ("should", "debería", "en general", "según corresponda") for business rules and acceptance.
  - **Metric floor:** `tests/evals/metric_baseline.json` holds the discovery eval metrics measured before this IMP. The eval run fails if any of them drops (`--update-metric-baseline` raises the floor on purpose).
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
