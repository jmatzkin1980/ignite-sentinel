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
)

__all__ = [
    "frontmatter_list",
    "parse_frontmatter",
    "parse_table_rows",
    "render_frontmatter",
    "table_to_dicts",
]
