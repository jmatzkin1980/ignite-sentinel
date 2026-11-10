"""IMP-270: `.docx` ingestion in three layers, and typed errors for unreadable sources.

The `.docx` fixture is built here with `zipfile`, so it is synthetic and stable: no
real client document in the repo. The extraction is compared against a golden.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.cli import main
from sentinel.source_formats import DocxError, SourceFormatError, read_docx, read_source, target_suffix
from sentinel.sync import sync_change

GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "docx" / "synthetic_extraction.md"
UPDATE = os.environ.get("SENTINEL_UPDATE_GOLDEN") == "1"

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
NS = (W + ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
      ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _p(text: str, style: str | None = None, num: int | None = None) -> str:
    props = ""
    if style:
        props += f'<w:pStyle w:val="{style}"/>'
    if num is not None:
        props += f'<w:numPr><w:ilvl w:val="{num}"/><w:numId w:val="1"/></w:numPr>'
    ppr = f"<w:pPr>{props}</w:pPr>" if props else ""
    return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document {NS}><w:body>
{_p("Portal de Facturación", "Ttulo1")}
{_p("Los usuarios de finanzas revisan las facturas mensuales antes de aprobarlas.")}
{_p("Alcance", "Ttulo2")}
{_p("Alta de facturas", num=0)}
{_p("Aprobación con doble firma", num=0)}
{_p("Solo el gerente de área", num=1)}
<w:p><w:r><w:t xml:space="preserve">El plazo de aprobación es </w:t></w:r><w:commentRangeStart w:id="0"/><w:r><w:t>de 48 horas</w:t></w:r><w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r><w:r><w:t>.</w:t></w:r></w:p>
<w:tbl>
<w:tr><w:tc>{_p("Rol")}</w:tc><w:tc>{_p("Permiso")}</w:tc></w:tr>
<w:tr><w:tc>{_p("Analista")}</w:tc><w:tc>{_p("Carga | edita")}</w:tc></w:tr>
<w:tr><w:tc>{_p("Gerente")}</w:tc><w:tc>{_p("Aprueba")}{_p("Rechaza")}</w:tc></w:tr>
</w:tbl>
<w:p><w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rId5"/></a:graphicData></a:graphic></w:drawing></w:r></w:p>
<w:sectPr/>
</w:body></w:document>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:styles {W}>
<w:style w:type="paragraph" w:styleId="Ttulo1"><w:name w:val="heading 1"/></w:style>
<w:style w:type="paragraph" w:styleId="Ttulo2"><w:name w:val="heading 2"/></w:style>
</w:styles>"""

