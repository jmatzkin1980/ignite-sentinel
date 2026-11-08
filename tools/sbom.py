"""CycloneDX SBOM for a release (IMP-289).

    python tools/sbom.py [-o dist/ignite-sentinel.cdx.json] [--root PATH]

Built from ``pyproject.toml`` (the package: name, version, license; the runtime
has no dependencies) and the hash-pinned locks of the optional extras in
``constraints/*.txt`` (one ``library`` component per pinned version, with its
SHA-256 hashes, the extras that pull it and its environment marker). Stdlib only
and deterministic: the serial number derives from the content, and the timestamp
is only written from ``SOURCE_DATE_EPOCH`` / ``--source-date-epoch``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_constraints  # noqa: E402

SPEC_VERSION = "1.6"
PROPERTY_PREFIX = "ignite-sentinel"


def purl(name: str, version: str) -> str:
    return f"pkg:pypi/{check_constraints.normalize_name(name)}@{version}"


def build_sbom(root: Path, source_date_epoch: int | None = None) -> dict:
    root = Path(root)
    project = check_constraints.load_project(root)
    name, version = project.get("name", ""), project.get("version", "")
    root_ref = purl(name, version)
    extras: dict[str, list[str]] = project.get("optional-dependencies", {})
    locks = check_constraints.lock_files(root)

    components: dict[str, dict] = {}
    direct: set[str] = set()
    fingerprint = hashlib.sha256(f"{root_ref}\n".encode("utf-8"))
    for extra in sorted(extras):
        path = locks.get(extra)
        if path is None:
            continue
        text = path.read_text(encoding="utf-8")
        fingerprint.update(f"{extra}\n{text}\n".encode("utf-8"))
        direct_names = set()
        for requirement in extras[extra]:
            match = check_constraints.NAME_RE.match(requirement)
            if match:
                direct_names.add(check_constraints.normalize_name(match.group(1)))
        for req in check_constraints.parse_requirements(text):
            if not req.name or not req.version:
                continue
            ref = purl(req.name, req.version)
            component = components.setdefault(ref, {
                "type": "library",
                "bom-ref": ref,
                "name": req.name,
                "version": req.version,
                "purl": ref,
                "hashes": [],
                "_extras": set(),
                "_markers": set(),
            })
            for value in req.hashes:
                entry = {"alg": "SHA-256", "content": value.split(":", 1)[1]}
                if entry not in component["hashes"]:
                    component["hashes"].append(entry)
            component["_extras"].add(extra)
            if req.marker:
                component["_markers"].add(req.marker)
            if req.name in direct_names:
                direct.add(ref)

    ordered = []
    for ref in sorted(components):
        component = components[ref]
        properties = [{"name": f"{PROPERTY_PREFIX}:extra", "value": extra} for extra in sorted(component.pop("_extras"))]
        properties += [{"name": f"{PROPERTY_PREFIX}:marker", "value": marker} for marker in sorted(component.pop("_markers"))]
        component["properties"] = properties
        ordered.append(component)

    root_component = {"type": "application", "bom-ref": root_ref, "name": name, "version": version, "purl": root_ref}
    if project.get("license"):
        root_component["licenses"] = [{"license": {"id": project["license"]}}]
    metadata: dict = {
        "tools": {"components": [{"type": "application", "name": "ignite-sentinel tools/sbom.py"}]},
        "component": root_component,
    }
    if source_date_epoch is not None:
        stamp = datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc)
        metadata["timestamp"] = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"{root_ref}#{fingerprint.hexdigest()}")
    dependencies = [{"ref": root_ref, "dependsOn": sorted(direct)}]
    dependencies += [{"ref": component["bom-ref"]} for component in ordered]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": SPEC_VERSION,
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": metadata,
        "components": ordered,
        "dependencies": dependencies,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    parser.add_argument("--source-date-epoch", type=int, default=None,
                        help="timestamp (defaults to $SOURCE_DATE_EPOCH; omitted when neither is set)")
    args = parser.parse_args(argv)
    epoch = args.source_date_epoch
    if epoch is None and os.environ.get("SOURCE_DATE_EPOCH", "").isdigit():
        epoch = int(os.environ["SOURCE_DATE_EPOCH"])
    text = json.dumps(build_sbom(Path(args.root), source_date_epoch=epoch), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"SBOM written: {output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
