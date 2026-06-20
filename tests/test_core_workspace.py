from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.core.io import read_json, write_json
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

    def test_core_state_and_workspace_state_update_same_file(self):
        path = state_path("CORE")
        write_json(path, {"project_id": "CORE", "phase": "initialized"})

        update_state("CORE", health="DIRTY")
        state = workspace_read_json(path, {})
        self.assertEqual(state["health"], "DIRTY")
        self.assertIn("updated_at", state)

        workspace_update_state("CORE", phase="brief_completed")
        self.assertEqual(read_json(path, {})["phase"], "brief_completed")


if __name__ == "__main__":
    unittest.main()
