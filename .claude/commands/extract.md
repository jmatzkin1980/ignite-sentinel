---
description: Inventory a change request element by element, record cited proposals (requirement, brief section or discard), confirm them by section and measure coverage.
argument-hint: PROJECT_ID --change CHG-NNN [--proposals PATH | --confirm SECTION|all | --confirm-item ID | --reject-item ID --reason TEXT]
---

# Ignite Extract

Arguments received from the user invocation: `$ARGUMENTS`

Extract the request of a change element by element and measure its coverage. Parse `PROJECT_ID` and `--change CHG-NNN` (required) from:

```text
/extract PROJECT_ID --change CHG-NNN
/extract PROJECT_ID --change CHG-NNN --proposals PATH
/extract PROJECT_ID --change CHG-NNN --confirm SECTION|all
/extract PROJECT_ID --change CHG-NNN --confirm-item ID
/extract PROJECT_ID --change CHG-NNN --reject-item ID --reason TEXT
```

Run from the repository root:

```powershell
python -m sentinel /extract PROJECT_ID --change CHG-NNN
python -m sentinel /extract PROJECT_ID --change CHG-NNN --proposals PATH
python -m sentinel /extract PROJECT_ID --change CHG-NNN --confirm SECTION|all
python -m sentinel /extract PROJECT_ID --change CHG-NNN --confirm-item ID
python -m sentinel /extract PROJECT_ID --change CHG-NNN --reject-item ID --reason TEXT
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

Transcribe, never draft: nothing enters without a verbatim quote of the request, and nothing is confirmed without the BA. With `--confirm SECTION|all` the BA confirms the proposals of a section (or all of them), which writes the EARS rows and fills the brief sections. What is flagged (`Marca`: contradiction, divergence, no support, or an open gap) is not confirmed in bulk: it is held, and each one is confirmed with `--confirm-item ID` after the BA reads it in `review.md`, or taken out with `--reject-item ID --reason TEXT`. `--proposals`, `--confirm`, `--confirm-item` and `--reject-item` are alternatives; `--reason` goes only with `--reject-item`.

Every result carries `coverage` (what share of the request is confirmed), `next_step` and a one-line `message`. Report the message and the coverage, and say which flagged items wait for the BA.
