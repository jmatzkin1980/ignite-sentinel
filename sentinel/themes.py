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

import json
import re
from pathlib import Path
from typing import Any

from .resources import package_resource

BUILTIN_THEMES_DIR = "themes"
DEFAULT_THEME = "neutral"
MODES = ("light", "dark")
FONT_TOKENS = {"--font": "font", "--font-mono": "font_mono"}

_TOKEN_REF = re.compile(r"var\((--[a-z0-9-]+)")
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_EXTERNAL = re.compile(r"https?://|url\(|^//", re.IGNORECASE)
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
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def validate_theme(theme: dict) -> list[str]:
    """Return human-readable validation errors (empty list = valid)."""
    if not isinstance(theme, dict):
        return ["theme must be a JSON object"]
    errors: list[str] = []
    for key in ("name", "label"):
        if not isinstance(theme.get(key), str) or not theme.get(key):
            errors.append(f"missing or empty '{key}'")
    if not isinstance(theme.get("procedencia"), dict) or not theme.get("procedencia"):
        errors.append("missing or empty 'procedencia' (where the palette comes from)")
    typography = theme.get("tipografia") if isinstance(theme.get("tipografia"), dict) else {}
    for field in FONT_TOKENS.values():
        if not isinstance(typography.get(field), str) or not typography.get(field):
            errors.append(f"missing 'tipografia.{field}'")

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
            if not isinstance(value, str) or not _HEX.match(value):
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
            for field in ("fg", "bg", "border"):
                ref = spec.get(field)
                for mode in MODES:
                    if not isinstance(tokens.get(mode), dict) or ref not in tokens[mode]:
                        errors.append(f"semantica.{role}.{field} references {ref} which is not a {mode} token")

    for text in _strings(theme):
        if _EXTERNAL.search(text):
            errors.append(f"external reference not allowed (local-first): {text!r}")
    return errors


def _read_builtin(name: str) -> dict:
    if not _NAME.match(name):
        raise ThemeError(f"invalid theme name {name!r}: use a built-in name or a path to a .json file")
    available = list_builtin_themes()
    if name not in available:
        raise ThemeError(f"unknown theme {name!r}; available: {', '.join(available)}")
    return json.loads(package_resource(BUILTIN_THEMES_DIR, f"{name}.json").read_text(encoding="utf-8"))


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
        ":root{" + _declarations(theme, "light", "light", fonts=True) + "}\n"
        '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){' + dark + "}}\n"
        ':root[data-theme="dark"]{' + dark + "}\n"
    )


def theme_css(theme: dict) -> str:
    return emit_root_css(theme) + "\n" + base_css()


def load_theme(name_or_path: str | Path | None = None) -> dict:
    """Load and validate a theme by built-in name or by path to a JSON file."""
    if name_or_path is None:
        name_or_path = DEFAULT_THEME
    if isinstance(name_or_path, Path) or str(name_or_path).lower().endswith(".json"):
        path = Path(name_or_path)
        try:
            theme = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ThemeError(f"theme file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ThemeError(f"theme file is not valid JSON: {path}: {exc}") from exc
    else:
        theme = _read_builtin(str(name_or_path))
    errors = validate_theme(theme)
    if errors:
        raise ThemeError(f"invalid theme {theme.get('name', name_or_path)!r}: " + "; ".join(errors))
    return theme
