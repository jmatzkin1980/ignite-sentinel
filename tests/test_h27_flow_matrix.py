"""IMP-408: the flow x step matrix of the guide equals what /next can say."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from sentinel.commands import skill_for_command
from sentinel.readiness_verdict import CHANGE_COMMANDS, NEXT_STEPS

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "user_guide" / "22-flow-step-matrix.md"
KEY = re.compile(r"^`([a-z_]+)`$")


def _cells(line: str) -> list[str]:
    escaped = "\\|"
    return [c.strip().replace(escaped, "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _sections() -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    current = ""
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif line.startswith("|") and current:
            sections[current].append(_cells(line))
    return sections


def _verb(command: str) -> str:
    found = re.search(r"/([a-z][a-z-]*)", command)
    return found.group(1) if found else ""


def _keyed(section: str) -> dict[str, list[str]]:
    rows = {}
    for cells in _sections()[section]:
        found = KEY.match(cells[0])
        if found:
            rows[found.group(1)] = cells
    return rows


class FlowMatrixTest(unittest.TestCase):
    def test_every_project_step_has_a_row(self):
        rows = _keyed("Project path")
        self.assertEqual(set(rows), set(NEXT_STEPS))
        for key, cells in rows.items():
            with self.subTest(step=key):
                command = NEXT_STEPS[key][2]
                self.assertEqual(cells[2], skill_for_command(command) or "—")
                self.assertEqual(_verb(cells[1]), _verb(command))
                self.assertTrue(cells[3] and cells[4])

    def test_every_change_step_has_a_row_and_an_equivalent(self):
        rows = _keyed("Change path")
        self.assertEqual(set(rows), set(CHANGE_COMMANDS))
        for key, cells in rows.items():
            with self.subTest(step=key):
                command = CHANGE_COMMANDS[key].replace("{cross_command}", "/cross")
                expected = skill_for_command(command) if command else "—"
                self.assertEqual(cells[2], expected or "—")
                if command:
                    self.assertEqual(_verb(cells[1]), _verb(command))
                self.assertTrue(cells[3] and cells[4])
                equivalent = cells[5]
                found = re.match(r"^`(\w+)`", equivalent)
                if found:
                    self.assertIn(found.group(1), NEXT_STEPS)
                else:
                    self.assertRegex(equivalent, r"^none — .{20,}")

    def test_starting_points_a_to_j(self):
        letters = set()
        for cells in _sections()["Starting points"]:
            found = re.match(r"^([A-J])\. ", cells[0])
            if found:
                letters.add(found.group(1))
        self.assertEqual(letters, set("ABCDEFGHIJ"))

    def test_guide_links_the_page(self):
        for rel in ("README.md", "user_guide/00-user-guide.md", "user_guide/03-workflows.md"):
            with self.subTest(file=rel):
                self.assertIn("22-flow-step-matrix.md", (ROOT / rel).read_text(encoding="utf-8"))
        scenarios = (ROOT / "user_guide" / "12-scenarios.md").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^## Scenario ", scenarios, re.M)), 11)


if __name__ == "__main__":
    unittest.main()
