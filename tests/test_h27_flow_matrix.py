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

    def test_project_extraction_rows(self):
        rows = _keyed("Change path")
        for key in ("crosses", "extract_inventory", "extract_proposals", "extract_confirm", "extract_orphans",
                    "extract_verify"):
            with self.subTest(step=key):
                self.assertTrue(rows[key][5].startswith(f"`{key}`"), rows[key][5])
        self.assertTrue(rows["extract_confirm_flagged"][5].startswith("`extract_confirm`"))
        self.assertTrue(rows["extract_partial"][5].startswith("`extract_proposals`"))
        self.assertTrue(rows["extract_verify_result"][5].startswith("`extract_verify`"))
        self.assertTrue(rows["baseline"][5].startswith("`crosses`"))

    def test_no_cell_promises_inc_6(self):
        for section, rows in _sections().items():
            for cells in rows:
                for cell in cells:
                    with self.subTest(section=section, cell=cell[:40]):
                        self.assertNotIn("inc 6", cell)

    def test_rows_d_f_no_longer_promise_inc_7(self):
        rows = {cells[0][:1]: cells for cells in _sections()["Starting points"] if re.match(r"^[A-J]\. ", cells[0])}
        for letter in "DF":
            for cell in rows[letter]:
                with self.subTest(row=letter, cell=cell[:40]):
                    self.assertNotIn("inc 7", cell)
        self.assertIn("--derived-from", " ".join(rows["F"]))
        self.assertIn("--change CHG-001", rows["F"][4])
        self.assertIn("not found in a partial baseline: confirm", rows["D"][3])

    def test_escalation_offers_split_change(self):
        cells = [cell for rows in _sections().values() for row in rows for cell in row if "escalat" in cell.lower()]
        self.assertTrue(cells)
        for cell in cells:
            with self.subTest(cell=cell[:40]):
                self.assertIn("/split", cell)
                self.assertIn("--change", cell)
                self.assertNotIn("inc 7", cell)

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
