"""IMP-341 — a retired source stops feeding memory.

`/sources --retire` used to change only the F-NN row: the raw or change copy
stayed in memory, `/retrieve` kept returning it and `/reindex` indexed it again.
Now retiring removes its rows from memory, `/reindex` (incremental and `--full`)
skips its files, `/retrieve` and context packs filter it at query time, the copy
stays on disk for audit, and `--current` brings it back on the next `/reindex`.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.memory import ContextBroker, reindex_workspace
from sentinel.sources import load_source_manifest

RAW = (
    "# Reporting Portal\n\n"
    "We need a reporting portal for the operations team. The objective is to "
    "reduce manual work. Data is stored in the legacy billing system.\n"
)
# A word no other workspace file carries, so a hit can only come from this source.
MARKER = "quokkaledger"
WRONG = (
    "# Wrong file\n\n"
    f"- The {MARKER} module settles invoices every night.\n"
    f"- The {MARKER} export keeps twelve months of data.\n"
)


def _run(argv: list[str]) -> dict:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"{argv} exited {code}: {out.getvalue()}")
    return json.loads(out.getvalue())


class RetiredSourceMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        raw = self.temp / "raw.md"
        raw.write_text(RAW, encoding="utf-8")
        _run(["init", "RET", "--brief-version", "1"])
        _run(["ingest", "RET", "--source", str(raw)])
        wrong = self.temp / "wrong.md"
        wrong.write_text(WRONG, encoding="utf-8")
        self.source_id = _run(["sync", "RET", "--source", str(wrong)])["source_id"]
        self.ws = self.temp / "workspaces" / "RET"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _hits(self) -> list[dict]:
        rows = ContextBroker("RET").retrieve(MARKER, "imp341", limit=20)
        return [row for row in rows if MARKER in str(row.get("text", ""))]

    def _stored_paths(self) -> list[str]:
        data = json.loads((self.ws / "memory.lancedb" / "memory.json").read_text(encoding="utf-8"))
        return [chunk["source_path"] for chunk in data["chunks"] if MARKER in chunk.get("text", "")]

    def _copy(self) -> Path:
        row = next(row for row in load_source_manifest("RET")["registry"] if row["id"] == self.source_id)
        return self.temp / row["copies"][0]

    def test_before_retiring_the_source_feeds_memory(self) -> None:
        self.assertTrue(self._hits())

    def test_retire_removes_it_from_memory_and_keeps_the_copy(self) -> None:
        result = _run(["sources", "RET", "--id", self.source_id, "--retire", "--reason", "wrong file loaded by mistake"])
        self.assertTrue(result["memory_removed"])
        self.assertEqual(self._hits(), [])
        self.assertEqual(self._stored_paths(), [])
        self.assertTrue(self._copy().exists())  # kept for audit, never deleted
        # The rest of memory is untouched.
        self.assertTrue(ContextBroker("RET").retrieve("reporting portal", "imp341", limit=5))

    def test_reindex_skips_a_retired_source(self) -> None:
        _run(["sources", "RET", "--id", self.source_id, "--retire", "--reason", "wrong file loaded by mistake"])
        for full in (False, True):
            with self.subTest(full=full):
                result = reindex_workspace("RET", full=full)
                self.assertTrue(result["retired_skipped"])
                self.assertEqual(self._hits(), [])
                self.assertEqual(self._stored_paths(), [])

    def test_retrieve_filters_rows_left_from_before(self) -> None:
        broker = ContextBroker("RET")  # loaded while the source was still current
        _run(["sources", "RET", "--id", self.source_id, "--retire", "--reason", "wrong file loaded by mistake"])
        rows = broker.retrieve(MARKER, "imp341", limit=20)
        self.assertFalse([row for row in rows if MARKER in str(row.get("text", ""))])
        pack = broker.build_context_pack(MARKER, "imp341", limit=20)
        self.assertFalse([row for row in pack["results"] if MARKER in str(row.get("text", ""))])

    def test_current_brings_it_back_on_the_next_reindex(self) -> None:
        _run(["sources", "RET", "--id", self.source_id, "--retire", "--reason", "wrong file loaded by mistake"])
        _run(["sources", "RET", "--id", self.source_id, "--current", "--reason", "it was the right file after all"])
        self.assertEqual(self._hits(), [])  # nothing comes back until /reindex
        reindex_workspace("RET")
        self.assertTrue(self._hits())


if __name__ == "__main__":
    unittest.main()
