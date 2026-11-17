"""Small shared helpers that several commands used to copy (IMP-338)."""
from __future__ import annotations

from pathlib import Path

from ..errors import InputError
from .io import read_json
from .paths import state_path

PROJECT_LANGUAGES = {"es", "en"}
UNIQUE_PATH_LIMIT = 1000


def project_language(project_id: str) -> str:
    """The project's language from its state, `en` when unset or unknown."""
    state = read_json(state_path(project_id), {})
    language = state.get("project_language", "en") if isinstance(state, dict) else "en"
    return str(language) if language in PROJECT_LANGUAGES else "en"


def unique_path(path: Path, limit: int = UNIQUE_PATH_LIMIT) -> Path:
    """`path` if it is free, else the first free `<stem>-N<suffix>` with N from 2.

    Stops after `limit` candidates and raises an input error instead of looping.
    """
    if not path.exists():
        return path
    for index in range(2, limit):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise InputError(f"Could not allocate a unique path for {path}: {limit - 2} numbered copies already exist.")
