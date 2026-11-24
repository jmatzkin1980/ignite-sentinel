"""IMP-406 task 4: line-range arithmetic for the extraction (pure, no I/O).

A proposal declares the lines of the element it read (`Líneas: 59-68`); the coverage is
what those lines leave out of the element's content lines.
"""
from __future__ import annotations

import re

MARKUP_ONLY = re.compile(r"^[\s|:\-*_#>`=+]*$")
_ITEM = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*$")


def parse_line_ranges(value: str) -> list[list[int]] | None:
    """`59-68, 70` -> [[59, 68], [70, 70]], sorted and merged; empty or malformed -> None."""
    found: list[list[int]] = []
    for item in re.split(r"[,;]", str(value or "")):
        match = _ITEM.match(item)
        if match is None:
            return None
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if start < 1 or end < start:
            return None
        found.append([start, end])
    if not found:
        return None
    found.sort()
    merged = [found[0]]
    for start, end in found[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def content_lines(source_lines: list[str], spans: list[list[int]]) -> list[int]:
    """The line numbers of the spans that are not empty and not only table or markup scaffolding."""
    found: list[int] = []
    for start, end in spans:
        for number in range(start, end + 1):
            if 1 <= number <= len(source_lines) and not MARKUP_ONLY.match(source_lines[number - 1]):
                found.append(number)
    return found


def compress(numbers: list[int]) -> list[list[int]]:
    ranges: list[list[int]] = []
    for number in sorted(set(numbers)):
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1][1] = number
        else:
            ranges.append([number, number])
    return ranges


def format_ranges(ranges: list[list[int]]) -> str:
    return ", ".join(f"{a}-{b}" for a, b in ranges)


def quote_span(source_lines: list[str], spans: list[list[int]], quote: str) -> tuple[int, int] | None:
    """First and last line of the first occurrence of the quote in the (whitespace-squashed) text of the spans."""
    wanted = " ".join(str(quote or "").split())
    if not wanted:
        return None
    flat: list[str] = []
    owner: list[int] = []
    for start, end in spans:
        for number in range(start, end + 1):
            if not 1 <= number <= len(source_lines):
                continue
            for word in source_lines[number - 1].split():
                if flat:
                    flat.append(" ")
                    owner.append(number)
                flat.extend(word)
                owner.extend([number] * len(word))
    text = "".join(flat)
    at = text.find(wanted)
    if at < 0:
        return None
    return owner[at], owner[at + len(wanted) - 1]
