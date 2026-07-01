from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


_MARKDOWN_PARSE_CACHE: dict[tuple[Path, int, int, str, tuple[tuple[str, Any], ...]], Any] = {}
_MARKDOWN_PARSE_CACHE_HITS = 0
_MARKDOWN_PARSE_CACHE_MISSES = 0


def clear_markdown_parse_cache() -> None:
    global _MARKDOWN_PARSE_CACHE_HITS, _MARKDOWN_PARSE_CACHE_MISSES
    _MARKDOWN_PARSE_CACHE.clear()
    _MARKDOWN_PARSE_CACHE_HITS = 0
    _MARKDOWN_PARSE_CACHE_MISSES = 0


def markdown_parse_cache_stats() -> dict[str, int]:
    return {
        "entries": len(_MARKDOWN_PARSE_CACHE),
        "hits": _MARKDOWN_PARSE_CACHE_HITS,
        "misses": _MARKDOWN_PARSE_CACHE_MISSES,
    }


def _cache_key(path: Path, parser: str, options: dict[str, Any]) -> tuple[Path, int, int, str, tuple[tuple[str, Any], ...]]:
    normalized = path.expanduser().resolve(strict=False)
    stat = normalized.stat()
    return normalized, stat.st_mtime_ns, stat.st_size, parser, tuple(sorted(options.items()))


def _cached_markdown_parse(path: Path, parser: str, options: dict[str, Any], parse) -> Any:
    global _MARKDOWN_PARSE_CACHE_HITS, _MARKDOWN_PARSE_CACHE_MISSES
    key = _cache_key(path, parser, options)
    if key in _MARKDOWN_PARSE_CACHE:
        _MARKDOWN_PARSE_CACHE_HITS += 1
        return deepcopy(_MARKDOWN_PARSE_CACHE[key])
    _MARKDOWN_PARSE_CACHE_MISSES += 1
    result = parse(path.read_text(encoding="utf-8"))
    normalized, _, _, _, option_items = key
    for stale_key in [
        existing
        for existing in _MARKDOWN_PARSE_CACHE
        if existing[0] == normalized and existing[3] == parser and existing[4] == option_items
    ]:
        _MARKDOWN_PARSE_CACHE.pop(stale_key, None)
    _MARKDOWN_PARSE_CACHE[key] = result
    return deepcopy(result)


def parse_table_rows(
    text: str,
    *,
    strip_code_ticks: bool = True,
    skip_separator_rows: bool = False,
    require_pipe: bool = True,
) -> list[list[str]]:
    """Parse Sentinel-controlled Markdown table rows.

    This intentionally mirrors the simple table splitting already used across
    the runtime. It is not a full Markdown table parser.
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if require_pipe and not stripped.startswith("|"):
            continue
        cells = split_table_row(stripped, strip_code_ticks=strip_code_ticks)
        if skip_separator_rows and is_separator_row(cells):
            continue
        rows.append(cells)
    return rows


def parse_table_rows_file(
    path: Path,
    *,
    strip_code_ticks: bool = True,
    skip_separator_rows: bool = False,
    require_pipe: bool = True,
) -> list[list[str]]:
    return _cached_markdown_parse(
        path,
        "parse_table_rows",
        {
            "strip_code_ticks": strip_code_ticks,
            "skip_separator_rows": skip_separator_rows,
            "require_pipe": require_pipe,
        },
        lambda text: parse_table_rows(
            text,
            strip_code_ticks=strip_code_ticks,
            skip_separator_rows=skip_separator_rows,
            require_pipe=require_pipe,
        ),
    )


def table_to_dicts(
    text: str,
    headers: list[str] | None = None,
    *,
    strip_code_ticks: bool = True,
) -> list[dict[str, str]]:
    rows = parse_table_rows(text, strip_code_ticks=strip_code_ticks, skip_separator_rows=True)
    if not rows:
        return []
    keys = headers or rows[0]
    data_rows = rows if headers else rows[1:]
    return [
        {key: row[index] if index < len(row) else "" for index, key in enumerate(keys)}
        for row in data_rows
    ]


def table_to_dicts_file(
    path: Path,
    headers: list[str] | None = None,
    *,
    strip_code_ticks: bool = True,
) -> list[dict[str, str]]:
    return _cached_markdown_parse(
        path,
        "table_to_dicts",
        {
            "headers": tuple(headers or []),
            "strip_code_ticks": strip_code_ticks,
        },
        lambda text: table_to_dicts(text, headers=headers, strip_code_ticks=strip_code_ticks),
    )


def split_table_row(line: str, *, strip_code_ticks: bool = True) -> list[str]:
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if strip_code_ticks:
        return [cell.strip("`") for cell in cells]
    return cells


def is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(cell and set(cell.replace(":", "").strip()) <= {"-"} for cell in cells)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse small YAML frontmatter subset emitted by Sentinel artifacts."""
    block = frontmatter_block(text)
    if block is None:
        return {}
    data: dict[str, Any] = {}
    current_key = ""
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        stripped_line = raw_line.lstrip()
        if stripped_line.startswith("- ") and current_key:
            values = data.setdefault(current_key, [])
            if isinstance(values, list):
                values.append(stripped_line[2:].strip())
            continue
        if raw_line.startswith("  ") and current_key and ":" in raw_line:
            values = data.setdefault(current_key, {})
            if values == []:
                values = {}
                data[current_key] = values
            if isinstance(values, dict):
                key, value = raw_line.strip().split(":", 1)
                values[key.strip()] = value.strip().strip('"')
            continue
        if ":" in raw_line and not raw_line.startswith(" "):
            key, value = raw_line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            data[current_key] = [] if value == "" else value.strip('"')
    return data


def parse_frontmatter_file(path: Path) -> dict[str, Any]:
    return _cached_markdown_parse(path, "parse_frontmatter", {}, parse_frontmatter)


def render_frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(frontmatter_list([str(item) for item in value]).splitlines())
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for subkey, subvalue in value.items():
                lines.append(f"  {subkey}: {subvalue}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def frontmatter_list(values: list[str]) -> str:
    return "\n".join(f"  - {value}" for value in values)


def frontmatter_block(text: str) -> str | None:
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return None
    start, end = bounds
    return text[start:end]


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return 4, end


def update_frontmatter_keys(
    text: str,
    updates: dict[str, str],
    *,
    quote_keys: set[str] | None = None,
) -> str | None:
    """Update scalar keys in an existing Sentinel frontmatter block.

    The function preserves existing key order and list blocks. New scalar keys
    are inserted after status when present, matching story lifecycle behavior.
    """
    bounds = frontmatter_bounds(text)
    if bounds is None:
        return None
    parse_frontmatter(text)
    quote_keys = quote_keys or set()
    start, end = bounds
    lines = text[start:end].splitlines()
    for key, value in updates.items():
        lines = upsert_frontmatter_scalar(lines, key, value, quote=key in quote_keys)
    return "---\n" + "\n".join(lines) + text[end:]


def upsert_frontmatter_scalar(lines: list[str], key: str, value: str, *, quote: bool = False) -> list[str]:
    rendered = f'{key}: "{value}"' if quote else f"{key}: {value}"
    for index, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            result = list(lines)
            result[index] = rendered
            return result
    result = list(lines)
    insert_at = 0
    for index, line in enumerate(result):
        if line.startswith("status:"):
            insert_at = index + 1
            break
    result.insert(insert_at, rendered)
    return result
