"""Visual themes for derived HTML views (IMP-238).

A theme is data, not code: light/dark colour tokens, a ``semantica`` map that
says what each status colour means (the legend is generated from it), the
typography and the provenance of the palette. Built-in themes live in
``sentinel/themes/*.json`` and are read through ``importlib.resources`` so they
also work inside the ``.pyz`` zipapp. The repository ships exactly one built-in
theme, ``neutral``; brand themes are a user's local concern (IMP-241).

The tokens a theme must define are derived from ``base.css``: every
``var(--x)`` the stylesheet uses has to exist in both modes, so the stylesheet
and the validator cannot drift apart. Local-first: a theme may not reference
any external URL.
"""

from __future__ import annotations

import html
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from .core.io import parse_json, read_json_resource
from .resources import package_resource

BUILTIN_THEMES_DIR = "themes"
DEFAULT_THEME = "neutral"
USER_THEMES_ENV = "IGNITE_THEMES_DIR"
WORKSPACE_THEMES_DIR = (".sentinel", "themes")
MAX_FONT_BYTES = 1_500_000
RUNTIME_FONT_KEY = "_font_faces"
WOFF2_MAGIC = b"wOF2"
MODES = ("light", "dark")
FONT_TOKENS = {"--font": "font", "--font-mono": "font_mono"}

