from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .discovery import ingest
from .generation import generate_backlog, generate_specs
from .health import run_health
from .maturity import evaluate
from .memory import ContextBroker, reindex_workspace
from .quality import generate_quality
from .sync import sync_change
from .traceability import load_graph, write_mermaid_graph, write_traceability_matrix
from .validation import validate_project
from .workspace import ensure_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel", description="Ignite Sentinel vNext Core BA CLI")
    sub = parser.add_subparsers(dest="command", required=True)

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
    retrieve_p.add_argument("--write-pack", action="store_true")

    sync_p = sub.add_parser("sync")
    sync_p.add_argument("project_id")
    sync_p.add_argument("--source", required=True)
    sync_p.add_argument("--note", default="")

    for name in ("maturity", "specs", "backlog", "quality", "health", "trace", "validate", "reindex"):
        command = sub.add_parser(name)
        command.add_argument("project_id")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            path = ensure_workspace(args.project_id)
            print(json.dumps({"workspace": str(path)}, indent=2))
        elif args.command == "ingest":
            print(json.dumps(ingest(args.project_id, Path(args.source)), indent=2))
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
                )
            else:
                result = broker.retrieve(
                    args.query,
                    args.workflow,
                    args.limit,
                    args.artifact_type,
                    args.domain,
                    args.trace_id,
                )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "sync":
            print(json.dumps(sync_change(args.project_id, Path(args.source), args.note), indent=2, ensure_ascii=False))
        elif args.command == "maturity":
            print(json.dumps(evaluate(args.project_id), indent=2, ensure_ascii=False))
        elif args.command == "specs":
            print(json.dumps(generate_specs(args.project_id), indent=2, ensure_ascii=False))
        elif args.command == "backlog":
            print(json.dumps(generate_backlog(args.project_id), indent=2, ensure_ascii=False))
        elif args.command == "quality":
            print(json.dumps(generate_quality(args.project_id), indent=2, ensure_ascii=False))
        elif args.command == "health":
            print(json.dumps(run_health(args.project_id), indent=2, ensure_ascii=False))
        elif args.command == "trace":
            matrix = write_traceability_matrix(args.project_id)
            mermaid = write_mermaid_graph(args.project_id)
            print(json.dumps({"graph": load_graph(args.project_id), "matrix": str(matrix), "mermaid": str(mermaid)}, indent=2, ensure_ascii=False))
        elif args.command == "validate":
            result = validate_project(args.project_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["verdict"] == "VALID" else 1
        elif args.command == "reindex":
            print(json.dumps(reindex_workspace(args.project_id), indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"sentinel error: {exc}", file=sys.stderr)
        return 1
