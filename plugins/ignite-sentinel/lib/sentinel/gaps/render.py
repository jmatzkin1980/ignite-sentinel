"""Gap persistence: gaps.md rendering, gap rows and the gap response sections."""
from __future__ import annotations

from ..core.markdown import table_cell
from ..workspace import workspace_path
from .model import gap_kind, parse_gap_table
from .text import description_for_gap, example_response_for_gap, expected_format_for_gap, human_title_for_gap, lens_for_gap, question_for_gap, unblocks_for_gap, why_gap_matters


def parse_gap_rows(text: str) -> list[dict[str, str]]:
    return parse_gap_table(text)


def no_gaps_text(language: str) -> str:
    if language == "es":
        return """## No se detectaron gaps abiertos

El escaneo determinístico de discovery no detectó gaps bloqueantes ni de seguimiento. Si el cliente o los equipos de dominio tienen contexto adicional, agregarlo en `Notas adicionales` y devolverlo como input de cambio.
"""
    return """## No Open Gaps Detected

No blocking or follow-up gaps were detected by the deterministic discovery scan. If the client or domain teams have additional context, add it under `Additional Notes` and send it back as a change input.
"""


def source_consulted_text(language: str) -> str:
    return "Carpetas de contexto e input fuente." if language == "es" else "Context folders and source input."


def none_gap_row(language: str) -> str:
    if language == "es":
        return "| NONE | Todos | none | CLOSED | N/A | No se detectaron gaps bloqueantes por escaneo determinístico. | N/A | Input fuente. | N/A | checklist | N/A | N/A | N/A | N/A |"
    return "| NONE | All | none | CLOSED | N/A | No blocking gaps detected by deterministic scan. | N/A | Source input. | N/A | checklist | N/A | N/A | N/A | N/A |"


def gap_trace_row(gap: dict[str, str], req_id: str, language: str) -> str:
    cells = [
        gap["id"],
        gap.get("lens", lens_for_gap(gap["id"])),
        gap["severity"],
        gap.get("status", "OPEN"),
        f"`{req_id}`",
        description_for_gap(gap, language),
        gap.get("question") or question_for_gap(gap["id"], language),
        source_consulted_text(language),
        gap.get("evidence_mention") or "N/A",
        gap.get("origin", "checklist"),
        gap.get("resolution_note") or "N/A",
        gap.get("unit") or "N/A",
        gap_kind(gap),
        gap.get("closure_reason") or "N/A",
    ]
    # IMP-321: free text (an agent's question, a quote with a newline or a pipe) must not
    # end the row or open a new cell, or the gap is lost or its columns shift.
    return "| " + " | ".join(table_cell(cell) for cell in cells) + " |"


def gap_meanwhile_map(project_id: str) -> dict[str, dict[str, str]]:
    """IMP-257: the value to build with meanwhile, from an active assumption that closes the gap."""
    from ..brief_model import V2_GAP_ROUTES

    path = workspace_path(project_id) / "01_discovery" / "assumptions.md"
    if not path.exists():
        return {}
    from ..assumptions import assumption_rows

    found: dict[str, dict[str, str]] = {}
    for row in assumption_rows(path.read_text(encoding="utf-8")):
        gap_id = str(row.get("closes_gap", "")).strip("` ").upper()
        if gap_id and str(row.get("status", "")).upper() in {"ASSUMED", "INFERRED"} and gap_id not in found:
            place = V2_GAP_ROUTES.get(gap_id, "")
            found[gap_id] = {"assumption": row["id"], "statement": row["statement"], "where": f"brief v2 §{place}" if place else ""}
    return found


def meanwhile_markdown(gap: dict[str, str], language: str) -> str:
    meanwhile = gap.get("_meanwhile")
    if not isinstance(meanwhile, dict):
        return ""
    where = f" — {'aparece en' if language == 'es' else 'appears in'} {meanwhile['where']}" if meanwhile.get("where") else ""
    label = "Mientras tanto (inferido, a ratificar):" if language == "es" else "Meanwhile (inferred, to ratify):"
    return f"\n{label} {meanwhile['statement']} (`{meanwhile['assumption']}`){where}\n"