_TOKEN_REF = re.compile(r"var\((--[a-z0-9-]+)")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")  # used with fullmatch
_TOKEN_KEY = re.compile(r"--[a-z0-9-]+")  # used with fullmatch: keys are emitted into CSS
_FONT_FORBIDDEN = re.compile(r"[;{}@\\<>]")
_EXTERNAL = re.compile(r"https?://|url\(|//", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SAFE_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ThemeError(ValueError):
    """A theme could not be found or is invalid."""


def list_builtin_themes() -> list[str]:
    root = package_resource(BUILTIN_THEMES_DIR)
    return sorted(item.name[:-5] for item in root.iterdir() if item.is_file() and item.name.endswith(".json"))


def base_css() -> str:
    return package_resource(BUILTIN_THEMES_DIR, "base.css").read_text(encoding="utf-8")


def required_tokens() -> set[str]:
    css = _CSS_COMMENT.sub("", base_css())
    return set(_TOKEN_REF.findall(css)) - set(FONT_TOKENS)


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == RUNTIME_FONT_KEY:
                continue  # computed at load time from local files, never theme input
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def validate_theme(theme: dict, *, require_provenance: bool = True) -> list[str]:
    """Return human-readable validation errors (empty list = valid).

    ``require_provenance=False`` is used for user-local themes (IMP-241): a missing
    ``procedencia`` is then a warning (``theme_warnings``), not an error.
    """
    if not isinstance(theme, dict):
        return ["theme must be a JSON object"]
    errors: list[str] = []
    for key in ("name", "label"):
        if not isinstance(theme.get(key), str) or not theme.get(key):
            errors.append(f"missing or empty '{key}'")
    if require_provenance and (not isinstance(theme.get("procedencia"), dict) or not theme.get("procedencia")):
        errors.append("missing or empty 'procedencia' (where the palette comes from)")
    typography = theme.get("tipografia") if isinstance(theme.get("tipografia"), dict) else {}
    errors += _font_file_errors(typography)
    for field in FONT_TOKENS.values():
        if not isinstance(typography.get(field), str) or not typography.get(field):
            errors.append(f"missing 'tipografia.{field}'")
        elif _FONT_FORBIDDEN.search(typography[field]):
            errors.append(f"tipografia.{field} contains characters not allowed in a font list (; {{ }} @ \\ < >)")

    tokens = theme.get("tokens") if isinstance(theme.get("tokens"), dict) else {}
    required = required_tokens()
    for mode in MODES:
        mode_tokens = tokens.get(mode)
        if not isinstance(mode_tokens, dict):
            errors.append(f"missing 'tokens.{mode}'")
            continue
        for token in sorted(required - set(mode_tokens)):
            errors.append(f"token {token} missing in {mode} mode")
        for token, value in sorted(mode_tokens.items()):
            if not isinstance(token, str) or not _TOKEN_KEY.fullmatch(token):
                errors.append(f"token name {token!r} in {mode} mode must match --[a-z0-9-]+")
            if not isinstance(value, str) or not _HEX.fullmatch(value):
                errors.append(f"token {token} in {mode} mode must be #RRGGBB, got {value!r}")

    semantics = theme.get("semantica")
    if not isinstance(semantics, dict) or not semantics:
        errors.append("missing or empty 'semantica' (the legend is generated from it)")
    else:
        for role, spec in semantics.items():
            if not isinstance(spec, dict):
                errors.append(f"semantica.{role} must be an object")
                continue
            label = spec.get("label")
            if not isinstance(label, dict) or not label.get("en"):
                errors.append(f"semantica.{role} needs label.en")
            elif not all(isinstance(text, str) for text in label.values()):
                errors.append(f"semantica.{role} labels must be strings")
            for field in ("fg", "bg", "border"):
                ref = spec.get(field)
                if not isinstance(ref, str):
                    errors.append(f"semantica.{role}.{field} must be a token name string, got {ref!r}")
                    continue
                for mode in MODES:
                    if not isinstance(tokens.get(mode), dict) or ref not in tokens[mode]:
                        errors.append(f"semantica.{role}.{field} references {ref} which is not a {mode} token")

    for key in _underscore_keys(theme):
        errors.append(f"keys starting with '_' are reserved for the runtime: {key!r}")
    for text in _strings(theme):
        if _EXTERNAL.search(text):
            errors.append(f"external reference not allowed (local-first): {text!r}")
    return errors


def _underscore_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(key, str) and key.startswith("_") and not (prefix == "" and key == RUNTIME_FONT_KEY and isinstance(item, str) and item == ""):
                found.append(path)
            found += _underscore_keys(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += _underscore_keys(item, f"{prefix}[{index}]")
    return found


def theme_warnings(theme: dict) -> list[str]:
    """Soft findings for user themes (IMP-241): reported by /doctor, never block loading."""
    warnings: list[str] = []
    if not isinstance(theme.get("procedencia"), dict) or not theme.get("procedencia"):
        warnings.append(f"theme {theme.get('name')!r} has no 'procedencia' (say where the palette comes from)")
    return warnings


def _font_file_errors(typography: dict) -> list[str]:
    files = typography.get("font_files")
    if files is None or files == []:
        return []
    errors: list[str] = []
    if not isinstance(files, list):
        return ["tipografia.font_files must be a list"]
    license_name = typography.get("font_license")
    if not isinstance(license_name, str) or not _SAFE_FILE.fullmatch(license_name):
        errors.append("tipografia.font_license must name the licence file (e.g. OFL.txt) next to the theme")
    for index, spec in enumerate(files):
        if not isinstance(spec, dict):
            errors.append(f"tipografia.font_files[{index}] must be an object")
            continue
        family, filename = spec.get("family"), spec.get("file")
        if not isinstance(family, str) or not family or _FONT_FORBIDDEN.search(family) or '"' in family or _CONTROL.search(family):
            errors.append(f"tipografia.font_files[{index}].family is missing or has characters not allowed in CSS")
        if not isinstance(filename, str) or not _SAFE_FILE.fullmatch(filename) or not filename.lower().endswith(".woff2"):
            errors.append(f"tipografia.font_files[{index}].file must be a .woff2 file name next to the theme (no folders)")
        weight = spec.get("weight", 400)
        if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 1000:
            errors.append(f"tipografia.font_files[{index}].weight must be an integer")
        if spec.get("style", "normal") not in {"normal", "italic"}:
            errors.append(f"tipografia.font_files[{index}].style must be normal or italic")
    return errors


def _embed_fonts(theme: dict, folder: Path) -> str:
    """@font-face rules with data: URIs for the theme's local .woff2 files (no network)."""
    typography = theme.get("tipografia") or {}
    files = typography.get("font_files") or []
    if not files:
        return ""
    license_path = folder / str(typography["font_license"])
    if not _plain_file_inside(license_path, folder):
        raise ThemeError(f"theme {theme.get('name')!r} embeds fonts but its licence file is missing or not a plain file: {typography['font_license']}")
    rules = []
    for spec in files:
        path = folder / spec["file"]
        if not _plain_file_inside(path, folder):
            raise ThemeError(f"theme {theme.get('name')!r}: font file not found or not a plain file in the theme folder: {spec['file']}")
        if path.stat().st_size > MAX_FONT_BYTES:
            raise ThemeError(f"theme {theme.get('name')!r}: font {spec['file']} exceeds {MAX_FONT_BYTES} bytes")
        data = path.read_bytes()
        if not data.startswith(WOFF2_MAGIC):
            raise ThemeError(f"theme {theme.get('name')!r}: {spec['file']} is not a woff2 font (bad signature)")
        encoded = base64.b64encode(data).decode("ascii")
        rules.append(
            f'@font-face{{font-family:"{spec["family"]}";font-style:{spec.get("style", "normal")};'
            f'font-weight:{int(spec.get("weight", 400))};font-display:swap;'
            f"src:url(data:font/woff2;base64,{encoded}) format(\"woff2\");}}"
        )
    return "\n".join(rules) + "\n"


def _folder_label(folder: Path) -> str:
    """A search folder for messages, without the user's absolute home path."""
    parts = Path(folder).parts
    if len(parts) >= 2 and parts[-2:] == WORKSPACE_THEMES_DIR:
        return "<workspace>/" + "/".join(WORKSPACE_THEMES_DIR)
    if os.environ.get(USER_THEMES_ENV):
        return f"${USER_THEMES_ENV}"
    return "~/.ignite/themes"


def _inside(path: Path, folder: Path) -> bool:
    try:
        return Path(path).resolve().parent == Path(folder).resolve()
    except OSError:
        return False


def _plain_file_inside(path: Path, folder: Path) -> bool:
    """A regular file directly in ``folder``: no symlink, no junction, no escape (IMP-241 review)."""
    return path.is_file() and not path.is_symlink() and _inside(path, folder)


def user_theme_dirs(workspace: str | Path | None = None) -> list[Path]:
    """Where user-local themes live (IMP-241): the workspace's, then the user's home."""
    dirs: list[Path] = []
    if workspace is not None:
        dirs.append(Path(workspace).joinpath(*WORKSPACE_THEMES_DIR))
    home = os.environ.get(USER_THEMES_ENV)
    dirs.append(Path(home) if home else Path.home() / ".ignite" / "themes")
    return dirs


def _read_builtin(name: str) -> dict:
    if not _NAME.match(name):
        raise ThemeError(f"invalid theme name {name!r}: use a built-in name or a path to a .json file")
    available = list_builtin_themes()
    if name not in available:
        raise ThemeError(f"unknown theme {name!r}; available: {', '.join(available)}")
    return read_json_resource(package_resource(BUILTIN_THEMES_DIR, f"{name}.json"))


def _declarations(theme: dict, mode: str, scheme: str, *, fonts: bool) -> str:
    parts = [f"color-scheme:{scheme}"]
    parts += [f"{token}:{value}" for token, value in sorted(theme["tokens"][mode].items())]
    if fonts:
        parts += [f"{token}:{theme['tipografia'][field]}" for token, field in FONT_TOKENS.items()]
    return ";".join(parts) + ";"


def emit_root_css(theme: dict) -> str:
    """CSS custom properties for both modes, deterministic (tokens sorted).

    Light on bare ``:root``; dark under ``prefers-color-scheme`` (unless the
    viewer forced light) and under an explicit ``[data-theme="dark"]`` toggle.
    """
    dark = _declarations(theme, "dark", "dark", fonts=False)
    return (
        str(theme.get(RUNTIME_FONT_KEY, ""))
        + ":root{" + _declarations(theme, "light", "light", fonts=True) + "}\n"
        '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){' + dark + "}}\n"
        ':root[data-theme="dark"]{' + dark + "}\n"
    )


def theme_css(theme: dict) -> str:
    return emit_root_css(theme) + "\n" + base_css()


def _relative_luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG 2.x contrast ratio between two #RRGGBB colours (1.0 to 21.0)."""
    lighter, darker = sorted((_relative_luminance(fg_hex), _relative_luminance(bg_hex)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def legend_html(theme: dict, language: str = "en") -> str:
    """Colour legend generated from ``semantica`` (falls back to English labels)."""
    items = []
    for role, spec in theme["semantica"].items():
        labels = spec.get("label", {})
        text = labels.get(language) or labels.get("en", role)
        items.append(f'<li><span class="chip chip-{html.escape(role)}">{html.escape(text)}</span></li>')
    return '<ul class="legend">' + "".join(items) + "</ul>"


def load_theme(name_or_path: str | Path | None = None, *, search_dirs: list[Path] | tuple[Path, ...] = ()) -> dict:
    """Load and validate a theme by name or by path to a JSON file.

    A built-in name always resolves to the repo theme. Any other name is looked up as
    ``<dir>/<name>.json`` in ``search_dirs`` (IMP-241: workspace, then home). Themes
    loaded from a file are user themes: ``procedencia`` is a warning, local ``.woff2``
    fonts are embedded as ``data:`` URIs.
    """
    if name_or_path is None:
        name_or_path = DEFAULT_THEME
    text = str(name_or_path)
    is_path = isinstance(name_or_path, Path) or text.lower().endswith(".json") or "/" in text or "\\" in text
    builtins = {name.casefold(): name for name in list_builtin_themes()}
    if not is_path and text.casefold() in builtins:
        name_or_path = text = builtins[text.casefold()]
    elif not is_path and search_dirs and not _NAME.fullmatch(text):
        raise ThemeError(f"theme name {text!r} may only contain letters, digits, '-' and '_' (or pass a path to a .json file)")
    if not is_path and text not in builtins.values():
        for folder in search_dirs:
            candidate = Path(folder) / f"{text}.json"
            if candidate.is_file():
                name_or_path, is_path = candidate, True
                break
        else:
            if search_dirs:
                places = ", ".join(_folder_label(Path(folder)) for folder in search_dirs)
                raise ThemeError(f"theme {text!r} not found among built-in themes ({', '.join(list_builtin_themes())}) or in {places}")
    user_theme = is_path
    if is_path:
        path = Path(name_or_path)
        try:
            # utf-8-sig: accept the BOM PowerShell's Set-Content -Encoding UTF8 writes.
            theme = parse_json(path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise ThemeError(f"theme file not found: {path}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise ThemeError(f"theme file could not be read as UTF-8 text: {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ThemeError(f"theme file is not valid JSON: {path}: {exc}") from exc
    else:
        theme = _read_builtin(str(name_or_path))
    if not isinstance(theme, dict):
        raise ThemeError(f"theme {str(name_or_path)!r} must be a JSON object")
    errors = validate_theme(theme, require_provenance=not user_theme)
    if errors:
        raise ThemeError(f"invalid theme {theme.get('name', name_or_path)!r}: " + "; ".join(errors))
    if user_theme:
        theme[RUNTIME_FONT_KEY] = _embed_fonts(theme, Path(name_or_path).parent)
    return theme
