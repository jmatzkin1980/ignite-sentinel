# Flow and step matrix

Which skill, command and artifacts each step of Sentinel uses, per starting point. In chat you do not need to read this page to work: ask what you want ("tengo estos documentos, ¿por dónde arranco?") and the agent starts with the entry check of `sentinel-intake-triage`. This page is the reference behind that answer, and a test keeps it equal to what `/next` says.

## Starting points

You arrive with a different pile each time. Discovery always ends in a mature project brief, but it starts from different places: the agent recognizes where you start and takes the shortest path, and what arrives mature is verified with a citation, never redone.

| Starting point | What arrives | Path | Verification-only steps | First commands |
|---|---|---|---|---|
| A. New project, short request | a few lines | project | none | `/init P`, `/ingest P --source PEDIDO`, then the rounds with `/resolve-gaps` |
| B. New project, mature external brief | a large brief, nothing built | project (or series if it already splits into releases) | the brief is extracted and confirmed with a citation, not rewritten (change-only today; inc 6 brings extraction to the project) | `/init P`, `/ingest P --source BRIEF`, `/sync P --source DOC` for each further document |
| C. Change on something built, everything mature | request, baseline, previous plan, design | change | the cross-reads done by hand are registered with `/cross --claims`; structured answers are transcribed into the response format | `/init P`, `/ingest P --source PEDIDO --change`, `/sources P --load DOC --role linea_de_base --change CHG-001` (and `plan_previo`, `diseno_nuevo`) |
| D. Change with a partial or documentary baseline | a survey from a wiki, no code | change | the baseline is loaded by role; its reliability staying visible comes with inc 7 | `/sources P --load DOC --role linea_de_base --change CHG-001`; `/harvest P --source HARVEST.md --change CHG-001` once the code is accessible |
| E. Change without design | no prototype | change | the design cross is `no_aplica` | `/ingest P --source PEDIDO --change`, `/sources P --load DOC --role linea_de_base --change CHG-001` |
| F. Design in Figma, images or JS | a non-textual prototype | change | none today: a non-textual design is asked for as an HTML or text export or left pending; reading renders as a derived source with provenance comes with inc 7 | `/sources P --load DOC --role diseno_nuevo --change CHG-001`, `/prototype P --inventory` |
| G. Several versions of the request | r2 v5, v6 … | change | the versions are listed and the BA says which governs | `/sources P --load DOC --role pedido --change CHG-001`, then `/sources P --id F-NN --superseded-by F-MM` when the BA decides |
| H. Resume after weeks or by another person | a workspace halfway | project or change | none: read what was decided before asking again | `/status P`, `/next P` (with `--change CHG-001` for a change) |
| I. Review with third parties | Sentinel artifacts | project or change | none | `/export P --artifact gaps --format interview`, `/view P --artifact brief` |
| J. Agent without expert guide | a BA who does not know the commands | the entry check decides | the entry check names what is mature | start with the entry check of `sentinel-intake-triage`: it classifies each document, picks the path and gives the first commands with roles |

## Project path

You ask "what is next?" and `/next P` gives one step. The table lists every step it can give, the command it names and the skill to load before running it.

