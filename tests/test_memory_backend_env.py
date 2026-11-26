"""SENTINEL_MEMORY_BACKEND=json keeps the broker on the JSON index even with LanceDB installed."""

from __future__ import annotations

import importlib.util
import os
import unittest
from unittest import mock

from sentinel.memory import ContextBroker


class MemoryBackendEnv(unittest.TestCase):
    def _broker(self, env: dict[str, str]) -> ContextBroker:
        broker = ContextBroker.__new__(ContextBroker)
        broker.lance_dir = mock.MagicMock()
        broker._lancedb = None
        broker._table = None
        broker.backend = "json-hybrid"
        broker.lancedb_degraded_reason = ""
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.dict("sys.modules", {"lancedb": mock.MagicMock()}):
                broker._connect_lancedb()
        return broker

    def test_json_switch_skips_lancedb(self) -> None:
        broker = self._broker({"SENTINEL_MEMORY_BACKEND": "json"})
        self.assertEqual(broker.backend, "json-hybrid")
        self.assertIsNone(broker._lancedb)
        self.assertIn("SENTINEL_MEMORY_BACKEND=json", broker.lancedb_degraded_reason)
        broker.lance_dir.mkdir.assert_not_called()

    def test_switch_is_case_and_space_tolerant(self) -> None:
        broker = self._broker({"SENTINEL_MEMORY_BACKEND": " JSON "})
        self.assertIsNone(broker._lancedb)
        broker.lance_dir.mkdir.assert_not_called()

    def test_other_values_still_try_lancedb(self) -> None:
        broker = self._broker({"SENTINEL_MEMORY_BACKEND": "lancedb"})
        broker.lance_dir.mkdir.assert_called()


if __name__ == "__main__":
    unittest.main()
