"""Write eval reports and keep only the newest N per kind.

Shared by the eval runners and the retrieval eval test. Reports live under
``tests/evals/reports/`` (git-ignored, reproducible) and are named
``<kind>_<YYYY-MM-DD>.json``; a same-day rerun overwrites its file, and older
files of the same kind beyond the retention window are deleted.

Environment:
  SENTINEL_EVAL_KEEP_REPORTS  reports kept per kind (default 5; <= 0 keeps all)
  SENTINEL_EVAL_REPORTS=0     do not write reports at all (e.g. CI)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_KEEP = 5
_DATE = r"\d{4}-\d{2}-\d{2}"


def default_keep() -> int:
    try:
        return int(os.environ.get("SENTINEL_EVAL_KEEP_REPORTS", DEFAULT_KEEP))
    except ValueError:
        return DEFAULT_KEEP


def reports_enabled() -> bool:
    return os.environ.get("SENTINEL_EVAL_REPORTS", "1") != "0"


def _reports_of(kind: str, reports_dir: Path) -> list[Path]:
    pattern = re.compile(rf"^{re.escape(kind)}_{_DATE}\.json$")
    if not reports_dir.is_dir():
        return []
    # ISO dates sort lexicographically, so name order is chronological order.
    return sorted(p for p in reports_dir.iterdir() if p.is_file() and pattern.match(p.name))


def prune(kind: str, *, reports_dir: Path = REPORTS_DIR, keep: int | None = None, dry_run: bool = False) -> list[Path]:
    """Delete (or, with ``dry_run``, only list) reports of ``kind`` beyond the newest ``keep``."""
    keep = default_keep() if keep is None else keep
    if keep <= 0:
        return []
    doomed = _reports_of(kind, reports_dir)[:-keep]
    if not dry_run:
        for path in doomed:
            path.unlink(missing_ok=True)
    return doomed


def write_report(
    kind: str,
    day: str,
    payload: dict,
    *,
    reports_dir: Path = REPORTS_DIR,
    keep: int | None = None,
) -> Path | None:
    """Write ``<kind>_<day>.json`` and prune older reports of the same kind.

    Returns the written path, or ``None`` when reports are disabled.
    """
    if not reports_enabled():
        return None
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{kind}_{day}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    prune(kind, reports_dir=reports_dir, keep=keep)
    return out
