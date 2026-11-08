from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .core.io import read_json
from .resources import read_package_json

_DEFAULT_HANDOFF_CONTRACTS_DIR = Path(__file__).resolve().parent / "handoff_contracts"
HANDOFF_CONTRACTS_DIR = _DEFAULT_HANDOFF_CONTRACTS_DIR


def load_handoff_contract_registry(contracts_dir: Path | str | None = None) -> dict[str, Any]:
    """Load the declarative handoff contract registry.

    Contracts document edge-level handoff expectations. Some edges point to
    existing validation checks; only uncovered edges should declare new fields.
    """
    if contracts_dir is None and HANDOFF_CONTRACTS_DIR == _DEFAULT_HANDOFF_CONTRACTS_DIR:
        data = _load_package_cached()
    else:
        directory = Path(contracts_dir) if contracts_dir is not None else HANDOFF_CONTRACTS_DIR
        data = _load_path_cached(str(directory))
    return normalize_handoff_contract_registry(data)


@lru_cache(maxsize=None)
def _load_path_cached(directory: str) -> dict[str, Any]:
    return read_json(Path(directory) / "registry.json", {})


@lru_cache(maxsize=None)
def _load_package_cached() -> dict[str, Any]:
    return read_package_json("handoff_contracts", "registry.json")


def normalize_handoff_contract_registry(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"version": 1, "contracts": []}
    contracts = data.get("contracts", [])
    if not isinstance(contracts, list):
        contracts = []
    normalized = []
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        contract_id = str(contract.get("id", "")).strip()
        edge = str(contract.get("edge", "")).strip()
        if not contract_id or not edge:
            continue
        normalized.append(
            {
                "id": contract_id,
                "edge": edge,
                "description": str(contract.get("description", "")).strip(),
                "artifact": str(contract.get("artifact", "")).strip(),
                "existing_check": str(contract.get("existing_check", "")).strip(),
                "required_fields": normalize_required_fields(contract.get("required_fields", [])),
            }
        )
    return {"version": int(data.get("version", 1) or 1), "contracts": normalized}


def normalize_required_fields(fields: Any) -> list[dict[str, Any]]:
    if not isinstance(fields, list):
        return []
    normalized = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("id", "")).strip()
        markers = [str(marker).strip() for marker in field.get("markers", []) if str(marker).strip()]
        if field_id and markers:
            normalized.append(
                {
                    "id": field_id,
                    "description": str(field.get("description", "")).strip(),
                    "markers": markers,
                }
            )
    return normalized
