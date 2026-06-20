from __future__ import annotations

import unittest
from pathlib import Path


SENTINEL_ROOT = Path(__file__).resolve().parents[1] / "sentinel"


class CoreArchitectureTests(unittest.TestCase):
    def python_sources(self) -> list[Path]:
        return sorted(SENTINEL_ROOT.rglob("*.py"))

    def test_domain_code_does_not_parse_json_directly(self):
        allowed = {
            SENTINEL_ROOT / "adapters.py",  # local command manifest loader/writer.
            SENTINEL_ROOT / "core" / "io.py",  # canonical JSON IO.
            SENTINEL_ROOT / "mcp.py",  # stdio JSON-RPC payload parsing.
        }
        offenders = [
            path.relative_to(SENTINEL_ROOT.parent).as_posix()
            for path in self.python_sources()
            if path not in allowed and "json.loads(" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_domain_code_does_not_use_raw_open(self):
        allowed = {
            SENTINEL_ROOT / "core" / "io.py",  # append_text centralizes append-only writes.
            SENTINEL_ROOT / "dashboard.py",  # opens local browser snapshot.
            SENTINEL_ROOT / "sources.py",  # binary hashing reader.
            SENTINEL_ROOT / "view.py",  # opens local browser snapshot.
        }
        offenders = [
            path.relative_to(SENTINEL_ROOT.parent).as_posix()
            for path in self.python_sources()
            if path not in allowed and ".open(" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_domain_code_uses_core_graph_facade(self):
        allowed = {
            SENTINEL_ROOT / "cli.py",  # trace export renders matrix/mermaid.
            SENTINEL_ROOT / "core" / "graph.py",  # canonical facade over traceability.
            SENTINEL_ROOT / "protocols.py",  # command protocol materializes matrix/mermaid.
        }
        offenders = [
            path.relative_to(SENTINEL_ROOT.parent).as_posix()
            for path in self.python_sources()
            if path not in allowed and "from .traceability import" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
