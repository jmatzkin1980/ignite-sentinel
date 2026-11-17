from __future__ import annotations

import unittest
from pathlib import Path

import sentinel
from sentinel.knowledge import ledger, metabolism


class KnowledgePackageTests(unittest.TestCase):
    def test_knowledge_lives_in_the_package(self):
        self.assertTrue(callable(ledger.materialize_knowledge_ledger))
        self.assertTrue(callable(ledger.knowledge_ledger_summary))
        self.assertTrue(callable(metabolism.metabolize_knowledge))

    def test_flat_compatibility_shims_are_gone(self):
        # IMP-338: nothing imported the flat modules any more.
        package_dir = Path(sentinel.__file__).resolve().parent
        for name in ("knowledge_ledger", "knowledge_metabolism"):
            self.assertFalse((package_dir / f"{name}.py").exists(), name)


if __name__ == "__main__":
    unittest.main()