def write_gap_elicitation(project_id: str, gaps: list[dict[str, str]], language: str, path=None) -> None:
    """The side record behind the response sections: kind, closure, example, recommended, meanwhile."""
    from ..core.io import write_json

    records = {}
    for gap in gaps:
        options = candidate_options_for_gap(gap, language)
        records[gap["id"]] = {
            "kind": gap_kind(gap),
            "closure_reason": gap.get("closure_reason") or None,
            "example": example_response_for_gap(gap["id"], language),
            "recommended": {"label": options[0]["label"], "text": options[0]["text"], "inferred": True} if options else None,
            "meanwhile": gap.get("_meanwhile"),
        }
    write_json(path or workspace_path(project_id) / "01_discovery" / "gap_elicitation.json", records)


def change_border_guide(language: str) -> str:
    """IMP-382: how to write the border under GAP-SCOPE; shown only when the parent is a change.

    No `### GAP-` heading here: this file can be answered in place, and an example section would count as an answer.
    """
    if language == "es":
        return """
Las respuestas no se escriben en este archivo: van en un archivo aparte (por ejemplo `input/respuestas/CHG-nnn-respuestas.md`) y se procesan con `/resolve-gaps P --source ARCHIVO --change CHG-nnn`.

Al responder GAP-SCOPE de un cambio, agregar debajo de la respuesta el borde: una línea `zona | tipo | nombre` por superficie.
Zonas: nuevo, adyacente, preservado. Tipos: pantalla, proceso, endpoint, dato, rol, integracion, regla.
Un cuarto campo opcional, `alias`, da un nombre corto para repetir en Superficie (hasta 40 caracteres, sin `;` ni `|`, sin tildes, único en el borde): `zona | tipo | nombre | alias`. Superficie acepta el nombre o el alias y guarda siempre el nombre.

    - Borde:
      - nuevo | pantalla | Botón "Guardar borrador" en el alta de proveedores
      - adyacente | endpoint | Envío actual del alta de proveedores
      - preservado | proceso | Envío completo del alta

Para cerrar un gap con lo que ya dice la línea de base, confirmar la respuesta y agregar el motivo con su cita (ruta bajo 00_raw/ y frase literal de al menos 20 caracteres):

    - Estado de decisión: confirmado
    - Evidencia o referencia: `00_raw/06_baseline/sad-compras.md` "responde en menos de dos segundos"
    - Motivo de cierre: by_baseline

Sólo cierra una fuente cargada como línea de base (/sources … --load … --role linea_de_base).

Si la respuesta está en EARS ("Cuando …, el sistema debe …"), declarar qué hace con lo existente; sin esa línea la respuesta no se confirma:

    - Delta: ADDED | MODIFIED | REMOVED | UNCHANGED (sólo si la respuesta está en EARS)
    - Afecta: US-003, US-007 | ninguna (sólo si el Delta es MODIFIED o REMOVED y el proyecto ya tiene historias)
    - Superficie: Listado "Mis borradores"; Botón "Guardar borrador" en el alta de proveedores (una o más del borde, separadas por `;`; obligatoria en toda respuesta EARS de un cambio)
"""
    return """
Answers are not written in this file: they go in a separate file (for example `input/respuestas/CHG-nnn-answers.md`) and are processed with `/resolve-gaps P --source FILE --change CHG-nnn`.

When answering GAP-SCOPE of a change, add the border below the answer: one `zone | type | name` line per surface.
Zones: nuevo, adyacente, preservado. Types: pantalla, proceso, endpoint, dato, rol, integracion, regla.
An optional fourth field, `alias`, gives a short name to repeat in Surface (up to 40 characters, no `;` or `|`, no accents, unique in the border): `zone | type | name | alias`. Surface accepts the name or the alias and always stores the name.

    - Borde:
      - nuevo | pantalla | "Save draft" button in the supplier registration
      - adyacente | endpoint | Current submission of the supplier registration
      - preservado | proceso | Full submission of the registration

To close a gap with what the baseline already says, confirm the answer and add the reason with its citation (a path under 00_raw/ and a literal quote of at least 20 characters):

    - Decision status: confirmed
    - Evidence or reference: `00_raw/06_baseline/sad-purchasing.md` "responds in under two seconds"
    - Closure reason: by_baseline

It only closes from a source loaded as the baseline (/sources ... --load ... --role linea_de_base).

If the answer is in EARS ("When ..., the system shall ..."), declare what it does to the existing system; without this line the answer is not confirmed:

    - Delta: ADDED | MODIFIED | REMOVED | UNCHANGED (only if the answer is in EARS)
    - Affects: US-003, US-007 | none (only if the Delta is MODIFIED or REMOVED and the project already has stories)
    - Surface: "Save draft" button in the supplier registration; Current submission of the supplier registration (one or more of the border, separated by `;`; required on every EARS answer of a change)
"""


