"""IMP-410 (H27 inc 3): the earlier decisions a change's questions already have.

The side file `01_discovery/CHG-nnn/prior_decisions.json` maps a question id to the decision that already
answers it. It never rewrites `gaps.md` rows by itself: `render_gaps` reads it to prefill the section, and
the BA confirms (`/gaps --change --id --accept-prior`, or an answer file) or writes a new answer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.io import read_json, write_json


def prior_path(base: Path, change_id: str) -> Path:
    return base / "01_discovery" / change_id / "prior_decisions.json"


def load_priors(base: Path, change_id: str) -> dict[str, dict]:
    data = read_json(prior_path(base, change_id), {})
    return {str(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def save_priors(base: Path, change_id: str, entries: dict[str, dict]) -> None:
    write_json(prior_path(base, change_id), entries)


def _flat(text: Any) -> str:
    return " ".join(str(text or "").split())


def prior_note(entry: dict, language: str) -> str:
    """The `resolution_note` of a PRE_DECIDED row."""
    prior, answer = entry.get("prior", ""), _flat(entry.get("answer"))[:120]
    if entry.get("match") == "suggested":
        return f"posible decisión previa en {prior}: {answer}" if language == "es" else f"possible earlier decision in {prior}: {answer}"
    if entry.get("match") == "design_request":
        return (f"ya registrado en el pedido como pedido a Diseño ({prior}): {answer}" if language == "es"
                else f"already registered in the request as a request to Design ({prior}): {answer}")
    return f"ya decidido en {prior}: {answer}" if language == "es" else f"already decided in {prior}: {answer}"


def prefill_lines(entry: dict, gap_id: str, project_id: str, change_id: str, language: str) -> list[str]:
    prior, answer = entry.get("prior", ""), _flat(entry.get("answer"))
    es = language == "es"
    match = entry.get("match")
    if match == "suggested":
        return [f"Posible decisión previa en {prior} (sugerida por memoria): {answer}" if es
                else f"Possible earlier decision in {prior} (suggested by memory): {answer}"]
    if match == "design_request":
        return [f"Ya registrado en el pedido como pedido a Diseño ({prior}): {answer}" if es
                else f"Already registered in the request as a request to Design ({prior}): {answer}"]
    command = f"/gaps {project_id} --change {change_id} --id {gap_id} --accept-prior"
    if es:
        return [f"Ya decidido en {prior}: {answer}",
                f"Si sigue valiendo, confirmalo con `{command}` o con «Estado de decisión: confirmado»; "
                "si cambió, escribí la respuesta nueva."]
    return [f"Already decided in {prior}: {answer}",
            f"If it still holds, confirm it with `{command}` or with \"Decision status: confirmed\"; "
            "if it changed, write the new answer."]


def pre_decided_gaps(project_id: str, change_id: str) -> list[dict[str, str]]:
    """The questions of the change still waiting for the BA to confirm what was already decided."""
    from .changes import change_gaps_path
    from .gaps import parse_gap_rows
    from .workspace import workspace_path

    base = workspace_path(project_id)
    path = change_gaps_path(base, change_id)
    if not path.exists():
        return []
    priors = load_priors(base, change_id)
    return [{"id": row["id"], "prior": str(priors.get(row["id"], {}).get("prior", ""))}
            for row in parse_gap_rows(path.read_text(encoding="utf-8-sig"))
            if str(row.get("status", "")).strip("`").upper() == "PRE_DECIDED"]
