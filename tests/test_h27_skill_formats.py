"""IMP-408 (H27 inc 2): the formats the skills teach are the ones the real parsers read.

Every `sentinel-example kind=K [lang=L]` fence in a canonical skill is parsed here by the runtime
parser of its kind. A skill example that drifts from its parser fails this file instead of reaching
the BA as a rejected answer.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IDS_SCOPE_ANSWER  # noqa: E402

from sentinel.change_requirements import parse_delta, parse_surfaces
from sentinel.compilers.change_spec_doc import BLOCKS, COPY, NO_DATA
from sentinel.changes import parse_border
from sentinel.assumptions import validate_assumptions
from sentinel.change_assumptions import SUPUESTO_STATUSES
from sentinel.cross_review import rules as cross_rules
from sentinel.crosses.claims import CITATION_RULES, parse_claims
from sentinel.crosses.record import _gap_texts
from sentinel.ears import classify_ears
from sentinel.extraction.consolidation import unanchored_sentences
from sentinel.extraction.inventory import element_lines, parse_request_elements
from sentinel.extraction.lines import parse_line_ranges
from sentinel.extraction.proposals import READINGS, SECTION_ALIASES, SECTION_KEYS, TREATMENTS, TYPES, parse_proposals
from sentinel.extraction.verify import parse_verify_results
from sentinel.gap_resolution import _gap_block, apply_gap_responses, ears_statements, option_choice
from sentinel.gaps import gap_option_labels, parse_gap_responses
from sentinel.harvest import parse_harvest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / ".codex" / "skills"

EXAMPLE_OWNERS = {
    "gap-response": "sentinel-gap-response",
    "harvest": "sentinel-brownfield-harvest",
    "cross-claims": "sentinel-discovery",
    "extraction-proposals": "sentinel-discovery",
    "verify-result": "sentinel-discovery",
    "coherence-crosses": "sentinel-self-review",
    "change-assumptions": "sentinel-assume",
    "gap-assumption": "sentinel-gap-response",
    "consolidation": "sentinel-project-brief",
    "change-functionality": "sentinel-specs",
}

FENCE = re.compile(
    r"^```sentinel-example kind=(?P<kind>[a-z-]+)(?: lang=(?P<lang>es|en))?\n(?P<body>.*?)^```[ \t]*$",
    re.M | re.S,
)
_BORDER_LINE = re.compile(r"^\s+[-*]?\s*\S+ \| \S.* \| \S")


def skill_text(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8-sig")


def examples(skill: str, kind: str | None = None) -> list[tuple[str, str, str]]:
    found = [(m.group("kind"), m.group("lang") or "es", m.group("body")) for m in FENCE.finditer(skill_text(skill))]
    return [item for item in found if kind is None or item[0] == kind]


def examples_of(kind: str) -> list[tuple[str, str]]:
    return [(lang, body) for _, lang, body in examples(EXAMPLE_OWNERS[kind], kind)]


def border_of(body: str, lang: str) -> list[dict]:
    """The border of the first GAP-SCOPE block of the example; a bad line is a failed check, not an InputError."""
    block = _gap_block(body, "GAP-SCOPE")
    try:
        return parse_border(block, "", lang)
    except Exception as error:  # InputError: the real parser refuses the example
        raise AssertionError(f"the border of the example is refused: {error}") from error


def check_gap_response(body: str, lang: str) -> None:
    responses = parse_gap_responses(body)
    assert responses, "no `### GAP-` block parsed"
    dis_claim = {
        "text": "x",
        "citations": [
            {"side": "pedido", "source_id": "F-01", "quote": "q", "line": 1},
            {"side": "diseno", "source_id": "F-03", "quote": "q", "line": 1},
        ],
    }
    rows = []
    for gap_id in responses:
        question = _gap_texts("divergencia", dis_claim, lang == "es")[1] if gap_id.startswith("GAP-DIS-") else "x"
        rows.append({"id": gap_id, "lens": "product", "severity": "high", "status": "OPEN", "question": question, "description": "x"})
    for response in responses.values():
        if str(response.get("closure", "")).strip().lower().replace(" ", "_") == "by_baseline":
            response["baseline_checked"] = True  # what the change path sets when the citation validates
    result = apply_gap_responses(rows, responses, language=lang)
    closed = sorted(gap["id"] for gap in result["closed"])  # type: ignore[union-attr]
    assert closed == sorted(responses), f"closed {closed}, example has {sorted(responses)}; findings: {result['findings']}"
    assert result["findings"] == [], result["findings"]

    border: list[dict] = []
    for gap_id, response in responses.items():
        block = _gap_block(body, gap_id)
        if re.search(r"^[ \t]*-[ \t]*Borde[ \t]*:", block, re.M | re.I):
            border = border_of(body, lang)
            expected = sum(1 for line in block.splitlines() if _BORDER_LINE.match(line))
            assert len(border) == expected, f"{gap_id}: {len(border)} surfaces for {expected} lines"
    for gap_id, response in responses.items():
        if ears_statements(response["answer"]):
            assert parse_delta(response.get("delta", "")) is not None, f"{gap_id}: no valid Delta"
            valid, unknown = parse_surfaces(response.get("surface", ""), border)
            assert valid and not unknown, f"{gap_id}: surfaces {valid} / unknown {unknown}"
        if response.get("option"):
            row = next(r for r in rows if r["id"] == gap_id)
            choice, note = option_choice(gap_id, response, gap_option_labels(row), lang)
            assert choice and note is None, f"{gap_id}: option {response['option']!r} gives {choice!r}, {note}"


def check_cross(body: str, lang: str) -> None:
    claims, errors = parse_claims(body, lang)
    assert errors == [], errors
    for claim in claims:
        low_p, high_p, low_d, high_d = CITATION_RULES[claim["tag"]]
        for side, low, high in (("pedido", low_p, high_p), ("diseno", low_d, high_d)):
            count = sum(1 for cite in claim["citations"] if cite["side"] == side)
            assert count >= low and (high is None or count <= high), f"{claim['tag']}: {count} {side} quotes"


def check_proposals(body: str) -> None:
    blocks, warnings = parse_proposals(body)
    assert blocks and warnings == [], warnings
    for element_id, block in blocks.items():
        treatment = TREATMENTS.get(block["treatment"].lower())
        assert treatment, f"{element_id}: treatment {block['treatment']!r}"
        assert parse_line_ranges(block["lines"]) is not None, f"{element_id}: lines {block['lines']!r}"
        assert block["reading"] == "" or block["reading"].lower() in READINGS, f"{element_id}: reading"
        assert block["errors"] == [], block["errors"]
        assert block["type"] in ("", "aplica", "extension"), f"{element_id}: Tipo {block['type']!r}"
        for cited in block["decisions"]:
            assert cited.startswith("GAP-"), f"{element_id}: Decisión {cited!r} is not a GAP id"
        if treatment in ("requisito", "seccion"):
            assert len(block["quote"]) >= 20, f"{element_id}: quote shorter than 20 characters"
        if treatment == "requisito":
            assert block["statements"], f"{element_id}: no statement"
            for statement in block["statements"]:
                assert classify_ears(statement["text"]), f"{element_id}: not EARS: {statement['text']}"
                assert parse_delta(statement["delta"]) is not None, f"{element_id}: no valid Delta"
                assert statement["surface"].strip(), f"{element_id}: no Surface"
        elif treatment == "seccion":
            key = block["section"].strip().lower()
            assert key in SECTION_KEYS or key in SECTION_ALIASES, f"{element_id}: section {key!r}"
        else:
            assert block["reason"].strip(), f"{element_id}: a discard needs its reason"


def check_verify(body: str) -> None:
    results, unknown = parse_verify_results(body)
    assert results and unknown == [], (results, unknown)
    for element_id, result in results.items():
        if result["verdict"] == "difiere":
            assert result["note"], f"{element_id}: a difiere without a note"


def check_harvest(body: str) -> None:
    parsed = parse_harvest(body)
    assert parsed["errors"] == [], parsed["errors"]
    assert all(parsed["coverage"].values()), parsed["coverage"]


REQUEST = REPO / "tests" / "fixtures" / "change_crosses" / "pedido_contradiccion.md"


def _flat(text: str) -> str:
    return " ".join(str(text).split())


def check_coherence(body: str) -> None:
    """IMP-410: the example of the lens crosses is what `/self-review --crosses --change` validates."""
    payload = json.loads(body)
    request = _flat(REQUEST.read_text(encoding="utf-8"))
    border = []
    for line in IDS_SCOPE_ANSWER.splitlines():
        parts = [part.strip() for part in line.strip().lstrip("-").split("|")]
        if len(parts) >= 3 and parts[0] in ("nuevo", "adyacente", "preservado"):
            border.append(f"{parts[1]} — {parts[2]}")
    catalog = cross_rules()
    assert payload["crosses"], "no crosses"
    for cross in payload["crosses"]:
        rule = catalog.get(cross["rule"])
        assert rule is not None, f"unknown rule {cross['rule']}"
        assert cross["kind"] in rule["kinds"], f"{cross['rule']} takes {rule['kinds']}"
        assert any(cross["a"]["place"] == p or cross["a"]["place"].startswith(p + ".") for p in rule["from"]), "a.place"
        side = cross["b"]["place"] if cross["kind"] == "conflict" else cross["missing_in"]
        assert any(side == p or side.startswith(p + ".") for p in rule["to"]), "b.place or missing_in"
        assert str(cross["finding"]).strip(), "empty finding"
        assert str(cross["question"]).strip().endswith("?"), "the question must end with ?"
        quotes = [cross["a"]["quote"]] + ([cross["b"]["quote"]] if cross["kind"] == "conflict" else [])
        for quote in quotes:
            assert _flat(quote) in request or _flat(quote) in border, f"quote not in the request or the border: {quote!r}"


def check_change_assumptions(body: str) -> None:
    """IMP-412: the example of `/assume --change` is what the real validator accepts, and it closes a question."""
    payload = json.loads(body)
    validate_assumptions(payload, REQUEST.read_text(encoding="utf-8"))
    for item in payload["assumptions"]:
        assert str(item.get("closes_gap", "")).startswith("GAP-"), f"{item.get('id')}: closes_gap"
        assert str(item.get("validate_with", "")).strip(), f"{item.get('id')}: validate_with"


def check_gap_assumption(body: str) -> None:
    """IMP-412: a `supuesto` answer carries `Valida`, a substantive answer and a literal quote of the request."""
    responses = parse_gap_responses(body)
    assert responses, "no `### GAP-` block parsed"
    request = _flat(REQUEST.read_text(encoding="utf-8"))
    for gap_id, response in responses.items():
        status = str(response.get("decision_status", "")).strip().lower().replace(" ", "_")
        assert status in SUPUESTO_STATUSES, f"{gap_id}: status {status!r} is not an assumption"
        assert str(response.get("validates", "")).strip(), f"{gap_id}: no Valida"
        assert len(str(response.get("answer", "")).split()) >= 5, f"{gap_id}: answer is not substantive"
        quotes = re.findall(r"[\"“]([^\"”]+)[\"”]", str(response.get("evidence", "")))
        assert quotes, f"{gap_id}: no quoted evidence"
        for quote in quotes:
            assert _flat(quote) in request, f"{gap_id}: quote not in the request: {quote!r}"


CONSOLIDATION_ANSWER = "Rige el diseño: el umbral de aprobación es 1.000.000."


def check_consolidation(body: str) -> None:
    """IMP-414: the example of `/extract --consolidate` is what the runtime parser reads and its anchoring accepts."""
    blocks, warnings = parse_proposals(body)
    assert blocks and warnings == [], warnings
    request = REQUEST.read_text(encoding="utf-8")
    found = {e["id"]: e for e in parse_request_elements(request, "F-01", "pedido.md")}
    lines = request.splitlines()
    for element_id, block in blocks.items():
        assert block["decisions"], f"{element_id}: no Decisión"
        for cited in block["decisions"]:
            assert cited.startswith("GAP-"), f"{element_id}: Decisión {cited!r} is not a GAP id"
        assert parse_line_ranges(block["lines"]) is not None, f"{element_id}: lines {block['lines']!r}"
        text = "\n".join(block["summary_lines"]).strip()
        assert text, f"{element_id}: no Texto"
        assert block["type"] == "" or block["type"].lower() in TYPES, f"{element_id}: Tipo {block['type']!r}"
        if TYPES.get(block["type"].lower(), "aplica") == "aplica":
            assert element_id in found, f"{element_id} is not an element of the sample request"
            first, last = element_lines(found[element_id])
            element_text = "\n".join(lines[first - 1:last]) + "\n" + element_id
            stale = unanchored_sentences(text, element_text, [CONSOLIDATION_ANSWER])
            assert stale == [], f"{element_id}: not in the element nor in the answer: {stale}"


def check_change_functionality(body: str, lang: str) -> None:
    """IMP-416: the functionality section of the example has the eight blocks of the writer, in order, and its table header."""
    assert re.search(r"(?m)^## FUN-\d+ ", body), "no `## FUN-` section"
    start = body.index("## FUN-")
    end = body.find("\n## ", start + 1)
    section = body[start:end if end >= 0 else len(body)]
    titles = re.findall(r"(?m)^### (.+?)\s*$", section)
    assert titles == BLOCKS[lang], f"blocks {titles}, the writer's are {BLOCKS[lang]}"
    parts = re.split(r"(?m)^### .+$", section)[1:]
    for title, content in zip(titles, parts):
        assert content.strip(), f"{title}: empty block (it says `_{NO_DATA[lang]}_` when nothing is registered)"
    copy = COPY[lang]
    trace = re.search(rf"(?m)^{re.escape(copy['trace'])}\s*$", body)
    if trace:
        header = "| " + " | ".join(copy["trace_header"]) + " |"
        assert header in body[trace.end():], f"traceability header is not {header!r}"


class SkillFormatTests(unittest.TestCase):
    def test_every_kind_has_an_example_in_its_owner(self):
        for kind, skill in EXAMPLE_OWNERS.items():
            self.assertTrue(examples(skill, kind), f"{skill} has no sentinel-example kind={kind}")
        for skill_dir in sorted(SKILLS.iterdir()):
            if not (skill_dir / "SKILL.md").exists():
                continue
            for kind, _, _ in examples(skill_dir.name):
                self.assertIn(kind, EXAMPLE_OWNERS, f"{skill_dir.name}: unknown example kind {kind}")
                self.assertEqual(EXAMPLE_OWNERS[kind], skill_dir.name, f"kind {kind} belongs to {EXAMPLE_OWNERS[kind]}")
        for skill in sorted(set(EXAMPLE_OWNERS.values())):
            self.assertRegex(skill_text(skill), r"(?m)^## Formato\s*$", f"{skill} lacks `## Formato`")

    def test_gap_response_examples_parse_and_close(self):
        found = examples_of("gap-response")
        self.assertEqual({"es", "en"}, {lang for lang, _ in found})
        for lang, body in found:
            with self.subTest(lang=lang):
                check_gap_response(body, lang)
        es_body = next(body for lang, body in found if lang == "es")
        for label in ("Opción:", "Redactado por:", "Borde:", "Delta:", "Superficie:", "Motivo de cierre:"):
            self.assertIn(label, es_body)

    def test_harvest_example_parses(self):
        for _, body in examples_of("harvest"):
            check_harvest(body)

    def test_cross_examples_parse(self):
        found = examples_of("cross-claims")
        for lang, body in found:
            check_cross(body, lang)
        tags = {claim["tag"] for lang, body in found for claim in parse_claims(body, lang)[0]}
        self.assertEqual(
            {"respaldado", "sin_respaldo", "solo_en_diseno", "divergencia", "contradiccion", "sin_hallazgos"}, tags
        )
        self.assertEqual({"es", "en"}, {lang for lang, _ in found})

    def test_proposal_examples_parse(self):
        found = examples_of("extraction-proposals")
        for _, body in found:
            check_proposals(body)
        treatments = {block["treatment"].lower() for _, body in found for block in parse_proposals(body)[0].values()}
        self.assertEqual({"requisito", "seccion", "descarte"}, treatments)

    def test_verify_example_parses(self):
        found = examples_of("verify-result")
        for _, body in found:
            check_verify(body)
        verdicts = {r["verdict"] for _, body in found for r in parse_verify_results(body)[0].values()}
        self.assertEqual({"igual", "difiere"}, verdicts)

    def test_coherence_examples_parse(self):
        found = examples_of("coherence-crosses")
        self.assertTrue(found)
        kinds = set()
        for _, body in found:
            check_coherence(body)
            kinds |= {cross["kind"] for cross in json.loads(body)["crosses"]}
        self.assertEqual({"missing", "conflict"}, kinds)

    def test_a_stale_coherence_example_fails(self):
        _, body = examples_of("coherence-crosses")[0]
        stale = body.replace('"rule": "cross_d_design_technical"', '"rule": "cross_z"', 1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(AssertionError):
            check_coherence(stale)

    def test_sync_skill_teaches_loading_by_role(self):
        text = skill_text("sentinel-sync")
        self.assertRegex(text, r"(?m)^## Loading a document by role")
        for needle in ("--role linea_de_base", "`diseno_nuevo`", "`plan_previo`", "`pedido`", "--id F-NN --role", "--no-baseline", "GAP-VER"):
            self.assertIn(needle, text)

    def test_change_assumption_examples_parse(self):
        found = examples_of("change-assumptions")
        self.assertTrue(found)
        for _, body in found:
            check_change_assumptions(body)

    def test_gap_assumption_examples_parse(self):
        found = examples_of("gap-assumption")
        self.assertEqual({"es", "en"}, {lang for lang, _ in found})
        for _, body in found:
            check_gap_assumption(body)

    def test_change_functionality_examples_parse(self):
        found = examples_of("change-functionality")
        self.assertEqual({"es", "en"}, {lang for lang, _ in found})
        for lang, body in found:
            with self.subTest(lang=lang):
                check_change_functionality(body, lang)

    def test_a_stale_change_functionality_example_fails(self):
        lang, body = next((lang, body) for lang, body in examples_of("change-functionality") if lang == "es")
        stale = body.replace("### No regresión", "### Regresión", 1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(AssertionError):
            check_change_functionality(stale, lang)
        gone = re.sub(r"(?s)### No regresión.*?(?=### Decisiones)", "", body, count=1)
        with self.assertRaises(AssertionError):
            check_change_functionality(gone, lang)

    def test_a_stale_gap_assumption_example_fails(self):
        _, body = examples_of("gap-assumption")[0]
        stale = re.sub(r"(Estado de decisión|Decision status): \w+", r"\g<1>: confirmado", body, count=1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(AssertionError):
            check_gap_assumption(stale)

    def test_consolidation_examples_parse(self):
        found = examples_of("consolidation")
        self.assertEqual({"es", "en"}, {lang for lang, _ in found})
        for _, body in found:
            check_consolidation(body)

    def test_a_stale_consolidation_example_fails(self):
        _, body = examples_of("consolidation")[0]
        check_consolidation(body)
        stale = re.sub(r"(?m)^(- (?:Texto|Text):.*?) [|]$", lambda m: m.group(1) + " Además se avisa por SMS al proveedor. |", body, count=1)
        self.assertNotEqual(stale, body)
        with self.assertRaises(AssertionError):
            check_consolidation(stale)

    def test_proposals_example_has_extension(self):
        found = examples_of("extraction-proposals")
        types = {block["type"] for _, body in found for block in parse_proposals(body)[0].values()}
        self.assertIn("extension", types)

    def test_a_stale_example_fails(self):
        lang, body = next((lang, body) for lang, body in examples_of("gap-response") if lang == "es")
        check_gap_response(body, lang)
        match = re.search(r"^(\s*-?\s*)nuevo \| [^|\n]+ \| [^\n]+$", body, re.M)
        self.assertIsNotNone(match, "the es example has a `nuevo` border line")
        stale = body.replace(match.group(0), f"{match.group(1)}nuevo | pantallita | X", 1)
        with self.assertRaises(AssertionError):
            check_gap_response(stale, lang)


if __name__ == "__main__":
    unittest.main()
