"""IMP-270: source formats, with `.docx` read in three layers.

Text sources (`.md`, `.txt`, `.html`, `.htm`) are read as UTF-8, as before. A
`.docx` is read with the standard library only (`zipfile` + `xml.etree`), in three
layers:

1. **Text** with headings, lists and tables, as Markdown. Images appear inline as
   links to the extracted copies.
2. **Images** from `word/media/` and `media/`, copied next to the Markdown in a
   `<stem>_media/` folder.
3. **Comments** with author, date and the text they are anchored to.

The extraction is dated and carries the sha256 of the original, which is only ever
read. It then goes through the same redaction as any other source (IMP-285) and is
registered as an F-NN row (IMP-250a) by the command that crosses it.

A file that is neither UTF-8 text nor a readable `.docx` raises a typed
`SourceFormatError` instead of a bare `UnicodeDecodeError`. A UTF-8 file with an
unknown extension is still stored as Markdown, but the command says so.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

TEXT_SUFFIXES = (".md", ".txt", ".html", ".htm")
DOCX_SUFFIX = ".docx"
SUPPORTED_SUFFIXES = TEXT_SUFFIXES + (DOCX_SUFFIX,)
MEDIA_PREFIXES = ("word/media/", "media/")
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # a .docx bigger than this once unzipped is refused
MAX_ENTRIES = 5000

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_HEADING_NAME = re.compile(r"^(?:heading|t[ií]tulo|encabezado)\s*(\d)$", re.I)
_TITLE_NAME = re.compile(r"^(?:title|t[ií]tulo)$", re.I)


class SourceFormatError(ValueError):
    """A source Sentinel cannot read: not UTF-8 text and not a readable `.docx`."""


class DocxError(SourceFormatError):
    """A `.docx` that is corrupt, truncated or not a Word document."""


@dataclass
class SourceText:
    text: str
    kind: str  # "text" or "docx"
    warning: str | None = None
    images: list[tuple[str, bytes]] = field(default_factory=list)  # (file name in <stem>_media/, bytes)
    comments: int = 0


def target_suffix(source: Path) -> str:
    """The suffix of the workspace copy: known text keeps its own, the rest is Markdown."""
    suffix = source.suffix.lower()
    return suffix if suffix in TEXT_SUFFIXES else ".md"


def media_dir_name(stem: str) -> str:
    return f"{stem}_media"


def read_source(source: Path, *, extracted_at: str | None = None, media_stem: str | None = None) -> SourceText:
    """Read a source as text. `.docx` goes through the three-layer reader."""
    if source.suffix.lower() == DOCX_SUFFIX:
        return read_docx(source, extracted_at=extracted_at, media_stem=media_stem)
    data = source.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceFormatError(
            f"{source.name}: not UTF-8 text and not a supported document "
            f"(supported: {', '.join(SUPPORTED_SUFFIXES)}). Convert it to Markdown first."
        ) from exc
    warning = None
    if source.suffix.lower() not in TEXT_SUFFIXES:
        warning = f"{source.name}: unknown extension {source.suffix or '(none)'}; stored as Markdown."
    return SourceText(text=text, kind="text", warning=warning)


# --- .docx ---------------------------------------------------------------------


def _parse(archive: zipfile.ZipFile, name: str, source: Path, required: bool = False) -> ET.Element | None:
    try:
        data = archive.read(name)
    except KeyError:
        if required:
            raise DocxError(f"{source.name}: not a Word document ({name} is missing).") from None
        return None
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise DocxError(f"{source.name}: {name} is not valid XML ({exc}).") from exc


def _heading_levels(styles: ET.Element | None) -> dict[str, int]:
    levels: dict[str, int] = {}
    if styles is None:
        return levels
    for style in styles.iter(f"{_W}style"):
        style_id = style.get(f"{_W}styleId", "")
        name_el = style.find(f"{_W}name")
        name = (name_el.get(f"{_W}val", "") if name_el is not None else "").strip()
        match = _HEADING_NAME.match(name)
        if match:
            levels[style_id] = max(1, min(6, int(match.group(1))))
        elif _TITLE_NAME.match(name):
            levels[style_id] = 1
    return levels


def _relationships(archive: zipfile.ZipFile, source: Path) -> dict[str, str]:
    rels = _parse(archive, "word/_rels/document.xml.rels", source)
    if rels is None:
        return {}
    return {rel.get("Id", ""): posixpath.normpath(posixpath.join("word", rel.get("Target", "")))
            for rel in rels.iter(f"{_REL}Relationship")}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


class _Walker:
    """Walks document.xml in order, collecting Markdown and comment anchors."""

    def __init__(self, levels: dict[str, int], rels: dict[str, str], media_names: dict[str, str], media_dir: str):
        self.levels = levels
        self.rels = rels
        self.media_names = media_names
        self.media_dir = media_dir
        self.active: set[str] = set()
        self.anchors: dict[str, list[str]] = {}

    def _emit(self, parts: list[str], text: str) -> None:
        parts.append(text)
        for comment_id in self.active:
            self.anchors.setdefault(comment_id, []).append(text)

    def paragraph_text(self, paragraph: ET.Element) -> str:
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag
            if tag == f"{_W}t" and node.text:
                self._emit(parts, node.text)
            elif tag == f"{_W}tab":
                self._emit(parts, "\t")
            elif tag in (f"{_W}br", f"{_W}cr"):
                self._emit(parts, " ")
            elif tag == f"{_W}commentRangeStart":
                self.active.add(node.get(f"{_W}id", ""))
            elif tag == f"{_W}commentRangeEnd":
                self.active.discard(node.get(f"{_W}id", ""))
            elif tag == f"{_A}blip":
                target = self.rels.get(node.get(f"{_R}embed", ""), "")
                name = self.media_names.get(target)
                if name:
                    parts.append(f"![{name}]({self.media_dir}/{name})")
        return "".join(parts).strip()

    def paragraph(self, paragraph: ET.Element) -> str:
        text = self.paragraph_text(paragraph)
        if not text:
            return ""
        props = paragraph.find(f"{_W}pPr")
        style = props.find(f"{_W}pStyle") if props is not None else None
        level = self.levels.get(style.get(f"{_W}val", "")) if style is not None else None
        if level:
            return f"{'#' * level} {text}"
        numbering = props.find(f"{_W}numPr") if props is not None else None
        if numbering is not None:
            ilvl = numbering.find(f"{_W}ilvl")
            depth = int(ilvl.get(f"{_W}val", "0")) if ilvl is not None else 0
            return f"{'  ' * depth}- {text}"
        return text

    def table(self, table: ET.Element) -> str:
        rows: list[list[str]] = []
        for row in table.findall(f"{_W}tr"):
            cells = []
            for cell in row.findall(f"{_W}tc"):
                texts = [self.paragraph_text(p) for p in cell.iter(f"{_W}p")]
                cells.append(_cell("<br>".join(t for t in texts if t)))
            rows.append(cells)
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
        return "\n".join(lines)

    def blocks(self, container: ET.Element) -> list[str]:
        out: list[str] = []
        for child in container:
            if child.tag == f"{_W}p":
                block = self.paragraph(child)
            elif child.tag == f"{_W}tbl":
                block = self.table(child)
            elif child.tag == f"{_W}sdt":
                content = child.find(f"{_W}sdtContent")
                block = "\n\n".join(self.blocks(content)) if content is not None else ""
            else:
                continue
            if block:
                out.append(block)
        return out


def _join_list_runs(blocks: list[str]) -> str:
    """Blank line between blocks, except between consecutive list items."""
    text = ""
    for index, block in enumerate(blocks):
        if index:
            both_items = blocks[index - 1].lstrip().startswith("- ") and block.lstrip().startswith("- ")
            text += "\n" if both_items else "\n\n"
        text += block
    return text


def read_docx(source: Path, *, extracted_at: str | None = None, media_stem: str | None = None) -> SourceText:
    data = source.read_bytes()
    digest = sha256(data).hexdigest()
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocxError(f"{source.name}: not a valid .docx (not a readable zip archive).") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES or sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise DocxError(f"{source.name}: refused, too large once unzipped.")
        try:
            document = _parse(archive, "word/document.xml", source, required=True)
            levels = _heading_levels(_parse(archive, "word/styles.xml", source))
            rels = _relationships(archive, source)
            comments_xml = _parse(archive, "word/comments.xml", source)
            images: list[tuple[str, bytes]] = []
            media_names: dict[str, str] = {}
            used: set[str] = set()
            # word/media/ first: it is where Word keeps what the body embeds.
            rank = lambda item: (0 if item.filename.startswith("word/media/") else 1, item.filename)
            for info in sorted(infos, key=rank):
                name = info.filename
                if info.is_dir() or not name.startswith(MEDIA_PREFIXES):
                    continue
                base = posixpath.basename(name)
                if not base:
                    continue
                out_name = base if base not in used else f"{name.split('/')[0]}-{base}"
                used.add(out_name)
                media_names[posixpath.normpath(name)] = out_name
                images.append((out_name, archive.read(name)))
        except (zipfile.BadZipFile, EOFError, OSError) as exc:  # truncated or damaged entries
            raise DocxError(f"{source.name}: damaged .docx ({exc}).") from exc

    media_dir = media_dir_name(media_stem or source.stem)
    walker = _Walker(levels, rels, media_names, media_dir)
    body = document.find(f"{_W}body")
    blocks = walker.blocks(body) if body is not None else []

    comments: list[str] = []
    if comments_xml is not None:
        for comment in comments_xml.iter(f"{_W}comment"):
            comment_id = comment.get(f"{_W}id", "")
            author = comment.get(f"{_W}author", "") or "unknown"
            date = (comment.get(f"{_W}date", "") or "")[:10] or "undated"
            text = " ".join(t.text or "" for t in comment.iter(f"{_W}t")).strip()
            anchor = "".join(walker.anchors.get(comment_id, [])).strip()
            on = f' on "{anchor}"' if anchor else " (no anchor)"
            comments.append(f'- `C-{comment_id}` {author}, {date}: "{text}"{on}')

    when = extracted_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"> Extracted from `{source.name}` (sha256 `{digest}`) on {when} by Ignite Sentinel (IMP-270). "
        "The original is only read.",
        "",
        _join_list_runs(blocks) if blocks else "_No text in the document body._",
        "",
        "## Comments (extracted)",
        "",
        "\n".join(comments) if comments else "- None.",
        "",
        "## Images (extracted)",
        "",
        "\n".join(f"- `{original}` -> `{media_dir}/{name}`" for original, name in media_names.items()) if media_names else "- None.",
        "",
    ]
    return SourceText(text="\n".join(lines), kind="docx", images=images, comments=len(comments))
