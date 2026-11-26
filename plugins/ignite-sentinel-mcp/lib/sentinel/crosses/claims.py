"""IMP-404 task 2: the claims file of a cross-read, and the check of its quotes by source role.

Nothing here interprets the sources: a claim is a tag, a sentence the BA wrote and verbatim
quotes. A quote must appear in a registered source of the right role (transcribe, never draft).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from ..changes import MIN_BASELINE_QUOTE, _squash, change_language, resolve_scope
from ..extraction.inventory import _read_text, _resolve, _row_path, pedido_rows
from ..source_registry import row_role
from ..sources import load_source_manifest
from ..workspace import workspace_path

TAGS = {
    "RESPALDADO": "respaldado",
    "BACKED": "respaldado",
    "SIN RESPALDO EN DISEÑO": "sin_respaldo",
    "SIN RESPALDO EN DISENO": "sin_respaldo",
    "NOT IN DESIGN": "sin_respaldo",
    "SOLO EN DISEÑO": "solo_en_diseno",
    "SOLO EN DISENO": "solo_en_diseno",
    "ONLY IN DESIGN": "solo_en_diseno",
    "DIVERGENCIA": "divergencia",
    "DIVERGENCE": "divergencia",
    "CONTRADICCIÓN": "contradiccion",
    "CONTRADICCION": "contradiccion",
    "CONTRADICTION": "contradiccion",
    "SIN HALLAZGOS": "sin_hallazgos",
    "NOTHING FOUND": "sin_hallazgos",
}

TAG_NAMES = {
    "es": {
        "respaldado": "RESPALDADO",
        "sin_respaldo": "SIN RESPALDO EN DISEÑO",
        "solo_en_diseno": "SOLO EN DISEÑO",
        "divergencia": "DIVERGENCIA",
        "contradiccion": "CONTRADICCIÓN",
        "sin_hallazgos": "SIN HALLAZGOS",
    },
    "en": {
        "respaldado": "BACKED",
        "sin_respaldo": "NOT IN DESIGN",
        "solo_en_diseno": "ONLY IN DESIGN",
        "divergencia": "DIVERGENCE",
        "contradiccion": "CONTRADICTION",
        "sin_hallazgos": "NOTHING FOUND",
    },
}

KIND_TAGS = {
    "diseno": ("respaldado", "sin_respaldo", "solo_en_diseno", "divergencia", "sin_hallazgos"),
    "contradicciones": ("contradiccion", "sin_hallazgos"),
}

# tag -> (min pedido, max pedido, min diseno, max diseno); None = no cap
CITATION_RULES: dict[str, tuple[int, int | None, int, int | None]] = {
    "respaldado": (1, 1, 1, None),
    "sin_respaldo": (1, 1, 0, 0),
    "solo_en_diseno": (0, 0, 1, None),
    "divergencia": (1, 1, 1, 1),
    "contradiccion": (2, 2, 0, 0),
    "sin_hallazgos": (0, 0, 0, 0),
}

_RULE_TEXT = {
    "es": {
        "respaldado": "una cita Pedido y al menos una Diseño",
        "sin_respaldo": "una cita Pedido y ninguna Diseño",
        "solo_en_diseno": "al menos una cita Diseño y ninguna Pedido",
        "divergencia": "una cita Pedido y una Diseño",
        "contradiccion": "dos citas Pedido y ninguna Diseño",
        "sin_hallazgos": "ninguna cita",
    },
    "en": {
        "respaldado": "one Request quote and at least one Design quote",
        "sin_respaldo": "one Request quote and no Design quote",
        "solo_en_diseno": "at least one Design quote and no Request quote",
        "divergencia": "one Request quote and one Design quote",
        "contradiccion": "two Request quotes and no Design quote",
        "sin_hallazgos": "no quote",
    },
}

SIDES = {"pedido": "pedido", "request": "pedido", "diseño": "diseno", "diseno": "diseno", "design": "diseno"}
SIDE_ROLES = {"pedido": "pedido", "diseno": "diseno_nuevo"}

MIN_REQUEST_QUOTE = MIN_BASELINE_QUOTE
MIN_DESIGN_QUOTE = 8
CONTEXT_LINES = 10

_CLAIM_RE = re.compile(r"^ ?[-*]\s*(?:\*\*)?\[(?P<tag>[^\]]+)\](?:\*\*)?\s*(?P<text>.+?)\s*$")
# a line that opens like a claim (bullet or number, then a bracket) but did not match the format above
_CLAIMISH_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s*(?:\*\*)?\s*\[")
_SIDE_WORDS = "Pedido|Request|Diseño|Diseno|Design"
_CITE_RE = re.compile(
    rf"^\s+[-*]\s*(?P<side>{_SIDE_WORDS})\s*:\s*(?P<source>F-\d+)\s+"
    r"(?P<quote>\".+\"|“.+”|«.+»)\s*$",
    re.I,
)
_CITE_SHAPE_RE = re.compile(rf"^\s+[-*]\s*(?:{_SIDE_WORDS})\s*:", re.I)
_INDENTED = re.compile(r"^(?: {2,}|\t)")


def _prefix(number: int, es: bool) -> str:
    return f"línea {number}: " if es else f"line {number}: "


def _tag_list(es: bool) -> str:
    return ", ".join(TAG_NAMES["es" if es else "en"].values())


def parse_claims(text: str, language: str = "es") -> tuple[list[dict], list[str]]:
    """The tagged claims of a cross-read file with their quotes, and the format errors found. Pure."""
    es = language == "es"
    claims: list[dict] = []
    errors: list[str] = []
    invalid = False  # the last claim line had an unknown tag: its quotes are not the previous claim's
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), start=1):
        line = raw.rstrip()
        head = _prefix(number, es)
        indented = bool(_INDENTED.match(line))
        cite = _CITE_RE.match(line) if indented else None
        if cite:
            if invalid:
                continue
            if not claims:
                errors.append(head + ("cita sin una afirmación etiquetada antes" if es
                                      else "quote without a tagged claim before it"))
                continue
            claims[-1]["citations"].append({
                "line": number,
                "side": SIDES[cite.group("side").lower()],
                "source_id": cite.group("source"),
                "quote": cite.group("quote")[1:-1].strip(),
            })
            continue
        if indented and _CITE_SHAPE_RE.match(line):
            errors.append(head + ("cita mal escrita: falta F-NN o la cita entre comillas" if es
                                  else "malformed quote line: the F-NN or the quoted text is missing")
                          + (" (comillas válidas: \"…\", “…” o «…»)" if es else " (valid quotes: \"…\", “…” or «…»)"))
            continue
        claim = None if indented else _CLAIM_RE.match(line)
        if claim is None and _CLAIMISH_RE.match(line):
            errors.append(head + (f"afirmación mal escrita: usá «- [ETIQUETA] texto» (etiquetas: {_tag_list(es)}): {line.strip()[:60]}" if es
                                  else f"malformed claim: use «- [TAG] text» (tags: {_tag_list(es)}): {line.strip()[:60]}"))
            invalid = True  # its quotes are not the previous claim's
            continue
        if claim:
            tag_text = " ".join(claim.group("tag").split())
            tag = TAGS.get(tag_text.upper())
            if tag is None:
                errors.append(head + (f"etiqueta desconocida [{tag_text}]; etiquetas: {_tag_list(es)}" if es
                                  else f"unknown tag [{tag_text}]; tags: {_tag_list(es)}"))
                invalid = True
                continue
            invalid = False
            claims.append({"line": number, "tag": tag, "text": claim.group("text"), "citations": []})
    if not claims:
        errors.append("el archivo no trae ninguna afirmación etiquetada" if es else "the file has no tagged claim")
    return claims, errors


_HIDDEN = re.compile(r"<script\b.*?</script\b[^>]*>|<style\b.*?</style\b[^>]*>|<!--.*?--!?>", re.I | re.S)
_TAG = re.compile(r"<[^>]*>")
_INLINE_TAG = re.compile(
    r"</?(?:a|abbr|b|big|cite|code|em|font|i|kbd|mark|small|span|strong|sub|sup|u)\b[^>]*>", re.I)
_ATTRIBUTE_TEXT = re.compile(
    r"""\b(?:placeholder|alt|title|aria-label|value)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)


