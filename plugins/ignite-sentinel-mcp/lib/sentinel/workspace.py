from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.io import read_json, write_json, append_bytes, write_text
from .core.paths import (
    config_path,
    graph_path,
    memory_path,
    repo_root,
    source_manifest_path,
    state_path,
    workspace_path,
)
from .core.state import read_state, update_state, write_state
from .core.time import utc_now

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

# IMP-212: written into every workspace so a user who versions their project to
# collaborate over GitHub keeps reconstructible/regenerable paths out of git while
# the matured artifacts (the versionable source of truth) stay tracked. The user
# owns this file in their own repo; the public framework repo ignores workspaces/*
# wholesale instead (see the root .gitignore, two-audience note).
WORKSPACE_GITIGNORE = """# Per-workspace ignore rules (IMP-212). You own this in your own project repo.
# Your matured artifacts (discovery, gaps, brief, PRD, specs, backlog,
# traceability) ARE the versionable source of truth and stay tracked. The paths
# below stay OUT because they are reconstructible or regenerable, not evidence:
memory.lancedb/
08_context_packs/views/*.html
08_context_packs/synthetic/
# IMP-241: workspace-local themes (brand palettes, fonts) never enter git.
.sentinel/
"""


# IMP-26w (H16b gate): new projects compile the brief v2. A workspace created before
# this keeps no `brief_version` and stays on v1.
DEFAULT_BRIEF_VERSION = 2


def ensure_workspace(project_id: str, root: Path | None = None, brief_version: int | None = None) -> Path:
    base = workspace_path(project_id, root)
    for relative in WORKSPACE_DIRS:
        (base / relative).mkdir(parents=True, exist_ok=True)
    if not state_path(project_id, root).exists():
        write_state(  # IMP-300: durable state.json with schema_version, derived counts apart
            project_id,
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
                "brief_settings": {"brief_version": int(brief_version or DEFAULT_BRIEF_VERSION)},
                "gap_counts": {},
                "metrics": {
                    "requirements": 0,
                    "gaps_open": 0,
                    "decisions_pending": 0,
                    "user_stories": 0,
                },
            },
            root,
        )
    if not graph_path(project_id, root).exists():
        write_json(graph_path(project_id, root), {"nodes": [], "edges": []})
    if not config_path(project_id, root).exists():
        write_text(config_path(project_id, root), default_config(project_id))
    gitignore_file = base / ".gitignore"
    if not gitignore_file.exists():
        write_text(gitignore_file, WORKSPACE_GITIGNORE)
    else:
        ensure_local_themes_ignored(gitignore_file)
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


LOCAL_THEMES_IGNORE_RULE = ".sentinel/"


def ensure_local_themes_ignored(gitignore_file: Path) -> bool:
    """IMP-241: append the local-themes rule to a pre-existing workspace .gitignore.

    Append-only and idempotent: existing rules are never rewritten. Returns True when
    the rule was added.
    """
    raw = gitignore_file.read_bytes()
    if local_themes_rule_present(raw):
        return False
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    prefix = b"" if not raw or raw.endswith(b"\n") else newline
    block = prefix + b"# IMP-241: workspace-local themes (brand palettes, fonts) never enter git." + newline + LOCAL_THEMES_IGNORE_RULE.encode("ascii") + newline
    append_bytes(gitignore_file, block, root=gitignore_file.parent)  # append-only: existing bytes are never rewritten
    return True


def local_themes_rule_present(raw: bytes) -> bool:
    """True when a .gitignore already excludes .sentinel/ in any common spelling."""
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    variants = {".sentinel", ".sentinel/", "/.sentinel", "/.sentinel/", ".sentinel/*", "/.sentinel/*", ".sentinel/**", "/.sentinel/**"}
    return any(line.strip().lstrip("\ufeff") in variants for line in text.splitlines())


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