| Step | Command | Skill | Reads | Writes |
|---|---|---|---|---|
| `ingest` | `/ingest P --source PATH` | sentinel-discovery | the first request file (`--source`) | `00_raw/`, `01_discovery/gaps.md`, `01_discovery/gap_questions.md` |
| `brief_settings` | `/brief P --profile {profiles} --genesis {genesis}` | sentinel-project-brief | the raw input, `state.json` | the brief profile and genesis in `state.json` |
| `resolve_blocking` | `/resolve-gaps P --source PATH` | sentinel-gap-response | the response file (`--source`), `01_discovery/gaps.md` | `01_discovery/gaps.md`, `01_discovery/decision_log.md` |
| `fix_brief` | `/brief P` | sentinel-project-brief | the findings `/brief` reported, `01_discovery/gaps.md` | `02_requirements/project-brief.md` on the next `/brief` |
| `specs` | `/specs P` | sentinel-specs | `02_requirements/project-brief.md` | `03_specs/`, the PRD |
| `fix_specs` | `/specs P` | sentinel-specs | the specs readiness report, `01_discovery/gaps.md` | `03_specs/` on the next `/specs` |
| `backlog` | `/backlog P` | sentinel-backlog | `03_specs/` | `04_backlog/` |
| `quality` | `/quality P` | sentinel-quality | `04_backlog/` | `05_quality/` |
| `resolve_gaps` | `/resolve-gaps P --source PATH` | sentinel-gap-response | the response file (`--source`), `01_discovery/gaps.md` | `01_discovery/gaps.md`, `01_discovery/decision_log.md` |
| `brief` | `/brief P` | sentinel-project-brief | `01_discovery/gaps.md`, the sources | `02_requirements/project-brief.md` |
| `brief_missing` | `/brief P` | sentinel-project-brief | `01_discovery/gaps.md`, the sources | `02_requirements/project-brief.md` |
| `health` | `/health P` | sentinel-health | the whole workspace (read-only) | nothing: it reports the findings |
| `handoff` | `/validate P` | sentinel-health | `04_backlog/`, `05_quality/`, `06_traceability/` | `06_traceability/` report; exports with `/export` |

## Change path

For a change to something built, `/next P --change CHG-001` gives the first step still pending, in this order. The last column says which step of the project path does the same job, or why there is none.