def visible_variants(text: str, suffix: str) -> list[str]:
    """What a reader sees of an HTML file, in the readings a BA may copy it in: scripts, styles and comments gone,
    attribute text (placeholder, alt, title, aria-label, value) added, and tags as spaces or, for inline tags, nothing."""
    if suffix.lower() not in (".html", ".htm"):
        return [text]
    shown = _HIDDEN.sub(" ", text)
    attributes = " ".join(a or b for a, b in _ATTRIBUTE_TEXT.findall(shown))
    spaced = _TAG.sub(" ", shown)
    joined = _TAG.sub(" ", _INLINE_TAG.sub("", shown))
    return [html.unescape(f"{body} {attributes}") for body in (spaced, joined)]


def visible_text(text: str, suffix: str) -> str:
    """What a reader sees: an HTML file without scripts, styles, comments and tags; other text as is."""
    return visible_variants(text, suffix)[0]


def locate_quote(text: str, suffix: str, quote: str) -> dict | None:
    """Where a quote sits: its start in the squashed visible text and, if the raw text has it, its line."""
    needle = _squash(quote)
    if not needle:
        return None
    start = -1
    for variant in visible_variants(text, suffix):
        start = _squash(variant).find(needle)
        if start >= 0:
            break
    if start < 0:
        return None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


    def window(first: int, size: int) -> str:
        return _squash(" ".join(lines[first : first + size]))

    line: int | None = None
    for index in range(len(lines)):
        # the line the quote starts on: the window from here has it, the shorter one from the next line does not
        if needle in window(index, CONTEXT_LINES + 1) and needle not in window(index + 1, CONTEXT_LINES):
            line = index + 1
            break
    return {"line": line, "start": start}


