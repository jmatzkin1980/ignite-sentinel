from __future__ import annotations

import os
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

from sentinel.core.graph import add_edge, add_node, load_graph, nodes_by_type, save_graph
from sentinel.core.io import append_text, clear_read_json_cache, read_json, read_json_cache_stats, write_json
from sentinel.core.paths import graph_path, memory_path, source_manifest_path, state_path, workspace_path
from sentinel.core.state import update_state
from sentinel.workspace import (
    read_json as workspace_read_json,
    state_path as workspace_state_path,
    update_state as workspace_update_state,
    workspace_path as workspace_workspace_path,
    write_json as workspace_write_json,
)


class CoreWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)
        clear_read_json_cache()

    def test_core_paths_match_workspace_shims(self):
        self.assertEqual(workspace_path("CORE"), workspace_workspace_path("CORE"))
        self.assertEqual(state_path("CORE"), workspace_state_path("CORE"))
        self.assertEqual(graph_path("CORE"), workspace_path("CORE") / "06_traceability" / "traceability_graph.json")
        self.assertEqual(memory_path("CORE"), workspace_path("CORE") / "memory.lancedb" / "memory.json")
        self.assertEqual(source_manifest_path("CORE"), workspace_path("CORE") / "00_raw" / "source_manifest.json")

    def test_core_io_is_available_and_workspace_shim_delegates(self):
        path = workspace_path("CORE") / "state.json"
        write_json(path, {"project_id": "CORE", "phase": "initialized"})
        self.assertEqual(workspace_read_json(path, {}), {"project_id": "CORE", "phase": "initialized"})

        workspace_write_json(path, {"project_id": "CORE", "phase": "updated"})
        self.assertEqual(read_json(path, {}), {"project_id": "CORE", "phase": "updated"})
        self.assertFalse((path.parent / ".state.json.tmp").exists())

        log_path = workspace_path("CORE") / "06_traceability" / "command_protocol_log.md"
        append_text(log_path, "one\n")
        append_text(log_path, "two\n")
        self.assertEqual(log_path.read_text(encoding="utf-8"), "one\ntwo\n")

    def test_core_state_and_workspace_state_update_same_file(self):
        path = state_path("CORE")
        write_json(path, {"project_id": "CORE", "phase": "initialized"})

        update_state("CORE", health="DIRTY")
        state = workspace_read_json(path, {})
        self.assertEqual(state["health"], "DIRTY")
        self.assertIn("updated_at", state)

        workspace_update_state("CORE", phase="brief_completed")
        self.assertEqual(read_json(path, {})["phase"], "brief_completed")

    def test_core_io_normal_write_after_read_has_no_conflict_warning(self):
        path = workspace_path("CORE") / "state.json"
        write_json(path, {"project_id": "CORE", "phase": "initialized"})
        read_json(path, {})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            write_json(path, {"project_id": "CORE", "phase": "updated"})

        self.assertEqual(caught, [])
        self.assertEqual(read_json(path, {})["phase"], "updated")

    def test_core_io_warns_when_file_changed_between_read_and_write(self):
        path = workspace_path("CORE") / "state.json"
        write_json(path, {"project_id": "CORE", "phase": "initialized"})
        self.assertEqual(read_json(path, {})["phase"], "initialized")
        path.write_text('{"project_id": "CORE", "phase": "external"}\n', encoding="utf-8")

        with self.assertWarnsRegex(RuntimeWarning, "Optimistic write conflict detected"):
            write_json(path, {"project_id": "CORE", "phase": "updated"})

        self.assertEqual(read_json(path, {})["phase"], "updated")

    def test_read_json_cache_hits_and_invalidates_on_write(self):
        path = workspace_path("CORE") / "state.json"
        clear_read_json_cache()
        write_json(path, {"project_id": "CORE", "phase": "initialized"})

        self.assertEqual(read_json(path, {})["phase"], "initialized")
        self.assertEqual(read_json(path, {})["phase"], "initialized")
        self.assertEqual(read_json_cache_stats()["hits"], 1)

        write_json(path, {"project_id": "CORE", "phase": "updated"})
        self.assertEqual(read_json(path, {})["phase"], "updated")
        self.assertEqual(read_json_cache_stats()["misses"], 2)

    def test_read_json_cache_does_not_expose_mutable_cached_value(self):
        path = workspace_path("CORE") / "state.json"
        clear_read_json_cache()
        write_json(path, {"items": ["a"]})

        first = read_json(path, {})
        first["items"].append("mutated")

        self.assertEqual(read_json(path, {})["items"], ["a"])

    def test_read_json_missing_path_default_is_not_cached(self):
        path = workspace_path("CORE") / "missing.json"
        clear_read_json_cache()

        self.assertEqual(read_json(path, {"missing": True}), {"missing": True})
        self.assertEqual(read_json(path, []), [])
        self.assertEqual(read_json_cache_stats()["entries"], 0)

    def test_core_graph_facade_uses_traceability_contract(self):
        node_id = add_node("CORE", "REQ", "requirement", workspace_path("CORE") / "req.md", "Requirement")
        add_edge("CORE", node_id, "GAP-001", "raises")
        graph = load_graph("CORE")

        self.assertEqual(node_id, "REQ-001")
        self.assertEqual(nodes_by_type("CORE", "requirement")[0]["id"], "REQ-001")
        self.assertEqual(graph["edges"], [{"from": "REQ-001", "to": "GAP-001", "relation": "raises"}])

        save_graph("CORE", graph)
        self.assertEqual(read_json(graph_path("CORE"), {})["nodes"][0]["id"], "REQ-001")


if __name__ == "__main__":
    unittest.main()
