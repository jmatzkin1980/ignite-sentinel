"""IMP-330 - memory and graph writes that keep what is already there.

N1: the LanceDB table must be opened, not overwritten, by every new broker
(lancedb 0.33 `list_tables()` returns a response object, not a list of names).
M3: a non-full reindex re-embeds an artifact whose rows the table lost.
H2/H3: the graph and the memory index are not rewritten when nothing changed.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sentinel import traceability
from sentinel.cli import main
from sentinel.memory import ContextBroker, lancedb_literal, lancedb_table_names, reindex_workspace

try:  # pragma: no cover - depends on the optional extra
    import lancedb  # type: ignore  # noqa: F401

    HAS_LANCEDB = True
except Exception:  # pragma: no cover
    HAS_LANCEDB = False


class _Response:
    def __init__(self, tables, page_token=None):
        self.tables = tables
        self.page_token = page_token


class TableNamesTests(unittest.TestCase):
    def test_response_object_with_tables(self) -> None:
        db = mock.Mock(spec=["list_tables"])
        db.list_tables.return_value = _Response(["ba_memory"])
        self.assertIn("ba_memory", lancedb_table_names(db))

    def test_plain_list(self) -> None:
        db = mock.Mock(spec=["list_tables"])
        db.list_tables.return_value = ["ba_memory", "other"]
        self.assertEqual(lancedb_table_names(db), {"ba_memory", "other"})

    def test_paginated_response(self) -> None:
        db = mock.Mock(spec=["list_tables"])
        db.list_tables.side_effect = [_Response(["a"], page_token="p2"), _Response(["ba_memory"])]
        self.assertEqual(lancedb_table_names(db), {"a", "ba_memory"})

    def test_older_api_table_names_only(self) -> None:
        db = mock.Mock(spec=["table_names"])
        db.table_names.return_value = ["ba_memory"]
        self.assertEqual(lancedb_table_names(db), {"ba_memory"})


class _Workspace(unittest.TestCase):
    project = "MEMW"

    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(main(["init", self.project, "--brief-version", "1"]), 0)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)


@unittest.skipUnless(HAS_LANCEDB, "lancedb not installed")
class LanceTablePersistsTests(_Workspace):
    def _index(self, broker: ContextBroker, artifact_id: str, text: str, **kwargs) -> bool:
        return broker.index_artifact(
            artifact_id=artifact_id,
            artifact_type="requirements",
            source_path=Path(f"{artifact_id}.md"),
            text=text,
            **kwargs,
        )

    def test_second_broker_keeps_rows(self) -> None:
        first = ContextBroker(self.project)
        self.assertEqual(first.backend, "lancedb-hybrid")
        self._index(first, "A", "alpha unique widget metric for the dashboard")
        self._index(first, "B", "beta distinct gadget pipeline for the service")
        rows = first._table.count_rows()
        self.assertGreater(rows, 1)
        second = ContextBroker(self.project)
        self.assertEqual(second._table.count_rows(), rows)

    def test_non_full_reindex_restores_lost_rows(self) -> None:
        broker = ContextBroker(self.project)
        text = "gamma separate module workflow for the backlog"
        self._index(broker, "C", text)
        broker._table.delete(f"artifact_id = '{lancedb_literal('C')}'")
        again = ContextBroker(self.project)
        self.assertTrue(self._index(again, "C", text, skip_unchanged=True))
        self.assertGreater(again._table.count_rows(), 1)
        # Once restored, the unchanged artifact is skipped.
        self.assertFalse(self._index(ContextBroker(self.project), "C", text, skip_unchanged=True))


class GraphSaveSkipTests(_Workspace):
    def _count_saves(self, call):
        with mock.patch.object(traceability, "save_graph", wraps=traceability.save_graph) as spy:
            call()
        return spy.call_count

    def test_existing_edge_does_not_rewrite_graph(self) -> None:
        self.assertEqual(self._count_saves(lambda: traceability.add_edge(self.project, "X-1", "Y-1", "derives")), 1)
        self.assertEqual(self._count_saves(lambda: traceability.add_edge(self.project, "X-1", "Y-1", "derives")), 0)

    def test_unchanged_node_does_not_rewrite_graph(self) -> None:
        path = self.temp / "doc.md"
        node_id = traceability.add_node(self.project, "REQ", "doc", path, "Title")
        self.assertEqual(
            self._count_saves(lambda: traceability.add_node(self.project, "REQ", "doc", path, "Title")), 0
        )
        self.assertEqual(
            self._count_saves(lambda: traceability.upsert_node(self.project, node_id, "doc", path, "Title")), 0
        )
        self.assertEqual(
            self._count_saves(lambda: traceability.add_node(self.project, "REQ", "doc", path, "New title")), 1
        )
        self.assertEqual(
            self._count_saves(lambda: traceability.upsert_node(self.project, node_id, "doc", path, "Other")), 1
        )
        nodes = traceability.nodes_by_type(self.project, "doc")
        self.assertEqual([node["title"] for node in nodes], ["Other"])


class MemorySaveSkipTests(_Workspace):
    def test_same_trace_edges_do_not_rewrite_index(self) -> None:
        broker = ContextBroker(self.project)
        edges = [{"from": "A", "to": "B", "relation": "derives"}]
        broker.index_trace_edges(edges)
        with mock.patch.object(broker, "_save", wraps=broker._save) as spy:
            broker.index_trace_edges([dict(edge) for edge in edges])
        self.assertEqual(spy.call_count, 0)

    def test_reindex_saves_the_index_once(self) -> None:
        folder = self.temp / "workspaces" / self.project / "00_raw" / "01_business_context"
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(3):
            (folder / f"note-{index}.md").write_text(f"# Note {index}\n\nbusiness fact number {index}\n", encoding="utf-8")
        import sentinel.memory as memory_module

        with mock.patch.object(memory_module, "write_json", wraps=memory_module.write_json) as spy:
            result = reindex_workspace(self.project, full=True)
        self.assertGreater(result["count"], 1)
        index_writes = [c for c in spy.call_args_list if Path(c.args[0]).name == "memory.json"]
        self.assertEqual(len(index_writes), 1)



# These modules test the LanceDB backend itself: they ignore SENTINEL_MEMORY_BACKEND=json,
# which CI uses to keep the rest of the suite on the JSON index.
_MEMORY_BACKEND_ENV = None


def setUpModule() -> None:
    global _MEMORY_BACKEND_ENV
    _MEMORY_BACKEND_ENV = os.environ.pop("SENTINEL_MEMORY_BACKEND", None)


def tearDownModule() -> None:
    if _MEMORY_BACKEND_ENV is not None:
        os.environ["SENTINEL_MEMORY_BACKEND"] = _MEMORY_BACKEND_ENV


if __name__ == "__main__":
    unittest.main()
