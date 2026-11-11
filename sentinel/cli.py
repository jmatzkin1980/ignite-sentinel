from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .protocols import postflight_command, preflight_command

VIEW_ARTIFACTS = {"gaps", "brief", "prd", "specs", "backlog", "readiness"}

COMMANDS = {
    "doctor",
    "dashboard",
    "init",
    "ingest",
    "retrieve",
    "sync",
    "maturity",
    "specs",
    "backlog",
    "backlog-status",
    "quality",
    "health",
    "trace",
    "validate",
    "view",
    "reindex",
    "gaps",
    "annotate",
    "challenge",
    "scrutinize",
    "self-review",
    "assume",
    "compose",
    "refine-backlog",
    "implementation-feedback",
    "story-status",
    "brief",
    "resolve-gaps",
    "context-request",
    "next",
    "status",
    "export",
    "stakeholders",
    "sources",
}


def require_retrieve_query(query: str | None) -> str:
    if not query:
        raise ValueError("/retrieve requires --query unless --timeline is used")
    return query


def require_retrieve_workflow(workflow: str | None) -> str:
    if not workflow:
        raise ValueError("/retrieve requires --workflow unless --timeline is used")
    return workflow


def main(argv: list[str] | None = None) -> int:
    argv = normalize_slash_command(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Ignite Sentinel vNext Core BA CLI. Commands accept slash aliases, e.g. `/maturity PROJECT_ID`.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_p = sub.add_parser("doctor")
    doctor_p.add_argument("--root", default=".")

    dashboard_p = sub.add_parser("dashboard")
    dashboard_p.add_argument("--root", default=".")
    dashboard_p.add_argument("--open", action="store_true")
    dashboard_p.add_argument("--theme", default=None, help="built-in theme name or path to a local theme JSON (default: neutral)")

    view_p = sub.add_parser("view")
    view_p.add_argument("project_id")
    view_p.add_argument("--artifact", required=True, choices=sorted(VIEW_ARTIFACTS))
    view_p.add_argument("--open", action="store_true")
    view_p.add_argument("--theme", default=None, help="built-in theme name or path to a local theme JSON (default: workspace config theme, else neutral)")

    init_p = sub.add_parser("init")
    init_p.add_argument("project_id")
    init_p.add_argument("--brief-version", type=int, choices=(1, 2), help="IMP-26w: 2 (default) compiles the brief v2; 1 keeps v1")

    ingest_p = sub.add_parser("ingest")
    ingest_p.add_argument("project_id")
    ingest_p.add_argument("--source", required=True)

    retrieve_p = sub.add_parser("retrieve")
    retrieve_p.add_argument("project_id")
    retrieve_p.add_argument("--query")
    retrieve_p.add_argument("--workflow")
    retrieve_p.add_argument("--limit", type=int, default=5)
    retrieve_p.add_argument("--artifact-type")
    retrieve_p.add_argument("--domain")
    retrieve_p.add_argument("--trace-id")
    retrieve_p.add_argument("--iteration-min", type=int, default=1)
    retrieve_p.add_argument("--status")
    retrieve_p.add_argument("--language")
    retrieve_p.add_argument("--sensitivity")
    retrieve_p.add_argument("--section")
    retrieve_p.add_argument("--max-chars", type=int)
    retrieve_p.add_argument("--summary-only", action="store_true")
    retrieve_p.add_argument("--write-pack", action="store_true")
    # IMP-126: recency-first ordering and a read-only episodic timeline.
    retrieve_p.add_argument("--order", choices=["relevance", "recency"], default="relevance")
    retrieve_p.add_argument("--timeline", action="store_true")

    sync_p = sub.add_parser("sync")
    sync_p.add_argument("project_id")
    sync_p.add_argument("--source")
    sync_p.add_argument("--note", default="")
    sync_p.add_argument("--digest", action="store_true")

    resolve_p = sub.add_parser("resolve-gaps")
    resolve_p.add_argument("project_id")
    resolve_p.add_argument("--source", required=True)

    annotate_p = sub.add_parser("annotate")
    annotate_p.add_argument("project_id")
    annotate_p.add_argument("--source", required=True)

    challenge_p = sub.add_parser("challenge")
    challenge_p.add_argument("project_id")
    challenge_p.add_argument("--source", required=True)

    scrutinize_p = sub.add_parser("scrutinize")
    scrutinize_p.add_argument("project_id")
    scrutinize_p.add_argument("--source", required=True)
    scrutinize_p.add_argument("--lens")
    scrutinize_p.add_argument(
        "--mode",
        default="scrutiny",
        choices=["scrutiny", "implementability-probe", "anchors"],
    )

    self_review_p = sub.add_parser("self-review")
    self_review_p.add_argument("project_id")
    self_review_p.add_argument("--source", required=True)
    self_review_p.add_argument("--sufficiency", action="store_true",
                               help="IMP-259: a clean-context reader checks the brief v2 is enough to start building")
    self_review_p.add_argument("--crosses", action="store_true",
                               help="IMP-260b: semantic crosses between the lenses of the brief v2")

    assume_p = sub.add_parser("assume")
    assume_p.add_argument("project_id")
    assume_p.add_argument("--source", required=True)

    compose_p = sub.add_parser("compose")
    compose_p.add_argument("project_id")
    compose_p.add_argument("--source", required=True)

    refine_backlog_p = sub.add_parser("refine-backlog")
    refine_backlog_p.add_argument("project_id")
    refine_backlog_p.add_argument("--source", required=True)

    implementation_feedback_p = sub.add_parser("implementation-feedback")
    implementation_feedback_p.add_argument("project_id")
    implementation_feedback_p.add_argument("--source", required=True)

    story_status_p = sub.add_parser("story-status")
    story_status_p.add_argument("project_id")
    story_status_p.add_argument("--story", required=True)
    story_status_p.add_argument("--set", required=True, dest="status")
    story_status_p.add_argument("--owner")
    story_status_p.add_argument("--evidence")

    context_request_p = sub.add_parser("context-request")
    context_request_p.add_argument("project_id")
    context_request_p.add_argument("--domain", choices=["technology", "design", "quality", "frontend", "backend"])
    context_request_p.add_argument("--id", dest="request_id")  # IMP-294: move a CTX along its lifecycle
    context_request_p.add_argument("--status", choices=["active", "answered", "closed", "obsolete"])
    context_request_p.add_argument("--reason", default="")
    next_p = sub.add_parser("next")  # IMP-294: the next step of /status, alone
    next_p.add_argument("project_id")

    stakeholders_p = sub.add_parser("stakeholders")
    stakeholders_p.add_argument("project_id")
    stakeholders_p.add_argument("--add", action="store_true")
    stakeholders_p.add_argument("--id", dest="stakeholder_id")
    stakeholders_p.add_argument("--name")
    stakeholders_p.add_argument("--domain")
    stakeholders_p.add_argument("--topic", default="")
    stakeholders_p.add_argument("--profile")
    stakeholders_p.add_argument("--notes", default="")

    sources_p = sub.add_parser("sources")  # IMP-250a: F-NN source registry
    sources_p.add_argument("project_id")
    sources_p.add_argument("--id", dest="source_id")
    sources_p.add_argument("--from", dest="from_who")
    sources_p.add_argument("--superseded-by", dest="superseded_by")
    sources_p.add_argument("--retire", action="store_true")
    sources_p.add_argument("--replacement")
    sources_p.add_argument("--expire", metavar="YYYY-MM-DD")
    sources_p.add_argument("--topic")
    sources_p.add_argument("--current", action="store_true")
    sources_p.add_argument("--close", action="store_true")
    sources_p.add_argument("--reason")
    # IMP-250b: authority, impact matrix cells, precedence and the closing report.
    sources_p.add_argument("--authority")
    sources_p.add_argument("--cell", metavar="DOCUMENT/SECTION")
    sources_p.add_argument("--mark", choices=["updated", "reviewed", "pending"])
    sources_p.add_argument("--precedence", metavar="SCOPE")
    sources_p.add_argument("--between", metavar="F-NN,F-NN")
    sources_p.add_argument("--report", action="store_true")

    export_p = sub.add_parser("export")
    export_p.add_argument("project_id")
    export_p.add_argument("--artifact", required=True, choices=["gaps", "brief", "context-request", "prd"])
    export_p.add_argument("--format", "--fmt", default="md", choices=["md", "mdx", "interview", "faq"])
    export_p.add_argument("--domain")
    export_p.add_argument("--final", action="store_true", help="IMP-272: refuse to export while pending marks remain")

    backlog_p = sub.add_parser("backlog")
    backlog_p.add_argument("project_id")
    backlog_p.add_argument("--with-task-seeds", action="store_true")
    backlog_p.add_argument("--story-format", choices=("user", "job"), default=None)

    for name in ("maturity", "specs", "backlog-status", "quality", "health", "trace", "validate", "gaps", "brief", "status"):
        command = sub.add_parser(name)
        command.add_argument("project_id")
        if name in {"backlog-status", "quality", "validate"}:
            command.add_argument("--override")
        if name == "status":
            command.add_argument("--full", action="store_true")
        if name == "brief":  # IMP-252: the BA confirms profile, genesis and validation direction
            command.add_argument("--profile", help="comma-separated: UI,API,BAT,INT,MIG,REG,MT")
            command.add_argument("--genesis", help="greenfield|brownfield-integration|brownfield-extension|brownfield-replacement (comma-separated when mixed)")
            command.add_argument("--validation-direction", choices=("to-build", "built"))
            command.add_argument("--brief-version", type=int, choices=(1, 2), help="2 compiles the brief v2 (opt-in per project)")
        if name == "gaps":  # IMP-271 / F7: BA disposition on a gap an agentic channel raised
            command.add_argument("--id", dest="gap_id")
            command.add_argument("--disposition", choices=("accepted", "rejected", "irrelevant"))
            command.add_argument("--reason", default="")
            command.add_argument("--top", type=int, help="IMP-257: the next round of at most N questions (default 5)")
    reindex_p = sub.add_parser("reindex")
    reindex_p.add_argument("project_id")
    reindex_p.add_argument("--full", action="store_true")

    args = parser.parse_args(argv)
    try:
        project_id = getattr(args, "project_id", None)
        if project_id is not None:
            # IMP-243: single validation point for every command and MCP tool, before
            # anything touches the disk.
            from .core.paths import validate_project_id

            validate_project_id(project_id)
        preflight_command(args.command, project_id)
        result = None
        if args.command == "init":
            from .workspace import ensure_workspace

            path = ensure_workspace(args.project_id, brief_version=getattr(args, "brief_version", None))
            result = {"workspace": str(path)}
            print_json(result)
        elif args.command == "doctor":
            from .doctor import run_doctor

            result = run_doctor(Path(args.root))
            print_json(result)
            return 0 if result["verdict"] == "PASS" else 1
        elif args.command == "dashboard":
            from .dashboard import generate_dashboard

            result = generate_dashboard(Path(args.root), open_browser=bool(args.open), theme=args.theme)
            print_json(result)
        elif args.command == "view":
            from .view import generate_artifact_view

            result = generate_artifact_view(args.project_id, args.artifact, open_browser=bool(args.open), theme=args.theme)
            print_json(result)
        elif args.command == "ingest":
            from .discovery import ingest

            result = ingest(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "retrieve":
            from .memory import ContextBroker

            broker = ContextBroker(args.project_id)
            if args.timeline:
                result = broker.build_change_timeline(
                    args.limit if args.limit and args.limit > 0 else None,
                    args.artifact_type,
                    args.trace_id,
                )
            elif args.write_pack:
                result = broker.build_context_pack(
                    require_retrieve_query(args.query),
                    require_retrieve_workflow(args.workflow),
                    args.limit,
                    args.artifact_type,
                    args.domain,
                    args.trace_id,
                    args.iteration_min,
                    args.status,
                    args.language,
                    args.sensitivity,
                    args.section,
                    args.max_chars,
                    args.summary_only,
                    args.order,
                )
            else:
                result = broker.retrieve(
                    require_retrieve_query(args.query),
                    require_retrieve_workflow(args.workflow),
                    args.limit,
                    args.artifact_type,
                    args.domain,
                    args.trace_id,
                    args.iteration_min,
                    args.status,
                    args.language,
                    args.sensitivity,
                    args.section,
                    args.max_chars,
                    args.summary_only,
                    args.order,
                )
            print_json(result)
        elif args.command == "sync":
            from .sync import sync_change, sync_pending_sources

            if args.source:
                result = sync_change(args.project_id, Path(args.source), args.note, digest=args.digest)
            else:
                result = sync_pending_sources(args.project_id, args.note or "autonomous sync", digest=args.digest)
            print_json(result)
        elif args.command == "gaps":
            if args.gap_id or args.disposition:
                if not (args.gap_id and args.disposition):
                    raise ValueError("/gaps --disposition goes with --id GAP-X")
                from .discovery import record_gap_disposition

                print_json(record_gap_disposition(args.project_id, args.gap_id, args.disposition, args.reason))
            elif args.top is not None:
                from .discovery.workflow import gap_round

                print_json(gap_round(args.project_id, args.top))
            else:
                from .discovery import regenerate_gaps

                result = regenerate_gaps(args.project_id)
                print_json(result)
        elif args.command == "resolve-gaps":
            from .gap_resolution import resolve_gaps

            result = resolve_gaps(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "annotate":
            from .discovery import apply_annotation

            result = apply_annotation(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "challenge":
            from .discovery import apply_challenge

            result = apply_challenge(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "scrutinize" and args.mode == "anchors":
            from .anchor_review import apply_anchor_review  # IMP-258b

            print_json(apply_anchor_review(args.project_id, Path(args.source)))
        elif args.command == "scrutinize":
            from .discovery import apply_scrutiny

            result = apply_scrutiny(args.project_id, Path(args.source), args.lens, mode=args.mode)
            print_json(result)
        elif args.command == "self-review" and args.crosses:
            from .cross_review import apply_cross_review

            print_json(apply_cross_review(args.project_id, Path(args.source)))
        elif args.command == "self-review" and args.sufficiency:
            from .sufficiency import apply_sufficiency

            print_json(apply_sufficiency(args.project_id, Path(args.source)))
        elif args.command == "self-review":
            from .self_review import apply_self_review

            result = apply_self_review(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "assume":
            from .assumptions import apply_assumptions

            result = apply_assumptions(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "compose":
            from .prd import apply_prd_composition

            result = apply_prd_composition(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "refine-backlog":
            from .backlog.refinement import apply_backlog_refinement

            result = apply_backlog_refinement(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "implementation-feedback":
            from .implementation_feedback import apply_implementation_feedback

            result = apply_implementation_feedback(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "story-status":
            from .backlog.status import update_story_status

            result = update_story_status(
                args.project_id,
                args.story,
                args.status,
                args.owner,
                Path(args.evidence) if args.evidence else None,
            )
            print_json(result)
        elif args.command == "maturity":
            from .maturity import evaluate

            result = evaluate(args.project_id)
            print_json(result)
        elif args.command == "brief":
            from .brief_schema import set_brief_settings, settings_status
            from .workspace import workspace_path
            from .maturity import generate_project_brief

            if any(value is not None for value in (args.profile, args.genesis, args.validation_direction, args.brief_version)):
                set_brief_settings(
                    args.project_id,
                    profiles=args.profile.split(",") if args.profile is not None else None,
                    genesis=[value.strip() for value in args.genesis.split(",") if value.strip()] if args.genesis is not None else None,
                    validation_direction=args.validation_direction,
                    brief_version=args.brief_version,
                )
            result = generate_project_brief(args.project_id)
            requirements = workspace_path(args.project_id) / "02_requirements" / "requirements.md"
            raw = requirements.read_text(encoding="utf-8") if requirements.exists() else ""
            result["brief_settings"] = settings_status(args.project_id, raw)
            print_json(result)
        elif args.command == "context-request":
            from .context_requests import generate_context_request, transition_context_request

            if args.request_id or args.status:
                if not (args.request_id and args.status) or args.domain:
                    raise ValueError("/context-request --id CTX-NNN goes with --status (and --reason), without --domain")
                result = transition_context_request(args.project_id, args.request_id, args.status, args.reason)
            elif not args.domain:
                raise ValueError("/context-request needs --domain, or --id CTX-NNN --status STATE")
            else:
                result = generate_context_request(args.project_id, args.domain)
            print_json(result)
        elif args.command == "next":
            from .status import project_next

            print_json(project_next(args.project_id))
        elif args.command == "status":
            from .status import project_status

            result = project_status(args.project_id, full=args.full)  # IMP-248: summary by default
            print_json(result)
        elif args.command == "stakeholders":
            from .stakeholders import add_stakeholder, list_stakeholders

            if args.add:
                result = add_stakeholder(
                    args.project_id,
                    name=args.name or "",
                    domain=args.domain or "",
                    stakeholder_id=args.stakeholder_id,
                    profile=args.profile,
                    topic=args.topic,
                    notes=args.notes,
                )
            else:
                result = list_stakeholders(args.project_id)
            print_json(result)
        elif args.command == "sources":
            from .sources import list_sources, source_precedence, update_source, write_closing_report

            changes = {
                "from_who": args.from_who,
                "superseded_by": args.superseded_by,
                "retire": args.retire,
                "replacement": args.replacement,
                "expire": args.expire,
                "topic": args.topic,
                "current": args.current,
                "close": args.close,
                "reason": args.reason,
                "authority": args.authority,
                "cell": args.cell,
                "mark": args.mark,
            }
            if args.precedence or args.between:
                if not (args.precedence and args.between):
                    raise ValueError("/sources --precedence SCOPE goes with --between F-NN,F-NN")
                ids = [item.strip() for item in args.between.split(",") if item.strip()]
                result = source_precedence(args.project_id, args.precedence, ids)
            elif args.report:
                if args.source_id or any(value for value in changes.values()):
                    raise ValueError("/sources --report takes no other option")
                result = write_closing_report(args.project_id)
            elif args.source_id:
                result = update_source(args.project_id, args.source_id, **changes)
            elif any(value for value in changes.values()):
                raise ValueError("/sources needs --id F-NN to change a row")
            else:
                result = list_sources(args.project_id)
            print_json(result)
        elif args.command == "export":
            from .export import export_artifact

            result = export_artifact(args.project_id, args.artifact, args.format, args.domain, final=args.final)
            print_json(result)
        elif args.command == "specs":
            from .generation import generate_specs

            result = generate_specs(args.project_id)
            print_json(result)
        elif args.command == "backlog":
            from .generation import generate_backlog

            result = generate_backlog(
                args.project_id,
                with_task_seeds=bool(args.with_task_seeds),
                story_format=args.story_format,
            )
            print_json(result)
        elif args.command == "backlog-status":
            from .backlog.rollup import backlog_status

            result = backlog_status(args.project_id, override_source=Path(args.override) if args.override else None)
            print_json(result)
        elif args.command == "quality":
            from .quality import generate_quality

            result = generate_quality(args.project_id, override_source=Path(args.override) if args.override else None)
            print_json(result)
        elif args.command == "health":
            from .health import run_health

            result = run_health(args.project_id)
            print_json(result)
        elif args.command == "trace":
            from .core.graph import load_graph
            from .traceability import write_mermaid_graph, write_traceability_matrix

            matrix = write_traceability_matrix(args.project_id)
            mermaid = write_mermaid_graph(args.project_id)
            result = {"graph": load_graph(args.project_id), "matrix": str(matrix), "mermaid": str(mermaid)}
            print_json(result)
        elif args.command == "validate":
            from .validation import validate_project

            result = validate_project(args.project_id, override_source=Path(args.override) if args.override else None)
            print_json(result)
            postflight_command(args.command, project_id, result)
            return 0 if result["verdict"] == "VALID" else 1
        elif args.command == "reindex":
            from .memory import reindex_workspace

            result = reindex_workspace(args.project_id, full=args.full)
            print_json(result)
        postflight_command(args.command, project_id, result)
        return 0
    except Exception as exc:
        print(f"sentinel error: {exc}", file=sys.stderr)
        return 1


def normalize_slash_command(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first.startswith("/") and first[1:] in COMMANDS:
        return [first[1:], *argv[1:]]
    return argv


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=True))
