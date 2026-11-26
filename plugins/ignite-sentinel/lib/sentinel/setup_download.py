"""The only network code in Ignite Sentinel (IMP-425, H27 inc 7b).

Declared exception to "Sentinel never downloads", decided by Jose on 2026-11-25
(IMP-425 renumbered from the planned IMP-426): `/setup --semantic-memory`
fetches a pinned embedding model, and only here.

Fences:
- stdlib only, no `sentinel` import; no module imports this file (a test walks
  the AST). `semantic_setup.subprocess_fetch` runs it as `python -I setup_download.py`
  (from a .pyz it first extracts this file to a private temporary folder).
- https only, and the host of the URL and of every redirect must be in the list
  given on the command line. An entry starting with "." allows that domain's
  subdomains (".hf.co" allows "us.aws.cdn.hf.co", not "hf.co" nor "evilhf.co").
- The body is never larger than MAXBYTES (the manifest's size for that file): a bigger
  Content-Length is refused up front and the stream stops, deleting the partial file,
  as soon as it passes the limit.
- The body goes to `dest + ".part"` and is renamed only when complete. This file
  writes with stdlib because it cannot import `sentinel.core.io` (documented
  exemption in tests/test_safe_writer.py).

Usage: python setup_download.py URL DEST MAXBYTES HOST [HOST...]
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 1024 * 1024
TIMEOUT = 60


def host_allowed(url: str, hosts: list[str]) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        has_userinfo = "@" in parsed.netloc
    except ValueError:
        return False
    if parsed.scheme != "https" or not host or has_userinfo:
        return False
    for entry in hosts:
        entry = entry.lower()
        if entry.startswith("."):
            if host.endswith(entry) and len(host) > len(entry):
                return True
        elif host == entry:
            return True
    return False


class _FencedRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts: list[str]) -> None:
        self._hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not host_allowed(newurl, self._hosts):
            raise urllib.error.URLError(f"redirect to a host outside the allowed list: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, hosts: list[str]):
    opener = urllib.request.build_opener(_FencedRedirects(hosts))
    return opener.open(url, timeout=TIMEOUT)


class _TooBig(Exception):
    pass


def main(argv: list[str]) -> int:
    if len(argv) < 4 or not argv[2].isdigit():
        print("usage: setup_download.py URL DEST MAXBYTES HOST [HOST...]", file=sys.stderr)
        return 2
    url, dest, limit, hosts = argv[0], argv[1], int(argv[2]), list(argv[3:])
    if not host_allowed(url, hosts):
        print(f"refusing {url}: only https on {', '.join(hosts)}", file=sys.stderr)
        return 2
    part = dest + ".part"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with _open(url, hosts) as response, open(part, "wb") as handle:
            declared = getattr(response, "headers", None) and response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > limit:
                raise _TooBig(f"Content-Length {declared} is over the expected {limit} bytes")
            received = 0
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > limit:
                    raise _TooBig(f"more than the expected {limit} bytes")
                handle.write(chunk)
        os.replace(part, dest)
    except (OSError, urllib.error.URLError, _TooBig) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        try:
            os.remove(part)
        except OSError:
            pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
