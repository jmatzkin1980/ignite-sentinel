from __future__ import annotations

import unittest
from pathlib import Path

import sentinel
from sentinel import discovery, gaps
import sentinel.discovery.channels as channels
import sentinel.discovery.intake as intake


class DiscoveryPackageTests(unittest.TestCase):
    def test_discovery_package_reexports_historical_api(self):
        self.assertIs(discovery.ingest, intake.ingest)
        self.assertIs(discovery.parse_gap_rows, gaps.parse_gap_rows)
        self.assertIs(discovery.apply_annotation, channels.apply_annotation)
        self.assertIs(discovery.apply_challenge, channels.apply_challenge)
        self.assertIs(discovery.apply_scrutiny, channels.apply_scrutiny)
        self.assertIs(discovery.refresh_knowledge_ledger, channels.refresh_knowledge_ledger)

    def test_discovery_exports_are_explicit(self):
        # IMP-338: an explicit __all__, no star import of a 3,700-line module.
        self.assertTrue(all(hasattr(discovery, name) for name in discovery.__all__))
        package_dir = Path(sentinel.__file__).resolve().parent / "discovery"
        self.assertFalse((package_dir / "workflow.py").exists())
        for path in package_dir.glob("*.py"):
            self.assertLess(len(path.read_text(encoding="utf-8").splitlines()), 1500, path.name)


if __name__ == "__main__":
    unittest.main()
