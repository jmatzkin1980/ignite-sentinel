---
description: Inventory a change request element by element, record cited proposals (requirement, brief section or discard), confirm them by section and measure coverage.
agent: sentinel-discovery
---

# Ignite Extract

Extract the request of a change element by element and measure its coverage. Parse `PROJECT_ID` and `--change CHG-NNN` (required) from:

```text
/extract PROJECT_ID --change CHG-NNN
/extract PROJECT_ID --change CHG-NNN --proposals PATH
/extract PROJECT_ID --change CHG-NNN --confirm SECTION|all
/extract PROJECT_ID --change CHG-NNN --confirm-item ID
/extract PROJECT_ID --change CHG-NNN --reject-item ID --reason TEXT
/extract PROJECT_ID --change CHG-NNN --verify [--sample N]
/extract PROJECT_ID --change CHG-NNN --verify-result PATH
```

Run from the repository root:

```powershell
python -m sentinel /extract PROJECT_ID --change CHG-NNN
python -m sentinel /extract PROJECT_ID --change CHG-NNN --proposals PATH
python -m sentinel /extract PROJECT_ID --change CHG-NNN --confirm SECTION|all
python -m sentinel /extract PROJECT_ID --change CHG-NNN --confirm-item ID
python -m sentinel /extract PROJECT_ID --change CHG-NNN --reject-item ID --reason TEXT
python -m sentinel /extract PROJECT_ID --change CHG-NNN --verify [--sample N]
python -m sentinel /extract PROJECT_ID --change CHG-NNN --verify-result PATH
```

Three phases. Without options it inventories the request (every rule, criterion, story, decision and section with its id) and writes a worksheet, `02_requirements/CHG-nnn/extraction/proposals_template.md`. With `--proposals PATH` it records the proposals: copy the worksheet outside `02_requirements`, and for each element write a block headed by its id with `Tratamiento: requisito|seccion|descarte` (in an English change: `Treatment: requirement|section|discard`), a `Cita` copied word for word from the request and, for a requirement, one `Enunciado` per statement with its own `Delta` and `Superficie`. Example:

```text
### RN-02
- Tratamiento: requisito
- Cita: "requiere aprobación de la jefa de Compras"
- Enunciado: Cuando el analista envía un alta con monto anual estimado mayor al umbral, el sistema debe dejarla Pendiente de aprobación.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Enunciado: Mientras un alta está Pendiente de aprobación, el sistema debe impedir órdenes de compra a ese proveedor.
  - Delta: ADDED
  - Superficie: Tabla de proveedores
```

Transcribe, never draft: nothing enters without a verbatim quote of the request, and nothing is confirmed without the BA. With `--confirm SECTION|all` the BA confirms the proposals of a section (or all of them), which writes the EARS rows and fills the brief sections. What is flagged (`Marca`: contradiction, divergence, no support, or an open gap) is not confirmed in bulk: it is held, and each one is confirmed with `--confirm-item ID` after the BA reads it in `review.md`, or taken out with `--reject-item ID --reason TEXT`. `--proposals`, `--confirm`, `--confirm-item`, `--reject-item`, `--verify` and `--verify-result` are alternatives; `--reason` goes only with `--reject-item` and `--sample` only with `--verify`.

`--delegated` (with `--confirm` or `--confirm-item`, optionally `--note TEXT`) confirms on behalf of the BA: the rules are the same (a partial reading or a coverage or verification mark still refuses), but the element is recorded apart as confirmed by delegation and listed in the status, the brief and the export seal to review; the BA ratifies it with `--confirm-item ID` without `--delegated`. A question answered with `- Confirmado por: delegación del BA` (`- Confirmed by:`) in a change leaves the same trace.

The inventory also writes a reading plan (`extraction/reading_plan.md`): the request in batches of at most 60000 characters, each with the lines of each source; read each batch in full and declare in `Líneas` the range you read. `--verify` draws a reproducible sample of the confirmed elements (10 by default) into `extraction/verify/NNN-muestra.md`; re-read each one against the request and answer under Resultados with `- ID: igual` or `- ID: difiere — what is missing`, then record it with `--verify-result PATH`: each `difiere` takes its element back to proposed with the mark `verificacion_difiere`.

Every result carries `coverage` (what share of the request is confirmed), `next_step` and a one-line `message`. Report the message and the coverage, and say which flagged items wait for the BA.
