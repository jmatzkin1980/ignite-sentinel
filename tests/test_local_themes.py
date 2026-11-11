"""IMP-241: user-local themes.

Search order for a theme *name*: built-in names always resolve to the repo theme;
other names are looked up in ``<workspace>/.sentinel/themes/`` (``/view`` only),
then in ``~/.ignite/themes/`` (overridable with ``IGNITE_THEMES_DIR``). Brand
themes never live in the repo. ``procedencia`` is required but its absence in a
user theme is a ``/doctor`` WARN, not a load error. Optional ``.woff2`` fonts are
embedded as ``data:`` URIs and need the OFL licence file next to them.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sentinel import themes
from sentinel.themes import ThemeError

# A tiny but structurally valid woff2 signature followed by padding: we only embed bytes.
WOFF2_BYTES = b"wOF2" + b"\x00" * 60


class _LocalThemesBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sentinel_local_themes_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home_themes = self.tmp / "home" / ".ignite" / "themes"
        self.home_themes.mkdir(parents=True)
        env = patch.dict(os.environ, {"IGNITE_THEMES_DIR": str(self.home_themes)})
        env.start()
        self.addCleanup(env.stop)

    def brand(self, name: str = "acme", **changes) -> dict:
        theme = copy.deepcopy(themes.load_theme())
        theme["name"] = name
        theme["label"] = name.title()
        theme["procedencia"] = {"origen": "Synthetic test theme"}
        theme.update(changes)
        return theme

    def write(self, folder: Path, theme: dict, filename: str | None = None) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (filename or f"{theme['name']}.json")
        path.write_text(json.dumps(theme), encoding="utf-8")
        return path


class SearchOrderTests(_LocalThemesBase):
    def test_home_theme_loads_by_name(self) -> None:
        self.write(self.home_themes, self.brand())
        theme = themes.load_theme("acme", search_dirs=themes.user_theme_dirs())
        self.assertEqual(theme["name"], "acme")

    def test_workspace_theme_wins_over_home(self) -> None:
        workspace_dir = self.tmp / "ws" / ".sentinel" / "themes"
        self.write(self.home_themes, self.brand(label="Home"))
        self.write(workspace_dir, self.brand(label="Workspace"))
        theme = themes.load_theme("acme", search_dirs=[workspace_dir, self.home_themes])
        self.assertEqual(theme["label"], "Workspace")

    def test_builtin_name_is_never_shadowed(self) -> None:
        self.write(self.home_themes, self.brand(name="neutral", label="Impostor"))
        theme = themes.load_theme("neutral", search_dirs=themes.user_theme_dirs())
        self.assertEqual(theme["label"], "Neutral")

    def test_unknown_name_lists_searched_places(self) -> None:
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme("missing-brand", search_dirs=themes.user_theme_dirs())
        self.assertIn("$IGNITE_THEMES_DIR", str(ctx.exception))  # a label, never the absolute home path
        self.assertIn("neutral", str(ctx.exception))

    def test_user_theme_dirs_for_a_workspace(self) -> None:
        dirs = themes.user_theme_dirs(workspace=self.tmp / "ws")
        self.assertEqual(dirs, [self.tmp / "ws" / ".sentinel" / "themes", self.home_themes])


class ProvenanceTests(_LocalThemesBase):
    def test_user_theme_without_provenance_loads_with_warning(self) -> None:
        theme = self.brand()
        del theme["procedencia"]
        path = self.write(self.home_themes, theme)
        loaded = themes.load_theme(path)
        self.assertEqual(loaded["name"], "acme")
        self.assertTrue(any("procedencia" in w for w in themes.theme_warnings(loaded)))

    def test_builtin_still_requires_provenance(self) -> None:
        builtin = copy.deepcopy(themes.load_theme())
        del builtin["procedencia"]
        self.assertTrue(any("procedencia" in e for e in themes.validate_theme(builtin)))


class FontTests(_LocalThemesBase):
    def _with_font(self, **font) -> Path:
        folder = self.home_themes
        (folder / "Heebo-Regular.woff2").parent.mkdir(parents=True, exist_ok=True)
        (folder / "Heebo-Regular.woff2").write_bytes(WOFF2_BYTES)
        (folder / "OFL.txt").write_text("SIL Open Font License 1.1 (synthetic test copy)", encoding="utf-8")
        theme = self.brand()
        theme["tipografia"] = {
            "font": "Heebo, system-ui, sans-serif",
            "font_mono": "Consolas, monospace",
            "font_license": "OFL.txt",
            "font_files": [{"family": "Heebo", "file": "Heebo-Regular.woff2", "weight": 400, "style": "normal", **font}],
        }
        return self.write(folder, theme)

    def test_woff2_is_embedded_as_data_uri(self) -> None:
        css = themes.emit_root_css(themes.load_theme(self._with_font()))
        expected = base64.b64encode(WOFF2_BYTES).decode("ascii")
        self.assertIn("@font-face{font-family:\"Heebo\";", css)
        self.assertIn(f"url(data:font/woff2;base64,{expected})", css)
        self.assertNotRegex(css, r"https?://")

    def test_font_without_licence_is_rejected(self) -> None:
        path = self._with_font()
        (path.parent / "OFL.txt").unlink()
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme(path)
        self.assertIn("OFL.txt", str(ctx.exception))

    def test_only_woff2_and_no_paths(self) -> None:
        for bad in ("font.ttf", "../Heebo-Regular.woff2", "sub/Heebo-Regular.woff2"):
            with self.subTest(file=bad), self.assertRaises(ThemeError):
                themes.load_theme(self._with_font(file=bad))

    def test_oversized_font_is_rejected(self) -> None:
        path = self._with_font()
        (path.parent / "Heebo-Regular.woff2").write_bytes(b"wOF2" + b"\x00" * (themes.MAX_FONT_BYTES + 1))
        with self.assertRaises(ThemeError):
            themes.load_theme(path)

    def test_font_family_cannot_inject_css(self) -> None:
        with self.assertRaises(ThemeError):
            themes.load_theme(self._with_font(family='x";}body{background:red'))


class DoctorLocalThemesTests(_LocalThemesBase):
    def test_no_local_themes_passes(self) -> None:
        from sentinel.doctor import user_themes_check

        self.assertEqual(user_themes_check(self.tmp)["status"], "PASS")

    def test_missing_provenance_and_shadow_and_invalid_warn(self) -> None:
        from sentinel.doctor import user_themes_check

        no_prov = self.brand(name="noprov")
        del no_prov["procedencia"]
        self.write(self.home_themes, no_prov)
        self.write(self.home_themes, self.brand(name="neutral"))
        (self.home_themes / "broken.json").write_text("{", encoding="utf-8")
        result = user_themes_check(self.tmp)
        self.assertEqual(result["status"], "WARN")
        for needle in ("noprov", "neutral", "broken"):
            self.assertIn(needle, result["detail"])


class LegacyWorkspaceGitignoreTests(_LocalThemesBase):
    def _legacy_workspace(self) -> Path:
        from sentinel.cli import main
        from sentinel.workspace import workspace_path

        old = Path.cwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, old)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "LEGACY", "--brief-version", "1"]), 0)
        base = workspace_path("LEGACY")
        (base / ".gitignore").write_text("memory.lancedb/\n", encoding="utf-8")  # pre-IMP-241 content
        return base

    def test_ensure_workspace_appends_the_local_themes_rule(self) -> None:
        from sentinel.workspace import ensure_workspace

        base = self._legacy_workspace()
        ensure_workspace("LEGACY")
        ensure_workspace("LEGACY")
        text = (base / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("memory.lancedb/\n"), "existing rules are kept")
        self.assertEqual(text.count(".sentinel/"), 1)

    def test_doctor_warns_when_local_themes_are_not_ignored(self) -> None:
        from sentinel.doctor import user_themes_check

        base = self._legacy_workspace()
        self.write(base / ".sentinel" / "themes", self.brand())
        result = user_themes_check(self.tmp)
        self.assertEqual(result["status"], "WARN")
        self.assertIn(".gitignore", result["detail"])


class SurfaceTests(_LocalThemesBase):
    def test_workspace_gitignore_excludes_local_themes(self) -> None:
        from sentinel.workspace import WORKSPACE_GITIGNORE

        self.assertIn(".sentinel/", WORKSPACE_GITIGNORE)

    def test_view_resolves_workspace_then_home(self) -> None:
        from sentinel.view import resolve_view_theme
        from sentinel.workspace import workspace_path

        old = Path.cwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, old)
        from sentinel.cli import main

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "LOCALTHEME", "--brief-version", "1"]), 0)
        self.write(workspace_path("LOCALTHEME") / ".sentinel" / "themes", self.brand(label="Workspace"))
        self.write(self.home_themes, self.brand(label="Home"))
        theme, theme_arg, warning = resolve_view_theme("LOCALTHEME", "acme")
        self.assertEqual((theme["label"], theme_arg, warning), ("Workspace", "acme", None))

    def test_dashboard_resolves_home_theme_by_name(self) -> None:
        from sentinel.dashboard import generate_dashboard

        self.write(self.home_themes, self.brand(label="Home"))
        (self.tmp / "root").mkdir()
        result = generate_dashboard(self.tmp / "root", theme="acme")
        self.assertEqual(result["theme"], "acme")
        self.assertIn("--theme acme", (self.tmp / "root" / "dashboard.html").read_text(encoding="utf-8"))


class ReviewFixTests(_LocalThemesBase):
    """Final-review findings for IMP-241 (each failed before its fix)."""

    def test_doctor_still_requires_provenance_on_the_repo_theme(self) -> None:
        from sentinel.doctor import themes_check

        root = self.tmp / "fake"
        source = Path(__file__).resolve().parents[1] / "sentinel" / "themes"
        shutil.copytree(source, root / "sentinel" / "themes", ignore=shutil.ignore_patterns("__pycache__"))
        neutral = root / "sentinel" / "themes" / "neutral.json"
        data = json.loads(neutral.read_text(encoding="utf-8"))
        del data["procedencia"]
        neutral.write_text(json.dumps(data), encoding="utf-8")
        result = themes_check(root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("procedencia", result["detail"])

    def test_non_font_bytes_are_rejected(self) -> None:
        path = self._font_theme(b"not a font at all")
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme(path)
        self.assertIn("woff2", str(ctx.exception))

    def test_symlinked_font_is_rejected(self) -> None:
        secret = self.tmp / "secret.txt"
        secret.write_bytes(b"wOF2 pretend secret")
        path = self._font_theme(WOFF2_BYTES)
        font = path.parent / "Heebo-Regular.woff2"
        font.unlink()
        try:
            os.symlink(secret, font)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks need privileges on this machine")
        with self.assertRaises(ThemeError):
            themes.load_theme(path)

    def test_resolved_font_must_stay_in_the_theme_folder(self) -> None:
        # Cross-platform proxy for the symlink rule: the containment check itself.
        self.assertFalse(themes._inside(self.tmp / "a" / "x.woff2", self.tmp / "b"))
        self.assertTrue(themes._inside(self.tmp / "b" / "x.woff2", self.tmp / "b"))

    def test_builtin_name_in_any_case_is_not_shadowed(self) -> None:
        self.write(self.home_themes, self.brand(name="neutral", label="Impostor"), filename="neutral.json")
        theme = themes.load_theme("Neutral", search_dirs=themes.user_theme_dirs())
        self.assertEqual(theme["label"], "Neutral")

    def test_theme_names_are_validated_before_lookup(self) -> None:
        for bad in ("C:acme", "acme:stream", "a b", ".hidden"):
            with self.subTest(name=bad), self.assertRaises(ThemeError):
                themes.load_theme(bad, search_dirs=themes.user_theme_dirs())

    def test_underscore_keys_are_rejected_in_input(self) -> None:
        theme = self.brand()
        theme["semantica"]["_x"] = copy.deepcopy(theme["semantica"]["ok"])
        path = self.write(self.home_themes, theme)
        with self.assertRaises(ThemeError):
            themes.load_theme(path)

    def test_font_spec_edge_cases(self) -> None:
        bool_weight = self._font_theme(WOFF2_BYTES, weight=True)
        with self.assertRaises(ThemeError):
            themes.load_theme(bool_weight)
        control = self._font_theme(WOFF2_BYTES, family="Hee\nbo")
        with self.assertRaises(ThemeError):
            themes.load_theme(control)

    def test_not_found_message_does_not_print_the_home_path(self) -> None:
        with self.assertRaises(ThemeError) as ctx:
            themes.load_theme("missing-brand", search_dirs=themes.user_theme_dirs())
        self.assertNotIn(str(self.tmp), str(ctx.exception))

    def test_gitignore_append_keeps_line_endings_and_detects_variants(self) -> None:
        from sentinel.workspace import ensure_local_themes_ignored

        lf = self.tmp / "lf.gitignore"
        lf.write_bytes(b"a/\nb/\n")
        self.assertTrue(ensure_local_themes_ignored(lf))
        self.assertNotIn(b"\r\n", lf.read_bytes())
        self.assertTrue(lf.read_bytes().startswith(b"a/\nb/\n"))
        crlf = self.tmp / "crlf.gitignore"
        crlf.write_bytes(b"a/\r\nb/\r\n")
        ensure_local_themes_ignored(crlf)
        self.assertNotIn(b"\n.sentinel/\n", crlf.read_bytes().replace(b"\r\n", b"\r\n"))
        self.assertTrue(crlf.read_bytes().endswith(b".sentinel/\r\n"))
        for variant in (b"/.sentinel/\n", b".sentinel\n", b".sentinel/*\n", b"\xef\xbb\xbf.sentinel/\n"):
            path = self.tmp / "variant.gitignore"
            path.write_bytes(variant)
            with self.subTest(variant=variant):
                self.assertFalse(ensure_local_themes_ignored(path))
        latin = self.tmp / "latin.gitignore"
        latin.write_bytes("caf\xe9/\n".encode("latin-1"))
        ensure_local_themes_ignored(latin)  # must not crash
        self.assertIn(b".sentinel/", latin.read_bytes())

    def _font_theme(self, data: bytes, **font) -> Path:
        folder = self.home_themes
        (folder / "Heebo-Regular.woff2").write_bytes(data)
        (folder / "OFL.txt").write_text("SIL Open Font License 1.1 (synthetic test copy)", encoding="utf-8")
        theme = self.brand()
        theme["tipografia"] = {
            "font": "Heebo, system-ui, sans-serif",
            "font_mono": "Consolas, monospace",
            "font_license": "OFL.txt",
            "font_files": [{"family": "Heebo", "file": "Heebo-Regular.woff2", "weight": 400, "style": "normal", **font}],
        }
        return self.write(folder, theme)


if __name__ == "__main__":
    unittest.main()