def render_gaps(project_id: str, gaps: list[dict[str, str]], req_id: str, language: str = "en", elicitation_path=None) -> str:
    if workspace_path(project_id).exists():
        meanwhile = gap_meanwhile_map(project_id)
        gaps = [{**gap, "_meanwhile": meanwhile[gap["id"]]} if gap.get("id") in meanwhile else gap for gap in gaps]
        write_gap_elicitation(project_id, gaps, language, elicitation_path)
    response_sections = "\n\n".join(render_gap_response_section(gap, req_id, language) for gap in gaps)
    if not response_sections:
        response_sections = no_gaps_text(language)

    rows = "\n".join(gap_trace_row(gap, req_id, language) for gap in gaps)
    if not rows:
        rows = none_gap_row(language)
    border_guide = change_border_guide(language) if str(req_id).startswith("CHG-") else ""
    if language == "es":
        return f"""# Gaps de Discovery - {project_id}

Versión del documento: `1.0`
Proyecto: `{project_id}`
Requerimiento padre: `{req_id}`
Audiencia: stakeholders del cliente, Producto, Tecnología, Diseño, Calidad y Delivery.
Propósito: recopilar información faltante o ambigua para madurar el requerimiento y poder generar project brief, PRD, specs, backlog, criterios de aceptación y tests.

## Cómo responder

Por favor responder directamente debajo de cada gap. Una respuesta breve sirve si es precisa. Si la respuesta corresponde a otro equipo, indicar el owner y cualquier información parcial disponible.

Formato sugerido de respuesta:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión: confirmado / pendiente / no aplica
{border_guide}
## Secciones para respuesta del cliente

{response_sections}

## Notas adicionales

Agregar cualquier nuevo requerimiento, restricción, decisión, screenshot, diagrama o ejemplo que no haya quedado cubierto arriba.

## Tabla de trazabilidad del framework

Esta tabla se mantiene para trazabilidad y procesamiento automático de Sentinel.

| Gap ID | Lente | Severidad | Estado | Padre | Descripción | Pregunta para cliente/dominio | Fuente consultada | Disparador detectado | Origen | Nota de resolución | Unidad | Clase | Cierre |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Trazabilidad de resolución

| Gap ID | Fuente de resolución | Seed promovida | Artefactos impactados |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""
    return f"""# Discovery Gaps - {project_id}

Document version: `1.0`
Project: `{project_id}`
Parent requirement: `{req_id}`
Audience: Client stakeholders, Product, Technology, Design, Quality, and Delivery.
Purpose: collect missing or ambiguous information so the requirement can mature into a project brief, PRD, specs, backlog, acceptance criteria, and tests.

## How To Respond

Please answer directly under each gap. A short answer is fine if it is precise. If a question belongs to another team, name the owner and add any known partial answer.

Suggested response format:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status: confirmed / pending / not applicable
{border_guide}
## Client Response Sections

{response_sections}

## Additional Notes

Add any new requirement, constraint, decision, screenshot, diagram, or example that was not covered above.

## Framework Trace Table

This table is kept for Sentinel traceability and automated processing.

| Gap ID | Lens | Severity | Status | Parent | Description | Question For Client/Domain | Source Consulted | Detected Trigger | Origin | Resolution Note | Unit | Kind | Closure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}

## Resolution Trace

