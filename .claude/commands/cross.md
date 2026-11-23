---
description: Record the cited cross-reads of a change request against the new design and against itself, waive a cross-read, and decide the new surfaces the baseline cross-read did not find.
argument-hint: PROJECT_ID --change CHG-NNN [--kind diseno|contradicciones|linea_de_base (--claims PATH | --skip --reason TEXT) | --accept-new ID --type TYPE --name NAME | --decline-new ID --reason TEXT]
---

# Ignite Cross

Arguments received from the user invocation: `$ARGUMENTS`

Cross-read a change request with the new design and with itself, waive a cross-read, and decide the new surfaces the baseline cross-read did not find. Parse `PROJECT_ID` and `--change CHG-NNN` (required) from:

```text
/cross PROJECT_ID --change CHG-NNN
/cross PROJECT_ID --change CHG-NNN --kind diseno|contradicciones --claims PATH
/cross PROJECT_ID --change CHG-NNN --kind diseno|contradicciones|linea_de_base --skip --reason TEXT
/cross PROJECT_ID --change CHG-NNN --accept-new ID --type TYPE --name NAME
/cross PROJECT_ID --change CHG-NNN --decline-new ID --reason TEXT
```

Run from the repository root:

```powershell
python -m sentinel /cross PROJECT_ID --change CHG-NNN
python -m sentinel /cross PROJECT_ID --change CHG-NNN --kind diseno --claims PATH
python -m sentinel /cross PROJECT_ID --change CHG-NNN --kind contradicciones --skip --reason TEXT
python -m sentinel /cross PROJECT_ID --change CHG-NNN --accept-new ID --type TYPE --name NAME
python -m sentinel /cross PROJECT_ID --change CHG-NNN --decline-new ID --reason TEXT
```

A change has three cross-reads: the request against the baseline (`linea_de_base`, which is `/harvest ... --change`), the request against the new design (`diseno`, a prototype or design loaded with `/sources --load PATH --role diseno_nuevo --change CHG-NNN`) and the request against itself (`contradicciones`). Without options the command only reports where each one stands. With `--claims PATH` it records the cross-read the BA wrote: one `- [TAG] sentence` per claim, followed by indented `Pedido: F-NN "verbatim quote"` and `Diseño: F-NN "verbatim quote"` lines, where `F-NN` is the id of the source that holds the quote. Every quote is checked word for word against the registered sources of its role; a claim with a quote that is not there rejects the whole file. Example:

```text
- [RESPALDADO] La bandeja de la jefa de Compras está en el prototipo.
  - Pedido: F-02 "quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas"
  - Diseño: F-05 "Bandeja de aprobaciones"
- [SIN RESPALDO EN DISEÑO] El historial que consulta el auditor no tiene pantalla en el prototipo.
  - Pedido: F-02 "quiero consultar quién aprobó cada alta y cuándo"
- [DIVERGENCIA] El pedido fija el umbral en 5.000.000 y el prototipo muestra 1.000.000.
  - Pedido: F-02 "mayor a 5.000.000 requiere aprobación de la jefa de Compras"
  - Diseño: F-05 "Umbral de aprobación: 1.000.000"
```

Tags (Spanish or English change):

| Spanish | English | Quotes | Consequence |
| --- | --- | --- | --- |
| RESPALDADO | BACKED | one Request, one or more Design | none |
| SIN RESPALDO EN DISEÑO | NOT IN DESIGN | one Request | non-blocking question; flags the element in the extraction |
| SOLO EN DISEÑO | ONLY IN DESIGN | one or more Design | non-blocking question; flags the element in the extraction |
| DIVERGENCIA | DIVERGENCE | one Request, one Design | blocking question |
| CONTRADICCIÓN | CONTRADICTION | two Request (kind `contradicciones`) | blocking question |
| SIN HALLAZGOS | NOTHING FOUND | none (alone in the file) | none; the cross-read is done with nothing found |

Transcribe, never draft: nothing enters without a verbatim quote, and the BA never waives a cross-read through you. A cross-read the BA read and found nothing in is recorded with one claim `- [SIN HALLAZGOS] what was read` (`NOTHING FOUND`), with no quotes. `--skip` waives the cross-read of `--kind` and needs `--reason` with the why; it is also accepted on a stale cross-read. `--accept-new ID --type TYPE --name NAME` takes a `NO ENCONTRADO` candidate of the change's harvest (a `NEW-…` id), or the `GAP-SED-…` question of a `SOLO EN DISEÑO` claim, into the border as a new surface (`nuevo`; the `GAP-SED-…` one is closed with it); `--decline-new ID --reason TEXT` rules it out. `--claims`, `--skip`, `--accept-new` and `--decline-new` are alternatives; `--kind` goes with `--claims` or `--skip`; `--reason` goes with `--skip` or `--decline-new`; `--type` and `--name` go only with `--accept-new`. The cross-read with the baseline is not recorded here: use `/harvest PROJECT_ID --source PATH --change CHG-NNN`.

Every result carries `crosses` (the state of the three), `new_surface_candidates`, `next_step` and a one-line `message`. Report the message, which cross-reads are still missing and which blocking questions the cross-read opened.
