---
name: sentinel-specs
description: "Use when generating or reviewing the Ignite Sentinel PRD and AI-friendly specification layer with /specs: the human PRD, the compact spec index, bounded SPEC-U-* execution units, retrieval plans, and the REQ->PRD->SPEC trace. Trigger on 'generate the PRD', 'generate specs', spec-unit questions, or preparing the downstream handoff from a mature brief. Not for polishing PRD narrative (use sentinel-compose) or an adversarial pass over it (use sentinel-self-review)."
---

# Sentinel Specs

Use this skill to create the PRD and AI-friendly spec layer.

## Workflow

1. Run `python -m sentinel /maturity PROJECT_ID`.
2. If ready, run `python -m sentinel /specs PROJECT_ID`.
3. Review `workspaces/PROJECT_ID/03_specs/prd.md` for the complete human/business PRD: personas, FRs/ACs, NFRs, KPIs, JTBD traceability, execution plan, governance, and audit trail.
4. Review `workspaces/PROJECT_ID/03_specs/specs.md` for the agent-ready backlog contract and spec-unit index.
5. Review `workspaces/PROJECT_ID/03_specs/units/SPEC-U-NNN.md` for bounded, evidence-backed execution units before backlog slicing.
6. Review `workspaces/PROJECT_ID/08_context_packs/specs_generation.json` to see which declarative retrieval plan sections, focused memory context, and source `read_plan` anchors were used.
7. Run `python -m sentinel /trace PROJECT_ID` to confirm `REQ/project_brief -> PRD -> SPEC -> SPEC-U` linkage.

## Rules

- Specs must elaborate existing requirements.
- Do not proceed while maturity is `BLOCKED`.
- Keep Product, Technology, Design, Quality, and Delivery signals visible.
- Retrieval plans live in `sentinel/retrieval_plans/*.json`; tune section queries, filters, budgets, and lenses there instead of editing Python.
- PRD explains what and why for humans with traceable requirements and acceptance criteria; specs preserves the compact agent contract, retrieval plan, trace IDs, spec-unit index, and backlog handoff cues.
- Do not treat fixed placeholder IDs as execution scope. Use `SPEC-U-*` files when they exist; each unit carries frontmatter with trace IDs, EARS IDs, and source anchors.
- PRD generation performs evidence-backed extraction (IMP-005): personas, requirement-like statements, and quantitative metrics are quoted verbatim from the raw client input under `00_raw/00_client_requirement/` with `REQ-001` citations. When no signal exists, sections keep `[PENDING INPUT]` instead of inventing content.
- The PRD Scope section (§2) carries a `### Non-Goals` block (IMP-185) projected only from governed data: gaps closed out-of-scope/not-applicable and scope decisions, each cited by `GAP-*` id and change source. No such closures → the explicit "no non-goals recorded" marker, never an invented exclusion. It mirrors the brief's `### No-Objetivos (Non-Goals)` block; add a non-goal by closing the gap as not-applicable through `/resolve-gaps`, not by editing the PRD.
- `/specs PROJECT_ID --change CHG-nnn` (IMP-388) writes the specification of one change under `03_specs/CHG-nnn/` (`specs.md`, `units/`, `change_specs_report.json`). It writes the units of the change, one `SPEC-U-nnn` per ADDED, MODIFIED or REMOVED requirement of `02_requirements/CHG-nnn/requirements.md`. UNCHANGED rows are listed as "Comportamiento preservado", never as units. The `specs.md` is organized by functionality (see the section below). Unit ids come from a per-project registry and are not reused across changes. It refuses without the change brief (`/brief --change`), with blocking gaps still open, or with no ADDED/MODIFIED/REMOVED row. The Delta of each requirement is the BA's (see sentinel-gap-response); never edit it here. The stories of the change come next with `/backlog --change CHG-nnn` (see sentinel-backlog).
- Since IMP-414, `/specs --change` also writes `03_specs/CHG-nnn/prd.md`: the PRD of the change, in the format of the project PRD, from the **current consolidated final export** (`/export --artifact brief --change CHG-nnn --final`), its EARS rows, its closed decisions and the elements that left the change. Without a current final export the specs are written and the result says `prd_skipped` (prd.md pending: export the final brief first); run `/specs --change` again afterwards. `change_specs_report.json` records the PRD and the sha of the final it came from, and the specs count as stale when that final is replaced. It is never hand-edited, and the project's `03_specs/prd.md` is untouched.
- `/specs` returns `foundation_warnings` when the foundation it builds on (brief/requirements) drifted — its sources changed after it was generated. Explain the warning to the BA and recommend regenerating the stale upstream artifact through its owning command before relying on the new specs, or confirming the change is immaterial. The gate is soft by default (`drift_gate.strict` opts into blocking); nothing is rewritten, and you never "fix" drift by editing artifacts.
- Regenerating `/specs` over an existing spec layer records a **per-unit delta report** under `07_changes/04_regeneration/` (which `SPEC-U-*` units were added, removed, or changed; `state.json` keeps `last_spec_unit_delta_path`). Summarize the unit deltas after a regeneration so the BA sees exactly which execution units moved — especially before re-running `/backlog`.

## The change specification by functionality (IMP-416)

`03_specs/CHG-nnn/specs.md` is the document an AI builds a change from. It is organized by **functionality**: the units of the change grouped by the surface of the border they act on (a screen, a service, a rule), numbered `FUN-nn` in a stable order (new surfaces first). A unit that names no surface goes to a section of its own, "Sin superficie: lugar X" / "No surface: place X".

