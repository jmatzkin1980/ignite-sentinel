from __future__ import annotations

from importlib import resources
from typing import Any

from .core.io import read_json_resource


PACKAGE = "sentinel"


def package_resource(*parts: str) -> Any:
    return resources.files(PACKAGE).joinpath(*parts)


def read_package_json(*parts: str) -> Any:
    return read_json_resource(package_resource(*parts))


def package_json_files(directory: str) -> list[Any]:
    root = package_resource(directory)
    return sorted(
        (item for item in root.iterdir() if item.is_file() and item.name.endswith(".json")),
        key=lambda item: item.name,
    )
