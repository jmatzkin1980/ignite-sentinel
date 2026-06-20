from __future__ import annotations

import unittest

from sentinel import knowledge_ledger, knowledge_metabolism
from sentinel.knowledge import ledger, metabolism


class KnowledgePackageTests(unittest.TestCase):
    def test_flat_knowledge_modules_remain_compatibility_shims(self):
        self.assertIs(knowledge_ledger.materialize_knowledge_ledger, ledger.materialize_knowledge_ledger)
        self.assertIs(knowledge_ledger.knowledge_ledger_summary, ledger.knowledge_ledger_summary)
        self.assertIs(knowledge_metabolism.metabolize_knowledge, metabolism.metabolize_knowledge)


if __name__ == "__main__":
    unittest.main()
