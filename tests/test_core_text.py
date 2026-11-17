from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.core.text import unique_path
from sentinel.errors import EXIT_INPUT, InputError, exit_code_for


class UniquePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_free_path_is_returned_unchanged(self) -> None:
        target = self.root / "source.json"
        self.assertEqual(unique_path(target), target)

    def test_taken_path_gets_the_first_free_number(self) -> None:
        target = self.root / "source.json"
        target.write_text("{}", encoding="utf-8")
        (self.root / "source-2.json").write_text("{}", encoding="utf-8")
        self.assertEqual(unique_path(target), self.root / "source-3.json")

    def test_stops_at_the_bound_with_an_input_error(self) -> None:
        target = self.root / "source.json"
        for name in ("source.json", "source-2.json", "source-3.json"):
            (self.root / name).write_text("{}", encoding="utf-8")
        with self.assertRaises(InputError) as raised:
            unique_path(target, limit=4)
        self.assertEqual(exit_code_for(raised.exception), EXIT_INPUT)


if __name__ == "__main__":
    unittest.main()
