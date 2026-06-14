from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DOMAINS = [
    "product",
    "business",
    "functional",
    "technical",
    "design",
    "quality",
    "delivery",
    "compliance",
]

WORKSPACE_DIRS = [
    "00_raw",
    "00_raw/00_client_requirement",
    "00_raw/01_business_context",
    "00_raw/02_technology_context",
    "00_raw/03_design_context",
    "00_raw/04_quality_context",
    "00_raw/05_interactions",
    "01_discovery",
    "02_requirements",
    "03_specs",
    "04_backlog",
    "05_quality",
    "06_traceability",
    "07_changes",
    "07_changes/00_client_responses",
    "07_changes/01_meetings",
    "07_changes/02_mail_slack",
    "07_changes/03_domain_updates",
    "08_context_packs",
    "08_context_packs/requests",
    "08_context_packs/exports",
    "memory.lancedb",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path.cwd()


def workspace_path(project_id: str, root: Path | None = None) -> Path:
    return (root or repo_root()) / "workspaces" / project_id


def state_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "state.json"


def graph_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "06_traceability" / "traceability_graph.json"


def config_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "sentinel.config.yaml"


def memory_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "memory.lancedb" / "memory.json"


def source_manifest_path(project_id: str, root: Path | None = None) -> Path:
    return workspace_path(project_id, root) / "00_raw" / "source_manifest.json"


def ensure_workspace(project_id: str, root: Path | None = None) -> Path:
    base = workspace_path(project_id, root)
    for relative in WORKSPACE_DIRS:
        (base / relative).mkdir(parents=True, exist_ok=True)
    if not state_path(project_id, root).exists():
        write_json(
            state_path(project_id, root),
            {
                "project_id": project_id,
                "phase": "initialized",
                "health": "DIRTY",
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "artifacts": {},
                "project_language": "auto",
                "privacy_mode": "local-only",
                "readiness_stage": "DISCOVERY_RAW",
                "gap_counts": {},
                "metrics": {
                    "requirements": 0,
                    "gaps_open": 0,
                    "decisions_pending": 0,
                    "user_stories": 0,
                },
            },
        )
    if not graph_path(project_id, root).exists():
        write_json(graph_path(project_id, root), {"nodes": [], "edges": []})
    if not config_path(project_id, root).exists():
        config_path(project_id, root).write_text(default_config(project_id), encoding="utf-8")
    if not memory_path(project_id, root).exists():
        write_json(memory_path(project_id, root), {"chunks": [], "artifacts": [], "trace_edges": []})
    if not source_manifest_path(project_id, root).exists():
        write_json(source_manifest_path(project_id, root), {"sources": {}})
    return base


def default_config(project_id: str) -> str:
    domains = "\n".join(f"  - {domain}" for domain in DEFAULT_DOMAINS)
    return f"""project_id: {project_id}
version: 0.1.0
project_language: auto
privacy_mode: local-only
domains:
{domains}
maturity:
  blocking_gap_severities:
    - critical
    - high
  required_domains:
    - product
    - functional
    - quality
gap_resolution:
  auto_close_rule: confirmed_structured
backlog_gate:
  threshold: 1.0
  strict: false
privacy_scan:
  mode: warn
memory:
  provider: lancedb-hybrid
  lancedb_optional: true
  fallback: json-hybrid
  embedding: local-hash
  context_folders:
    - 00_raw/00_client_requirement
    - 00_raw/01_business_context
    - 00_raw/02_technology_context
    - 00_raw/03_design_context
    - 00_raw/04_quality_context
    - 00_raw/05_interactions
"""


def load_config(project_id: str, root: Path | None = None) -> dict[str, Any]:
    path = config_path(project_id, root)
    if not path.exists():
        return {
            "project_id": project_id,
            "project_language": "auto",
            "privacy_mode": "local-only",
            "domains": DEFAULT_DOMAINS,
            "maturity": {
                "blocking_gap_severities": ["critical", "high"],
                "required_domains": ["product", "functional", "quality"],
            },
            "gap_resolution": {"auto_close_rule": "confirmed_structured"},
            "backlog_gate": {"threshold": "1.0", "strict": False},
            "privacy_scan": {"mode": "warn"},
            "memory": {"provider": "lancedb-hybrid", "fallback": "json-hybrid", "embedding": "local-hash"},
        }
    return parse_simple_yaml(path.read_text(encoding="utf-8"))


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset emitted by default_config without external deps."""
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line.endswith(":"):
            current_section = line[:-1]
            data[current_section] = []
            current_key = None
        elif indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = coerce_scalar(value.strip())
            current_section = None
            current_key = None
        elif indent == 2 and line.startswith("- ") and current_section:
            if not isinstance(data.get(current_section), list):
                data[current_section] = []
            data[current_section].append(coerce_scalar(line[2:].strip()))
        elif indent == 2 and current_section and ":" in line:
            if not isinstance(data.get(current_section), dict):
                data[current_section] = {}
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            data[current_section][key] = [] if value == "" else coerce_scalar(value)
            current_key = key
        elif indent == 4 and line.startswith("- ") and current_section and current_key:
            section = data.setdefault(current_section, {})
            section.setdefault(current_key, [])
            section[current_key].append(coerce_scalar(line[2:].strip()))
    return data


def coerce_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_state(project_id: str, **changes: Any) -> dict[str, Any]:
    state = read_json(state_path(project_id), {})
    state.update(changes)
    state["updated_at"] = utc_now()
    write_json(state_path(project_id), state)
    return state