- Each `## FUN-nn — name (type, zone)` section has eight blocks, in this order, with the titles of the change language (`change_language`): Objetivo, As-is (lo que existe hoy), To-be (cómo debe quedar), Interfaces que toca, No regresión, Decisiones que la afectan, Supuestos y pendientes, Orden y dependencias (English: Objective, As-is (what exists today), To-be (target behavior), Interfaces touched, No regression, Decisions affecting it, Assumptions and open items, Order and dependencies).
- **Transcribe, don't draft.** A block shows only registered data, quoted with its citation `path:Lnn-Lmm`: the request's lines, the consolidated text of the BA (`/extract --consolidate`), the closed decisions, the assumptions and the harvest facts. A block with nothing registered says `_sin dato registrado_` (English: `_no data recorded_`). Never fill it and never rewrite a quote; the way to give a block content is the evidence upstream (a consolidation, a decision, a harvest), then `/specs --change` again.
- After the functionalities comes the traceability table (Unidad, REQ-EARS, Elemento, Cita, Superficie, GAP; English: Unit, REQ-EARS, Element, Citation, Surface, GAP) and the preserved behavior (UNCHANGED rows). The units in `units/SPEC-U-nnn.md` keep the line anchor of their element (`ruta:Lnn-Lmm`) and their headings in the language of the change.
- `change_specs_report.json` records the `functionalities`. A report of 0.31 (without them) reads as `old`, and `/next --change` asks to regenerate specs and backlog. The stories take their cuts from these functionalities (see sentinel-backlog).
- The project's `specs.md` is not this document: without `--change` nothing changes.

The shape of a functionality section is under `## Formato` (the Compras domain there is made up). The test suite checks that the eight blocks are the ones the writer produces, in order.

## Anti-patterns

Each row is a mistake this skill exists to prevent, with the correction:

- **Inventing PRD content** — writing personas, FRs, or metrics with no signal in the raw input. → PRD extraction is evidence-backed and quoted verbatim with `REQ-001` citations; with no signal, keep `[PENDING INPUT]`.
- **Generating over a `BLOCKED` maturity** — running `/specs` to "make progress" while blocking gaps remain. → Specs elaborate mature requirements; resolve the blocking gaps first.
- **Treating placeholder IDs as scope** — building execution scope from fixed `SPEC-001` placeholders. → Use `SPEC-U-*` units when they exist; each carries its own trace IDs, EARS IDs, and source anchors.
- **Hand-writing a Non-Goal** — editing the PRD `### Non-Goals` block to add an exclusion. → Close the relevant gap as not-applicable through `/resolve-gaps`; the block is projected only from governed data.
- **Ignoring foundation or unit drift** — relying on regenerated specs without reading the warnings. → Explain `foundation_warnings`, and summarize the per-unit delta report under `07_changes/04_regeneration/` before re-running `/backlog`.

## Formato

One functionality section of `03_specs/CHG-nnn/specs.md`, with its eight blocks and the traceability table. It is output you review, not a file you write; a block without registered data keeps the marker.

```sentinel-example kind=change-functionality lang=es
## FUN-01 — Aprobación por monto (pantalla, nuevo)

### Objetivo

> «Un alta con monto anual estimado mayor a 1.000.000 requiere aprobación de la jefa de Compras.» (pedido.md:L31)

### As-is (lo que existe hoy)

_sin dato registrado_

### To-be (cómo debe quedar)

- RN-02 (MODIFIED): Cuando un alta de proveedor tiene un monto anual estimado mayor a 1.000.000, el sistema debe pedir la aprobación de la jefa de Compras.

### Interfaces que toca

- Pantalla «Aprobación por monto» (a construir)

### No regresión

- `REQ-EARS-001` pass-to-pass: el alta de proveedores con monto menor al umbral sigue sin pedir aprobación.

### Decisiones que la afectan

| GAP | Pregunta | Respuesta |
| --- | --- | --- |
| GAP-DIS-3F9A1C07 | ¿Rige 5.000.000 o 1.000.000? | Rige el diseño: el umbral de aprobación es 1.000.000. |

### Supuestos y pendientes

_sin dato registrado_

### Orden y dependencias

- Va primero: es superficie nueva.

## Trazabilidad

| Unidad | REQ-EARS | Elemento | Cita | Superficie | GAP |
| --- | --- | --- | --- | --- | --- |
| SPEC-U-001 | `REQ-EARS-002` | RN-02 | pedido.md:L31 | Aprobación por monto | GAP-DIS-3F9A1C07 |
```

The same in English:

```sentinel-example kind=change-functionality lang=en
## FUN-01 — Amount approval (screen, new)

### Objective

> «A vendor registration with an estimated annual amount above 1,000,000 requires approval from the head of Procurement.» (request.md:L31)

### As-is (what exists today)

_no data recorded_

### To-be (target behavior)

- RN-02 (MODIFIED): When a vendor registration has an estimated annual amount above 1,000,000, the system shall ask for the approval of the head of Procurement.

### Interfaces touched

- Screen «Amount approval» (to build)

### No regression

- `REQ-EARS-001` pass-to-pass: registering a vendor below the threshold still asks for no approval.

### Decisions affecting it

| GAP | Question | Answer |
| --- | --- | --- |
| GAP-DIS-3F9A1C07 | Does 5,000,000 or 1,000,000 apply? | The design applies: the approval threshold is 1,000,000. |

### Assumptions and open items

_no data recorded_

### Order and dependencies

- Goes first: it is a new surface.

## Traceability

| Unit | REQ-EARS | Element | Citation | Surface | GAP |
| --- | --- | --- | --- | --- | --- |
| SPEC-U-001 | `REQ-EARS-002` | RN-02 | request.md:L31 | Amount approval | GAP-DIS-3F9A1C07 |
```
