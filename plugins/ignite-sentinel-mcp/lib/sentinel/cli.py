from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

from .commands import COMMANDS, VIEW_ARTIFACTS, build_parser, skill_for_next_text  # noqa: F401  IMP-303: the single command registry
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


_TEXT_SOURCE_SUFFIXES = {".md", ".markdown", ".txt", ".json", ".html", ".htm", ".csv"}


def check_source_exists(args) -> None:
    """IMP-312: a `--source` file that does not exist is invalid input (exit 3), not a traceback."""
    source = getattr(args, "source", None)
    if not source or (args.command == "prototype" and getattr(args, "inventory", False)):
        return  # --inventory takes a source id (F-NN), not a path
    from .errors import InputError

    path = Path(source)
    if not path.exists():
        raise InputError(
            f"--source file not found: {source}",
            next_step=f"Check the path; it is read relative to the folder you run Sentinel from ({Path.cwd()}).",
        )
    if path.is_dir():
        # IMP-323: a folder used to end in exit 1 with a PermissionError traceback.
        # IMP-361: /sync too; it reads one file per run (without --source it scans the input folders).
        next_step = "Pass the file itself."
        if args.command == "sync":
            next_step = (
                "Pass one file at a time, or run /sync without --source to scan the input and "
                "context folders for new or modified files."
            )
        raise InputError(f"--source must be a file, not a folder: {source}", next_step=next_step)
    if path.suffix.lower() in _TEXT_SOURCE_SUFFIXES:
        # IMP-323: a UTF-16 file (what PowerShell 5.1 `>` writes) failed after the command had
        # already copied it into the workspace; refuse it before anything is written.
        try:
            path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise InputError(
                f"--source is not UTF-8 text: {source}",
                next_step="Save the file as UTF-8 (in PowerShell: Out-File -Encoding utf8) and run the command again.",
            ) from None


def run_command(args, argv: list[str]) -> int:
    if args.command in {"specs", "backlog", "validate", "next", "status"} and getattr(args, "release", None) and getattr(args, "change", None):
        from .changes import change_language, get_change
        from .errors import InputError

        try:
            language = change_language(args.project_id, get_change(args.project_id, args.change))
        except Exception:  # an unknown change or workspace is reported by the command itself
            language = "es"
        if language == "en":
            message = f"/{args.command} --change cannot be combined with --release: a change does not belong to a release series."
            next_step = f"Run /{args.command} {args.project_id} --change {args.change} without --release."
        else:
            message = f"/{args.command} --change no se combina con --release: un cambio no pertenece a una serie de releases."
            next_step = f"Corré /{args.command} {args.project_id} --change {args.change} sin --release."
        return report_error(InputError(message, next_step=next_step))
    if getattr(args, "release", None):
        try:
            from .core.paths import validate_project_id
            from .release_scope import run_release_command, scoped_argv

            validate_project_id(args.project_id)
            return run_release_command(scoped_argv(argv)[1], args.project_id, args.release)
        except Exception as exc:
            return report_error(exc)
    from .traceability import deferred_graph_saves

    # IMP-345: the graph is written once per command (after its artifacts), not per node or edge.
    with deferred_graph_saves():
        return _run_project_command(args)