def cross_sources(project_id: str, change_id: str | None) -> dict[str, dict[str, dict]]:
    pedido = {str(row["id"]): row for row in pedido_rows(project_id, change_id)}
    if change_id is None:  # H27 inc 6b: the design of the project is what no change holds
        from ..changes import _project_rows

        diseno = {str(row["id"]): row for row in _project_rows(project_id) if row_role(row) == "diseno_nuevo"}
        return {"pedido": pedido, "diseno": diseno}
    diseno = {
        str(row["id"]): row
        for row in load_source_manifest(project_id).get("registry", [])
        if row.get("validity", "current") == "current" and row_role(row) == "diseno_nuevo"
    }
    return {"pedido": pedido, "diseno": diseno}


def validate_claims(project_id: str, change_id: str, kind: str, claims: list[dict]) -> tuple[list[dict], list[str]]:
    """The claims with each quote enriched with its `path` and `line`, or the errors in the change's language."""
    change = resolve_scope(project_id, change_id).entry
    es = change_language(project_id, change) == "es"
    base = workspace_path(project_id)
    registry = {str(row.get("id")): row for row in load_source_manifest(project_id).get("registry", [])}
    sources = cross_sources(project_id, change_id)
    texts: dict[str, str | None] = {}
    errors: list[str] = []
    result: list[dict] = []
    names = TAG_NAMES["es" if es else "en"]
    allowed = KIND_TAGS.get(kind, ())
    if len(claims) > 1 and any(c["tag"] == "sin_hallazgos" for c in claims):
        first = next(c for c in claims if c["tag"] == "sin_hallazgos")
        return [], [_prefix(int(first["line"]), es) + (
            f"[{names['sin_hallazgos']}] va solo: un cruce sin hallazgos no trae otras afirmaciones" if es
            else f"[{names['sin_hallazgos']}] stands alone: a cross-read with nothing found has no other claims")]

    for claim in claims:
        tag = claim["tag"]
        head = _prefix(int(claim["line"]), es)
        label = names[tag]
        if tag not in allowed:
            valid = ", ".join(names[t] for t in allowed) or "-"
            errors.append(head + (f"[{label}] no va en el cruce {kind}; etiquetas válidas: {valid}" if es
                                  else f"[{label}] does not belong in the {kind} cross-read; valid tags: {valid}"))
            continue
        counts = {side: sum(1 for c in claim["citations"] if c["side"] == side) for side in ("pedido", "diseno")}
        low_p, high_p, low_d, high_d = CITATION_RULES[tag]
        if (counts["pedido"] < low_p or (high_p is not None and counts["pedido"] > high_p)
                or counts["diseno"] < low_d or (high_d is not None and counts["diseno"] > high_d)):
            rule = _RULE_TEXT["es" if es else "en"][tag]
            errors.append(head + (f"[{label}] lleva {rule}" if es else f"[{label}] takes {rule}"))
            continue
        enriched: list[dict] = []
        places: list[tuple[str, int, int]] = []
        claim_ok = True
        for cite in claim["citations"]:
            found = _check_citation(project_id, change_id, cite, registry, sources, base, texts, es, head, errors)
            if found is None:
                claim_ok = False
                continue
            enriched.append(found["cite"])
            places.append((cite["source_id"], found["start"], found["start"] + len(_squash(cite["quote"]))))
        if claim_ok and tag == "contradiccion" and len(places) == 2:
            (src_a, a0, a1), (src_b, b0, b1) = places
            if src_a == src_b and a0 < b1 and b0 < a1:
                errors.append(head + ("las dos citas de una contradicción tienen que ser de lugares distintos del pedido"
                                      if es else "the two quotes of a contradiction must come from different places in the request"))
                claim_ok = False
        if claim_ok:
            result.append({**claim, "citations": enriched})
    return ([], errors) if errors else (result, [])


