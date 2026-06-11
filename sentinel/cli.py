from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .doctor import run_doctor
from .context_requests import generate_context_request
from .discovery import apply_annotation
from .discovery import ingest
from .discovery import regenerate_gaps
from .export import export_artifact
from .gap_resolution import resolve_gaps
from .generation import generate_backlog, generate_specs
from .health import run_health
from .maturity import evaluate, generate_project_brief
from .memory import ContextBroker, reindex_workspace
from .protocols import postflight_command, preflight_command
from .quality import generate_quality
from .status import project_status
from .sync import sync_change, sync_pending_sources
from .traceability import load_graph, write_mermaid_graph, write_traceability_matrix
from .validation import validate_project
from .workspace import ensure_workspace

COMMANDS = {
    "doctor",
    "init",
    "ingest",
    "retrieve",
    "sync",
    "maturity",
    "specs",
    "backlog",
    "quality",
    "health",
    "trace",
    "validate",
    "reindex",
    "gaps",
    "annotate",
    "brief",
    "resolve-gaps",
    "context-request",
    "status",
    "export",
}


def main(argv: list[str] | None = None) -> int:
    argv = normalize_slash_command(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Ignite Sentinel vNext Core BA CLI. Commands accept slash aliases, e.g. `/maturity PROJECT_ID`.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_p = sub.add_parser("doctor")
    doctor_p.add_argument("--root", default=".")

    init_p = sub.add_parser("init")
    init_p.add_argument("project_id")

    ingest_p = sub.add_parser("ingest")
    ingest_p.add_argument("project_id")
    ingest_p.add_argument("--source", required=True)

    retrieve_p = sub.add_parser("retrieve")
    retrieve_p.add_argument("project_id")
    retrieve_p.add_argument("--query", required=True)
    retrieve_p.add_argument("--workflow", required=True)
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

    sync_p = sub.add_parser("sync")
    sync_p.add_argument("project_id")
    sync_p.add_argument("--source")
    sync_p.add_argument("--note", default="")

    resolve_p = sub.add_parser("resolve-gaps")
    resolve_p.add_argument("project_id")
    resolve_p.add_argument("--source", required=True)

    annotate_p = sub.add_parser("annotate")
    annotate_p.add_argument("project_id")
    annotate_p.add_argument("--source", required=True)

    context_request_p = sub.add_parser("context-request")
    context_request_p.add_argument("project_id")
    context_request_p.add_argument("--domain", required=True, choices=["technology", "design", "quality", "frontend", "backend"])

    export_p = sub.add_parser("export")
    export_p.add_argument("project_id")
    export_p.add_argument("--artifact", required=True, choices=["gaps", "brief", "context-request"])
    export_p.add_argument("--format", default="md", choices=["md"])
    export_p.add_argument("--domain")

    for name in ("maturity", "specs", "backlog", "quality", "health", "trace", "validate", "reindex", "gaps", "brief", "status"):
        command = sub.add_parser(name)
        command.add_argument("project_id")

    args = parser.parse_args(argv)
    try:
        project_id = getattr(args, "project_id", None)
        preflight_command(args.command, project_id)
        result = None
        if args.command == "init":
            path = ensure_workspace(args.project_id)
            result = {"workspace": str(path)}
            print_json(result)
        elif args.command == "doctor":
            result = run_doctor(Path(args.root))
            print_json(result)
            return 0 if result["verdict"] == "PASS" else 1
        elif args.command == "ingest":
            result = ingest(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "retrieve":
            broker = ContextBroker(args.project_id)
            if args.write_pack:
                result = broker.build_context_pack(
                    args.query,
                    args.workflow,
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
                )
            else:
                result = broker.retrieve(
                    args.query,
                    args.workflow,
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
                )
            print_json(result)
        elif args.command == "sync":
            if args.source:
                result = sync_change(args.project_id, Path(args.source), args.note)
            else:
                result = sync_pending_sources(args.project_id, args.note or "autonomous sync")
            print_json(result)
        elif args.command == "gaps":
            result = regenerate_gaps(args.project_id)
            print_json(result)
        elif args.command == "resolve-gaps":
            result = resolve_gaps(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "annotate":
            result = apply_annotation(args.project_id, Path(args.source))
            print_json(result)
        elif args.command == "maturity":
            result = evaluate(args.project_id)
            print_json(result)
        elif args.command == "brief":
            result = generate_project_brief(args.project_id)
            print_json(result)
        elif args.command == "context-request":
            result = generate_context_request(args.project_id, args.domain)
            print_json(result)
        elif args.command == "status":
            result = project_status(args.project_id)
            print_json(result)
        elif args.command == "export":
            result = export_artifact(args.project_id, args.artifact, args.format, args.domain)
            print_json(result)
        elif args.command == "specs":
            result = generate_specs(args.project_id)
            print_json(result)
        elif args.command == "backlog":
            result = generate_backlog(args.project_id)
            print_json(result)
        elif args.command == "quality":
            result = generate_quality(args.project_id)
            print_json(result)
        elif args.command == "health":
            result = run_health(args.project_id)
            print_json(result)
        elif args.command == "trace":
            matrix = write_traceability_matrix(args.project_id)
            mermaid = write_mermaid_graph(args.project_id)
            result = {"graph": load_graph(args.project_id), "matrix": str(matrix), "mermaid": str(mermaid)}
            print_json(result)
        elif args.command == "validate":
            result = validate_project(args.project_id)
            print_json(result)
            postflight_command(args.command, project_id, result)
            return 0 if result["verdict"] == "VALID" else 1
        elif args.command == "reindex":
            result = reindex_workspace(args.project_id)
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
