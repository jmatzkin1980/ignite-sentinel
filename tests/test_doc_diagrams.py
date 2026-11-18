"""IMP-364 (H24): documentation diagrams are committed SVG images, not ```mermaid blocks.

GitHub's mobile app does not render Mermaid, so README.md and user_guide/*.md show each
diagram as an image under user_guide/images/, rendered from a .mmd source next to it by
tools/render_doc_diagrams.py. These checks need no browser: they fail when a source has no
SVG, an SVG is stale against its source, an SVG uses HTML labels (foreignObject), a page
still has a mermaid fence, or a page points to an image that does not exist.
Generated workspace output (for example tests/fixtures/golden/**/trace-graph.md) is out of scope.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "user_guide" / "images"
PAGES = [ROOT / "README.md", *sorted((ROOT / "user_guide").glob("*.md"))]
SHA_LINE = re.compile(r"\A<!-- source-sha256: ([0-9a-f]{64}) -->\r?\n")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*mermaid\b", re.MULTILINE | re.IGNORECASE)
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
RERENDER = "run python tools/render_doc_diagrams.py and commit the .svg"


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class DocDiagramTests(unittest.TestCase):
    def test_every_source_has_a_current_svg(self) -> None:
        sources = sorted(IMAGES.glob("*.mmd"))
        self.assertTrue(sources, "no diagram sources in user_guide/images/")
        for source in sources:
            svg = source.with_suffix(".svg")
            with self.subTest(diagram=source.name):
                self.assertTrue(svg.is_file(), f"{source.name} has no {svg.name}: {RERENDER}")
                match = SHA_LINE.match(svg.read_text(encoding="utf-8"))
                self.assertIsNotNone(match, f"{svg.name} does not start with a source-sha256 comment: {RERENDER}")
                self.assertEqual(match.group(1), source_sha256(source), f"{svg.name} is stale against {source.name}: {RERENDER}")

    def test_every_svg_has_a_source(self) -> None:
        for svg in sorted(IMAGES.glob("*.svg")):
            with self.subTest(svg=svg.name):
                self.assertTrue(svg.with_suffix(".mmd").is_file(), f"{svg.name} has no .mmd source next to it")

    def test_svgs_use_plain_text_labels(self) -> None:
        # An <img> on GitHub drops HTML labels inside foreignObject, so the labels vanish.
        for svg in sorted(IMAGES.glob("*.svg")):
            with self.subTest(svg=svg.name):
                self.assertNotIn("foreignObject", svg.read_text(encoding="utf-8"))

    def test_pages_have_no_mermaid_fence(self) -> None:
        for page in PAGES:
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                self.assertIsNone(FENCE.search(page.read_text(encoding="utf-8")),
                                  "use an SVG under user_guide/images/ instead of a mermaid block")

    def test_referenced_images_exist(self) -> None:
        for page in PAGES:
            text = page.read_text(encoding="utf-8")
            for target in MARKDOWN_IMAGE.findall(text) + HTML_IMAGE.findall(text):
                if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
                    continue
                path = (page.parent / unquote(target.split("#", 1)[0].split("?", 1)[0])).resolve()
                with self.subTest(page=page.name, image=target):
                    self.assertTrue(path.is_file(), f"{page.name} shows {target}, which does not exist")


if __name__ == "__main__":
    unittest.main()