def rebase_claim(project_id: str, change_id: str, claim: dict, current: set[str]) -> dict | None:
    """H27 inc 6a: the claim with its quotes moved to the sources now current, or None if one does not fit.

    A quote of a source that is still current stays as it is (a row's content never changes). One of a
    source that is not is looked for, verbatim, in the current sources of the same side: first the row
    that replaced it, then the others in registry order; the first that has it takes `source_id`,
    `path` and `line`. If any quote is not found the claim is not rebased (the caller re-reads it).
    """
    base = workspace_path(project_id)
    registry = {str(row.get("id")): row for row in load_source_manifest(project_id).get("registry", [])}
    held = {str(i) for i in resolve_scope(project_id, change_id).entry.get("sources") or []}
    # the design side of the cross-read is every current prototype of the workspace; a quote moves only onto
    # the rows that belong to this change, never onto another change's source
    sources = {side: {i: row for i, row in rows.items() if i in held}
               for side, rows in cross_sources(project_id, change_id).items()}
    texts: dict[str, str | None] = {}

    def where(source_id: str, quote: str) -> dict | None:
        row = registry.get(source_id)
        if row is None:
            return None
        if source_id not in texts:
            texts[source_id] = _read_text(base, _row_path(row))
        text = texts[source_id]
        return None if text is None else locate_quote(text, Path(_row_path(row)).suffix, quote)

    rebased: list[dict] = []
    places: list[tuple[str, int, int]] = []
    moved = False
    for cite in claim.get("citations", []):
        source_id = str(cite.get("source_id"))
        quote = str(cite.get("quote", ""))
        if source_id in current:
            rebased.append(dict(cite))
            found = where(source_id, quote) if claim.get("tag") == "contradiccion" else None
            if found is not None:
                places.append((source_id, found["start"], found["start"] + len(_squash(quote))))
            continue
        side = cite.get("side")
        if side not in sources:
            return None
        replaced = (registry.get(source_id) or {}).get("superseded_by")
        order = [str(replaced)] if str(replaced) in sources[side] else []
        order += [i for i in sources[side] if i not in order]
        hit = None
        for candidate in order:
            found = where(candidate, quote)
            if found is not None:
                hit = (candidate, found)
                break
        if hit is None:
            return None
        candidate, found = hit
        moved = True
        places.append((candidate, found["start"], found["start"] + len(_squash(quote))))
        rebased.append({**cite, "source_id": candidate, "path": _workspace_path(base, _row_path(registry[candidate])),
                        "line": found["line"]})
    if moved and claim.get("tag") == "contradiccion" and len(places) == 2:
        (src_a, a0, a1), (src_b, b0, b1) = places
        if src_a == src_b and a0 < b1 and b0 < a1:
            return None  # the two quotes now land on the same place: it is not the same contradiction
    return {**claim, "citations": rebased}


