"""Tests explicit respondent profile declarations in domain context."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from sentinel.domain_context import respondent_profile_from_domain_context


class RespondentProfileDomainContextTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="domain_context_test_")
        self.base = Path(self.tmpdir)
        self.context_dir = self.base / "00_raw" / "02_technology_context"
        self.context_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detects_declared_frontmatter_profile(self):
        (self.context_dir / "tech.md").write_text(
            "---\nrespondent_profile: technical\n---\n\nTechnical API context.",
            encoding="utf-8",
        )

        self.assertEqual("technical", respondent_profile_from_domain_context(self.base))

    def test_ignores_free_text_without_frontmatter(self):
        (self.context_dir / "tech.md").write_text(
            "This was written by the technical architect for a business owner.",
            encoding="utf-8",
        )

        self.assertIsNone(respondent_profile_from_domain_context(self.base))

    def test_invalid_declared_profile_is_ignored(self):
        (self.context_dir / "tech.md").write_text(
            "---\nrespondent_profile: architect\n---\n\nArchitecture context.",
            encoding="utf-8",
        )

        self.assertIsNone(respondent_profile_from_domain_context(self.base))


if __name__ == "__main__":
    unittest.main()
