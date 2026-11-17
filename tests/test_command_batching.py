"""IMP-345 - one graph write and one memory broker per command.

The graph used to be written once per changed node or edge (dozens of times in
/ingest, /specs or /backlog), and /specs and /backlog built a ContextBroker (the
embedder plus LanceDB) per artifact or story. A command now writes the graph
once, after its artifacts, and those two commands share one broker.

Crash choice: the graph is written on the way out even when the command
raises, so the artifacts written before the error keep their nodes, as when
every change was saved at once.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sentinel.memory as memory_module
from sentinel import traceability
from sentinel.cli import main
from sentinel.memory import ContextBroker, shared_broker, shared_brokers

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_golden_artifacts import SCENARIOS  # noqa: E402

PROJECT = "BATCH"
_JSON_ONLY = mock.patch.object(ContextBroker, "_connect_lancedb", lambda self: None)


def _run(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class _Counter:
    """Counts graph file writes and broker constructions while active."""

    def __init__(self) -> None:
        self.graph_writes = 0
        self.brokers = 0

    @contextlib.contextmanager
    def watching(self):
        real_write = traceability.write_json
        real_init = ContextBroker.__init__

        def write(path, data, *args, **kwargs):
            if Path(path).name == "traceability_graph.json":
                self.graph_writes += 1
            return real_write(path, data, *args, **kwargs)

        def init(broker, *args, **kwargs):
            self.brokers += 1
            return real_init(broker, *args, **kwargs)

        with mock.patch.object(traceability, "write_json", write), mock.patch.object(ContextBroker, "__init__", init):
            yield self


def _graph(root: Path) -> dict:
    return json.loads((root / "workspaces" / PROJECT / "06_traceability" / "traceability_graph.json").read_text(encoding="utf-8"))


class CommandBatchingTests(unittest.TestCase):
    """A workspace driven to READY_FOR_SPECS once, copied for each test."""

    @classmethod
    def setUpClass(cls) -> None:
        _JSON_ONLY.start()
        cls.old_cwd = Path.cwd()
        cls.template = Path(tempfile.mkdtemp())
        scenario = SCENARIOS["en"]
        os.chdir(cls.template)
        try:
            raw = cls.template / "raw.md"
            raw.write_text(scenario["raw"], encoding="utf-8")
            cls.counts: dict[str, _Counter] = {}
            for name, argv in [("init", ["init", PROJECT, "--brief-version", "1"]),
                               ("ingest", ["ingest", PROJECT, "--source", str(raw)])]:
                with _Counter().watching() as counter:
                    assert _run(argv) == 0, name
                cls.counts[name] = counter
            for index, statement in enumerate(scenario["ears"], start=1):
                answer = cls.template / f"answer-{index}.md"
                answer.write_text(scenario["answer"].format(s=statement, i=index), encoding="utf-8")
                with _Counter().watching() as counter:
                    assert _run(["resolve-gaps", PROJECT, "--source", str(answer)]) == 0
                cls.counts[f"resolve-gaps-{index}"] = counter
            assert _run(["brief", PROJECT]) == 0
        finally:
            os.chdir(cls.old_cwd)

    @classmethod
    def tearDownClass(cls) -> None:
        _JSON_ONLY.stop()
        shutil.rmtree(cls.template, ignore_errors=True)

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()) / "ws"
        shutil.copytree(self.template, self.root)
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.root.parent, ignore_errors=True)

    def test_ingest_and_resolve_gaps_write_the_graph_once(self) -> None:
        for name, counter in self.counts.items():
            if name == "init":
                continue
            with self.subTest(command=name):
                self.assertEqual(counter.graph_writes, 1)

    def test_specs_and_backlog_write_the_graph_once_with_one_broker(self) -> None:
        for command in ("specs", "backlog", "backlog"):
            with self.subTest(command=command), _Counter().watching() as counter:
                self.assertEqual(_run([command, PROJECT]), 0)
            self.assertLessEqual(counter.graph_writes, 1)
            self.assertEqual(counter.brokers, 1, f"/{command} built {counter.brokers} brokers")

    def test_failure_mid_backlog_keeps_the_nodes_of_written_artifacts(self) -> None:
        self.assertEqual(_run(["specs", PROJECT]), 0)
        with mock.patch("sentinel.generation.backlog_status", side_effect=RuntimeError("boom")):
            self.assertNotEqual(_run(["backlog", PROJECT]), 0)
        backlog = self.root / "workspaces" / PROJECT / "04_backlog"
        stories = sorted(path.name for path in backlog.glob("US-*.md"))
        self.assertTrue(stories)
        story_nodes = sorted(
            Path(node["path"]).name for node in _graph(self.root)["nodes"] if node.get("type") == "user_story"
        )
        self.assertEqual(story_nodes, stories)  # every written story has its node on disk
        self.assertEqual(_run(["health", PROJECT]), 0)
        # A rerun completes and leaves the graph an uninterrupted run leaves.
        self.assertEqual(_run(["backlog", PROJECT]), 0)
        after_rerun = _graph(self.root)
        clean = Path(tempfile.mkdtemp()) / "ws"
        try:
            shutil.copytree(self.template, clean)
            os.chdir(clean)
            self.assertEqual(_run(["specs", PROJECT]), 0)
            self.assertEqual(_run(["backlog", PROJECT]), 0)
            uninterrupted = _graph(clean)
        finally:
            os.chdir(self.root)
            shutil.rmtree(clean.parent, ignore_errors=True)
        # A second /backlog may record a regeneration diff the single run does not; the rest matches.
        ids = lambda graph: sorted(  # noqa: E731
            (n["id"], n["type"], n.get("path")) for n in graph["nodes"] if n.get("type") != "regeneration_diff"
        )
        self.assertEqual(ids(after_rerun), ids(uninterrupted))


class DeferredGraphSavesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(_run(["init", PROJECT, "--brief-version", "1"]), 0)
        self.graph_file = self.temp / "workspaces" / PROJECT / "06_traceability" / "traceability_graph.json"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _stored(self) -> dict:
        return json.loads(self.graph_file.read_text(encoding="utf-8"))

    def test_reads_see_deferred_changes_and_the_file_is_written_once(self) -> None:
        doc = self.temp / "workspaces" / PROJECT / "a.md"
        with mock.patch.object(traceability, "write_json", wraps=traceability.write_json) as spy:
            with traceability.deferred_graph_saves():
                with traceability.deferred_graph_saves():  # nested: only the outer block writes
                    node = traceability.add_node(PROJECT, "REQ", "doc", doc, "A")
                    traceability.add_edge(PROJECT, node, "X-1", "derives")
                self.assertEqual(self._stored()["nodes"], [])
                self.assertEqual(traceability.parents_of(PROJECT, "X-1"), [node])
                # same path and type: the upsert finds the node not yet on disk
                self.assertEqual(traceability.add_node(PROJECT, "REQ", "doc", doc, "A"), node)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual([n["id"] for n in self._stored()["nodes"]], [node])
        self.assertEqual(self._stored()["nodes"][0]["path"], "a.md")  # stored relative (IMP-301)

    def test_written_when_the_block_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            with traceability.deferred_graph_saves():
                traceability.add_edge(PROJECT, "A-1", "B-1", "derives")
                raise RuntimeError("boom")
        self.assertEqual(self._stored()["edges"], [{"from": "A-1", "to": "B-1", "relation": "derives"}])

    def test_unchanged_graph_is_not_written(self) -> None:
        with mock.patch.object(traceability, "write_json", wraps=traceability.write_json) as spy:
            with traceability.deferred_graph_saves():
                traceability.load_graph(PROJECT)
        self.assertEqual(spy.call_count, 0)

    def test_caller_mutation_without_save_does_not_leak(self) -> None:
        with traceability.deferred_graph_saves():
            traceability.add_edge(PROJECT, "A-1", "B-1", "derives")
            graph = traceability.load_graph(PROJECT)
            graph["edges"][0]["relation"] = "mutated"
        self.assertEqual(self._stored()["edges"][0]["relation"], "derives")


class SharedBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        _JSON_ONLY.start()
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        self.assertEqual(_run(["init", PROJECT, "--brief-version", "1"]), 0)

    def tearDown(self) -> None:
        _JSON_ONLY.stop()
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _index(self, broker: ContextBroker, artifact_id: str) -> None:
        broker.index_artifact(artifact_id, "note", Path(f"{artifact_id}.md"), f"# {artifact_id}\n\nfact about {artifact_id}\n")

    def test_one_broker_inside_the_block_a_new_one_outside(self) -> None:
        with shared_brokers():
            first = shared_broker(PROJECT)
            with shared_brokers():
                self.assertIs(shared_broker(PROJECT), first)
        self.assertIsNot(shared_broker(PROJECT), first)
        self.assertEqual(memory_module._SHARED_BROKERS, {})

    def test_shared_broker_keeps_rows_another_broker_wrote(self) -> None:
        with shared_brokers():
            self._index(shared_broker(PROJECT), "A")
            self._index(ContextBroker(PROJECT), "B")  # a broker built outside the share
            self._index(shared_broker(PROJECT), "C")
        ids = {artifact["artifact_id"] for artifact in ContextBroker(PROJECT).data["artifacts"]}
        self.assertEqual(ids, {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
