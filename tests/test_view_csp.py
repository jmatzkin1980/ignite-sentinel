"""IMP-288: Content-Security-Policy in every page the shell renders.

Views and the dashboard are local, self-contained pages. The policy lets inline
styles and scripts run and embedded (`data:`) images and fonts load, and denies
everything else: no remote resource, no connection, no form submission, no base
URL rewrite. It is a `<meta http-equiv>` placed before any script, because the
pages are opened from disk where there are no response headers.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from sentinel.shell import VIEW_CSP, render_shell
from sentinel.themes import load_theme

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
    "font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"
)
META = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">')


def _render() -> str:
    return render_shell(
        theme=load_theme(), title="t", heading="h", nav="", content="<p>x</p>", page_css="", page_js="", language="en"
    )


class CspTests(unittest.TestCase):
    def test_policy_matches_the_specification(self) -> None:
        self.assertEqual(VIEW_CSP, EXPECTED)

    def test_shell_emits_the_policy_before_any_script_or_style(self) -> None:
        page = _render()
        match = META.search(page)
        self.assertIsNotNone(match, "the shell must carry the CSP meta tag")
        self.assertEqual(match.group(1), EXPECTED)
        self.assertLess(match.start(), page.index("<script"))
        self.assertLess(match.start(), page.index("<style"))

    def test_every_golden_page_carries_the_policy(self) -> None:
        pages = sorted((REPO_ROOT / "tests" / "fixtures" / "golden").rglob("*.html"))
        self.assertTrue(pages)
        missing = [p.relative_to(REPO_ROOT).as_posix() for p in pages if EXPECTED not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [])

    def test_templates_reference_no_remote_resource(self) -> None:
        offenders = []
        for path in sorted((REPO_ROOT / "sentinel" / "themes" / "templates").iterdir()):
            text = path.read_text(encoding="utf-8")
            for pattern in (r"""(?:src|href)\s*=\s*["']https?://""", r"url\(\s*['\"]?https?://", r"@import", r"\bfetch\(", r"XMLHttpRequest", r"new WebSocket"):
                if re.search(pattern, text):
                    offenders.append(f"{path.name}: {pattern}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
