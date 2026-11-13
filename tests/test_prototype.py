"""IMP-274 (H17b): the HTML prototype inventory, `/prototype --inventory`.

The synthetic prototype `tests/fixtures/synthetic_prototype/claims-portal.html`
(labelled as such) has three screens, hidden states and copy in JavaScript. The
seeded secret is built at test time, so no secret-shaped literal sits in the repo.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from sentinel.cli import main
from sentinel.prototype import extract_inventory

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "synthetic_prototype" / "claims-portal.html"
HTML = FIXTURE.read_text(encoding="utf-8")
CLOUD_KEY = "AKIA" + "IOSFODNN7EXAMPLE"  # split so no secret-shaped literal sits in the repo


class ExtractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = extract_inventory(HTML)
        self.screens = {s["key"]: s for s in self.inventory["screens"]}

    def test_fixture_is_labelled_synthetic(self) -> None:
        self.assertIn("synthetic", HTML.lower())

    def test_screens_by_data_screen(self) -> None:
        self.assertEqual([s["key"] for s in self.inventory["screens"]], ["page", "sign-in", "claims", "new-claim"])
        self.assertEqual(self.screens["page"]["title"], "Outside any screen")
        self.assertEqual(self.screens["claims"]["title"], "My claims")
        self.assertTrue(self.screens["new-claim"]["hidden"])
        self.assertEqual([s["id"] for s in self.inventory["screens"]], ["S1", "S2", "S3", "S4"])

    def test_elements_and_hidden_states(self) -> None:
        sign_in = {(e["kind"], e["text"]) for e in self.screens["sign-in"]["elements"]}
        self.assertIn(("button", "Continue"), sign_in)
        self.assertIn(("field", "Password"), sign_in)
        error = next(e for e in self.screens["sign-in"]["elements"] if e["kind"] == "message")
        self.assertEqual((error["text"], error["hidden"]), ("The email or the password is not right.", True))
        columns = [e["text"] for e in self.screens["claims"]["elements"] if e["kind"] == "column"]
        self.assertEqual(columns, ["Claim", "Filed on", "Status", "Amount"])
        options = [e["text"] for e in self.screens["new-claim"]["elements"] if e["kind"] == "option"]
        self.assertEqual(options, ["Car accident", "Home damage", "Theft"])
        self.assertIn(("button", "Submit claim"), {(e["kind"], e["text"]) for e in self.screens["new-claim"]["elements"]})
        self.assertEqual(self.screens["claims"]["elements"][0]["id"], "S3-E01")

    def test_javascript_copy_without_code(self) -> None:
        texts = [lit["text"] for lit in self.inventory["js_literals"]]
        for wanted in ("Submitted", "Under review", "Approved, payment on its way.", "The attachment is larger than 10 MB.",
                       "Your session expired. Sign in again."):
            self.assertIn(wanted, texts)
        for code in ("/api/claims", "#"):
            self.assertNotIn(code, texts)
        self.assertEqual(self.inventory["js_literals"][0]["id"], "JS-01")

    def test_section_ids_or_the_page(self) -> None:
        sections = extract_inventory('<section id="home"><h1>Home</h1></section><section id="help"><p>Ask us.</p></section>')
        self.assertEqual([s["key"] for s in sections["screens"]], ["home", "help"])
        page = extract_inventory("<h1>Only page</h1><button>Go</button>")
        self.assertEqual([(s["key"], len(s["elements"])) for s in page["screens"]], [("page", 2)])

    def test_deterministic(self) -> None:
        self.assertEqual(extract_inventory(HTML), self.inventory)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        self.base = Path("workspaces") / "P"

    def tearDown(self) -> None:
        os.chdir(self.old)
        self.tmp.cleanup()

    def cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_inventory_of_an_ingested_prototype_redacts_the_secret(self) -> None:
        seeded = HTML.replace('const endpoint = "/api/claims";', f'const endpoint = "/api/claims"; const apiKey = "{CLOUD_KEY}";')
        Path("claims-portal.html").write_text(seeded, encoding="utf-8")
        self.assertEqual(self.cli("init", "P")[0], 0)
        self.assertEqual(self.cli("ingest", "P", "--source", "claims-portal.html")[0], 0)
        code, out = self.cli("prototype", "P", "--inventory")
        self.assertEqual(code, 0, out)
        summary = json.loads(out)["prototypes"][0]
        self.assertEqual((summary["source"], summary["screens"]), ("F-01", 4))
        inventory = (self.base / "02_requirements" / "prototype" / "inventory.json").read_text(encoding="utf-8")
        view = (self.base / "02_requirements" / "prototype" / "inventory.md").read_text(encoding="utf-8")
        self.assertNotIn(CLOUD_KEY, inventory + view)
        self.assertIn("| S2-E06 | button | Continue |", view)
        self.assertEqual(self.cli("view", "P", "--artifact", "prototype")[0], 0)
        first = (self.base / "02_requirements" / "prototype" / "inventory.json").read_bytes()
        self.assertEqual(self.cli("prototype", "P", "--inventory")[0], 0)
        self.assertEqual((self.base / "02_requirements" / "prototype" / "inventory.json").read_bytes(), first)

    def test_without_a_prototype_it_says_so(self) -> None:
        self.assertEqual(self.cli("init", "P")[0], 0)
        Path("notes.md").write_text("Meeting notes about the claims portal, with enough words.\n", encoding="utf-8")
        self.assertEqual(self.cli("ingest", "P", "--source", "notes.md")[0], 0)
        code, out = self.cli("prototype", "P", "--inventory")
        self.assertNotEqual(code, 0)
        self.assertIn("no HTML prototype", out)
        code, out = self.cli("prototype", "P", "--inventory", "--source", "F-99")
        self.assertIn("no HTML prototype for F-99", out)


if __name__ == "__main__":
    unittest.main()