| Gap ID | Resolution Source | Promoted Seed | Impacted Artifacts |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
"""


def evidence_note_for_gap(gap: dict[str, str], language: str = "en") -> str:
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention:
        return ""
    if language == "es":
        notes = {
            "GAP-DESIGN-FLOW": f'El input menciona "{mention}" pero no describe el journey, la navegación ni el flujo de interacción alrededor.',
            "GAP-DESIGN-STATES": f'El input menciona "{mention}" pero no describe los estados de carga, vacío, error y recuperación.',
            "GAP-DESIGN-PROTOTYPE-INPUT": f'El input menciona "{mention}" pero no indica qué debe prototipar o validar Diseño.',
            "GAP-FRONTEND-SURFACE": f'El input menciona "{mention}" pero no detalla validaciones, roles, copy ni binding de datos de esa superficie.',
            "GAP-BACKEND-SURFACE": f'El input menciona "{mention}" pero no describe contratos, persistencia ni comportamiento ante fallas.',
            "GAP-TECH-DEEP-DIVE-INPUT": f'El input menciona "{mention}" pero no aporta arquitectura, repositorios ni source of truth para profundizar.',
            "GAP-METRIC-SOURCE": f'La métrica "{mention}" aparece sin fuente, baseline ni método de medición.',
            "GAP-METRIC-DEFINITION": f'El input menciona "{mention}" pero no define la métrica: falta fórmula/unidad, fuente o umbral.',
            "GAP-AUTH-MODEL": f'El input menciona "{mention}" pero no describe el método de autenticación, el modelo de permisos ni el catálogo de roles.',
        }
        return notes.get(gap["id"], f'El input menciona "{mention}" pero no describe la información faltante de este gap.')
    notes = {
        "GAP-DESIGN-FLOW": f'The input mentions "{mention}" but does not describe the journey, navigation, or interaction flow around it.',
        "GAP-DESIGN-STATES": f'The input mentions "{mention}" but does not describe loading, empty, error, and recovery states.',
        "GAP-DESIGN-PROTOTYPE-INPUT": f'The input mentions "{mention}" but does not state what Design must prototype or validate.',
        "GAP-FRONTEND-SURFACE": f'The input mentions "{mention}" but does not detail validations, roles, copy, or data binding for that surface.',
        "GAP-BACKEND-SURFACE": f'The input mentions "{mention}" but does not describe contracts, persistence, or failure behavior.',
        "GAP-TECH-DEEP-DIVE-INPUT": f'The input mentions "{mention}" but provides no architecture, repository, or source-of-truth input to deepen it.',
        "GAP-METRIC-SOURCE": f'The metric "{mention}" appears without a source, baseline, or measurement method.',
        "GAP-METRIC-DEFINITION": f'The input mentions "{mention}" but does not define the metric: missing formula/unit, source, or threshold.',
        "GAP-AUTH-MODEL": f'The input mentions "{mention}" but does not describe the auth method, permission model, or role catalog.',
    }
    return notes.get(gap["id"], f'The input mentions "{mention}" but does not describe the missing information for this gap.')


def candidate_options_for_gap(gap: dict[str, str], language: str = "en") -> list[dict[str, str]]:
    """Return cited, non-selected answer candidates for gaps with local evidence."""
    if gap.get("status", "OPEN") == "CLOSED":
        return []
    mention = str(gap.get("evidence_mention", "")).strip()
    if not mention or mention.upper() == "N/A":
        return []
    gap_id = gap["id"]
    title = human_title_for_gap(gap_id, language)
    if language == "es":
        if gap_id == "GAP-METRIC-SOURCE":
            texts = [
                f"Confirmar que `{mention}` es la meta de exito y aportar fuente, baseline, owner y metodo de medicion.",
                f"Tratar `{mention}` como objetivo direccional hasta confirmar fuente/baseline, indicando que evidencia falta.",
            ]
        elif gap_id in {"GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"}:
            texts = [
                f"Aplicar el detalle faltante de `{title}` a la superficie mencionada `{mention}`.",
                f"Declarar que `{mention}` queda fuera del alcance MVP y nombrar la alternativa o diferimiento.",
            ]
        else:
            texts = [
                f"Confirmar que `{mention}` esta dentro del alcance y responder el detalle faltante de `{title}`.",
                f"Confirmar que `{mention}` es solo contexto, fuera de alcance o pendiente, y explicitar el limite.",
            ]
        return [{"label": chr(65 + idx), "text": text, "citation": mention} for idx, text in enumerate(texts)]
    if gap_id == "GAP-METRIC-SOURCE":
        texts = [
            f"Confirm `{mention}` is the success target and provide source, baseline, owner, and measurement method.",
            f"Treat `{mention}` as a directional target until source/baseline are confirmed, naming the missing evidence.",
        ]
    elif gap_id in {"GAP-DESIGN-STATES", "GAP-FRONTEND-SURFACE"}:
        texts = [
            f"Apply the missing `{title}` detail to the mentioned surface `{mention}`.",
            f"Declare `{mention}` out of MVP scope and name the alternative or deferral.",
        ]
    else:
        texts = [
            f"Confirm `{mention}` is in scope and answer the missing `{title}` detail.",
            f"Confirm `{mention}` is context-only, out of scope, or pending, and state the boundary.",
        ]
    return [{"label": chr(65 + idx), "text": text, "citation": mention} for idx, text in enumerate(texts)]


def candidate_options_markdown(gap: dict[str, str], language: str = "en") -> str:
    options = candidate_options_for_gap(gap, language)
    if not options:
        return ""
    if language == "es":
        lines = ["Opciones candidatas citadas (no seleccionadas):"]
        for index, option in enumerate(options):
            mark = " (recomendada: inferida, no se aplica sola)" if index == 0 else ""
            lines.append(f"- Opcion {option['label']}{mark}: {option['text']} Cita local: `{option['citation']}`.")
        lines.append("Estas opciones no cierran el gap; el BA/owner debe confirmar una respuesta.")
        return "\n".join(lines)
    lines = ["Cited candidate options (not selected):"]
    for index, option in enumerate(options):
        mark = " (recommended: inferred, never applied by itself)" if index == 0 else ""
        lines.append(f"- Option {option['label']}{mark}: {option['text']} Local citation: `{option['citation']}`.")
    lines.append("These options do not close the gap; the BA/owner must confirm an answer.")
    return "\n".join(lines)


def render_gap_response_section(gap: dict[str, str], req_id: str, language: str = "en") -> str:
    gap_id = gap["id"]
    lens = gap.get("lens", lens_for_gap(gap_id))
    evidence_note = evidence_note_for_gap(gap, language)
    evidence_label = "Evidencia que dispara la pregunta:" if language == "es" else "Evidence that triggers the question:"
    evidence_block = f"\n{evidence_label}\n{evidence_note}\n" if evidence_note else ""
    candidate_options = candidate_options_markdown(gap, language)
    candidate_block = f"\n{candidate_options}\n" if candidate_options else ""
    candidate_block += meanwhile_markdown(gap, language)
    if language == "es":
        return f"""### {gap_id} - {human_title_for_gap(gap_id, language)}

