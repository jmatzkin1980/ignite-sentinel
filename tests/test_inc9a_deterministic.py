"""IMP-435 (H27 inc 9a) task 6: the same governed outputs on any machine and memory backend, and reads that write nothing.

- B-08: a source outside the working folder shows as `F-nn` and its file name, never the machine's absolute path; the
  requirement snapshot of `specs.md` ends on a whole line.
- B-09 (owner decision Q5): `prd.md`, `specs.md`, `EPIC-*.md` and `US-*.md` quote no retrieval hit; their context rows
  come from the trace graph, so the JSON index and LanceDB write the same bytes.
- C-06 / C-15: `/status`, `/next`, `/validate`, `/view`, `/dashboard` (with and without `--release`) leave every file
  of the workspace as it was: same bytes, same modification time.
- B-39: `/doctor` warns when the installed LanceDB is not the pinned one.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from change_inc8b_flow import ISOLATED_ENV  # noqa: E402
from helpers import run_cli, run_ok  # noqa: E402
from inc9a_baseline import build_borrador  # noqa: E402
from release_project_flow import run_release_flow  # noqa: E402
from sentinel.core.io import forget_read_snapshots  # noqa: E402

FX = Path(__file__).resolve().parent / "fixtures" / "inc9a"
HAS_LANCEDB = importlib.util.find_spec("lancedb") is not None


@contextmanager
def flow(work: Path, backend: str | None = "json") -> Iterator[None]:
    """cwd `work`, no inherited memory/theme env, fresh read caches; `backend` "json" or None (LanceDB when installed)."""
    saved = {name: os.environ.pop(name) for name in ISOLATED_ENV if name in os.environ}
    old = os.getcwd()
    forget_read_snapshots()
    if backend:
        os.environ["SENTINEL_MEMORY_BACKEND"] = backend
    os.chdir(work)
    try:
        yield
    finally:
        os.chdir(old)
        os.environ.pop("SENTINEL_MEMORY_BACKEND", None)
        os.environ.update(saved)


def build_alta(work: Path, sources: Path, backend: str | None = "json", until_backlog: bool = True) -> Path:
    """Project ALTA from the request and answers copied into `sources` (a folder outside `work`)."""
    sources.mkdir(parents=True, exist_ok=True)
    for name in ("pedido_alta.md", "respuestas_alta.md"):
        shutil.copy(FX / name, sources / name)
    work.mkdir(parents=True, exist_ok=True)
    steps = [["init", "ALTA"], ["ingest", "ALTA", "--source", str(sources / "pedido_alta.md")],
             ["resolve-gaps", "ALTA", "--source", str(sources / "respuestas_alta.md")],
             ["brief", "ALTA", "--profile", "UI", "--genesis", "greenfield"], ["specs", "ALTA"]]
    if until_backlog:
        steps.append(["backlog", "ALTA"])
    with flow(work, backend):
        for argv in steps:
            run_ok(argv)
    return work / "workspaces" / "ALTA"


# The command protocol's own record of every command (IMP-300 append-only log, its lock and state backup, the rendered
# log, and `last_command`, `last_command_at`, `updated_at` in state.json) is the audit trail, not an output: it stays out of the comparison.
PROTOCOL_RECORD = (".sentinel/", "06_traceability/command_protocol_log.md")


def tree_state(root: Path) -> dict[str, tuple[str, int]]:
    out = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if f"/{PROTOCOL_RECORD[0]}" in relative or relative.endswith(PROTOCOL_RECORD[1])                 or (path.name == PROTOCOL_RECORD[1].rsplit("/", 1)[1] and "06_traceability/r" in relative):
            continue  # also the release mirror's own record (`.series_work/rN/...`) and its copy in `06_traceability/rN/`
        if path.name == "state.json":
            state = json.loads(path.read_text(encoding="utf-8"))
            for key in ("last_command", "last_command_at", "updated_at"):
                state.pop(key, None)
            out[relative] = (json.dumps(state, sort_keys=True), 0)
            continue
        out[relative] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    return out


class PathIndependence(unittest.TestCase):
    def test_specs_md_path_independent(self):
        """B-08: the same request ingested from two external folders of different length writes the same bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            short = build_alta(root / "w1", root / "s", until_backlog=False)
            long_ = build_alta(root / "w2", root / "an_external_folder_with_a_much_longer_name" / "nested" / "src",
                               until_backlog=False)
            user = Path.home().name
            for relative in ("03_specs/specs.md", "02_requirements/project-brief.md", "07_changes/source_log.md"):
                a = (short / relative).read_bytes()
                b = (long_ / relative).read_bytes()
                self.assertEqual(a, b, relative)
                text = a.decode("utf-8")
                self.assertNotIn(":/", text, relative)
                self.assertNotIn(user, text, relative)
                self.assertIn("pedido_alta.md", text, relative)


