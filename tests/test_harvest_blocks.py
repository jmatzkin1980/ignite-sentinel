"""IMP-326: /harvest accumulates blocks delivered one at a time.

The sentinel-brownfield-harvest skill says "You may deliver one block at a time; each run of
/harvest registers that harvest". The runtime refused a file without B0 (a fact's repo had
to be listed in the same file) and overwrote harvest.json on each run, so a second harvest
silently replaced the first one, which the brief v2 reads.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main

RAW = "# Risk dashboard\n\nObjective: review risk queues before the daily meeting.\n"

FIRST = """# Harvest part 1

## B0 Inventory
- repo: queue-api — services/queue-api

## B1 Architecture and components
- [FACT queue-api:src/app.py] The queue API is a Flask app with three blueprints.
"""

SECOND = """# Harvest part 2

## B2 Data model and stores
- [FACT queue-api:src/models.py] Queues are stored in a PostgreSQL table named queues.
"""

FIRST_FIXED = """# Harvest part 1, corrected

## B1 Architecture and components
- [FACT queue-api:src/app.py] The queue API is a Flask app with four blueprints.
"""


def quiet(argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return main(argv)


class HarvestBlocksTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        (self.temp / "raw.md").write_text(RAW, encoding="utf-8")
        self.assertEqual(quiet(["init", "HRV", "--brief-version", "1"]), 0)
        self.assertEqual(quiet(["ingest", "HRV", "--source", str(self.temp / "raw.md")]), 0)
        self.record_path = self.temp / "workspaces" / "HRV" / "01_discovery" / "harvest.json"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def harvest(self, name, text):
        path = self.temp / name
        path.write_text(text, encoding="utf-8")
        return quiet(["harvest", "HRV", "--source", str(path)])

    def record(self):
        return json.loads(self.record_path.read_text(encoding="utf-8"))

    def blocks(self):
        return sorted({entry["block"] for entry in self.record()["entries"]})

    def test_a_later_block_without_b0_is_accepted_and_both_are_kept(self):
        self.assertEqual(self.harvest("h1.md", FIRST), 0)
        self.assertEqual(self.harvest("h2.md", SECOND), 0)
        self.assertEqual(self.blocks(), ["B1", "B2"])
        self.assertEqual(self.record()["repos"], ["queue-api"])
        self.assertEqual(self.record()["coverage"]["fact"], 2)

    def test_redelivering_a_block_replaces_only_that_block(self):
        self.harvest("h1.md", FIRST)
        self.harvest("h2.md", SECOND)
        self.assertEqual(self.harvest("h1b.md", FIRST_FIXED), 0)
        texts = [entry["text"] for entry in self.record()["entries"]]
        self.assertIn("The queue API is a Flask app with four blueprints.", texts)
        self.assertNotIn("The queue API is a Flask app with three blueprints.", texts)
        self.assertEqual(self.blocks(), ["B1", "B2"])

    def test_first_harvest_still_needs_b0(self):
        self.assertEqual(self.harvest("h2.md", SECOND), 3)


if __name__ == "__main__":
    unittest.main()
