"""IMP-238: visual theme model (sentinel/themes.py).

A theme is data: light/dark colour tokens, a semantics map that generates the
colour legend, typography and provenance. The tokens a theme must define are
derived from ``sentinel/themes/base.css`` (every ``var(--x)`` it uses), so the
stylesheet and the validator cannot drift apart. The repository ships exactly
one built-in theme, ``neutral``; brand themes live locally (IMP-241).
"""

from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from sentinel import themes
from sentinel.themes import ThemeError

ROOT = Path(__file__).resolve().parents[1]


class _TmpThemeMixin:
    def _write_theme(self, theme: dict) -> Path:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_theme_")
        self.addCleanup(holder.cleanup)
        path = Path(holder.name) / "custom.json"
        path.write_text(json.dumps(theme), encoding="utf-8")
        return path

    def _neutral(self) -> dict:
        return copy.deepcopy(themes.load_theme())


class ThemeLoadingTests(_TmpThemeMixin, unittest.TestCase):
    def test_builtin_themes_are_exactly_neutral(self) -> None:
        self.assertEqual(themes.list_builtin_themes(), ["neutral"])

    def test_neutral_loads_and_is_valid(self) -> None:
        theme = themes.load_theme()
        self.assertEqual(theme["name"], "neutral")
        self.assertEqual(themes.validate_theme(theme), [])

    def test_required_tokens_come_from_base_css(self) -> None:
        required = themes.required_tokens()
        self.assertIn("--bg", required)
        self.assertNotIn("--font", required)
        self.assertNotIn("--font-mono", required)
        theme = themes.load_theme()
        for mode in ("light", "dark"):
            missing = required - set(theme["tokens"][mode])
            self.assertEqual(missing, set(), f"{mode} misses {sorted(missing)}")

    def test_missing_token_names_the_token(self) -> None:
        theme = self._neutral()
        del theme["tokens"]["dark"]["--ok-text"]
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme(self._write_theme(theme))
        self.assertIn("--ok-text", str(ctx.exception))
        self.assertIn("dark", str(ctx.exception))

    def test_extra_token_is_allowed(self) -> None:
        theme = self._neutral()
        for mode in ("light", "dark"):
            theme["tokens"][mode]["--extra"] = "#000000"
        self.assertEqual(themes.validate_theme(theme), [])

    def test_short_hex_is_rejected(self) -> None:
        theme = self._neutral()
        theme["tokens"]["light"]["--bg"] = "#FFF"
        errors = themes.validate_theme(theme)
        self.assertTrue(any("--bg" in e for e in errors), errors)

    def test_external_url_is_rejected(self) -> None:
        theme = self._neutral()
        theme["tipografia"]["font"] = "x, url(https://fonts.example/x.woff2)"
        errors = themes.validate_theme(theme)
        self.assertTrue(any("external" in e for e in errors), errors)

    def test_semantica_must_reference_existing_tokens(self) -> None:
        theme = self._neutral()
        theme["semantica"]["ok"]["fg"] = "--nope"
        errors = themes.validate_theme(theme)
        self.assertTrue(any("--nope" in e for e in errors), errors)

    def test_name_with_path_separator_is_rejected(self) -> None:
        for name in ("../neutral", "a/b", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ThemeError):
                themes.load_theme(name)

    def test_unknown_builtin_is_rejected(self) -> None:
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme("nope")
        self.assertIn("neutral", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
