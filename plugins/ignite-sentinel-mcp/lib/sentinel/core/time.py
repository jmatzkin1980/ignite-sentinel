from __future__ import annotations

import time
from datetime import datetime, timezone


def utc_now_ns() -> int:
    """Sub-second companion of `utc_now()` for markers compared against file mtimes."""
    return time.time_ns()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