class SnapshotCut(unittest.TestCase):
    def test_snapshot_cut_at_line(self):
        """B-08: the snapshot is cut at the last line boundary before the limit, never in the middle of a word."""
        from sentinel.compilers.specs import bounded_text, render_specs

        lines = [f"- Line {n}: el analista carga los datos fiscales del proveedor número {n}." for n in range(80)]
        text = "\n".join(lines)
        cut = bounded_text(text, 2200, at_line=True)
        body = cut.split("\n\n[TRUNCATED")[0]
        self.assertIn("[TRUNCATED IN GENERATED ARTIFACT", cut)
        self.assertLessEqual(len(body), 2200)
        self.assertIn(body.splitlines()[-1], lines)
        self.assertTrue(text.startswith(body))
        specs = render_specs("ALTA", text, {}, "project-brief.md")
        snapshot = specs.split("progressive disclosure.\n\n", 1)[1].split("\n\n[TRUNCATED", 1)[0]
        self.assertIn(snapshot.splitlines()[-1], lines)


class BackendIndependence(unittest.TestCase):
    @unittest.skipUnless(HAS_LANCEDB, "lancedb is not installed")
    def test_governed_md_backend_independent(self):
        """B-09 (Q5): JSON index and LanceDB write the same prd.md, specs.md, EPIC-001.md and US-*.md."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "src"
            json_ws = build_alta(root / "json", sources, "json")
            lance_ws = build_alta(root / "lance", sources, None)
            self.assertTrue(any((lance_ws / "memory.lancedb").rglob("*.lance")), "LanceDB was not used")
            self.assertFalse(any((json_ws / "memory.lancedb").rglob("*.lance")), "the JSON run used LanceDB")
            stories = sorted(p.name for p in (json_ws / "04_backlog").glob("US-*.md"))
            self.assertTrue(stories)
            self.assertEqual(stories, sorted(p.name for p in (lance_ws / "04_backlog").glob("US-*.md")))
            for relative in ["03_specs/prd.md", "03_specs/specs.md", "04_backlog/EPIC-001.md",
                             *(f"04_backlog/{name}" for name in stories)]:
                a = (json_ws / relative).read_text(encoding="utf-8")
                b = (lance_ws / relative).read_text(encoding="utf-8")
                self.assertEqual(a, b, relative)
                self.assertNotIn("Retrieved Signal", a, relative)


class ReadOnlyCommands(unittest.TestCase):
    def test_read_only_commands_write_nothing(self):
        """C-06, C-15: the read-only commands leave every file of the workspace as it was (bytes and mtime).

        A view writes its HTML the first time; afterwards the same view rewrites nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            borr, serie = root / "borr", root / "serie"
            borr.mkdir()
            serie.mkdir()
            build_borrador(borr)
            run_release_flow(serie)
            cases = [
                (borr, "BORR", [["status", "BORR"], ["next", "BORR"], ["validate", "BORR", "--change", "CHG-001"],
                                ["view", "BORR", "--artifact", "brief", "--change", "CHG-001"], ["dashboard"]]),
                (serie, "CLAIMS", [["status", "CLAIMS"], ["next", "CLAIMS"], ["validate", "CLAIMS"], ["dashboard"],
                                   ["status", "CLAIMS", "--release", "r1"], ["next", "CLAIMS", "--release", "r1"],
                                   ["validate", "CLAIMS", "--release", "r1"]]),
            ]
            # a view's own output is its HTML file: it is rendered once first, and the read leaves it as it was.
            views = {"BORR": [["view", "BORR", "--artifact", "brief", "--change", "CHG-001"]],
                     "CLAIMS": [["view", "CLAIMS", "--artifact", "brief", "--release", "r1"]]}
            cases[1][2].append(views["CLAIMS"][0])
            for work, project, commands in cases:
                with flow(work):
                    for argv in views[project]:
                        run_ok(argv)
                    for argv in commands:
                        before = tree_state(work / "workspaces")
                        code, out = run_cli(argv)
                        # /validate exits 5 when it finds issues: a verdict, still a read
                        self.assertIn(code, (0, 5) if argv[0] == "validate" else (0,), out[-1500:])
                        after = tree_state(work / "workspaces")
                        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
                        self.assertEqual(changed, [], " ".join(argv))


class DoctorLanceDBPin(unittest.TestCase):
    def test_doctor_lancedb_pin(self):
        """B-39: an installed LanceDB that is not the pinned one is a WARN naming both versions."""
        from sentinel.doctor import lancedb_pin_check, run_doctor

        with tempfile.TemporaryDirectory() as tmp:
            constraints = Path(tmp) / "memory.txt"
            constraints.write_text("lance-namespace==0.13.0 \\\n    --hash=sha256:00\nlancedb==0.40.0 \\\n"
                                   "    --hash=sha256:11\n", encoding="utf-8")
            fake = types.SimpleNamespace(__version__="0.33.0")
            with patch.dict(sys.modules, {"lancedb": fake}), \
                    patch("sentinel.doctor.importlib.util.find_spec", return_value=object()):
                check = lancedb_pin_check(constraints)
                self.assertEqual(check["status"], "WARN")
                self.assertIn("0.33.0", check["detail"])
                self.assertIn("0.40.0", check["detail"])
            with patch.dict(sys.modules, {"lancedb": types.SimpleNamespace(__version__="0.40.0")}), \
                    patch("sentinel.doctor.importlib.util.find_spec", return_value=object()):
                self.assertEqual(lancedb_pin_check(constraints)["status"], "PASS")
            names = [c["name"] for c in run_doctor(Path(tmp))["checks"]]
            self.assertIn("LanceDB pinned version", names)


if __name__ == "__main__":
    unittest.main()