def _run_project_command(args) -> int:
    try:
        project_id = getattr(args, "project_id", None)
        if project_id is not None:
            # IMP-243: single validation point for every command and MCP tool, before
            # anything touches the disk.
            from .core.paths import validate_project_id

            validate_project_id(project_id)
        check_source_exists(args)
        preflight_command(args.command, project_id, getattr(args, "change", None))
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
        elif args.command == "setup":
            from . import semantic_setup

            try:
                if args.status:
                    result = semantic_setup.semantic_status()
                    print_json(result)
                    # 0 when installed or not installed yet; 1 when an installed file does not match the manifest
                    return EXIT_BUG if result["status"] == "mismatch" else EXIT_OK
                else:
                    offline = Path(args.offline_from) if args.offline_from else None
                    result = semantic_setup.install_semantic_memory(offline_from=offline, root=Path(args.root))
            except semantic_setup.SetupError as exc:
                print(f"sentinel error: {exc}", file=sys.stderr)
                return EXIT_BUG
            print_json(result)
        elif args.command == "dashboard":
            from .dashboard import generate_dashboard

            result = generate_dashboard(Path(args.root), open_browser=bool(args.open), theme=args.theme)
            print_json(result)
        elif args.command == "view":
            from .view import generate_artifact_view

            result = generate_artifact_view(args.project_id, args.artifact, open_browser=bool(args.open), theme=args.theme,
                                            change_id=args.change)
            print_json(result)
        elif args.command == "ingest":
            from .discovery import ingest

            result = ingest(args.project_id, Path(args.source), replace=bool(args.replace), change=bool(args.change))
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
            from .sync import sync_change, sync_change_with_analysis, sync_pending_sources

            if args.change:
                if args.analysis or args.digest:
                    raise ValueError("/sync --change takes --source, --role, --supersedes and --note")
                from .change_sync import sync_change_scope

                result = sync_change_scope(args.project_id, args.change, Path(args.source) if args.source else None,
                                           args.role, args.supersedes, args.note)
            elif args.role or args.supersedes:
                raise ValueError("/sync --role and --supersedes go with --change CHG-NNN")
            elif args.analysis:
                if not args.source:
                    from .errors import InputError

                    raise InputError("/sync --analysis needs --source NOTE: the analysis cites the note it reads.")
                result = sync_change_with_analysis(args.project_id, Path(args.source), Path(args.analysis),
                                                   args.note, digest=args.digest)
            elif args.source:
                result = sync_change(args.project_id, Path(args.source), args.note, digest=args.digest)
            else:
                result = sync_pending_sources(args.project_id, args.note or "autonomous sync", digest=args.digest)
            print_json(result)
        elif args.command == "gaps":
            if args.accept_prior:
                if not (args.change and args.gap_id):
                    raise ValueError("/gaps --accept-prior goes with --change and --id")
                from .changes import accept_prior_decision

                print_json(accept_prior_decision(args.project_id, args.change, args.gap_id))
            elif args.impact:
                if not (args.change and args.gap_id):
                    raise ValueError("/gaps --impact goes with --change and --id")
                if not args.reason.strip():
                    raise ValueError("/gaps --impact needs --reason")
                from .changes import set_gap_impact

                print_json(set_gap_impact(args.project_id, args.change, args.gap_id, args.impact, args.reason))
            elif args.change and args.gap_id and not args.disposition and args.top is None:
                from .changes import change_language, get_change
                from .errors import InputError

                es = change_language(args.project_id, get_change(args.project_id, args.change)) == "es"
                raise InputError(
                    "/gaps --change con --id va con --impact construccion|operativo --reason TEXTO." if es
                    else "/gaps --change with --id goes with --impact construccion|operativo --reason TEXT.",
                    next_step=f"/gaps {args.project_id} --change {args.change} --id {args.gap_id} --impact construccion|operativo --reason TEXTO",
                )
            elif args.change and (args.gap_id or args.disposition or args.top is not None):
                from .errors import InputError

                clash = "--id/--disposition" if (args.gap_id or args.disposition) else "--top"
                raise InputError(
                    f"/gaps --change no se combina con {clash}: --change sólo regenera los gaps del cambio.",
                    next_step="Corré /gaps --change CHG-NNN solo, o quitá --change para usar " + clash + ".",
                )
            elif args.gap_id or args.disposition:
                if not (args.gap_id and args.disposition):
                    raise ValueError("/gaps --disposition goes with --id GAP-X")
                from .discovery import record_gap_disposition

                print_json(record_gap_disposition(args.project_id, args.gap_id, args.disposition, args.reason))
            elif args.change:
                from .changes import regenerate_change_gaps

                print_json(regenerate_change_gaps(args.project_id, args.change))
            elif args.top is not None:
                from .discovery.elicitation import gap_round

                print_json(gap_round(args.project_id, args.top))
            else:
                from .discovery import regenerate_gaps

                result = regenerate_gaps(args.project_id)
                print_json(result)
        elif args.command == "resolve-gaps":
            from .gap_resolution import resolve_gaps

            result = resolve_gaps(args.project_id, Path(args.source), change_id=args.change)
            print_json(result)
        elif args.command == "annotate":
            from .discovery import apply_annotation

            result = apply_annotation(args.project_id, Path(args.source), change_id=args.change)
            print_json(result)
        elif args.command == "challenge":
            from .discovery import apply_challenge

            result = apply_challenge(args.project_id, Path(args.source), change_id=args.change)
            print_json(result)
        elif args.command == "scrutinize" and args.mode == "anchors":
            if args.change:  # IMP-418: the anchors are the project's
                from .changes import refusal_language
                from .errors import InputError

                es = refusal_language(args.project_id, args.change) == "es"
                file_word = "ARCHIVO" if es else "FILE"
                raise InputError(
                    f"--mode anchors revisa las anclas del proyecto; en el cambio usá /scrutinize {args.project_id} --source {file_word} --change {args.change}" if es
                    else f"--mode anchors reviews the project's anchors; in the change use /scrutinize {args.project_id} --source {file_word} --change {args.change}",
                    next_step=f"/scrutinize {args.project_id} --source {file_word} --change {args.change}")
            from .anchor_review import apply_anchor_review  # IMP-258b

            print_json(apply_anchor_review(args.project_id, Path(args.source)))
        elif args.command == "scrutinize":
            from .discovery import apply_scrutiny

            result = apply_scrutiny(args.project_id, Path(args.source), args.lens, mode=args.mode, change_id=args.change)
            print_json(result)
        elif args.command == "harvest":
            from .harvest import apply_harvest

            print_json(apply_harvest(args.project_id, Path(args.source), args.change))
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

            result = apply_manual(args.project_id, Path(args.source), args.change)
            print_json(result)
        elif args.command == "prototype" and args.trace:
            if not args.source:
                raise ValueError("/prototype --trace needs --source TRACE.json (written with the sentinel-prototype-trace skill)")
            from .prototype_trace import apply_trace

            result = apply_trace(args.project_id, Path(args.source), args.change)
            print_json(result)
        elif args.command == "prototype":
            from .prototype import build_inventory

            result = build_inventory(args.project_id, args.source or "", args.change)
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
        elif args.command == "self-review" and args.change and not args.crosses:
            from .errors import InputError

            raise InputError("/self-review --change va con --crosses")
        elif args.command == "self-review" and args.skip and not args.change:
            from .errors import InputError

            raise InputError("/self-review --skip goes with --crosses --change")
        elif args.command == "self-review" and args.crosses and args.change:
            from .change_coherence import run_change_coherence

            print_json(run_change_coherence(args.project_id, args.change, args.source, args.skip, args.reason))
        elif args.command == "self-review" and not args.source:
            from .errors import InputError

            raise InputError("/self-review needs --source PATH")
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
        elif args.command == "assume" and not args.change and not args.source:
            from .errors import InputError

            raise InputError("/assume needs --source PATH")
        elif args.command == "assume" and not args.change and (
                args.id or args.validate or args.invalidate or args.reason):
            raise ValueError("/assume --id, --validate, --invalidate and --reason go with --change")
        elif args.command == "assume" and args.change:
            from .change_assumptions import apply_change_assumptions, set_change_assumption_status

            moving = bool(args.id or args.validate or args.invalidate or args.reason)
            if args.source and not moving:
                print_json(apply_change_assumptions(args.project_id, args.change, Path(args.source)))
            elif (not args.source and args.id and args.reason and args.validate != args.invalidate):
                print_json(set_change_assumption_status(
                    args.project_id, args.change, args.id,
                    "validate" if args.validate else "invalidate", args.reason))
            elif not args.source and args.id and args.validate != args.invalidate:
                # --reason missing: the status function names it in the change's language
                print_json(set_change_assumption_status(
                    args.project_id, args.change, args.id,
                    "validate" if args.validate else "invalidate", ""))
            else:
                raise ValueError("/assume --change takes --source PATH, or --id ASM --validate|--invalidate --reason TEXT")
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
            from .maturity import generate_project_brief, refuse_change_only_brief

            project_flags = {"--profile": args.profile, "--genesis": args.genesis,
                             "--validation-direction": args.validation_direction, "--brief-version": args.brief_version}
            if args.change:
                from .errors import InputError

                clash = [flag for flag, value in project_flags.items() if value is not None]
                if clash:
                    raise InputError(
                        f"/brief --change no se combina con {', '.join(clash)}: esos ajustes son del proyecto.",
                        next_step=f"Corré /brief {args.project_id} --change {args.change} solo, o quitá --change para ajustar el proyecto.",
                    )
                from .changes import get_change
                from .compilers.change_brief import compile_change_brief

                get_change(args.project_id, args.change)
                result = compile_change_brief(args.project_id, args.change)
            else:
                refuse_change_only_brief(args.project_id)
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
        elif args.command == "extract":
            from .extraction import run_extract

            if not args.change:  # IMP-420: the project's request
                from .changes import refuse_project_extraction

                refuse_project_extraction(args.project_id, "extract", {
                    "--consolidate": args.consolidate, "--confirm-replacement": args.confirm_replacement,
                    "--keep-text": args.keep_text})
            forms = [bool(x) for x in (args.proposals, args.confirm, args.confirm_item, args.reject_item,
                                       args.verify, args.verify_result, args.consolidate, args.confirm_replacement,
                                       args.keep_text)]
            if sum(forms) > 1:
                raise ValueError(
                    "/extract takes one of --proposals, --confirm, --confirm-item, --reject-item, --verify, "
                    "--verify-result, --consolidate, --confirm-replacement or --keep-text")
            if args.sample is not None and not args.verify:
                raise ValueError("/extract --sample goes with --verify")
            if args.reason and not (args.reject_item or args.confirm_item or args.keep_text):
                raise ValueError("/extract --reason goes with --reject-item, --confirm-item or --keep-text")
            if args.gap and not args.keep_text:
                raise ValueError("/extract --gap goes with --keep-text")
            if args.keep_text and not args.gap:
                raise ValueError("/extract --keep-text needs --gap")
            if args.reject_item and not args.reason:
                raise ValueError("/extract --reject-item needs --reason")
            if args.delegated and not (args.confirm or args.confirm_item or args.confirm_replacement):
                raise ValueError("/extract --delegated goes with --confirm, --confirm-item or --confirm-replacement")
            if args.note and not args.delegated:
                raise ValueError("/extract --note goes with --delegated")
            print_json(run_extract(
                args.project_id, args.change, proposals=args.proposals, confirm=args.confirm,
                confirm_item=args.confirm_item, reject_item=args.reject_item, reason=args.reason,
                verify=args.verify, sample=args.sample, verify_result=args.verify_result,
                delegated=args.delegated, note=args.note or "",
                consolidate=args.consolidate, confirm_replacement=args.confirm_replacement,
                keep_text=args.keep_text, gap=args.gap,
            ))
        elif args.command == "cross":
            from .crosses import run_cross

            if not args.change:  # IMP-420: the project's request
                from .changes import refuse_project_extraction

                refuse_project_extraction(args.project_id, "cross", {
                    "--accept-new": args.accept_new, "--decline-new": args.decline_new})
            if sum(bool(x) for x in (args.claims, args.skip, args.accept_new, args.decline_new)) > 1:
                raise ValueError("/cross takes one of --claims, --skip, --accept-new or --decline-new")
            if (args.claims or args.skip) and not args.kind:
                raise ValueError("/cross --claims and --skip need --kind")
            if args.kind and (args.accept_new or args.decline_new or not (args.claims or args.skip)):
                raise ValueError("/cross --kind goes with --claims or --skip")
            if bool(args.reason) != bool(args.skip or args.decline_new):
                raise ValueError("/cross --reason goes with --skip or --decline-new (and they need it)")
            if bool(args.surface_type or args.name) != bool(args.accept_new) or (
                args.accept_new and not (args.surface_type and args.name)
            ):
                raise ValueError("/cross --accept-new needs --type and --name (and only it takes them)")
            print_json(run_cross(
                args.project_id, args.change, kind=args.kind, claims=args.claims, skip=args.skip, reason=args.reason,
                accept_new=args.accept_new, surface_type=args.surface_type, name=args.name, decline_new=args.decline_new,
                delta=args.delta,
            ))
        elif args.command == "next":
            from .status import project_next

            print_json(project_next(args.project_id, args.change))
        elif args.command == "status":
            from .status import project_status

            result = project_status(args.project_id, full=args.full, change_id=args.change)  # IMP-248: summary by default
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
            elif any((args.stakeholder_id, args.name, args.domain, args.topic, args.profile, args.notes)):
                # IMP-333: a field without --add used to be ignored in silence
                raise ValueError("/stakeholders --id/--name/--domain/--topic/--profile/--notes go with --add")
            else:
                result = list_stakeholders(args.project_id)
            print_json(result)
        elif args.command == "sources":
            from .sources import list_sources, load_message, load_source, source_precedence, update_source, write_closing_report

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
            role_option = args.role  # IMP-400: --id F-NN --role ROLE
            if args.derived_from and not args.load:
                raise ValueError("/sources --derived-from goes with --load PATH --role diseno_nuevo")
            if args.reliability and not args.load:
                raise ValueError("/sources --reliability goes with --load PATH --role linea_de_base")
            if args.no_baseline:
                # IMP-400: --change CHG --no-baseline --reason TEXT waives the change's baseline step.
                if not args.change:
                    raise ValueError("/sources --no-baseline needs --change CHG-NNN")
                if args.keep_single:
                    raise ValueError("/sources --no-baseline and --keep-single are two decisions: run them one at a time")
                if (args.load or args.role or args.precedence or args.between or args.report or args.source_id
                        or any(value for key, value in changes.items() if key != "reason")):
                    raise ValueError("/sources --no-baseline takes only --change and --reason")
                from .sources import waive_baseline

                result = waive_baseline(args.project_id, args.change, args.reason or "")
            elif args.keep_single:
                # T2-05: --change CHG --keep-single --reason TEXT records the BA's escalation decision.
                if not args.change:
                    raise ValueError("/sources --keep-single needs --change CHG-NNN")
                if (args.load or args.role or args.precedence or args.between or args.report or args.source_id
                        or any(value for key, value in changes.items() if key != "reason")):
                    raise ValueError("/sources --keep-single takes only --change and --reason")
                from .sources import keep_single_change

                result = keep_single_change(args.project_id, args.change, args.reason or "")
            elif args.load or args.change:
                # IMP-400: --load PATH --role ROLE [--change CHG] registers a source with its role.
                if args.precedence or args.between or args.report or args.source_id or any(value for value in changes.values()):
                    raise ValueError("/sources --load takes only --role, --change, --derived-from and --reliability")
                if not args.load:
                    raise ValueError("/sources --change goes with --load PATH --role ROLE")
                if not args.role:
                    raise ValueError("/sources --load needs --role pedido|linea_de_base|plan_previo|diseno_nuevo")
                result = load_source(args.project_id, Path(args.load), args.role, args.change,
                                     derived_from=args.derived_from or None, reliability=args.reliability or None)
                result = {**result, "message": load_message(args.project_id, result)}
            elif args.precedence or args.between:
                if not (args.precedence and args.between):
                    raise ValueError("/sources --precedence SCOPE goes with --between F-NN,F-NN")
                if args.report or args.source_id or role_option or any(value for value in changes.values()):
                    # IMP-333: other options used to be ignored in silence
                    raise ValueError("/sources --precedence --between takes no other option")
                ids = [item.strip() for item in args.between.split(",") if item.strip()]
                result = source_precedence(args.project_id, args.precedence, ids)
            elif args.report:
                if args.source_id or role_option or any(value for value in changes.values()):
                    raise ValueError("/sources --report takes no other option")
                result = write_closing_report(args.project_id)
            elif args.source_id:
                result = update_source(args.project_id, args.source_id, role=role_option, **changes)
            elif role_option or any(value for value in changes.values()):
                raise ValueError("/sources needs --id F-NN to change a row (--role goes with --id F-NN or --load PATH)")
            else:
                result = list_sources(args.project_id)
            print_json(result)
        elif args.command == "export":
            from .export import export_artifact

            result = export_artifact(args.project_id, args.artifact, args.format, args.domain, final=args.final,
                                     change_id=args.change)
            print_json(result)
        elif args.command == "specs":
            if args.change:
                from .changes import get_change
                from .compilers.change_specs import compile_change_specs

                get_change(args.project_id, args.change)
                result = compile_change_specs(args.project_id, args.change)
            else:
                from .generation import generate_specs

                result = generate_specs(args.project_id)
            print_json(result)
        elif args.command == "backlog":
            if args.change:
                from .changes import get_change
                from .compilers.change_backlog import compile_change_backlog

                get_change(args.project_id, args.change)
                result = compile_change_backlog(
                    args.project_id, args.change,
                    story_format=args.story_format, with_task_seeds=bool(args.with_task_seeds),
                )
            else:
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
        elif args.command == "trace" and args.reviewed:
            from .health import review_suspicious_links, run_health

            if args.release:
                raise ValueError("/trace --reviewed applies to the project, not to a release")
            result = review_suspicious_links(args.project_id, args.reviewed, args.reason)
            result["health"] = run_health(args.project_id)["verdict"]  # the finding it cleared
            print_json(result)
        elif args.command == "trace":
            from .core.graph import load_graph
            from .traceability import write_mermaid_graph, write_traceability_matrix

            if args.reason:
                raise ValueError("/trace --reason goes with --reviewed CHG-NNN")
            matrix = write_traceability_matrix(args.project_id)
            mermaid = write_mermaid_graph(args.project_id)
            result = {"graph": load_graph(args.project_id), "matrix": str(matrix), "mermaid": str(mermaid)}
            print_json(result)
        elif args.command == "validate":
            if args.change:
                from .change_validation import validate_change
                from .changes import get_change

                get_change(args.project_id, args.change)
                result = validate_change(args.project_id, args.change)
            else:
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
        try:
            from .protocols import settle_after_failure

            settle_after_failure(args.command, getattr(args, "project_id", None))  # IMP-369
        except Exception:  # noqa: BLE001 - reporting the original error matters more
            pass
        return report_error(exc)


def report_error(exc: BaseException) -> int:
    """IMP-302: print the error and its next step; return its exit code (see sentinel/errors.py)."""
    code = exit_code_for(exc)
    print(f"sentinel error: {exc}", file=sys.stderr)
    next_step = next_step_for(exc)
    if next_step:
        skill = skill_for_next_text(next_step)
        print(f"next step: {next_step} (skill: {skill})" if skill else f"next step: {next_step}", file=sys.stderr)
    if code == EXIT_BUG:
        traceback.print_exception(exc, file=sys.stderr)
    return code


_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def normalize_slash_command(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    first = argv[0]
    if first.startswith("/") and first[1:] in COMMANDS:
        return [first[1:], *argv[1:]]
    # IMP-315: Git Bash (MSYS) rewrites a leading `/init` into its own install
    # path (`C:/Program Files/Git/init`) before Python starts. Claude Code on
    # Windows runs the plugin's commands through Git Bash, so read a drive path
    # whose last segment is a command back as that command.
    if _DRIVE_PATH.match(first):
        name = re.split(r"[\\/]", first)[-1]
        if name in COMMANDS:
            return [name, *argv[1:]]
    return argv


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=True))
