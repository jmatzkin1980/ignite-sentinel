from __future__ import annotations

from typing import Any


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
    """Parse the small YAML frontmatter subset emitted by Sentinel artifacts."""
    block = frontmatter_block(text)
    if block is None:
        return {}
    data: dict[str, Any] = {}
    current_key = ""
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - ") and current_key:
            values = data.setdefault(current_key, [])
            if isinstance(values, list):
                values.append(raw_line[4:].strip())
            continue
        if ":" in raw_line and not raw_line.startswith(" "):
            key, value = raw_line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            data[current_key] = [] if value == "" else value.strip('"')
    return data


def render_frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(frontmatter_list([str(item) for item in value]).splitlines())
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
