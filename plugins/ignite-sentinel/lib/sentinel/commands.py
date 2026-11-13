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
from dataclasses import dataclass, field
from typing import Callable

READ_ONLY = "read-only"
MUTATING = "mutating"
EXEMPT = "exempt"

VIEW_ARTIFACTS = frozenset({"gaps", "brief", "prd", "specs", "backlog", "readiness", "release-guide", "prototype",
                            "prototype-trace", "prototype-manual", "diagrams"})
EXPORT_ARTIFACTS = ("gaps", "brief", "context-request", "prd")


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

    @property
    def tool(self) -> str:
        return self.name.replace("-", "_")


def _project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")


def _project_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_id")
    parser.add_argument("--source", required=True)


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


def _scrutinize(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--source", required=True)
    p.add_argument("--lens")
    p.add_argument("--mode", default="scrutiny", choices=["scrutiny", "implementability-probe", "anchors"])


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


def _self_review(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--source", required=True)
    p.add_argument("--sufficiency", action="store_true",
                   help="IMP-259: a clean-context reader checks the brief v2 is enough to start building")
    p.add_argument("--crosses", action="store_true",
                   help="IMP-260b: semantic crosses between the lenses of the brief v2")


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


def _export(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--artifact", required=True, choices=list(EXPORT_ARTIFACTS))
    p.add_argument("--format", "--fmt", default="md", choices=["md", "mdx", "interview", "faq"])
    p.add_argument("--domain")
    p.add_argument("--final", action="store_true", help="IMP-272: refuse to export while pending marks remain")


def _backlog(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--with-task-seeds", action="store_true")
    p.add_argument("--story-format", choices=("user", "job"), default=None)


def _status(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--full", action="store_true")


def _brief(p: argparse.ArgumentParser) -> None:  # IMP-252: the BA confirms profile, genesis and validation direction
    p.add_argument("project_id")
    p.add_argument("--profile", help="comma-separated: UI,API,BAT,INT,MIG,REG,MT")
    p.add_argument("--genesis", help="greenfield|brownfield-integration|brownfield-extension|brownfield-replacement (comma-separated when mixed)")
    p.add_argument("--validation-direction", choices=("to-build", "built"))
    p.add_argument("--brief-version", type=int, choices=(1, 2), help="2 compiles the brief v2 (opt-in per project)")


def _gaps(p: argparse.ArgumentParser) -> None:  # IMP-271 / F7: BA disposition on a gap an agentic channel raised
    p.add_argument("project_id")
    p.add_argument("--id", dest="gap_id")
    p.add_argument("--disposition", choices=("accepted", "rejected", "irrelevant"))
    p.add_argument("--reason", default="")
    p.add_argument("--top", type=int, help="IMP-257: the next round of at most N questions (default 5)")


def _reindex(p: argparse.ArgumentParser) -> None:
    p.add_argument("project_id")
    p.add_argument("--full", action="store_true")


ROOT_OMIT = {"root": "the MCP server runs at the repository root; --root is a CLI convenience"}

REGISTRY: tuple[Command, ...] = (
    Command("doctor", EXEMPT, _doctor, exempt_reason="environment check over the repository, no project workspace",
            mcp_omits=ROOT_OMIT),
    Command("dashboard", EXEMPT, _dashboard, exempt_reason="read-only portfolio view across workspaces, no single project",
            mcp_params={"open_browser": ("open",)}, mcp_omits=ROOT_OMIT),
    Command("view", READ_ONLY, _view, release=True, mcp_params={"open_browser": ("open",)}),
    Command("init", EXEMPT, _init, exempt_reason="creates the workspace (state.json) that the protocol log needs"),
    Command("ingest", MUTATING, _project_source),
    Command("retrieve", READ_ONLY, _retrieve),
    Command("sync", MUTATING, _sync),
    Command("resolve-gaps", MUTATING, _project_source),
    Command("annotate", MUTATING, _project_source),
    Command("challenge", MUTATING, _project_source),
    Command("scrutinize", MUTATING, _scrutinize),
    Command("harvest", MUTATING, _project_source),  # IMP-262
    # IMP-263: /split --assess writes 01_discovery/split_assessment.md and its JSON.
    Command("split", MUTATING, _split,
            mcp_params={"mode": ("assess", "propose", "confirm", "move", "close"), "release": ("close",)}),
    # IMP-274: /prototype --inventory writes 02_requirements/prototype/inventory.json and .md.
    Command("prototype", MUTATING, _prototype, mcp_params={"mode": ("inventory", "trace", "manual")}),
    Command("self-review", MUTATING, _self_review),
    Command("assume", MUTATING, _project_source),
    Command("compose", MUTATING, _project_source),
    Command("refine-backlog", MUTATING, _project_source),
    Command("implementation-feedback", MUTATING, _project_source),
    Command("story-status", MUTATING, _story_status, release=True),
    Command("context-request", MUTATING, _context_request, mcp_params={"id": ("request_id",)}),
    Command("next", READ_ONLY, _project, release=True),  # IMP-294: the next step of /status, alone
    # IMP-244: /stakeholders writes the stakeholder registry, so it is logged and snapshotted
    # like every other writer (listing goes through it too; cost is negligible).
    Command("stakeholders", MUTATING, _stakeholders, mcp_params={"id": ("stakeholder_id",)}),
    # IMP-250a: /sources rewrites the F-NN registry and its source_log render.
    Command("sources", MUTATING, _sources, mcp_params={"id": ("source_id",)}),
    Command("export", MUTATING, _export),
    Command("backlog", MUTATING, _backlog, release=True),
    Command("maturity", READ_ONLY, _project),
    Command("specs", MUTATING, _project, release=True),
    Command("backlog-status", MUTATING, _project_override),
    Command("quality", MUTATING, _project_override, release=True),
    Command("health", READ_ONLY, _project),
    Command("trace", READ_ONLY, _project, release=True),
    Command("validate", READ_ONLY, _project_override, release=True),
    Command("gaps", MUTATING, _gaps, mcp_params={"id": ("gap_id",)}),
    Command("brief", MUTATING, _brief),
    Command("status", READ_ONLY, _status, release=True),
    Command("reindex", MUTATING, _reindex),
)

BY_NAME: dict[str, Command] = {command.name: command for command in REGISTRY}
COMMANDS: frozenset[str] = frozenset(BY_NAME)
READ_ONLY_COMMANDS: frozenset[str] = frozenset(c.name for c in REGISTRY if c.protocol == READ_ONLY)
MUTATING_COMMANDS: frozenset[str] = frozenset(c.name for c in REGISTRY if c.protocol == MUTATING)
PROTOCOL_EXEMPT_COMMANDS: dict[str, str] = {c.name: c.exempt_reason for c in REGISTRY if c.protocol == EXEMPT}
RELEASE_COMMANDS: tuple[str, ...] = tuple(c.name for c in REGISTRY if c.release)
MCP_TOOLS: frozenset[str] = frozenset(c.tool for c in REGISTRY if c.mcp)


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
