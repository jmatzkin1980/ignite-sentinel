"""IMP-301 (H18): memory, graph and state store workspace-relative paths.

A workspace moved or cloned to another folder gives the same /validate, /health
and /retrieve, and regenerating an artifact does not duplicate its graph node.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath, PureWindowsPath

from sentinel.cli import main
from sentinel.core.paths import graph_path, memory_path, resolve_in_workspace, state_path, workspace_path, workspace_relative

PROJECT = "PORTABLE"
RAW = (
    "# Billing Portal\n\nFinance users review monthly invoices before approval. "
    "Approval must be logged with the approver and the date.\n"
)


def _run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = main(argv)
    return code, out.getvalue()


def _json(argv: list[str]) -> dict:
    code, text = _run(argv)
    assert code == 0, (argv, code, text)
    return json.loads(text)


def _raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_absolute(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _stored_paths(project_id: str) -> list[str]:
    """Every path value Sentinel persisted for the workspace: graph, memory, manifest, state."""
    values = [str(node.get("path", "")) for node in _raw(graph_path(project_id)).get("nodes", [])]
    memory = _raw(memory_path(project_id))
    for key in ("artifacts", "chunks"):
        for item in memory.get(key, []):
            values += [str(item.get("source_path", "")), str(item.get("file_path", ""))]
    manifest = memory_path(project_id).parent / "artifact_manifest.json"
    if manifest.exists():
        for item in _raw(manifest).get("artifacts", []):
            values += [str(item.get("source_path", "")), str(item.get("file_path", ""))]
    state = _raw(state_path(project_id))
    values += [str(value) for value in (state.get("artifacts") or {}).values()]
    values += [str(value) for key, value in state.items() if key.startswith("last_") and key.endswith("_source")]
    return [value for value in values if value]


class WorkspaceRelativeTests(unittest.TestCase):
    def test_paths_inside_the_workspace_become_relative(self) -> None:
        root = Path(tempfile.gettempdir()) / "repo"
        base = workspace_path(PROJECT, root)
        self.assertEqual(workspace_relative(PROJECT, (base / "03_specs" / "a.md").as_posix(), root), "03_specs/a.md")
        self.assertEqual(workspace_relative(PROJECT, "03_specs/a.md", root), "03_specs/a.md")

    def test_a_path_from_another_copy_of_the_workspace_maps_too(self) -> None:
        root = Path(tempfile.gettempdir()) / "repo"
        old = f"C:/Users/someone/OneDrive/repo/workspaces/{PROJECT}/02_requirements/project-brief.md"
        self.assertEqual(workspace_relative(PROJECT, old, root), "02_requirements/project-brief.md")
        self.assertEqual(workspace_relative(PROJECT, f"/home/u/repo/workspaces/{PROJECT}/x.md", root), "x.md")
        self.assertEqual(workspace_relative(PROJECT, f"workspaces/{PROJECT}/x.md", root), "x.md", "cwd-relative")
        self.assertEqual(
            resolve_in_workspace(PROJECT, old, root),
            workspace_path(PROJECT, root) / "02_requirements" / "project-brief.md",
        )

    def test_a_path_outside_the_workspace_is_kept(self) -> None:
        root = Path(tempfile.gettempdir()) / "repo"
        self.assertEqual(workspace_relative(PROJECT, "C:/elsewhere/notes.md", root), "C:/elsewhere/notes.md")
        self.assertEqual(workspace_relative(PROJECT, "/srv/other/workspaces/OTHER/x.md", root), "/srv/other/workspaces/OTHER/x.md")


class PortablePathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        self.first = self.temp / "first"
        self.first.mkdir()
        os.chdir(self.first)
        raw = self.temp / "billing.md"
        raw.write_text(RAW, encoding="utf-8")
        self.assertEqual(_run(["init", PROJECT, "--brief-version", "1"])[0], 0)
        self.assertEqual(_run(["ingest", PROJECT, "--source", str(raw)])[0], 0)
        self.assertEqual(_run(["brief", PROJECT])[0], 0)
        self.assertEqual(_run(["reindex", PROJECT])[0], 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def snapshot(self) -> dict:
        validate = _json(["validate", PROJECT])
        health = _json(["health", PROJECT])
        retrieved = _json(["retrieve", PROJECT, "--query", "invoices approval logged", "--workflow", "discovery"])
        rows = retrieved if isinstance(retrieved, list) else retrieved.get("results", [])
        sources = [workspace_relative(PROJECT, str(row.get("source_path", ""))) for row in rows]
        graph = _raw(graph_path(PROJECT))
        return {
            "validate": (validate["verdict"], validate["findings"]),
            "health": (health["verdict"], health["findings"]),
            "sources": sources,
            "nodes": sorted((node["id"], node.get("path", "")) for node in graph["nodes"]),
        }

    def test_graph_memory_and_state_store_workspace_relative_paths(self) -> None:
        stored = _stored_paths(PROJECT)
        self.assertTrue(stored, "the flow persisted paths")
        self.assertEqual([value for value in stored if _is_absolute(value)], [])

    def test_a_moved_workspace_gives_the_same_results(self) -> None:
        before = self.snapshot()
        self.assertTrue(before["sources"], "retrieve found the source")
        self.assertFalse([f for f in before["validate"][1] if "missing artifact" in f])

        second = self.temp / "second" / "clone"
        shutil.copytree(self.first / "workspaces", second / "workspaces")
        os.chdir(second)
        shutil.rmtree(self.first / "workspaces")  # nothing may still point there

        after = self.snapshot()
        self.assertEqual(after, before)
        self.assertEqual(_run(["brief", PROJECT])[0], 0)
        nodes = _raw(graph_path(PROJECT))["nodes"]
        self.assertEqual(len(nodes), len(before["nodes"]), "regenerating does not duplicate graph nodes")

    def write_legacy_absolute_paths(self, old_root: str) -> None:
        """Paths as 0.9.0 wrote them: absolute, under the folder the workspace used to live in."""
        old_base = f"{old_root}/workspaces/{PROJECT}/"

        def absolute(value: str) -> str:
            return value if not value or _is_absolute(value) else old_base + value

        graph = _raw(graph_path(PROJECT))
        for node in graph["nodes"]:
            node["path"] = absolute(node.get("path", ""))
        graph_path(PROJECT).write_text(json.dumps(graph), encoding="utf-8")
        memory = _raw(memory_path(PROJECT))
        for key in ("artifacts", "chunks"):
            for item in memory[key]:
                item["source_path"] = item["file_path"] = absolute(item["source_path"])
        memory_path(PROJECT).write_text(json.dumps(memory), encoding="utf-8")
        state = _raw(state_path(PROJECT))
        state["artifacts"] = {key: absolute(value) for key, value in (state.get("artifacts") or {}).items()}
        state_path(PROJECT).write_text(json.dumps(state), encoding="utf-8")

    def test_reindex_rewrites_legacy_absolute_paths(self) -> None:
        before = self.snapshot()
        self.write_legacy_absolute_paths("C:/Users/someone/OneDrive/old-repo")
        self.assertTrue([value for value in _stored_paths(PROJECT) if _is_absolute(value)])
        self.assertEqual(self.snapshot()["validate"], before["validate"], "legacy paths resolve before any rewrite")

        self.assertEqual(_run(["reindex", PROJECT])[0], 0)
        self.assertEqual([value for value in _stored_paths(PROJECT) if _is_absolute(value)], [])
        self.assertEqual(self.snapshot(), before)

    def test_the_090_migration_rewrites_legacy_absolute_paths(self) -> None:
        self.write_legacy_absolute_paths("/home/someone/old-repo")
        state = _raw(state_path(PROJECT))
        state.pop("schema_version", None)
        state_path(PROJECT).write_text(json.dumps(state), encoding="utf-8")

        self.assertEqual(_run(["status", PROJECT])[0], 0)
        self.assertEqual([value for value in _stored_paths(PROJECT) if _is_absolute(value)], [])

    def test_a_graph_path_outside_the_workspace_or_missing_is_a_health_finding(self) -> None:
        graph = _raw(graph_path(PROJECT))
        outside = (self.temp / "elsewhere" / "notes.md").as_posix()
        graph["nodes"].append({"id": "REQ-900", "type": "requirement", "path": outside, "title": "x", "status": "active", "domain": "product"})
        graph["nodes"].append({"id": "REQ-901", "type": "requirement", "path": "02_requirements/gone.md", "title": "y", "status": "active", "domain": "product"})
        graph_path(PROJECT).write_text(json.dumps(graph), encoding="utf-8")

        findings = _json(["health", PROJECT])["findings"]
        self.assertTrue([f for f in findings if "REQ-900" in f and "outside the workspace" in f], findings)
        self.assertTrue([f for f in findings if "REQ-901" in f and "does not exist" in f], findings)

    def test_doctor_reports_schema_and_absolute_paths(self) -> None:
        from sentinel.doctor import workspace_portability_check

        clean = workspace_portability_check(self.first)
        self.assertEqual(clean["status"], "PASS", clean)

        self.write_legacy_absolute_paths("C:/old")
        state = _raw(state_path(PROJECT))
        state.pop("schema_version", None)
        state_path(PROJECT).write_text(json.dumps(state), encoding="utf-8")
        dirty = workspace_portability_check(self.first)
        self.assertEqual(dirty["status"], "WARN")
        self.assertIn(PROJECT, dirty["detail"])
        self.assertIn("schema_version", dirty["detail"])
        self.assertIn("absolute paths", dirty["detail"])
        self.assertIn("/reindex", dirty["detail"])


if __name__ == "__main__":
    unittest.main()
