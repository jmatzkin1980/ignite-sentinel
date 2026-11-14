"""IMP-302 (H18): typed errors and the exit codes the CLI and MCP report.

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | unexpected error (a bug): anything not listed below |
| 2 | wrong usage (argparse) |
| 3 | invalid input: an unknown project, a missing file, a refused payload |
| 4 | gate refusal: a prerequisite, the project's health or its phase stops the command |
| 5 | unfavourable verdict: `/validate` is not VALID, `/doctor` is not PASS |
| 6 | workspace busy: another command holds its lock (IMP-299) |

``SentinelError`` carries the code and, when the runtime knows it, the next step.
``InputError`` and ``GateRefusal`` are also ``RuntimeError`` so existing handlers
keep catching them. A plain ``ValueError`` is the runtime's validation idiom and
maps to 3; any other exception maps to 1.

Stdlib only; it imports nothing from the rest of the package.
"""
from __future__ import annotations

import re

EXIT_OK = 0
EXIT_BUG = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_GATE = 4
EXIT_VERDICT = 5
EXIT_BUSY = 6

EXIT_CODES: dict[int, str] = {
    EXIT_OK: "success",
    EXIT_BUG: "unexpected error",
    EXIT_USAGE: "wrong usage",
    EXIT_INPUT: "invalid input",
    EXIT_GATE: "gate refusal",
    EXIT_VERDICT: "unfavourable verdict",
    EXIT_BUSY: "workspace busy",
}

_RUN_RE = re.compile(r"\b(Run /[a-z-]+[^.]*\.)")
_BEFORE_RE = re.compile(r"\bbefore (/[a-z-]+)")


class SentinelError(Exception):
    """An error the runtime raises on purpose, with its exit code and next step."""

    code = EXIT_INPUT

    def __init__(self, message: str = "", next_step: str = "") -> None:
        super().__init__(message)
        self.next_step = next_step or infer_next_step(message)


class InputError(SentinelError, RuntimeError):
    code = EXIT_INPUT


class GateRefusal(SentinelError, RuntimeError):
    code = EXIT_GATE


class WorkspaceBusy(SentinelError, RuntimeError):
    code = EXIT_BUSY


def infer_next_step(message: str) -> str:
    """The next step a message already names: "Run /x ..." or "before /x"."""
    found = _RUN_RE.search(message or "")
    if found:
        return found.group(1)
    found = _BEFORE_RE.search(message or "")
    return f"Run {found.group(1)} first." if found else ""


def exit_code_for(exc: BaseException) -> int:
    if isinstance(exc, SentinelError):
        return exc.code
    if isinstance(exc, ValueError):
        return EXIT_INPUT
    return EXIT_BUG


def next_step_for(exc: BaseException) -> str:
    return getattr(exc, "next_step", "") or (infer_next_step(str(exc)) if exit_code_for(exc) != EXIT_BUG else "")