COMMENTS = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:comments {W}>
<w:comment w:id="0" w:author="Ana Pérez" w:date="2026-10-01T10:00:00Z"><w:p><w:r><w:t>¿Hábiles o corridas?</w:t></w:r></w:p></w:comment>
</w:comments>"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
</Relationships>"""


def build_docx(path: Path, *, extra_media: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", DOCUMENT)
        archive.writestr("word/styles.xml", STYLES)
        archive.writestr("word/comments.xml", COMMENTS)
        archive.writestr("word/_rels/document.xml.rels", RELS)
        archive.writestr("word/media/image1.png", PNG)
        if extra_media:
            archive.writestr("media/image1.png", PNG + b"x")  # same name under media/: kept apart
    return path


class ReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_synthetic_docx_matches_golden(self) -> None:
        docx = build_docx(self.temp / "synthetic.docx")
        extraction = read_docx(docx, extracted_at="2026-11-09")
        if UPDATE:
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(extraction.text, encoding="utf-8", newline="\n")
        self.assertTrue(GOLDEN.exists(), f"missing golden {GOLDEN}; create it with SENTINEL_UPDATE_GOLDEN=1")
        expected = GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n")
        # The zip carries timestamps, so its sha256 changes per build: compare the rest.
        strip = lambda text: "\n".join(line for line in text.splitlines() if not line.startswith("> Extracted from"))
        self.assertEqual(strip(extraction.text), strip(expected))
        self.assertIn("sha256 `", extraction.text.splitlines()[0])

    def test_three_layers(self) -> None:
        extraction = read_docx(build_docx(self.temp / "synthetic.docx"), extracted_at="2026-11-09")
        text = extraction.text
        self.assertIn("# Portal de Facturación", text)
        self.assertIn("## Alcance", text)
        self.assertIn("- Alta de facturas\n- Aprobación con doble firma\n  - Solo el gerente de área", text)
        self.assertIn("| Analista | Carga \\| edita |", text)
        self.assertIn("| Gerente | Aprueba<br>Rechaza |", text)
        self.assertIn('`C-0` Ana Pérez, 2026-10-01: "¿Hábiles o corridas?" on "de 48 horas"', text)
        self.assertIn("![image1.png](synthetic_media/image1.png)", text)
        self.assertEqual(sorted(name for name, _ in extraction.images), ["image1.png", "media-image1.png"])
        self.assertEqual(extraction.comments, 1)

    def test_corrupt_docx_is_a_typed_error(self) -> None:
        bad = self.temp / "broken.docx"
        bad.write_bytes(b"PK\x03\x04 not really a zip")
        with self.assertRaises(DocxError):
            read_source(bad)
        truncated = self.temp / "truncated.docx"
        truncated.write_bytes(build_docx(self.temp / "ok.docx").read_bytes()[:200])
        with self.assertRaises(DocxError):
            read_source(truncated)
        no_document = self.temp / "empty.docx"
        with zipfile.ZipFile(no_document, "w") as archive:
            archive.writestr("other.xml", "<x/>")
        with self.assertRaisesRegex(DocxError, "word/document.xml"):
            read_source(no_document)
        self.assertTrue(issubclass(DocxError, SourceFormatError))

    def test_binary_source_is_a_typed_error_and_unknown_text_warns(self) -> None:
        pdf = self.temp / "spec.pdf"
        pdf.write_bytes(b"%PDF-1.7\n\xff\xfe\x00binary")
        with self.assertRaisesRegex(SourceFormatError, "not UTF-8 text"):
            read_source(pdf)
        csv = self.temp / "data.csv"
        csv.write_text("a,b\n1,2\n", encoding="utf-8")
        self.assertIn("unknown extension .csv", read_source(csv).warning)
        self.assertIsNone(read_source(self._md()).warning)
        self.assertEqual(target_suffix(Path("x.docx")), ".md")
        self.assertEqual(target_suffix(Path("x.HTML")), ".html")

    def _md(self) -> Path:
        path = self.temp / "note.md"
        path.write_text("# Note\n", encoding="utf-8")
        return path


class FlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_cwd = Path.cwd()
        self.temp = Path(tempfile.mkdtemp())
        os.chdir(self.temp)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["init", "DOC"]), 0)
        self.ws = self.temp / "workspaces" / "DOC"

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp, ignore_errors=True)

    def _manifest(self) -> dict:
        return json.loads((self.ws / "00_raw" / "source_manifest.json").read_text(encoding="utf-8"))

    def test_ingest_docx_stores_markdown_media_and_an_f_row(self) -> None:
        docx = build_docx(self.temp / "brief-cliente.docx")
        original = docx.read_bytes()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["ingest", "DOC", "--source", str(docx)]), 0)
        result = json.loads(out.getvalue()[out.getvalue().index("{\n  \"raw_id\""):])
        self.assertEqual(result["source_format"]["kind"], "docx")
        self.assertEqual(result["source_format"]["images"], 2)
        raw = (self.ws / "00_raw" / "brief-cliente.md").read_text(encoding="utf-8")
        self.assertIn("## Alcance", raw)
        self.assertTrue((self.ws / "00_raw" / "brief-cliente_media" / "image1.png").exists())
        self.assertEqual(docx.read_bytes(), original)  # the original is only read
        rows = self._manifest()["registry"]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["paths"][0].endswith("brief-cliente.docx"))

    def test_docx_secrets_are_redacted_like_any_source(self) -> None:
        fake_key = "AKIA" + "IOSFODNN7EXAMPLE"  # split so the doctor's tracked-files scan stays clean
        secret_doc = DOCUMENT.replace("Alta de facturas", f"Alta de facturas con clave {fake_key}")
        path = self.temp / "secreto.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", secret_doc)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["ingest", "DOC", "--source", str(path)]), 0)
        raw = (self.ws / "00_raw" / "secreto.md").read_text(encoding="utf-8")
        self.assertNotIn(fake_key, raw)

    def test_sync_docx_and_corrupt_docx_opens_no_row(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["ingest", "DOC", "--source", str(self._seed())]), 0)
        (self.temp / "01_meetings").mkdir()
        meeting = build_docx(self.temp / "01_meetings" / "acta.docx")
        result = sync_change("DOC", meeting, "acta en word")
        self.assertEqual(result["source_format"]["comments"], 1)
        self.assertTrue(Path(result["path"]).name.endswith(".md"))
        rows_before = len(self._manifest()["registry"])

        broken = self.temp / "01_meetings" / "rota.docx"
        broken.write_bytes(b"not a zip")
        with self.assertRaises(DocxError):
            sync_change("DOC", broken, "rota")
        self.assertEqual(len(self._manifest()["registry"]), rows_before)  # no open row left behind
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["sync", "DOC", "--source", str(broken)]), 1)
        self.assertIn("not a valid .docx", err.getvalue())

    def _seed(self) -> Path:
        path = self.temp / "billing.md"
        path.write_text("# Billing Portal\n\nFinance users review invoices before approval.\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