- Lente: `{lens}`
- Severidad: `{gap['severity']}`
- Estado: `{gap.get('status', 'OPEN')}`
- Requerimiento relacionado: `{req_id}`

Descripción breve:
{description_for_gap(gap, language)}
{evidence_block}
Por qué importa (riesgo si queda abierto):
{why_gap_matters(gap_id, language)}

Qué desbloquea esta respuesta:
{unblocks_for_gap(gap_id, language)}

Pregunta:
{gap.get('question') or question_for_gap(gap_id, language)}

Formato de respuesta esperado:
{expected_format_for_gap(gap_id, language)}

Ejemplo de respuesta útil:
{example_response_for_gap(gap_id, language)}
{candidate_block}

Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:
- Motivo de cierre:
"""
    return f"""### {gap_id} - {human_title_for_gap(gap_id)}

- Lens: `{lens}`
- Severity: `{gap['severity']}`
- Status: `{gap.get('status', 'OPEN')}`
- Related requirement: `{req_id}`

Brief description:
{gap['description']}
{evidence_block}
Why it matters (risk if left open):
{why_gap_matters(gap_id)}

What answering this unblocks:
{unblocks_for_gap(gap_id)}

Question:
{gap.get('question') or question_for_gap(gap_id)}

Expected response format:
{expected_format_for_gap(gap_id)}

Example of a useful answer:
{example_response_for_gap(gap_id)}
{candidate_block}

Client / domain response:

- Answer:
- Owner / source:
- Evidence or reference:
- Decision status:
- Closure reason:
"""
