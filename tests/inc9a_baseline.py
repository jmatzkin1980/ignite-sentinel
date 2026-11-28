"""IMP-435 (H27 inc 9a) task 0: the snapshot of what the project, the change and the series write before inc 9a.

The bytes are masked with `normalized_sha256` (checkout path, line endings, hashes) and built with the JSON index, so
they are the same in any checkout and with any memory backend. `python tests/inc9a_baseline.py` prints the JSON.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from change_inc8b_flow import isolated_flow  # noqa: E402
from helpers import run_ok  # noqa: E402
from release_project_flow import normalized_sha256, run_release_flow  # noqa: E402

FX = ROOT / "fixtures" / "inc9a"
BASELINE_PATH = FX / "before_sha256.json"
DIRS = ("02_requirements", "03_specs", "04_backlog", "05_quality", "08_context_packs")
SKIP = {"status_log.md"}  # the log carries timestamps
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)?")
# specs.md and the source log quote absolute paths and are cut at a fixed length, so what a context pack retrieves from
# them (the hits in `results`, their chunk ids and lines) moves with the checkout path: the baseline keeps the pack's
# structure and drops the hits (the text of a hit is not part of what 9a changes; B-09 owns it).
SHA16 = re.compile(r'("source_sha": ")[0-9a-f]{16}')


def _drop_hits(node, key=""):
    if isinstance(node, dict):
        return {k: _drop_hits(v, k) for k, v in node.items()}
    if isinstance(node, list):
        return [] if key == "results" else [_drop_hits(item, key) for item in node]
    if isinstance(node, int) and not isinstance(node, bool):
        return 0  # the counters of the budget count hits
    return "<EVIDENCE>" if key == "evidence" else node


def mask(path: Path, data: bytes) -> bytes:
    text = STAMP.sub("<TS>", data.decode("utf-8", "replace"))
    text = SHA16.sub(r"<SHA16>", text)
    if path.suffix == ".json" and "08_context_packs" in path.parts:
        text = json.dumps(_drop_hits(json.loads(text)), indent=1, sort_keys=True, ensure_ascii=False)
    return text.encode("utf-8")


def build_alta(work: Path) -> None:
    """Project ALTA: request + answers -> brief -> specs -> backlog -> quality."""
    with isolated_flow(work):
        for argv in (["init", "ALTA"], ["ingest", "ALTA", "--source", str(FX / "pedido_alta.md")],
                     ["resolve-gaps", "ALTA", "--source", str(FX / "respuestas_alta.md")],
                     ["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"],
                     ["specs", "ALTA"], ["backlog", "ALTA"], ["quality", "ALTA"]):
            run_ok(argv)


def build_borrador(work: Path) -> None:
    """Change CHG-001 of BORR ("Guardar borrador") up to its grouped backlog."""
    import test_change_next as tcn
    with isolated_flow(work):
        tcn.ChangeNextSequence.build_workspace()
        tcn.ChangeNextSequence("test_each_row_of_the_table_in_order").test_each_row_of_the_table_in_order()


def hashes(work: Path, project: str, release_filter: str | None = None) -> dict[str, str]:
    base = work / "workspaces" / project
    tokens = []
    for root, token in ((ROOT.parent, "<REPO>"), (work, "<WORK>"), (base, "<WORK>")):
        for value in {str(root), root.as_posix(), str(root.resolve()), root.resolve().as_posix()}:
            tokens.append((value, token))
    tokens.sort(key=lambda item: -len(item[0]))
    out = {}
    for name in DIRS:
        for path in sorted((base / name).rglob("*")):
            if path.is_file() and path.name not in SKIP:
                out[path.relative_to(base).as_posix()] = normalized_sha256(mask(path, path.read_bytes()), tokens)
    return out


def snapshot(work: Path) -> dict[str, dict[str, str]]:
    """Build the three scenarios under `work` and hash what they wrote."""
    result = {}
    for name, project, build in (("alta", "ALTA", build_alta), ("borrador", "BORR", build_borrador),
                                 ("series", "CLAIMS", run_release_flow)):
        sub = work / name
        sub.mkdir()
        build(sub)
        result[name] = hashes(sub, project)
    return result


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        json.dump(snapshot(Path(tmp)), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
        sys.stdout.write("\n")