| Step | Command | Skill | Reads | Writes | Project equivalent |
|---|---|---|---|---|---|
| `scope` | `/resolve-gaps P --source PATH --change CHG-001` | sentinel-gap-response | the scope response file, `01_discovery/CHG-nnn/` | `01_discovery/CHG-nnn/` scope and border | `resolve_blocking` — the same rounds and /resolve-gaps |
| `baseline` | `/sources P --load PATH --role linea_de_base --change CHG-001` | sentinel-sync | the document of what is built (`--load PATH`) | `00_raw/` copy, `07_changes/source_log.md` | none — the project path has no baseline yet; inc 6 reconnects loading by role to the project |
| `lenses` | `/resolve-gaps P --source PATH --change CHG-001` | sentinel-gap-response | the response file, `01_discovery/CHG-nnn/gaps.md` | `01_discovery/CHG-nnn/gaps.md` | `resolve_blocking` — the same rounds and /resolve-gaps |
| `crosses` | `/cross P --change CHG-001` | sentinel-discovery §Cross-reads of a change | the cross-read file with verbatim quotes | `01_discovery/CHG-nnn/crosses/` | none — /cross is change-only today; inc 6 reconnects it to the project |
| `cross_new_surfaces` | `/cross P --change CHG-001 --accept-new {first_candidate} --type TIPO --name NOMBRE` | sentinel-discovery §Cross-reads of a change | the new-surface candidates of the crosses | the border of the change | none — a new surface only exists against the confirmed border of something built |
| `coherence_view` | `/self-review P --crosses --change CHG-001` | sentinel-self-review §Change coherence | none | `01_discovery/CHG-nnn/coherence/view.md`, `checks.json` | none — the project runs the same engine (/self-review --crosses, IMP-260) on demand, not as a /next step |
| `coherence` | `/self-review P --crosses --change CHG-001 --source PATH` | sentinel-self-review §Change coherence | the semantic crosses JSON | `01_discovery/CHG-nnn/coherence/coherence.json`, `coherence.md` | none — the project runs the same engine (/self-review --crosses, IMP-260) on demand, not as a /next step |
| `extract_inventory` | `/extract P --change CHG-001` | sentinel-discovery §Extraction of a change | the request (`pedido` source) | the inventory of `01_discovery/CHG-nnn/extraction/` | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_unreadable` | `/sources P --load PATH --role pedido --change CHG-001` | sentinel-sync | the request file that could not be read | `07_changes/source_log.md` | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_proposals` | `/extract P --change CHG-001 --proposals PATH` | sentinel-discovery §Extraction of a change | the proposals file (`--proposals PATH`) | the proposals in `01_discovery/CHG-nnn/extraction/` | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_confirm` | `/extract P --change CHG-001 --confirm all` | sentinel-discovery §Extraction of a change | the proposals of the extraction | the confirmed rows of the extraction | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_confirm_flagged` | `/extract P --change CHG-001 --confirm-item {first_flagged}` | sentinel-discovery §Extraction of a change | the flagged proposal | the confirmed row of the extraction | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_partial` | `/extract P --change CHG-001 --proposals PATH` | sentinel-discovery §Extraction of a change | the partial proposals | the completed proposals of the extraction | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_orphans` | `/extract P --change CHG-001 --reject-item {first_orphan} --reason "..."` | sentinel-discovery §Extraction of a change | the rows that cite no line of the request | the rejected row with its reason | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `preserved` | `/extract P --change CHG-001 --proposals PATH` | sentinel-discovery §Extraction of a change | the confirmed border, the proposals | the UNCHANGED rows of the extraction | none — only a change preserves existing behavior (UNCHANGED rows) |
| `preserved_answer` | `/resolve-gaps P --source PATH --change CHG-001` | sentinel-gap-response | the response file | `01_discovery/CHG-nnn/gaps.md` | none — only a change preserves existing behavior (UNCHANGED rows) |
| `preserved_source` | `/sources P --load PATH --role pedido --change CHG-001` | sentinel-sync | the request file that holds the preserved surface | `07_changes/source_log.md` | none — only a change preserves existing behavior (UNCHANGED rows) |
| `brief` | `/brief P --change CHG-001` | sentinel-project-brief | the extraction and the gaps of the change | `02_requirements/CHG-nnn/` brief | `brief` — the brief compiler |
| `requirements` | `/resolve-gaps P --source PATH --change CHG-001` | sentinel-gap-response | the response file, the brief of the change | the EARS rows of the change | `resolve_gaps` — the same response format |
| `export_final` | `/export P --artifact brief --change CHG-001 --final` | sentinel-project-brief | the brief of the change, its seal | the final brief export (brief v2 format) | none — the project exports its brief without a milestone; inc 5 reconnects the change deliverable to the project compilers |
| `export_not_ready` | `/gaps P --change CHG-001 --id {first_deferred} --impact construccion\|operativo --reason "..."` | sentinel-discovery | the deferred items of the brief | the impact of each gap in `01_discovery/CHG-nnn/gaps.md` | none — the project exports its brief without a milestone; inc 5 reconnects the change deliverable to the project compilers |
| `extract_verify` | `/extract P --change CHG-001 --verify` | sentinel-discovery §Extraction of a change | a sample of confirmed rows, the request | the verification sample | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `extract_verify_result` | `/extract P --change CHG-001 --verify-result PATH` | sentinel-discovery §Extraction of a change | the verification result file | the reopened or verified rows | none — extraction with line coverage is change-only; inc 6 reconnects it to the project (§2b) |
| `specs` | `/specs P --change CHG-001` | sentinel-specs | the EARS rows of the change | `03_specs/CHG-nnn/` | `specs` — the specs compiler |
| `backlog` | `/backlog P --change CHG-001` | sentinel-backlog | `03_specs/CHG-nnn/` | `04_backlog/` stories of the change | `backlog` — the backlog compiler |
| `validate` | `/validate P --change CHG-001` | sentinel-health | the change and its derived files | nothing: it reports the findings | `handoff` — validate and hand off |
| `done` | — | — | the whole change | nothing | `handoff` — validate and hand off |

## Next

- [Workflows by situation](03-workflows.md)
- [Scenarios: worked examples](12-scenarios.md)
- [Driving Sentinel from chat](11-chat-commands.md)
- [Skills catalog](04-codex-skills-guide.md)
