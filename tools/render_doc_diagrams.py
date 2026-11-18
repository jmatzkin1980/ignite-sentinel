"""Render the documentation diagrams (user_guide/images/*.mmd) to static SVG files.

GitHub's mobile app does not render ```mermaid blocks, and the web view does not always
either, so README.md and user_guide/*.md show each diagram as an <img> of a committed SVG.
This script rebuilds those SVGs from their Mermaid sources, offline:

    python tools/render_doc_diagrams.py              # every user_guide/images/*.mmd
    python tools/render_doc_diagrams.py guide-idea   # only the named diagrams
    python tools/render_doc_diagrams.py --browser "C:/path/to/chrome.exe"

It loads the vendored, hash-pinned Mermaid (sentinel/vendor/mermaid/mermaid.min.js) in a
headless Chrome or Edge (`--dump-dom`), so nothing is downloaded and no npm tool is needed.
The browser comes from --browser, else the SENTINEL_CHROME environment variable, else the
usual install locations. Labels are plain SVG <text> (no foreignObject), the background is
solid white so the image reads on a dark theme, and each SVG starts with
`<!-- source-sha256: ... -->` so tests/test_doc_diagrams.py can tell when it is stale.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "user_guide" / "images"
MERMAID = ROOT / "sentinel" / "vendor" / "mermaid" / "mermaid.min.js"
DIAGRAMS_PY = ROOT / "sentinel" / "diagrams.py"
FONT = "Arial, Helvetica, sans-serif"
BROWSER_ENV = "SENTINEL_CHROME"
BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)
BROWSER_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><script src="{mermaid}"></script></head>
<body><pre id="result" data-status="pending"></pre>
<script>
(async () => {{
  const out = document.getElementById("result");
  try {{
    mermaid.initialize({config});
    const {{ svg }} = await mermaid.render({id}, {source});
    const bytes = new TextEncoder().encode(svg);
    let text = "";
    for (const b of bytes) text += String.fromCharCode(b);
    out.textContent = btoa(text);
    out.dataset.status = "ok";
  }} catch (err) {{
    out.textContent = String(err && err.message || err);
    out.dataset.status = "error";
  }}
}})();
</script></body></html>
"""


def source_sha256(path: Path) -> str:
    """sha256 of a .mmd with line endings normalized, so a CRLF checkout gives the same value."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_vendored_mermaid() -> None:
    match = re.search(r'^MERMAID_SHA256 = "([0-9a-f]{64})"', DIAGRAMS_PY.read_text(encoding="utf-8"), re.MULTILINE)
    if not MERMAID.is_file() or not match:
        raise SystemExit(f"render_doc_diagrams: vendored mermaid not found at {MERMAID}")
    actual = hashlib.sha256(MERMAID.read_bytes()).hexdigest()
    if actual != match.group(1):
        raise SystemExit(f"render_doc_diagrams: {MERMAID} does not match MERMAID_SHA256 in sentinel/diagrams.py")


def find_browser(explicit: str | None) -> str:
    for value, origin in ((explicit, "--browser"), (os.environ.get(BROWSER_ENV), BROWSER_ENV)):
        if value:
            if Path(value).is_file():
                return value
            raise SystemExit(f"render_doc_diagrams: {origin} points to {value!r}, which is not a file")
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        "render_doc_diagrams: no Chrome or Edge found. Pass --browser <path> or set "
        f"{BROWSER_ENV} to a Chrome, Chromium or Edge executable."
    )


def mermaid_config(name: str) -> dict:
    return {
        "startOnLoad": False,
        "securityLevel": "strict",
        "theme": "default",
        "htmlLabels": False,
        "flowchart": {"htmlLabels": False, "useMaxWidth": False, "wrappingWidth": 300},
        "deterministicIds": True,
        "deterministicIDSeed": name,
        "fontFamily": FONT,
        "themeVariables": {"fontFamily": FONT, "fontSize": "16px"},
    }


def render_svg(browser: str, name: str, source: str, workdir: Path) -> str:
    page = workdir / f"{name}.html"
    page.write_text(
        PAGE.format(
            mermaid=MERMAID.as_uri(),
            config=json.dumps(mermaid_config(name)),
            id=json.dumps(f"diagram-{name}"),
            source=json.dumps(source),
        ),
        encoding="utf-8",
    )
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--allow-file-access-from-files",
        f"--user-data-dir={workdir / 'profile'}",
        "--virtual-time-budget=20000",
        "--dump-dom",
        page.as_uri(),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    match = re.search(r'<pre id="result" data-status="(\w+)">(.*?)</pre>', completed.stdout, re.DOTALL)
    if not match:
        raise SystemExit(f"render_doc_diagrams: {name}: the browser returned no result (exit {completed.returncode}).\n{completed.stderr[-2000:]}")
    status, payload = match.groups()
    if status != "ok":
        raise SystemExit(f"render_doc_diagrams: {name}: mermaid {status}: {html.unescape(payload)}")
    return base64.b64decode(payload).decode("utf-8")


def postprocess(svg: str, name: str) -> str:
    """Make the SVG self-contained and stable: fixed size, white background, no HTML labels."""
    if "foreignObject" in svg:
        raise SystemExit(f"render_doc_diagrams: {name}: the SVG still has foreignObject (HTML labels)")
    opening = re.match(r"<svg\b[^>]*>", svg)
    if not opening:
        raise SystemExit(f"render_doc_diagrams: {name}: output does not start with <svg>")
    tag = opening.group(0)
    viewbox = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', tag)
    if not viewbox:
        raise SystemExit(f"render_doc_diagrams: {name}: no viewBox on the root <svg>")
    x, y, width, height = (float(value) for value in viewbox.groups())
    new_tag = re.sub(r'\s(?:width|height|style)="[^"]*"', "", tag)
    new_tag = new_tag[:-1] + f' width="{round(width)}" height="{round(height)}" style="background-color: #ffffff">'
    background = f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" fill="#ffffff"/>'
    svg = new_tag + background + svg[len(tag):]
    external = re.findall(r"(?:@import|url\((?!#)|(?:href|src)=\"(?!#)[^\"]+\")", svg)
    if external:
        raise SystemExit(f"render_doc_diagrams: {name}: external reference in the SVG: {external[:3]}")
    return svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render user_guide/images/*.mmd to SVG with the vendored mermaid.")
    parser.add_argument("names", nargs="*", help="diagram names (file stems) to render; default: all")
    parser.add_argument("--browser", help=f"Chrome, Chromium or Edge executable (default: ${BROWSER_ENV}, then the usual locations)")
    args = parser.parse_args(argv)

    sources = sorted(IMAGES.glob("*.mmd"))
    if args.names:
        wanted = set(args.names)
        unknown = wanted - {path.stem for path in sources}
        if unknown:
            raise SystemExit(f"render_doc_diagrams: no such diagram: {', '.join(sorted(unknown))}")
        sources = [path for path in sources if path.stem in wanted]
    if not sources:
        raise SystemExit(f"render_doc_diagrams: no .mmd files in {IMAGES}")
    check_vendored_mermaid()
    browser = find_browser(args.browser)
    print(f"browser: {browser}")
    with tempfile.TemporaryDirectory(prefix="sentinel-diagrams-", ignore_cleanup_errors=True) as tmp:
        for path in sources:
            source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            svg = postprocess(render_svg(browser, path.stem, source, Path(tmp)), path.stem)
            target = path.with_suffix(".svg")
            text = f"<!-- source-sha256: {source_sha256(path)} -->\n{svg}\n"
            target.write_bytes(text.encode("utf-8"))
            print(f"wrote {target.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