def _workspace_path(base: Path, relative: str) -> str:
    """The path as the workspace cites it (`00_raw/...`), when the file lives inside it."""
    found = _resolve(base, relative)
    if found is None:
        return relative
    try:
        return found.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return relative


def _check_citation(
    project_id: str, change_id: str, cite: dict, registry: dict[str, dict], sources: dict[str, dict[str, dict]],
    base: Path, texts: dict[str, str | None], es: bool, head: str, errors: list[str],
) -> dict | None:
    source_id = cite["source_id"]
    side = cite["side"]
    row = registry.get(source_id)
    if row is None:
        errors.append(head + (f"{source_id} no es una fuente registrada" if es else f"{source_id} is not a registered source"))
        return None
    if row.get("validity", "current") != "current":
        errors.append(head + (f"{source_id} fue reemplazada o retirada: citá la vigente" if es
                              else f"{source_id} was superseded or retired: cite the current one"))
        return None
    if source_id not in sources[side]:
        role = row_role(row)
        ids = ", ".join(sources[side]) or "-"
        if es:
            if side == "pedido":
                rule = f"«Pedido:» cita un pedido de {change_id} ({ids})"
            else:
                rule = (f"«Diseño:» cita una fuente diseno_nuevo ({ids}, o cargá el prototipo con "
                        f"/sources {project_id} --load ARCHIVO --role diseno_nuevo --change {change_id})")
            errors.append(head + f"{source_id} está registrada como {role or 'sin rol'}: {rule}")
        else:
            if side == "pedido":
                rule = f"«Request:» quotes a request of {change_id} ({ids})"
            else:
                rule = (f"«Design:» quotes a diseno_nuevo source ({ids}, or load the prototype with "
                        f"/sources {project_id} --load FILE --role diseno_nuevo --change {change_id})")
            errors.append(head + f"{source_id} is registered as {role or 'no role'}: {rule}")
        return None
    quote = cite["quote"]
    minimum = MIN_REQUEST_QUOTE if side == "pedido" else MIN_DESIGN_QUOTE
    if len(_squash(quote)) < minimum:
        errors.append(head + (f"la cita de {source_id} tiene menos de {minimum} caracteres" if es
                              else f"the quote from {source_id} is shorter than {minimum} characters"))
        return None
    path = _row_path(row)
    if source_id not in texts:
        texts[source_id] = _read_text(base, path)
    text = texts[source_id]
    if text is None:
        errors.append(head + (f"{source_id} no se puede leer como texto" if es else f"{source_id} cannot be read as text"))
        return None
    suffix = Path(path).suffix
    where = locate_quote(text, suffix, quote)
    if where is None:
        is_html = suffix.lower() in (".html", ".htm")
        if es:
            note = ", sobre el texto visible del HTML" if is_html else ""
            errors.append(head + f"la cita no aparece literal en {source_id} (`{path}`); se compara sin diferencias de espacios, respetando mayúsculas{note}")
        else:
            note = ", over the visible text of the HTML" if is_html else ""
            errors.append(head + f"the quote does not appear verbatim in {source_id} (`{path}`); compared ignoring whitespace differences, case-sensitive{note}")
        return None
    return {"cite": {**cite, "path": _workspace_path(base, path), "line": where["line"]}, "start": where["start"]}
