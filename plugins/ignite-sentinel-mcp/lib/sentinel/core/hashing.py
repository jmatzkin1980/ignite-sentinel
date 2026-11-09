"""Content hashes that ignore the line ending (IMP-291).

Sentinel writes with `os.linesep`, and git or an editor can flip a file between
CRLF and LF without changing its content. Every fingerprint that answers "did
this file change?" (drift, the source manifest, the out-of-CLI-edit check) is
taken over the content with CRLF folded to LF. Hashes recorded before IMP-291
were taken over raw bytes; `hash_matches` accepts either, so upgrading does not
flag every existing workspace.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def file_content_hash(path: Path) -> str:
    return content_sha256(path.read_bytes())


def hash_matches(recorded: object, data: bytes) -> bool:
    """True when `recorded` is this content's hash, line-ending aware or raw (pre-IMP-291)."""
    if not isinstance(recorded, str) or not recorded:
        return False
    return recorded == content_sha256(data) or recorded == hashlib.sha256(data).hexdigest()
