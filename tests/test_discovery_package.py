from __future__ import annotations

import unittest

from sentinel import discovery
from sentinel.discovery import workflow


class DiscoveryPackageTests(unittest.TestCase):
    def test_discovery_package_reexports_historical_api(self):
        self.assertIs(discovery.ingest, workflow.ingest)
        self.assertIs(discovery.parse_gap_rows, workflow.parse_gap_rows)
        self.assertIs(discovery.apply_annotation, workflow.apply_annotation)
        self.assertIs(discovery.apply_challenge, workflow.apply_challenge)
        self.assertIs(discovery.apply_scrutiny, workflow.apply_scrutiny)
        self.assertIs(discovery.refresh_knowledge_ledger, workflow.refresh_knowledge_ledger)


if __name__ == "__main__":
    unittest.main()
