"""IMP-284: the only place Sentinel opens a browser, and only on a local file.

Views and the dashboard are static pages on disk. Opening anything that is not
an existing local file (an `http(s)://` URL, a host, a path that does not exist)
is refused, so the runtime never starts a network request through the browser.
`/doctor` (`network_isolation_check`) keeps `webbrowser` imported only here.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path


def open_local_file(target: Path | str) -> None:
    if isinstance(target, str) and "://" in target:
        raise ValueError(f"refusing to open {target}: only local files are opened (file://)")
    path = Path(target)
    if not path.is_file():
        raise ValueError(f"refusing to open {path.as_posix()}: not an existing local file")
    uri = path.resolve().as_uri()
    if not uri.startswith("file://"):
        raise ValueError(f"refusing to open {uri}: only file:// pages are opened")
    webbrowser.open(uri)
