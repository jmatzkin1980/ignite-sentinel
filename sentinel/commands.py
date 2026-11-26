"""IMP-303 (H18): the single command registry.

Each command is declared once, here: its name, its place in the command protocol,
whether it takes ``--release``, its MCP tool and its arguments. The CLI parser,
``cli.COMMANDS``, the protocol sets (``protocols.py``), the release commands
(``release_scope.py``) and the runtime list the adapters compare with the manifest
all come from this registry. ``tests/test_command_registry.py`` checks the rest
against it: MCP tools and their parameters, the commands manifest, the router skill
and ``user_guide/01-command-reference.md``.

Stdlib only; it imports nothing from the rest of the package.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from typing import Callable

READ_ONLY = "read-only"
MUTATING = "mutating"
EXEMPT = "exempt"

VIEW_ARTIFACTS = frozenset({"gaps", "brief", "prd", "specs", "backlog", "readiness", "release-guide", "prototype",
                            "prototype-trace", "prototype-manual", "diagrams", "borde", "decisiones"})
EXPORT_ARTIFACTS = ("gaps", "brief", "context-request", "prd", "borde", "decisiones")


@dataclass(frozen=True)
class Command:
    """One command of the runtime.

    ``mcp_params`` maps an MCP tool parameter to the CLI destinations it covers when
    the names differ (``open_browser`` covers ``open``; a ``mode`` covers a mutually
    exclusive group). ``mcp_omits`` names CLI destinations the MCP tool leaves out on
    purpose, each with its reason.
    """

    name: str
    protocol: str
    configure: Callable[[argparse.ArgumentParser], None]
    exempt_reason: str = ""
    release: bool = False
    mcp: bool = True
    mcp_params: dict[str, tuple[str, ...]] = field(default_factory=dict)
    mcp_omits: dict[str, str] = field(default_factory=dict)
    # IMP-408: the skill that carries the command's work; skill_variants maps a substring of the command to another skill
    skill: str = ""
    skill_variants: tuple[tuple[str, str], ...] = ()

    @property
    def tool(self) -> str:
        return self.name.replace("-", "_")


def _project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")


def _project_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--source", required=True)


def _project_source_change(parser: argparse.ArgumentParser) -> None:
    _project_source(parser)
    parser.add_argument("--change", metavar="CHG-NNN", help="IMP-418: review this change's request, brief and gaps instead of the project's")


def _assume(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--source", help="the assumptions JSON (project: required; change: or --id with --validate|--invalidate)")
    # IMP-412: the assumptions of a change close its question; --validate/--invalidate move one
    parser.add_argument("--change", metavar="CHG-NNN", help="IMP-412: register the assumptions of this change (they close its question)")
    parser.add_argument("--id", metavar="ASM-ID", help="IMP-412: the change assumption to validate or invalidate")
    parser.add_argument("--validate", action="store_true", help="IMP-412: the assumption holds; the question keeps its closure")
    parser.add_argument("--invalidate", action="store_true", help="IMP-412: the assumption fails; the question opens again")
    parser.add_argument("--reason", help="IMP-412: why it was validated or invalidated")


def _resolve_gaps(parser: argparse.ArgumentParser) -> None:
    _project_source(parser)
    # IMP-382: answer this change's gaps (and confirm its border) instead of the project's
    parser.add_argument("--change", metavar="CHG-NNN", help="IMP-382: resolve this change's gaps instead of the project's")


def _harvest(parser: argparse.ArgumentParser) -> None:
    _project_source(parser)
    # IMP-384: send the harvest's gaps to this change instead of the project's
    parser.add_argument("--change", metavar="CHG-NNN", help="IMP-384: open the harvest's gaps in this change instead of the project's")


def _ingest(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--source", required=True)
    # IMP-320: replace the primary requirement on purpose; without it a second /ingest is refused.
    parser.add_argument("--replace", action="store_true")
    # IMP-382: open a change (CHG-nnn) on an existing system instead of the project's requirement.
    parser.add_argument("--change", action="store_true")


def _project_override(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--override")


def _doctor(p: argparse.ArgumentParser) -> None:
    p.add_argument("--root", default=".")


def _dashboard(p: argparse.ArgumentParser) -> None:
    p.add_argument("--root", default=".")
    p.add_argument("--open", action="store_true")
    p.add_argument("--theme", default=None, help="built-in theme name or path to a local theme JSON (default: neutral)")


def _view(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--artifact", required=True, choices=sorted(VIEW_ARTIFACTS))
    p.add_argument("--open", action="store_true")
    p.add_argument("--theme", default=None, help="built-in theme name or path to a local theme JSON (default: workspace config theme, else neutral)")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-386: view this change's brief or gaps (views/CHG-nnn-<artifact>.html)")


def _init(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--brief-version", type=int, choices=(1, 2), help="IMP-26w: 2 (default) compiles the brief v2; 1 keeps v1")


def _retrieve(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--query")
    p.add_argument("--workflow")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--artifact-type")
    p.add_argument("--domain")
    p.add_argument("--trace-id")
    p.add_argument("--iteration-min", type=int, default=1)
    p.add_argument("--status")
    p.add_argument("--language")
    p.add_argument("--sensitivity")
    p.add_argument("--section")
    p.add_argument("--max-chars", type=int)
    p.add_argument("--summary-only", action="store_true")
    p.add_argument("--write-pack", action="store_true")
    # IMP-126: recency-first ordering and a read-only episodic timeline.
    p.add_argument("--order", choices=["relevance", "recency"], default="relevance")
    p.add_argument("--timeline", action="store_true")


def _sync(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--source")
    p.add_argument("--note", default="")
    p.add_argument("--digest", action="store_true")
    p.add_argument("--analysis", help="IMP-337: an agent's cited change analysis of the --source note (JSON); "
                                      "each valid candidate opens a blocking GAP-CHG")
    # H27 inc 6a: /sync --change CHG-nnn loads the change's new source by role (--source goes with --role)
    p.add_argument("--change", help="H27: sync this change: load --source PATH --role ROLE (or scan the role folders), "
                                    "confirm the version and re-cross what it touched")
    p.add_argument("--role", help="H27: with --change and --source: pedido|linea_de_base|plan_previo|diseno_nuevo")
    p.add_argument("--supersedes", help="H27: with --change and --source: the F-NN row this source replaces")


def _scrutinize(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--source", required=True)
    p.add_argument("--lens")
    p.add_argument("--mode", default="scrutiny", choices=["scrutiny", "implementability-probe", "anchors"])
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-418: review this change's request, brief and gaps instead of the project's")


def _split(p: argparse.ArgumentParser) -> None:  # IMP-263/265/266 (H17a): release series
    p.add_argument("project_id")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--assess", action="store_true",
                      help="deterministic split signals over the brief v2: split, no split or cannot decide")
    mode.add_argument("--propose", action="store_true",
                      help="IMP-265: validate an agent-written series proposal (--source PROPOSAL.json) and store it")
    mode.add_argument("--confirm", action="store_true",
                      help="IMP-266: validate the partition of the stored proposal and confirm it (--ba, --tech)")
    mode.add_argument("--move", action="store_true",
                      help="IMP-268: move a unit between releases (--unit, --from, --to, --reason, --ba, --tech)")
    mode.add_argument("--close", metavar="RELEASE",
                      help="IMP-269: close a release (every story Done, --evidence of its closing check, --ba, --tech)")
    p.add_argument("--evidence", help="--close: a local file with the result of the release's closing check")
    p.add_argument("--source", help="the proposal JSON for --propose")
    p.add_argument("--ba", help="the BA who confirms the partition (--confirm, --move)")
    p.add_argument("--tech", help="the technical team that confirms the partition (--confirm, --move)")
    p.add_argument("--unit", help="--move: the unit, a C-NN, a P-N or a quote of the brief")
    p.add_argument("--from", dest="from_holder", help="--move: the release (rN) or sketch (sketch:<name>) it leaves")
    p.add_argument("--to", dest="to_holder", help="--move: the release (rN) or sketch (sketch:<name>) it goes to")
    p.add_argument("--reason", help="--move: why the unit moves")
    p.add_argument("--finding", default="", help="--move: the finding that motivated it (F-NN, GAP-..., DEC-...)")
    p.add_argument("--criterion", default="", help="--move: the written cut criterion that decides a round trip")


def _prototype(p: argparse.ArgumentParser) -> None:  # IMP-274/275/276 (H17b): HTML prototypes
    p.add_argument("project_id")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory", action="store_true",
                      help="inventory of visible elements per screen and JS copy of the ingested HTML prototypes")
    mode.add_argument("--trace", action="store_true",
                      help="IMP-275: validate and store one screen trace (--source TRACE.json, sentinel-prototype-trace skill)")
    mode.add_argument("--manual", action="store_true",
                      help="IMP-276: validate and merge the user manual (--source MANUAL.json, sentinel-prototype-manual skill)")
    p.add_argument("--source", help="--inventory: only this source (F-NN); --trace/--manual: the JSON")
    p.add_argument("--change", metavar="CHG-NNN",
                   help="H27 inc 7a: the prototype of this change (its diseno_nuevo rows) instead of the project's")


def _self_review(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--source", help="the review payload (required unless --change --skip)")
    p.add_argument("--sufficiency", action="store_true",
                   help="IMP-259: a clean-context reader checks the brief v2 is enough to start building")
    p.add_argument("--crosses", action="store_true",
                   help="IMP-260b: semantic crosses between the lenses of the brief v2")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-410: with --crosses, the lens view of this change (--source PATH or --skip --reason)")
    p.add_argument("--skip", action="store_true", help="IMP-410: with --crosses --change, waive the coherence reading (needs --reason)")
    p.add_argument("--reason", help="IMP-410: why the coherence reading is waived")


def _story_status(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--story", required=True)
    p.add_argument("--set", required=True, dest="status")
    p.add_argument("--owner")
    p.add_argument("--evidence")


def _context_request(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--domain", choices=["technology", "design", "quality", "frontend", "backend"])
    p.add_argument("--id", dest="request_id")  # IMP-294: move a CTX along its lifecycle
    p.add_argument("--status", choices=["active", "answered", "closed", "obsolete"])
    p.add_argument("--reason", default="")


def _stakeholders(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--add", action="store_true")
    p.add_argument("--id", dest="stakeholder_id")
    p.add_argument("--name")
    p.add_argument("--domain")
    p.add_argument("--topic", default="")
    p.add_argument("--profile")
    p.add_argument("--notes", default="")


def _sources(p: argparse.ArgumentParser) -> None:  # IMP-250a: F-NN source registry
    p.add_argument("project_id")
    p.add_argument("--id", dest="source_id")
    p.add_argument("--from", dest="from_who")
    p.add_argument("--superseded-by", dest="superseded_by")
    p.add_argument("--retire", action="store_true")
    p.add_argument("--replacement")
    p.add_argument("--expire", metavar="YYYY-MM-DD")
    p.add_argument("--topic")
    p.add_argument("--current", action="store_true")
    p.add_argument("--close", action="store_true")
    p.add_argument("--reason")
    # IMP-250b: authority, impact matrix cells, precedence and the closing report.
    p.add_argument("--authority")
    p.add_argument("--cell", metavar="DOCUMENT/SECTION")
    p.add_argument("--mark", choices=["updated", "reviewed", "pending"])
    p.add_argument("--precedence", metavar="SCOPE")
    p.add_argument("--between", metavar="F-NN,F-NN")
    p.add_argument("--report", action="store_true")
    # IMP-400: load a source with the role it plays in a change, or fix a row's role.
    p.add_argument("--load", metavar="PATH", help="IMP-400: register this file with --role (a redacted copy in the role's folder)")
    p.add_argument("--role", help="IMP-400: pedido, linea_de_base, plan_previo or diseno_nuevo")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-400: with --load, the change this source belongs to")
    p.add_argument("--derived-from", dest="derived_from", metavar="F-NN",
                   help="H27 inc 7a: with --load --role diseno_nuevo, the original prototype this readable copy derives from")
    p.add_argument("--reliability", metavar="documental|codigo|mixta",
                   help="H27 inc 7a: with --load --role linea_de_base, how the baseline was read; documental and mixta are partial: "
                        "a NOT FOUND against them asks to confirm")
    p.add_argument("--no-baseline", action="store_true", dest="no_baseline",
                   help="IMP-400: with --change and --reason, the change has no baseline to load")
    p.add_argument("--keep-single", action="store_true", dest="keep_single",
                   help="T2-05: with --change and --reason, the BA decides the change stays one change")


def _export(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--artifact", required=True, choices=list(EXPORT_ARTIFACTS))
    p.add_argument("--format", "--fmt", default="md", choices=["md", "mdx", "interview", "faq"])
    p.add_argument("--domain")
    p.add_argument("--final", action="store_true", help="IMP-272: refuse to export while pending marks remain")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-386: export this change's brief, gaps, borde or decisiones (exports/CHG-nnn-<name>)")


def _backlog(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--with-task-seeds", action="store_true")
    p.add_argument("--story-format", choices=("user", "job"), default=None)
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-393: build this change's stories (one epic per change) instead of the project's")


def _status(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--full", action="store_true")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-396: where this change stands instead of the project")


def _next(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-396: the next step of this change instead of the project's")


def _extract(p: argparse.ArgumentParser) -> None:  # IMP-402: extraction of a change request with coverage
    p.add_argument("project_id")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-402: the change whose request is extracted; IMP-420: omit it for the project's request")
    p.add_argument("--proposals", metavar="PATH", help="IMP-402: record the cited proposals in this file")
    p.add_argument("--confirm", metavar="SECTION|all", help="IMP-402: confirm the proposals of a section (or all); flagged ones are held")
    p.add_argument("--confirm-item", dest="confirm_item", metavar="ID", help="IMP-402: confirm one proposal, flagged or not")
    p.add_argument("--reject-item", dest="reject_item", metavar="ID", help="IMP-402: take one element back to pending (needs --reason)")
    p.add_argument("--reason", help="IMP-402: with --reject-item, why")
    p.add_argument("--verify", action="store_true", help="IMP-406: draw a sample of the confirmed elements to re-read against the request")
    p.add_argument("--sample", type=int, metavar="N", help="IMP-406: with --verify, how many elements (default 10)")
    p.add_argument("--verify-result", dest="verify_result", metavar="PATH", help="IMP-406: record the results of the open verification")
    p.add_argument("--consolidate", metavar="PATH",
                   help="IMP-414: record the text of the elements with the decision applied, one block per element")
    p.add_argument("--confirm-replacement", dest="confirm_replacement", metavar="ID",
                   help="IMP-414: confirm the replacement text of one element")
    p.add_argument("--keep-text", dest="keep_text", metavar="ID",
                   help="IMP-414: keep the request text of one element although a closed decision touches it (needs --gap and --reason)")
    p.add_argument("--gap", metavar="GAP", help="IMP-414: with --keep-text, the decision that touches the element")
    p.add_argument("--delegated", action="store_true",
                   help="IMP-412: confirm on behalf of the BA; recorded apart and listed to review")
    p.add_argument("--note", help="IMP-412: with --delegated, what the BA delegated")


def _cross(p: argparse.ArgumentParser) -> None:  # IMP-404: registered cross-reads of a change request
    p.add_argument("project_id")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-404: the change whose request is cross-read; IMP-420: omit it for the project's request")
    p.add_argument("--kind", metavar="TYPE", help="IMP-404: diseno, contradicciones or linea_de_base (with --claims or --skip)")
    p.add_argument("--claims", metavar="PATH", help="IMP-404: record the cited cross-read in this file")
    p.add_argument("--skip", action="store_true", help="IMP-404: waive the cross-read of --kind (needs --reason)")
    p.add_argument("--reason", help="IMP-404: with --skip or --decline-new, why")
    p.add_argument("--accept-new", dest="accept_new", metavar="ID", help="IMP-404: accept a new-surface candidate (needs --type and --name)")
    p.add_argument("--type", dest="surface_type", metavar="TYPE", help="IMP-404: with --accept-new, the surface type")
    p.add_argument("--name", help="IMP-404: with --accept-new, the surface name")
    p.add_argument("--decline-new", dest="decline_new", metavar="ID", help="IMP-404: decline a new-surface candidate (needs --reason)")
    p.add_argument("--delta", action="store_true",
                   help="IMP-418: with --claims, replace only the claims a new source touched and keep the rest with their questions")


def _brief(p: argparse.ArgumentParser) -> None:  # IMP-252: the BA confirms profile, genesis and validation direction
    p.add_argument("project_id")
    p.add_argument("--profile", help="comma-separated: UI,API,BAT,INT,MIG,REG,MT")
    p.add_argument("--genesis", help="greenfield|brownfield-integration|brownfield-extension|brownfield-replacement (comma-separated when mixed)")
    p.add_argument("--validation-direction", choices=("to-build", "built"))
    p.add_argument("--brief-version", type=int, choices=(1, 2), help="switch the project's brief compiler: 2 (the default for new projects) compiles the brief v2; 1 keeps v1")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-386: compile this change's brief instead of the project's")


def _specs(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-388: build this change's spec units instead of the project's")


def _validate(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--override")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-396: validate this change's artifacts instead of the project's")


def _gaps(p: argparse.ArgumentParser) -> None:  # IMP-271 / F7: BA disposition on a gap an agentic channel raised
    p.add_argument("project_id")
    p.add_argument("--id", dest="gap_id")
    p.add_argument("--disposition", choices=("accepted", "rejected", "irrelevant"))
    p.add_argument("--reason", default="")
    p.add_argument("--impact", choices=("construccion", "operativo"),
                   help="IMP-406: class of a deferred question of a change (with --change, --id and --reason)")
    p.add_argument("--change", metavar="CHG-NNN", help="IMP-382: regenerate this change's gaps instead of the project's")
    p.add_argument("--accept-prior", action="store_true",
                   help="IMP-410: close a pre-decided question of a change with its earlier decision (with --change and --id)")
    p.add_argument("--top", type=int, help="IMP-257: plan the next round of at most N questions; without it /gaps regenerates gaps.md")


def _trace(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    # IMP-369: record the BA review of a semantic change /health flagged (CHG-NNN)
    p.add_argument("--reviewed", metavar="CHG-NNN")
    p.add_argument("--reason", default="")


def _reindex(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--full", action="store_true")


ROOT_OMIT = {"root": "the MCP server runs at the repository root; --root is a CLI convenience"}

REGISTRY: tuple[Command, ...] = (
    Command("doctor", EXEMPT, _doctor, exempt_reason="environment check over the repository, no project workspace",
            mcp_omits=ROOT_OMIT, skill="sentinel-health"),
    Command("dashboard", EXEMPT, _dashboard, exempt_reason="read-only portfolio view across workspaces, no single project",
            mcp_params={"open_browser": ("open",)}, mcp_omits=ROOT_OMIT, skill="sentinel-views"),
    Command("view", READ_ONLY, _view, release=True, mcp_params={"open_browser": ("open",)}, skill="sentinel-views"),
    Command("init", EXEMPT, _init, exempt_reason="creates the workspace (state.json) that the protocol log needs", skill="sentinel-discovery"),
    Command("ingest", MUTATING, _ingest, skill="sentinel-discovery"),
    Command("retrieve", READ_ONLY, _retrieve, skill="sentinel-sync"),
    Command("sync", MUTATING, _sync, skill="sentinel-sync", skill_variants=(("--change", "sentinel-sync §Change sync"),)),
    Command("resolve-gaps", MUTATING, _resolve_gaps, skill="sentinel-gap-response"),
    Command("annotate", MUTATING, _project_source_change, skill="sentinel-annotate", skill_variants=(("--change", "sentinel-annotate §Change"),)),
    Command("challenge", MUTATING, _project_source_change, skill="sentinel-challenge", skill_variants=(("--change", "sentinel-challenge §Change"),)),
    Command("scrutinize", MUTATING, _scrutinize, skill="sentinel-scrutiny", skill_variants=(("--change", "sentinel-scrutiny §Change"),)),
    Command("harvest", MUTATING, _harvest, skill="sentinel-brownfield-harvest"),  # IMP-262
    # IMP-263: /split --assess writes 01_discovery/split_assessment.md and its JSON.
    Command("split", MUTATING, _split,
            mcp_params={"mode": ("assess", "propose", "confirm", "move", "close"), "release": ("close",)}, skill="sentinel-release-split"),
    # IMP-274: /prototype --inventory writes 02_requirements/prototype/inventory.json and .md.
    Command("prototype", MUTATING, _prototype, mcp_params={"mode": ("inventory", "trace", "manual")}, skill="sentinel-prototype-trace", skill_variants=(("--manual", "sentinel-prototype-manual"),)),
    Command("self-review", MUTATING, _self_review, skill="sentinel-self-review", skill_variants=(("--change", "sentinel-self-review §Change coherence"),)),
    Command("assume", MUTATING, _assume, skill="sentinel-assume", skill_variants=(("--change", "sentinel-assume §Change assumptions"),)),
    Command("compose", MUTATING, _project_source, skill="sentinel-compose"),
    Command("refine-backlog", MUTATING, _project_source, skill="sentinel-backlog-refine"),
    Command("implementation-feedback", MUTATING, _project_source, skill="sentinel-implementation-feedback"),
    Command("story-status", MUTATING, _story_status, release=True, skill="sentinel-backlog"),
    Command("context-request", MUTATING, _context_request, mcp_params={"id": ("request_id",)}, skill="sentinel-domain-request"),
    Command("next", READ_ONLY, _next, release=True, skill="sentinel-command-router"),  # IMP-294: the next step of /status, alone
    # IMP-244: /stakeholders writes the stakeholder registry, so it is logged and snapshotted
    # like every other writer (listing goes through it too; cost is negligible).
    Command("stakeholders", MUTATING, _stakeholders, mcp_params={"id": ("stakeholder_id",)}, skill="sentinel-discovery"),
    # IMP-250a: /sources rewrites the F-NN registry and its source_log render.
    Command("sources", MUTATING, _sources, mcp_params={"id": ("source_id",)}, skill="sentinel-sync", skill_variants=(("--keep-single", "sentinel-discovery §Delegate, extensions, speculative marks and conflicts"),)),
    Command("extract", MUTATING, _extract, skill="sentinel-discovery §Extraction of a change", skill_variants=(("--consolidate", "sentinel-project-brief §Consolidating the change brief"), ("--confirm-replacement", "sentinel-project-brief §Consolidating the change brief"), ("--keep-text", "sentinel-project-brief §Consolidating the change brief"))),  # IMP-402, IMP-414
    Command("cross", MUTATING, _cross, skill="sentinel-discovery §Cross-reads of a change"),  # IMP-404
    Command("export", MUTATING, _export, skill="sentinel-discovery", skill_variants=(("--artifact brief", "sentinel-project-brief"), ("--artifact prd", "sentinel-specs"), ("--artifact borde", "sentinel-views §Review views of a change"), ("--artifact decisiones", "sentinel-views §Review views of a change"))),
    Command("backlog", MUTATING, _backlog, release=True, skill="sentinel-backlog"),
    # IMP-306: /maturity rewrites its report, the readiness matrix and the brief.
    Command("maturity", MUTATING, _project, skill="sentinel-maturity"),
    Command("specs", MUTATING, _specs, release=True, skill="sentinel-specs"),
    Command("backlog-status", MUTATING, _project_override, skill="sentinel-backlog"),
    Command("quality", MUTATING, _project_override, release=True, skill="sentinel-quality"),
    Command("health", READ_ONLY, _project, skill="sentinel-health"),
    # IMP-306: /trace rewrites the traceability matrix and graph.
    Command("trace", MUTATING, _trace, release=True, skill="sentinel-health"),
    Command("validate", READ_ONLY, _validate, release=True, skill="sentinel-health"),
    Command("gaps", MUTATING, _gaps, mcp_params={"id": ("gap_id",)}, skill="sentinel-discovery"),
    Command("brief", MUTATING, _brief, skill="sentinel-project-brief"),
    Command("status", READ_ONLY, _status, release=True, skill="sentinel-command-router"),
    Command("reindex", MUTATING, _reindex, skill="sentinel-sync"),
)

BY_NAME: dict[str, Command] = {command.name: command for command in REGISTRY}
COMMANDS: frozenset[str] = frozenset(BY_NAME)
READ_ONLY_COMMANDS: frozenset[str] = frozenset(c.name for c in REGISTRY if c.protocol == READ_ONLY)
MUTATING_COMMANDS: frozenset[str] = frozenset(c.name for c in REGISTRY if c.protocol == MUTATING)
PROTOCOL_EXEMPT_COMMANDS: dict[str, str] = {c.name: c.exempt_reason for c in REGISTRY if c.protocol == EXEMPT}
RELEASE_COMMANDS: tuple[str, ...] = tuple(c.name for c in REGISTRY if c.release)
MCP_TOOLS: frozenset[str] = frozenset(c.tool for c in REGISTRY if c.mcp)

_VERB = re.compile(r"(?:^|\s)/([a-z][a-z-]*)\b")
_RUN_PREFIX = re.compile(r"^(Run|Corré|Correr|Ejecutá)\s+/")


def skill_for_command(command: str) -> str:
    """IMP-408: the skill of the first `/verb` of a command line that the registry knows ("" if none)."""
    for found in _VERB.finditer(command):
        entry = BY_NAME.get(found.group(1))
        if entry is None:
            continue
        for fragment, variant in entry.skill_variants:
            if fragment in command:
                return variant
        return entry.skill
    return ""


def skill_for_next_text(text: str) -> str:
    """IMP-408: the skill of a next-step text, only when the text is a command to run."""
    if text.startswith("/") or _RUN_PREFIX.match(text):
        return skill_for_command(text)
    return ""


def build_parser() -> argparse.ArgumentParser:
    """The CLI parser, built from the registry."""
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Ignite Sentinel vNext Core BA CLI. Commands accept slash aliases, e.g. `/maturity PROJECT_ID`.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in REGISTRY:
        command_parser = sub.add_parser(command.name)
        command.configure(command_parser)
        if command.release:
            # IMP-267b: derive for one release of a confirmed series (outputs under <folder>/<rN>/)
            command_parser.add_argument("--release", help="a release of the confirmed series (r<N> or r<N>.<M>)")
    return parser


def cli_destinations(name: str) -> set[str]:
    """The destinations of one command's CLI arguments (``project_id``, ``source``, ``open``...)."""
    parser = argparse.ArgumentParser(add_help=False)
    command = BY_NAME[name]
    command.configure(parser)
    dests = {action.dest for action in parser._actions}
    if command.release:
        dests.add("release")
    return dests


def cli_options(name: str) -> dict[str, tuple[str, bool]]:
    """IMP-333: each optional destination of one command -> (its first option string, whether it is a bare flag)."""
    parser = argparse.ArgumentParser(add_help=False)
    command = BY_NAME[name]
    command.configure(parser)
    if command.release:
        parser.add_argument("--release")
    return {action.dest: (action.option_strings[0], action.nargs == 0) for action in parser._actions if action.option_strings}
