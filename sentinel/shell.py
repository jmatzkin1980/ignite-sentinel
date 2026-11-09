"""Common HTML shell for Ignite Sentinel views (IMP-239).

Templates live in files under ``sentinel/themes/templates/`` and are filled with
``string.Template.substitute`` (strict: an unknown or missing placeholder is an
error). CSS and JS files are read raw and passed in as *values*, never parsed as
templates, so JavaScript ``${...}`` literals stay untouched.

The shell gives every view the same frame: skip link, sticky top bar with the
colour-mode toggle (persisted in ``localStorage`` behind ``try/catch``), a sticky
sidebar that becomes an off-canvas menu below 900 px (hamburger with
``aria-expanded``), and print rules. Output is deterministic: no clock, no
external URLs.
"""

from __future__ import annotations

import html
from string import Template

from .resources import package_resource
from .themes import theme_css

TEMPLATES = ("themes", "templates")

LABELS = {
    "es": {"skip": "Saltar al contenido", "menu": "Abrir o cerrar el menu", "nav": "Navegacion", "dark": "Modo oscuro", "light": "Modo claro"},
    "en": {"skip": "Skip to content", "menu": "Open or close the menu", "nav": "Navigation", "dark": "Dark mode", "light": "Light mode"},
}


def content_fingerprint(data: bytes) -> str:
    """12-hex sha256 of a file's content, independent of the OS line ending (IMP-246).

    The same workspace on Windows (CRLF) and Linux (LF) must produce the same page.
    """
    from .core.hashing import content_sha256

    return content_sha256(data)[:12]


def json_for_script(value: object) -> str:
    """JSON safe inside <script type="application/json">: no </ and no <!-- sequences."""
    import json

    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\u0021--")


def theme_argument_for_display(theme_arg: str) -> str:
    """The --theme value for a printed regen command: a built-in name as-is, a path by file name only, quoted.

    Never prints a directory (it can carry a user name or a client folder).
    """
    text = str(theme_arg or "").strip()
    if not any(sep in text for sep in ("/", "\\")) and not text.lower().endswith(".json"):
        return text
    name = text.replace("\\", "/").rsplit("/", 1)[-1]
    return '"' + name.replace('"', "") + '"'


def template_text(name: str) -> str:
    return package_resource(*TEMPLATES, name).read_text(encoding="utf-8")


def fill(name: str, **values: str) -> str:
    return Template(template_text(name)).substitute(**values)


# IMP-288: every page the shell renders is self-contained. Inline styles and
# scripts run, embedded (`data:`) images and fonts load (IMP-241 themes), and
# nothing else: no remote resource, connection, form submission or base rewrite.
# A meta tag, not a header: the pages are opened from disk.
VIEW_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
    "font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"
)


def render_shell(*, theme: dict, title: str, heading: str, nav: str, content: str, page_css: str, page_js: str, language: str = "es") -> str:
    labels = LABELS.get(language, LABELS["en"])
    return fill(
        "shell.html",
        lang=language,
        csp=VIEW_CSP,
        title=html.escape(title),
        heading=heading,
        theme_css=theme_css(theme),
        shell_css=template_text("shell.css"),
        page_css=page_css,
        skip_label=labels["skip"],
        menu_label=labels["menu"],
        nav_label=labels["nav"],
        mode_dark=labels["dark"],
        mode_light=labels["light"],
        nav=nav,
        content=content,
        shell_js=template_text("shell.js"),
        page_js=page_js,
    )
