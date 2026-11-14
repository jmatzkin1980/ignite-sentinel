from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from .commands import COMMANDS, VIEW_ARTIFACTS, build_parser  # noqa: F401  IMP-303: the single command registry
from .errors import EXIT_BUG, EXIT_OK, EXIT_VERDICT, exit_code_for, next_step_for
from .protocols import postflight_command, preflight_command


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
    args = build_parser().parse_args(argv)
    from .core.lock import command_scope

    try:
        # IMP-299: one command at a time per workspace (exit 6 after a bounded wait).
        workspace = command_workspace(args)
        with command_scope(args.command, workspace):
            if workspace is not None and (workspace / "state.json").is_file():
                from .core.state import migrate_state

                migrate_state(args.project_id)  # IMP-300: a 0.9.0 workspace, once; a newer schema exits 3
            return run_command(args, argv)
    except Exception as exc:
        return report_error(exc)


def command_workspace(args) -> Path | None:
    """The workspace a command locks: its project's, once the project id is known to be valid."""
    project_id = getattr(args, "project_id", None)
    if not project_id:
        return None
    from .core.paths import validate_project_id, workspace_path

    try:
        validate_project_id(project_id)
    except Exception:
        return None  # run_command reports the invalid id
    return workspace_path(project_id)


def run_command(args, argv: list[str]) -> int:
    if getattr(args, "release", None):
        try:
            from .core.paths import validate_project_id
            from .release_scope import run_release_command, scoped_argv

            validate_project_id(args.project_id)
            return run_release_command(scoped_argv(argv)[1], args.project_id, args.release)
        except Exception as exc:
            return report_error(exc)
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
            return EXIT_OK if result["verdict"] == "PASS" else EXIT_VERDICT
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
        elif args.command == "harvest":
            from .harvest import apply_harvest

            print_json(apply_harvest(args.project_id, Path(args.source)))
        elif args.command == "split" and args.propose:
            if not args.source:
                raise ValueError("/split --propose needs --source PROPOSAL.json (written with the sentinel-release-split skill)")
            from .split_proposal import apply_proposal

            result = apply_proposal(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "split" and args.confirm:
            from .release_split import confirm_partition

            print_json(confirm_partition(args.project_id, args.ba or "", args.tech or ""))
        elif args.command == "prototype" and args.manual:
            if not args.source:
                raise ValueError("/prototype --manual needs --source MANUAL.json (written with the sentinel-prototype-manual skill)")
            from .prototype_manual import apply_manual

            result = apply_manual(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "prototype" and args.trace:
            if not args.source:
                raise ValueError("/prototype --trace needs --source TRACE.json (written with the sentinel-prototype-trace skill)")
            from .prototype_trace import apply_trace

            result = apply_trace(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "prototype":
            from .prototype import build_inventory

            result = build_inventory(args.project_id, args.source or "")
            print_json(result)
        elif args.command == "split" and args.close:
            from .release_guide import close_release

            print_json(close_release(args.project_id, args.close, args.evidence or "", args.ba or "", args.tech or ""))
        elif args.command == "split" and args.move:
            if not (args.unit and args.from_holder and args.to_holder):
                raise ValueError("/split --move needs --unit, --from and --to (and --reason, --ba, --tech)")
            from .release_move import move_unit

            print_json(move_unit(args.project_id, args.unit, args.from_holder, args.to_holder, args.reason or "",
                                 args.ba or "", args.tech or "", finding=args.finding, criterion=args.criterion))
        elif args.command == "split":
            from .split import run_assess

            result = run_assess(args.project_id)
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
            return EXIT_OK if result["verdict"] == "VALID" else EXIT_VERDICT
        elif args.command == "reindex":
            from .memory import reindex_workspace

            result = reindex_workspace(args.project_id, full=args.full)
            print_json(result)
        postflight_command(args.command, project_id, result)
        return EXIT_OK
    except Exception as exc:
        return report_error(exc)


def report_error(exc: BaseException) -> int:
    """IMP-302: print the error and its next step; return its exit code (see sentinel/errors.py)."""
    code = exit_code_for(exc)
    print(f"sentinel error: {exc}", file=sys.stderr)
    next_step = next_step_for(exc)
    if next_step:
        print(f"next step: {next_step}", file=sys.stderr)
    if code == EXIT_BUG:
        traceback.print_exception(exc, file=sys.stderr)
    return code


def normalize_slash_command(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first.startswith("/") and first[1:] in COMMANDS:
        return [first[1:], *argv[1:]]
    return argv


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=True))
