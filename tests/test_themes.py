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


class ThemeCssTests(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = themes.load_theme()
        self.css = themes.emit_root_css(self.theme)

    def test_root_block_has_light_tokens_and_fonts(self) -> None:
        self.assertTrue(self.css.startswith(":root{"), self.css[:40])
        self.assertIn("color-scheme:light", self.css)
        self.assertIn(f"--bg:{self.theme['tokens']['light']['--bg']}", self.css)
        self.assertIn("--font:", self.css)
        self.assertIn("--font-mono:", self.css)

    def test_dark_mode_has_media_and_explicit_blocks(self) -> None:
        self.assertIn("@media (prefers-color-scheme: dark)", self.css)
        self.assertIn(':root:not([data-theme="light"])', self.css)
        self.assertIn(':root[data-theme="dark"]', self.css)
        self.assertEqual(self.css.count("color-scheme:dark"), 2)

    def test_output_is_deterministic_and_sorted(self) -> None:
        self.assertEqual(self.css, themes.emit_root_css(self.theme))
        root_block = self.css[len(":root{") : self.css.index("}")]
        colour_props = [p.split(":")[0] for p in root_block.split(";") if p.startswith("--") and p.split(":")[0] not in themes.FONT_TOKENS]
        self.assertEqual(colour_props, sorted(colour_props))

    def test_theme_css_includes_base_css(self) -> None:
        self.assertTrue(themes.theme_css(self.theme).endswith(themes.base_css()))


class ThemeSemanticsTests(unittest.TestCase):
    AA = 4.5

    def setUp(self) -> None:
        self.theme = themes.load_theme()

    def test_contrast_ratio_known_values(self) -> None:
        self.assertEqual(round(themes.contrast_ratio("#000000", "#FFFFFF"), 2), 21.0)
        self.assertEqual(round(themes.contrast_ratio("#00292E", "#FFFFFF"), 2), 15.48)
        self.assertEqual(round(themes.contrast_ratio("#BFD732", "#FFFFFF"), 2), 1.62)

    def test_neutral_meets_aa_in_both_modes(self) -> None:
        for mode in themes.MODES:
            tokens = self.theme["tokens"][mode]
            pairs = {"text": ("--text", "--bg"), "text-muted": ("--text-muted", "--bg")}
            pairs.update({role: (spec["fg"], spec["bg"]) for role, spec in self.theme["semantica"].items()})
            for name, (fg, bg) in pairs.items():
                ratio = themes.contrast_ratio(tokens[fg], tokens[bg])
                with self.subTest(mode=mode, pair=name):
                    self.assertGreaterEqual(ratio, self.AA, f"{mode}/{name}: {ratio:.2f} < {self.AA}")

    def test_legend_lists_every_role_in_spanish(self) -> None:
        legend = themes.legend_html(self.theme, "es")
        for role in ("ok", "info", "warn", "block", "governance"):
            self.assertIn(f"chip-{role}", legend)
        self.assertIn("Listo / resuelto", legend)

    def test_legend_falls_back_to_english(self) -> None:
        self.assertIn("Ready / resolved", themes.legend_html(self.theme, "pt"))

    def test_legend_escapes_labels(self) -> None:
        theme = copy.deepcopy(self.theme)
        theme["semantica"]["ok"]["label"] = {"en": "<b>&"}
        legend = themes.legend_html(theme)
        self.assertIn("&lt;b&gt;&amp;", legend)
        self.assertNotIn("<b>", legend)


class ThemeHardeningTests(_TmpThemeMixin, unittest.TestCase):
    """Final-review findings: CSS injection, robust loading, doctor root."""

    def test_token_key_cannot_inject_css(self) -> None:
        theme = self._neutral()
        key = "--z:0}body{background:url(https://e.x/i.png)}:root{--y"
        for mode in themes.MODES:
            theme["tokens"][mode][key] = "#000000"
        self.assertTrue(themes.validate_theme(theme))

    def test_font_cannot_inject_css(self) -> None:
        theme = self._neutral()
        theme["tipografia"]["font"] = "x;}@import '//evil.example/a.css';:root{--q:1"
        errors = themes.validate_theme(theme)
        self.assertTrue(any("tipografia.font" in e for e in errors), errors)

    def test_hex_with_trailing_newline_is_rejected(self) -> None:
        theme = self._neutral()
        theme["tokens"]["light"]["--bg"] = "#FFFFFF\n"
        self.assertTrue(any("--bg" in e for e in themes.validate_theme(theme)))

    def test_non_object_json_raises_theme_error(self) -> None:
        path = self._write_theme([])  # type: ignore[arg-type]
        with self.assertRaises(ThemeError):
            themes.load_theme(path)

    def test_utf8_bom_and_utf16_files(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_theme_")
        self.addCleanup(holder.cleanup)
        bom = Path(holder.name) / "bom.json"
        bom.write_text(json.dumps(self._neutral()), encoding="utf-8-sig")
        self.assertEqual(themes.load_theme(bom)["name"], "neutral")
        utf16 = Path(holder.name) / "utf16.json"
        utf16.write_text(json.dumps(self._neutral()), encoding="utf-16")
        with self.assertRaises(ThemeError):
            themes.load_theme(utf16)

    def test_directory_path_raises_theme_error(self) -> None:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_theme_")
        self.addCleanup(holder.cleanup)
        folder = Path(holder.name) / "dir.json"
        folder.mkdir()
        with self.assertRaises(ThemeError):
            themes.load_theme(folder)

    def test_non_string_semantics_values_are_reported_not_crashing(self) -> None:
        theme = self._neutral()
        theme["semantica"]["ok"]["fg"] = ["--ok-text"]
        theme["semantica"]["info"]["label"] = {"en": 5}
        errors = themes.validate_theme(theme)
        self.assertTrue(any("semantica.ok.fg" in e for e in errors), errors)
        self.assertTrue(any("semantica.info" in e for e in errors), errors)


class ThemeDoctorTests(unittest.TestCase):
    def _fake_root(self, extra: dict[str, str]) -> Path:
        holder = tempfile.TemporaryDirectory(prefix="sentinel_theme_root_")
        self.addCleanup(holder.cleanup)
        root = Path(holder.name)
        target = root / "sentinel" / "themes"
        target.mkdir(parents=True)
        source = ROOT / "sentinel" / "themes"
        for name in ("neutral.json", "base.css"):
            (target / name).write_bytes((source / name).read_bytes())
        for name, text in extra.items():
            (target / name).write_text(text, encoding="utf-8")
        return root

    def test_doctor_theme_check_reads_the_root_checkout(self) -> None:
        from sentinel.doctor import themes_check

        result = themes_check(self._fake_root({"brand.json": "{}"}))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("brand.json", result["detail"])

    def test_doctor_theme_check_rejects_brand_assets(self) -> None:
        from sentinel.doctor import themes_check

        result = themes_check(self._fake_root({"logo.svg": "<svg/>"}))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("logo.svg", result["detail"])

    def test_doctor_theme_check_passes_on_clean_fake_root(self) -> None:
        from sentinel.doctor import themes_check

        self.assertEqual(themes_check(self._fake_root({}))["status"], "PASS")

    def test_doctor_theme_check_passes_on_repo(self) -> None:
        from sentinel.doctor import themes_check

        result = themes_check(ROOT)
        self.assertEqual(result["status"], "PASS", result)

    def test_doctor_theme_check_fails_on_extra_theme(self) -> None:
        from sentinel.doctor import themes_check

        result = themes_check(ROOT, builtin=["neutral", "brand"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("brand", result["detail"])

    def test_run_doctor_includes_theme_check(self) -> None:
        from sentinel.doctor import run_doctor

        names = {check["name"] for check in run_doctor(ROOT)["checks"]}
        self.assertIn("visual themes", names)


if __name__ == "__main__":
    unittest.main()
