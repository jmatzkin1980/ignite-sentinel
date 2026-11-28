"""IMP-429 (H27 inc 7d): the project's release flow (specs, backlog, close, move) on the synthetic series,
and the machine-independent sha256 of what it writes (RF 4: the project output does not change a byte)."""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from sentinel.cli import main
from sentinel.memory import ContextBroker

ROOT = Path(__file__).resolve().parent
FX = ROOT / "fixtures" / "synthetic_series"
P = "CLAIMS"


def _cli(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(argv)
    return code, out.getvalue()


def run_release_flow(work: Path) -> None:
    """In `work`: v2 flow, confirm, r1 specs/backlog, r1 stories Done, close r1, move C-02 r3 -> r2."""
    old = os.getcwd()
    os.chdir(work)
    try:
        with patch.object(ContextBroker, "_connect_lancedb", lambda self: None):
            steps = [["init", P]]
            steps += [["ingest", P, "--source", str(FX / n)] + (["--replace"] if i else [])
                      for i, n in enumerate(("requirement.md", "approval_notes.md", "payment_notes.md"))]
            steps += [["gaps", P], ["resolve-gaps", P, "--source", str(FX / "gap_responses.md")], ["maturity", P],
                      ["brief", P, "--profile", "UI", "--genesis", "greenfield"],
                      ["split", P, "--propose", "--source", str(FX / "proposal.json")],
                      ["split", P, "--confirm", "--ba", "Synthetic BA", "--tech", "Synthetic team"],
                      ["specs", P, "--release", "r1"], ["backlog", P, "--release", "r1"]]
            for argv in steps:
                code, text = _cli(argv)
                if code:
                    raise AssertionError(f"{argv}: {text[-500:]}")
            base = Path("workspaces") / P
            evidence = work / "evidence.md"
            evidence.write_text("Synthetic evidence of r1.\n", encoding="utf-8")
            for sid in sorted(p.stem for p in (base / "04_backlog" / "r1").glob("US-*.md")):
                for status in ("Ready", "In Progress", "In Review", "Done"):
                    code, text = _cli(["story-status", P, "--release", "r1", "--story", sid, "--set", status])
                    if code:
                        raise AssertionError(text[-500:])
            tail = [["split", P, "--close", "r1", "--evidence", str(evidence), "--ba", "Synthetic BA", "--tech", "Synthetic team"],
                    ["split", P, "--move", "--unit", "C-02", "--from", "r3", "--to", "r2", "--reason", "the client asked for it",
                     "--ba", "Synthetic BA", "--tech", "Synthetic team"]]
            for argv in tail:
                code, text = _cli(argv)
                if code:
                    raise AssertionError(f"{argv}: {text[-500:]}")
    finally:
        os.chdir(old)


def normalized_sha256(data: bytes, tokens: list[tuple[str, str]]) -> str:
    text = data.decode("utf-8", "replace").replace(chr(13) + chr(10), chr(10))
    for value, token in tokens:
        text = text.replace(value, token)
    text = re.sub(r"[0-9a-f]{64}", "<SHA256>", text)
    text = re.sub(r"`[0-9a-f]{12}`", "`<SHA12>`", text)
    # IMP-435: the day the flow runs (a release closed, a unit moved: `date` in partition.json, scope_changes.*, the
    # release guide) is not part of the bytes; with it the baseline only held on the day it was taken.
    text = re.sub(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])", "<DATE>", text)
    # IMP-435 (B-08): specs.md quotes no machine path and is cut at a line boundary, so it is compared whole.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def release_output_hashes(work: Path) -> dict[str, str]:
    base = work / "workspaces" / P
    files = [*(base / "03_specs" / "r1").rglob("*"), *(base / "04_backlog" / "r1").rglob("*"),
             *(base / "02_requirements" / "series").glob("*")]
    tokens = []
    for root, token in ((ROOT.parent, "<REPO>"), (work, "<WORK>"), (base, "<WORK>")):
        for value in {str(root), root.as_posix(), str(root.resolve()), root.resolve().as_posix()}:
            tokens.append((value, token))
    tokens.sort(key=lambda item: -len(item[0]))
    return {path.relative_to(base).as_posix(): normalized_sha256(path.read_bytes(), tokens)
            for path in sorted(files) if path.is_file() and path.name != "status_log.md"}  # the log carries timestamps


if __name__ == "__main__":
    import json
    import sys
    with tempfile.TemporaryDirectory() as tmp:
        run_release_flow(Path(tmp))
        json.dump(release_output_hashes(Path(tmp)), sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
