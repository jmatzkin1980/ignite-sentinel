"""Shared Sentinel runtime primitives.

The core package starts small on purpose: it exposes behavior-preserving helpers
that existing domain modules can migrate to incrementally.
"""

from .markdown import (
    frontmatter_list,
    parse_frontmatter,
    parse_table_rows,
    render_frontmatter,
    table_to_dicts,
    update_frontmatter_keys,
)
from .io import append_text, read_json, write_json
from .paths import (
    config_path,
    graph_path,
    memory_path,
    repo_root,
    source_manifest_path,
    state_path,
    workspace_path,
)
from .state import read_state, update_state, write_state
from .time import utc_now

__all__ = [
    "append_text",
    "config_path",
    "frontmatter_list",
    "graph_path",
    "memory_path",
    "parse_frontmatter",
    "parse_table_rows",
    "read_json",
    "read_state",
    "repo_root",
    "render_frontmatter",
    "source_manifest_path",
    "state_path",
    "table_to_dicts",
    "update_frontmatter_keys",
    "update_state",
    "utc_now",
    "workspace_path",
    "write_json",
    "write_state",
]
