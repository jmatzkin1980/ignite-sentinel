# Backlog de Mejoras del Framework - Ignite Sentinel vNext

Backlog ejecutable del roadmap (`01-roadmap.md`). Cada ítem tiene ID estable `IMP-*`, estado y criterios de aceptación verificables. Estados: `PENDING` (sin empezar) → `IN PROGRESS` → `IMPLEMENTED` (código + tests listos, falta verificar en Windows) → `VERIFIED & PUSHED` (`verify.ps1` verde y pusheado, falta merge) → `VERIFIED & PUSHED & MERGED` (= `DONE`). `DEFERRED` = pospuesto.

Convención de trabajo: branch propio por ítem, PR a `main`, actualizar el estado aquí en el mismo PR. Al cerrar un ítem, registrar fecha y commit/PR en su sección.

---

## HANDOFF PARA CONTINUAR (leer primero — Codex u otra sesión)

Este documento es el **único input necesario** para continuar la implementación. Léelo completo antes de tocar código; complementa `AGENTS.md` y `CLAUDE.md` (reglas no negociables), no los reemplaza.

### Estado al 2026-06-12

- **Frente A–C: COMPLETO y MERGEADO a `main`.** Ítems cerrados: IMP-021, IMP-022, IMP-023, IMP-024, IMP-025, IMP-026, IMP-027, IMP-028, IMP-033 (más Horizontes 0–4 previos). Cada uno tiene su estado `VERIFIED & PUSHED & MERGED` o `DONE` con detalle en su sección.
- **Frente D (memoria): COMPLETO y MERGEADO a `main`.** Ítems cerrados: IMP-032 → IMP-029 → IMP-030 → IMP-031, más los toques menores de IMP-026/028/032.
- **Toques menores pendientes:** ninguno registrado al cierre del 2026-06-12.

#### Qué dejó el Frente D (resumen del estado de la memoria)

El retrieval pasó de léxico-hasheado a una arquitectura por capas, toda local-first y con fallback determinista intacto:

- **Embeddings (IMP-029):** clase `Embedder` autodetectada `model2vec` → `sentence-transformers` → `hash_embedding`; extra opcional `[memory-semantic]`; `embedder`/`embedding_version` registrados en memoria y context packs; `/doctor` reporta el nivel activo. Sin modelo, todo opera igual en `hash_embedding`.
- **Backend LanceDB real (IMP-030):** `lancedb-hybrid` con FTS nativo sobre `text` + Reciprocal Rank Fusion; `merge_insert` incremental por `chunk_id` (no más reescritura O(n²)); scoring `json-hybrid` normalizado como fallback de primera clase; causa de degradación visible en `/doctor`, `/health` y context packs; `why_retrieved` con rank por señal.
- **Chunking estructural (IMP-031):** heading-aware, tablas Markdown indivisibles, anchors `line_start`/`line_end` y `section_path` (retrieval como puntero, no volcado); `/reindex` incremental por `source_hash`/`embedding_version`/`chunking_version` y `/reindex --full` para reconstrucción total.
- **Falsabilidad (IMP-032):** `golden_queries` en los 4 fixtures + `tests/test_evals_retrieval.py` con recall@5/MRR y `summary.by_backend` (`json-hybrid` vs `lancedb-hybrid`); la query cross-lingual es métrica de progreso en modo hash y gate duro con embedder semántico activo.

### Qué falta hacer (orden obligatorio)

- **No quedan ítems funcionales pendientes del Horizonte 5.** Frente A-C y Frente D quedaron verificados, pusheados y mergeados a `main`.
- Los cambios posteriores fuera del backlog original quedan modelados así: **Horizonte 6 — Cierre documental y reconciliación post-merge** (IMP-034/035/036: user guide, README y este backlog) y **Horizonte 7 — Calidad y cobertura de tests** (IMP-037: evals de discovery ampliados). Mantener esa separación: H6 es prosa/estado, H7 es runtime de pruebas.

Cada ítem trae `Problema`, `Alcance`, `Aceptación` y `Afecta` en su sección. El criterio de "hecho" (DoD) es el bloque **Protocolo por ítem** de abajo.

### Protocolo de arranque (cada ítem)

1. Leer este handoff + la sección del ítem (`IMP-0XX`) + las invariantes de la sección 0.b de `03-propuesta-discovery-to-brief.md` (lentes = corazón; maduración gobernada; evidencia o silencio; local-first sin red ni dependencias obligatorias nuevas; BA en control).
2. Crear branch propio desde `main`: `git checkout -b imp-0XX-slug`.
3. Implementar tocando runtime + tests + (si aplica) adapters/skills/doctor/guías, **alineados juntos** (regla de AGENTS.md). Mutar artefactos solo vía CLI; nunca editar outputs a mano.
4. Verificar (Windows, desde la raíz): si el ítem agregó/cambió un comando o una skill, correr primero `python -m sentinel.adapters` (materializa `.kilo/.claude` commands y mirrors `.agents/.claude` de skills); luego `.\verify.ps1` (corre unittest + `/doctor` + evals; debe quedar verde). Regla general: solo necesitás regenerar adapters si tocaste un comando o una skill (p. ej. IMP-031 agregó la opción `/reindex --full` y por eso sí los regeneró; un ítem que solo cambia runtime interno, no).
5. Actualizar el estado del ítem en este archivo (a `IMPLEMENTED` y luego `VERIFIED & PUSHED & MERGED`) y agregar fila al `Registro de cambios` al final.
6. Abrir PR a `main`; mergear tras revisión.

### Definition of Ready/Done por ítem

- **Ready**: existe la sección del ítem con Aceptación verificable; las invariantes están entendidas; hay un fixture o test que lo haga falsable.
- **Done**: criterios de `Aceptación` del ítem cumplidos; `.\verify.ps1` verde (suite + doctor PASS/WARN + evals sin regresión); estado actualizado aquí; sin red en runtime ni dependencias obligatorias nuevas (las nuevas van como extras opcionales en `pyproject.toml`, p. ej. `[memory-semantic]`); fallback determinista intacto para VDIs restringidas (modo `json-hybrid` sigue de primera clase).

### Notas de entorno (importantes)

- **Windows / `python` no encontrado**: es el alias stub de Microsoft Store. Usar el launcher `py` o `.\verify.ps1` (resuelve `.venv`/`python`/`py` solo). Documentado en `CLAUDE.md` → "Verificación obligatoria".
- **Verificación**: `.\verify.ps1` (raíz del repo) corre los tres pasos. `-SkipEvals` para solo tests + doctor.
- `lancedb` es **opcional** (IMP-013): sin él el broker opera en `json-hybrid` y `/doctor` da WARN, no FAIL. IMP-029/030 mantuvieron este fallback de primera clase; los embeddings semánticos (`[memory-semantic]`) y `lancedb-hybrid` son capas opcionales que nunca deben volverse obligatorias en runtime.
- Las branches del Frente A–C y D ya están mergeadas; los próximos cambios deben salir de `main` directo.

### Mapa de superficies del retrieval (referencia — Frente D cerrado)

Esta sección es referencia del retrieval ya implementado (D1–D4 mergeados), útil si un ítem futuro vuelve a tocar memoria:

- Núcleo: `sentinel/memory.py` — `ContextBroker` (`__init__` carga memoria persistida; `index_artifact`; `retrieve` mezcla señales lexical/semantic/vector con RRF cuando hay backend `lancedb-hybrid`; `_lancedb_candidates`; `_connect_lancedb`; `backend`/`lancedb_degraded_reason`/`fts_ready`), `Embedder` autodetectado (`model2vec`→`sentence-transformers`→`hash_embedding`) con `active_embedder_status`, `chunk_texts` heading-aware, `reindex_workspace` incremental por `source_hash`/`embedding_version`/`chunking_version`, `why_retrieved` con ranks por señal.
- Falsabilidad: `tests/test_evals_retrieval.py` + `golden_queries` en los **4** `tests/fixtures/evals/*/answer_key.json`. El reporte agrega `summary.by_backend` (`json-hybrid` vs `lancedb-hybrid`). La query cross-lingual `GQ-XLING-METRIC` se registra como progreso en modo hash y pasa a **gate duro** cuando hay un embedder semántico local activo.
- Reporte: `tests/evals/reports/retrieval_eval_<fecha>.json` (gitignored).
- Doctor: `sentinel/doctor.py` reporta el nivel de embedder activo (IMP-029) y la causa de degradación de LanceDB (IMP-030).
- `pyproject.toml`: extras opcionales `[memory]` (lancedb) y `[memory-semantic]` (embeddings); ninguno obligatorio en runtime.

---

## Horizonte 0 — Higiene del repo

### IMP-001 — Normalizar line endings
- Estado: IN PROGRESS (2026-06-10: `.gitattributes` creado; falta el commit de renormalización `git add --renormalize .` desde la máquina del usuario)
- Problema: 79 archivos aparecen modificados solo por CRLF/LF, contaminando `git status` y los diffs de PR.
- Alcance: agregar `.gitattributes` con política explícita (`* text=auto` + excepciones binarias), renormalizar (`git add --renormalize .`) en un commit dedicado sin cambios funcionales.
- Aceptación: clon limpio en Windows y Linux muestra `git status` vacío; el commit de renormalización no mezcla otros cambios.
- Afecta: `.gitattributes`, posiblemente `user_guide/10-repo-and-branching-strategy.md`.

### IMP-002 — Destino de handoffs en la raíz
- Estado: DONE (2026-06-10)
- Problema: `general-proyecto.md` e `ignite_vnext_final_handoff.md` estaban sin trackear en la raíz del repo.
- Decisión del usuario: no forman parte del proyecto; su lugar es la carpeta personal de handoffs fuera del repo. Eliminarlos de la raíz (o ignorarlos) y no versionarlos. `docs/evolution/` es la memoria operativa dentro del repo.
- Aceptación: `git status` sin archivos huérfanos en raíz.

### IMP-003 — Política para `.7z` y launchers no trackeados
- Estado: DONE (2026-06-10: reglas en `.gitignore` para `*.7z`, `*.zip` y residuos locales; política documentada en `user_guide/10-repo-and-branching-strategy.md`)
- Problema: pendiente heredado del handoff §21; archivos `.7z` y launchers pueden aparecer en working tree sin regla definida.
- Alcance: regla en `.gitignore` y nota en `user_guide/10-repo-and-branching-strategy.md`.
- Aceptación: regla escrita y aplicada; ningún binario accidental commiteable.

### IMP-004 — Smoke test de onboarding desde clon limpio
- Estado: DONE (2026-06-10: checklist en `user_guide/06-installation-vscode.md` con corrida registrada — copia limpia, 17 tests OK, doctor PASS, gates verificados)
- Problema: el flujo completo desde clon limpio/ZIP en otra carpeta nunca se validó de punta a punta (handoff §21).
- Alcance: ejecutar y documentar checklist: clonar → `/doctor` → instalar deps → `/init` → `/ingest` fixture → `/maturity` → `/specs` → `/backlog` → `/validate`. Idealmente automatizar como script o test de integración opcional.
- Aceptación: checklist reproducible en `user_guide/06-installation-vscode.md` o nuevo doc; ejecución registrada con resultado PASS.

## Horizonte 1 — Calidad de discovery y generación

### IMP-015 — Motor de discovery más inquisitivo (PRIORIDAD #1 del usuario)
- Estado: DONE (2026-06-11, branch `imp-015-inquisitive-discovery`)
- Implementado: tier inquisitivo en `detect_gaps` — para superficies mencionadas sin contracara (pantalla sin journey/estados, API sin contratos/fallas, integración sin arquitectura), el gap dispara igual y ancla la pregunta a la mención detectada (`evidence_mention`). `gaps.md` muestra "Evidencia que dispara la pregunta" por gap y una columna "Disparador detectado" en la tabla de trazabilidad que sobrevive a `/gaps`. Falso positivo de GAP-OBJECTIVE corregido (tokens en inglés). Resultado en evals: `avg_target_recall` 0.00 → 1.00, recall 1.00, 0 falsos positivos; 3 tests unitarios nuevos (suite 20 OK).
- Problema: el mayor dolor declarado es tomar un requerimiento inicial y detectar con profundidad lo NO mencionado pero necesario para madurarlo. Los gaps actuales son determinísticos por lente y pueden quedarse en lo genérico; falta presión inquisitiva sobre lo implícito del requerimiento concreto.
- Alcance: profundizar `discovery.py` para que cada lente derive preguntas específicas del contenido ingestado (no solo checklist fija): detectar entidades, flujos, integraciones, actores y reglas mencionados y preguntar sistemáticamente por su contracara ausente (origen de datos, acceso, permisos, estados de error, volúmenes, edge cases, ciclo de vida, dependencias). Cada gap mantiene el formato human-friendly: ID, pregunta concreta, ejemplo de respuesta esperada, owner, evidencia que lo dispara.
- Aceptación: con un fixture realista, los gaps generados incluyen preguntas ancladas a evidencia específica del input (citando qué disparó cada pregunta), no solo plantilla genérica; comparación antes/después documentada; tests con casos de detección. Métrica: subir `avg_target_recall` del eval harness (baseline 0.00) y eliminar los `known_false_positives`, sin bajar el recall 1.00 de `must_fire`.
- Afecta: `sentinel/discovery.py`, templates de gaps, `tests/`, skill `sentinel-discovery`, guías.

### IMP-016 — Suite de fixtures sintéticos realistas
- Estado: DONE (2026-06-10: 3 fixtures en `tests/fixtures/evals/` — dashboard EN, integración EN, portal ES — con answer keys empíricos que documentan `must_fire`, `must_not_fire`, `known_false_positives` y `target_fire`; README con criterio para agregar fixtures)
- Problema: la evolución se valida con data sintética hasta que el framework sea sólido y agnóstico, pero los fixtures de test eran mínimos. Sin requerimientos sintéticos realistas (con omisiones típicas de cliente real) no se puede medir si IMP-015/005/006 mejoran de verdad.
- Alcance: crear 2-3 requerimientos sintéticos de dominios distintos con omisiones deliberadas y catalogadas; usarlos como banco de prueba de discovery y generación. Solo contenido inventado, sin rastro de clientes reales.
- Aceptación: fixtures versionados bajo `tests/fixtures/`, cada uno con su "answer key" de gaps esperados; tests que midan cobertura de detección contra ese answer key.

### IMP-013 — Modo degradado sin LanceDB (prioridad elevada)
- Estado: DONE (2026-06-11, branch `imp-013-lancedb-optional`, PR #3)
- Implementado: `lancedb` movido a extra opcional `[memory]`; `/doctor` da WARN con detalle del modo degradado (veredicto PASS sin lancedb); broker en `json-hybrid` determinístico con lifecycle completo; 2 tests nuevos; documentado en guías 06/09, README y CLAUDE.md. Además: `docs/` retirado del repo público (gitignored, memoria local).
- Problema: `/doctor` falla sin `lancedb` aunque el broker tiene fallback JSON funcional. El usuario confirmó que en algunas VDIs de cliente NO puede instalarlo, por lo que el modo degradado debe ser un escenario soportado de primera clase, no un edge case.
- Decisión orientadora: lancedb pasa a opcional; `/doctor` lo reporta como WARN con capacidades degradadas explícitas y el broker opera en modo JSON determinístico. Alinear `pyproject.toml`, doctor, tests y `user_guide/09-secure-environments.md`.
- Aceptación: comportamiento definido, documentado y testeado en ambos entornos (con y sin lancedb); los 17 tests pasan en ambos modos o el modo sin lancedb tiene suite propia.
- Afecta: `sentinel/doctor.py`, `sentinel/memory.py`, `pyproject.toml`, `tests/`, guías.

### IMP-005 — Extracción mejorada de FRs, personas y KPIs
- Estado: DONE (2026-06-11, branch `imp-005-evidence-extraction`)
- Implementado: funciones de extracción determinística en `discovery.py` (`extract_personas`, `extract_functional_signals`, `extract_metric_signals`) citando oraciones textuales del raw input (`00_raw/00_client_requirement/`, fallback al requirement). El PRD incluye "Evidence-Backed Personas", "Evidence-Backed Functional Statements" (FR-E*) y KPI-01 poblado con la métrica detectada y su evidencia, citando `REQ-001`. Sin señal: `[PENDING INPUT]` + gap correspondiente (nunca inventa). 2 tests nuevos (suite 24 OK).
- Problema: PRD/specs caen en scaffolding genérico aun cuando la evidencia ingestada trae señales reales (handoff §21).
- Alcance: mejorar `discovery.py`/`generation.py` para extraer y citar FRs, personas y KPIs desde evidencia; mantener `[PENDING INPUT]` cuando no hay señal (nunca inventar).
- Aceptación: con fixture realista, el PRD generado contiene FRs/personas/KPIs citando evidencia fuente; tests nuevos cubren extracción positiva y caso sin evidencia.
- Afecta: `sentinel/discovery.py`, `sentinel/generation.py`, `tests/`, skills `sentinel-specs`, guías.

### IMP-006 — Validación semántica profunda en `/validate`
- Estado: DONE (2026-06-11, branch `imp-006-semantic-validation`)
- Implementado: `score_artifact_text` + `semantic_quality_report` en `validation.py`. `/validate` agrega bloque `semantic_quality` (score y clasificación `evidence-backed`/`mixed`/`scaffolding` para brief, PRD y specs, contando señales de evidencia vs markers pending) y lista `warnings` no bloqueante — el verdict estructural no cambia. Documentado en command reference y skill sentinel-health. Test nuevo cubre los 3 niveles y el flujo integrado (suite 25 OK).
- Problema: `/validate` revisa estructura, prefijos y secciones, pero no completitud semántica (handoff §21).
- Alcance: detectar secciones con contenido placeholder/genérico vs. pobladas con evidencia; reportar score por artefacto; no bloquear, advertir.
- Aceptación: `/validate` distingue un PRD scaffolding de uno poblado en fixtures; salida documentada en `user_guide/01-command-reference.md`.
- Afecta: `sentinel/validation.py`, `tests/`, guías, skill `sentinel-health`.

### IMP-007 — Scoring y coverage en context packs
- Estado: DONE (2026-06-11, branch `imp-007-context-pack-scoring`)
- Implementado: `specs_generation.json` con `coverage_map`/`coverage_score` y `evidence_strength` + `result_count` por sección; `implementation_readiness.json` con `readiness_score` por story (1.0 = ready, decrece por blocker) y bloque `summary` (`stories_ready`, `avg_readiness_score`, `pending_context_by_domain`). Test de esquema integrado al lifecycle (suite 26 OK). Documentado en artifact reference y skill sentinel-backlog.
- Problema: `specs_generation.json` e `implementation_readiness.json` carecen de scoring, coverage map y evidencia rica por sección (handoff §21).
- Alcance: agregar por sección/story: score de evidencia, fuentes citadas, contexto pendiente cuantificado.
- Aceptación: ambos JSON incluyen los campos nuevos; agentes downstream pueden filtrar stories por readiness score; tests de esquema.
- Afecta: `sentinel/generation.py`, `sentinel/schemas/`, `tests/`, skill `sentinel-backlog`.

### IMP-008 — Métricas de madurez cuantificadas
- Estado: DONE (2026-06-11, branch `imp-008-maturity-metrics`)
- Implementado: `maturity_metrics()` en `maturity.py` — `gap_closure_rate`, `open_gaps_by_severity`, `artifact_evidence_scores` (reusa el scoring de IMP-006), `maturity_score` combinado (0-1) y `trend_vs_previous_run` persistido en `state.json` entre corridas de `/maturity`. `/status` expone el bloque `maturity_metrics`. Documentado en command reference y skill sentinel-maturity. Test integrado (suite 27 OK).
- Problema: `/maturity` y `/status` informan estado cualitativo; falta una medida de cuánta evidencia respalda el brief/PRD.
- Alcance: porcentaje de secciones con evidencia vs. pendientes, conteo de gaps por severidad, tendencia entre corridas.
- Aceptación: `/status` muestra métricas; documentado en command reference; tests.
- Afecta: `sentinel/maturity.py`, `sentinel/status.py`, `tests/`, guías.

## Horizonte 2 — Robustez del lifecycle vivo

### IMP-009 — Tests de staleness de backlog
- Estado: DONE (2026-06-11, branch `horizonte-2-robustez`)
- Implementado: test E2E que simula cambio de contexto de Tecnología post-backlog y verifica: health pasa a DIRTY con finding que ahora NOMBRA los dominios cambiados, `/backlog` queda bloqueado, y `/reindex` + `/maturity` + `/backlog` restauran CLEAN. Bonus: el test expuso y se corrigió un bug preexistente — regenerar `/backlog` rompía porque `add_node` acumulaba nodos duplicados con IDs nuevos (US-006..) mientras los archivos reiniciaban numeración; ahora `add_node` hace upsert por (type, path) y los trace IDs son estables entre regeneraciones (suite 28 OK).
- Problema: la regla "contexto de dominio cambió después del backlog → `/health` marca stale" existe, pero su cobertura de test es limitada.
- Alcance: tests que simulen cambio de contexto post-backlog y verifiquen detección, mensaje y recomendación de `/reindex` + `/backlog`.
- Aceptación: tests nuevos verdes; regresión protegida.
- Afecta: `tests/`, posiblemente `sentinel/health.py`.

### IMP-010 — Matices en cierre de gaps
- Estado: DONE (2026-06-11, branch `horizonte-2-robustez`)
- Implementado: clasificación con matices en `apply_gap_responses` — respuesta sustantiva + decisión confirmada cierra; respuesta vaga (`TBD`, deferral, <15 chars útiles) NUNCA cierra aunque esté "confirmada" (queda PARTIALLY_CLOSED con `resolution_note` "confirmed-but-vague"); respuesta sustantiva + decisión pendiente queda ANSWERED (visible y bloqueante si es severa); respuesta sin estado de decisión reconocible queda PARTIALLY_CLOSED "ambiguous". `count_gaps` cuenta ANSWERED por separado (rama muerta corregida), readiness lo considera, y el reporte de resolución muestra sección "Answered (Awaiting Confirmation)" con notas. Test con respuestas mixtas de 4 tipos (suite 29 OK).
- Problema: `/resolve-gaps` cierra solo confirmado/no-aplica; los estados intermedios (respuesta ambigua, confirmación pendiente, respuesta parcial) merecen representación más rica.
- Alcance: estados intermedios visibles en `gaps.md` y `state.json`; reglas de qué bloquea maturity y qué no.
- Aceptación: fixture con respuestas mixtas produce estados correctos; `/maturity` respeta los bloqueos; tests.
- Afecta: `sentinel/gap_resolution.py`, `sentinel/maturity.py`, `tests/`, templates de gaps, skill `sentinel-gap-response`.

### IMP-011 — Diff visible de regeneración
- Estado: DONE (2026-06-11, branch `horizonte-2-robustez`)
- Implementado: `record_regeneration_diff` en `generation.py` — al regenerar `prd.md`, `specs.md` o `EPIC-001.md` con contenido distinto, escribe `07_changes/04_regeneration/regen-NNN-<artefacto>.md` con CHG disparador, líneas +/- y secciones agregadas/quitadas; nodo `regeneration_diff` (DEC) con edge `triggers_regeneration` desde el CHG, indexado en memoria. Primera generación o contenido idéntico: sin diff. `04_regeneration/` excluido del hash de freshness de dominio (es metadata, no contexto). Test E2E sync→regeneración→diff trazado (suite 30 OK).
- Problema: tras `/sync` + regeneración, no queda un resumen legible de qué cambió en artefactos downstream.
- Alcance: al regenerar un artefacto impactado, registrar resumen de cambios (secciones agregadas/modificadas/eliminadas) en `07_changes/` y referenciarlo en el impact report.
- Aceptación: tras un sync con impacto, existe artefacto de diff legible y trazado al nodo `CHG`; tests.
- Afecta: `sentinel/sync.py`, `sentinel/generation.py`, `tests/`, guías.

## Horizonte 3 — Experiencia y adopción

### IMP-012 — Chat-first refinado
- Estado: DONE (2026-06-11, branch `horizonte-3-4-adopcion-estandares`)
- Implementado: tabla Intent-To-Command Map en `user_guide/11-chat-commands.md` (11 intenciones canónicas → secuencias, con qué reportar en cada caso y reglas para cualquier superficie de agente); referencia desde skill `sentinel-command-router` y `CLAUDE.md`. Las secuencias citan las capacidades nuevas (maturity_score, semantic_quality, readiness_score, regeneration diffs, staleness por dominio).
- Problema: el mapeo de lenguaje natural a secuencias de comandos depende de las instrucciones del agente; conviene consolidar patrones de intención y ejemplos.
- Alcance: ampliar `user_guide/11-chat-commands.md` y `12-scenarios.md` con tabla intención→secuencia; alinear skills Codex y agentes Kilo.
- Aceptación: escenarios de prueba en guía; adapters actualizados de forma consistente.
- Afecta: `user_guide/`, `.codex/skills/sentinel-command-router/`, `.kilo/`.

### IMP-014 — Adapter/guía para Claude
- Estado: DONE (2026-06-10, branch `feature/claude-adapter`)
- Implementado: `.claude/commands/` con 20 slash commands (espejo 1:1 de `.kilo/commands/`, incluye `/sentinel` como fallback), routing de chat commands en `CLAUDE.md` (cubre Claude Code en VS Code/CLI y Claude Desktop/Cowork), guía `user_guide/13-claude-adapter.md`, checks de adapter Claude en `/doctor` (`REQUIRED_CLAUDE_COMMANDS` + paths), assertions en tests, menciones en README, índice de user guide y AGENTS.md.
- Pendiente menor: skills locales `.claude/skills/` quedaron fuera de alcance por decisión (CLAUDE.md cubre la guía de workflow); reevaluar si el uso real lo pide.

## Horizonte 4 — Alineación con estándares de agentes AI (2026)

Contexto: auditoría y research del 2026-06-10. Agent Skills (SKILL.md) es estándar abierto desde dic-2025, leído por 32+ herramientas (Codex usa `.agents/skills/`, Claude Code usa `.claude/skills/`); AGENTS.md es estándar de la Linux Foundation leído por 20+ agentes (ya lo tenemos); la práctica de evals con answer keys y harness es el método establecido para medir calidad de agentes; MCP local (stdio) es la vía estándar para exponer herramientas a cualquier cliente.

### IMP-017 — Exponer Sentinel como servidor MCP local (stdio)
- Estado: DONE (2026-06-11, branch `horizonte-3-4-adopcion-estandares`)
- Implementado: `sentinel/mcp.py` con FastMCP — 18 tools (`sentinel_init` ... `sentinel_validate`) que ejecutan el CLI in-process capturando salida JSON; los gates devuelven errores estructurados con la razón. 100% local (stdio, sin red). Dependencia opcional `[mcp]`; sin ella todo lo demás funciona y `/doctor` da WARN. `--describe` lista los tools sin levantar el server. Config de Claude Desktop/Code documentada en guía 13; mención en README. Test cubre catálogo, ejecución vía `run_cli`, error de gate y registro FastMCP (suite 33 OK).
- Problema: cada IDE nuevo requiere un adapter de chat commands propio. MCP es ya el protocolo estándar para que cualquier cliente (Claude Desktop, Claude Code, VS Code, Cursor, Codex) invoque herramientas.
- Alcance: servidor MCP stdio repo-local (`python -m sentinel.mcp`) que exponga los comandos del lifecycle como tools con schemas (init, ingest, gaps, resolve_gaps, maturity, brief, sync, specs, backlog, quality, trace, health, validate, status, retrieve). 100% local: stdio, sin red, compatible con local-first privacy. Los gates se devuelven como errores estructurados con next-step.
- Aceptación: configurable en Claude Desktop/Code y al menos otro cliente MCP; smoke test del lifecycle vía MCP; documentado en user guide; `/doctor` lo verifica.
- Afecta: `sentinel/` (módulo nuevo), `pyproject.toml` (dependencia opcional `mcp`), tests, guías, doctor.

### IMP-018 — Converger skills al estándar abierto Agent Skills
- Estado: DONE (2026-06-11, branch `horizonte-3-4-adopcion-estandares`)
- Implementado: `.codex/skills/` queda como fuente canónica; `python -m sentinel.adapters` espeja las 12 skills (incluidos `references/`) en `.agents/skills/` (estándar leído por Codex, Cursor, Gemini CLI, etc.) y `.claude/skills/` (Claude Code). `skills_out_of_sync()` detecta drift, test en la suite, checks de directorios en `/doctor`, documentado en guía 10 y README.
- Problema: las 12 skills viven solo en `.codex/skills/`. El formato SKILL.md ya es estándar multi-herramienta, pero cada agente las busca en su directorio (`.agents/skills/` Codex y otros, `.claude/skills/` Claude Code).
- Alcance: definir fuente canónica única de skills y materializarlas en los directorios estándar (copia generada o referencia, según soporte de cada tool). Las skills quedan utilizables por Claude Code, Codex, Cursor, Gemini CLI y demás lectores del estándar sin trabajo extra.
- Aceptación: misma skill visible y funcional desde Claude Code y Codex; sin divergencia de contenido entre directorios (verificado por test o script); doctor actualizado.
- Afecta: `.codex/skills/`, `.claude/skills/`, `.agents/skills/`, doctor, tests, guías.

### IMP-019 — Fuente única para adapters de comandos
- Estado: DONE (2026-06-11, branch `horizonte-3-4-adopcion-estandares`)
- Implementado: manifest canónico `sentinel/templates/commands_manifest.json` (20 comandos: name, description, kilo_agent, body) + módulo `sentinel/adapters.py` con generador (`python -m sentinel.adapters`) que materializa `.kilo/commands/` y `.claude/commands/` de forma byte-equivalente a los actuales. `out_of_sync()` detecta drift; test de sincronía en la suite; `/doctor` toma las listas de comandos requeridos del manifest (una sola fuente) y verifica su existencia. Flujo documentado en guía 10. Codex sigue ruteando por patrón (no necesita archivos por comando).
- Problema: los 20 comandos están triplicados (`.kilo/commands/`, `.claude/commands/`, router Codex). Cada cambio de lifecycle exige tocar 3+ lugares; el riesgo de divergencia crece con cada plataforma nueva.
- Alcance: manifest único (p. ej. `sentinel/templates/commands.yaml`) con descripción, uso y guidance por comando, más generador que materializa los adapters por plataforma. Test que falla si un adapter quedó desincronizado del manifest.
- Aceptación: regenerar adapters desde manifest produce los archivos actuales (o mejores); test de sincronía en la suite; documentado el flujo en `10-repo-and-branching-strategy.md`.
- Afecta: `sentinel/templates/`, script generador, `.kilo/`, `.claude/`, `.codex/`, tests.

### IMP-020 — Eval harness para calidad de discovery
- Estado: DONE (2026-06-10: `tests/evals/run_discovery_evals.py` corre el lifecycle sobre cada fixture, compara contra answer keys y emite reporte JSON por corrida en `tests/evals/reports/` (gitignored). Baseline registrado: recall 1.00, target_recall 0.00, 1 falso positivo conocido (GAP-OBJECTIVE en crm-billing-sync). Exit 1 solo ante regresiones nuevas)
- Problema: IMP-016 aporta fixtures con answer keys, pero faltaba el harness que corra evals de punta a punta y agregue métricas (precision/recall de gaps detectados, cobertura por lente, regresiones entre versiones), siguiendo la práctica establecida de evals para agentes.
- Alcance: runner local que ejecute el lifecycle sobre cada fixture, compare contra answer keys y emita reporte de scores. Determinístico y local-first.
- Aceptación: un comando corre todos los evals y produce reporte comparable entre corridas; integrado a la verificación pre-PR para cambios de discovery/generation.
- Depende de: IMP-016.

## Horizonte 5 — Discovery semántico y memoria (propuesta 03)

Fuente: `docs/evolution/03-propuesta-discovery-to-brief.md` (APROBADA por el usuario, 2026-06-11). Cuatro frentes. Reglas no negociables vigentes (sección 0.b de la propuesta): el modelo de lentes es el corazón y conocimiento propio; maduración gobernada (no generación); evidencia o silencio explícito; local-first (sin red en runtime ni dependencias obligatorias nuevas); el BA en control. Orden sugerido A–C: IMP-027 → IMP-033 → IMP-021 → IMP-022 → IMP-024 → IMP-025 → IMP-023 → IMP-026 → IMP-028. Frente D en paralelo: IMP-032 → IMP-029 → IMP-030 → IMP-031. Cada ítem: branch propio + PR, surfaces de 3.b alineadas, evals sin regresión.

### Frente A — Discovery semántico con el agente como motor

### IMP-021 — Protocolo de análisis agéntico (`/annotate`)
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-021-annotate`, PR #12, merge `3be54f4`). Verificación final en Windows: adapters regenerados + `.\verify.ps1` en verde; evals sin regresión.
- Implementado: nuevo comando `/annotate PROJECT_ID --source ANALYSIS.json`. El runtime (`discovery.apply_annotation`) recibe un JSON con `gaps` (cada uno: `id` `GAP-*`, `lens` declarado en `sentinel/lenses/`, `severity` en rango, `question`, y `evidence` que debe ser cita **textual** del raw input) más `ambiguities`/`assumptions` opcionales. Validación dura (`validate_agent_gaps`): rechaza id malformado, lente no declarado (via `lens_registry.known_lenses`), severidad fuera de rango, falta de pregunta, evidencia ausente o **no encontrada verbatim** en `00_raw/` (el agente cita, nunca inventa — invariante #3). Gaps válidos se etiquetan `origin: agent`, se mergean en `gaps.md` (nueva columna `Origin` en la trace table, con round-trip en `parse_gap_rows`/`render_gaps`), se registran en `01_discovery/agent_annotation_log.md` + `annotations/`, y agregan nodo de trazabilidad `agent_annotation` (raw→annotation `annotated_by`, annotation→gap_report `raises`). `state.json` gana `gap_counts.agent_origin` (visible en `/status`). Los gaps agénticos respetan el lifecycle normal (resolve/maturity/gates). Superficies alineadas: `discovery.py`, `cli.py`, `protocols.py` (annotate en MUTATING), `gap.schema.json` (campo `origin`/`lens`/`question`/`evidence`), `ids.py` (`agent_annotation`→DISC), `mcp.py` (`sentinel_annotate`, 19 tools), `commands_manifest.json` (+ `.kilo/.claude` regenerados via `python -m sentinel.adapters`), skill canónica `.codex/skills/sentinel-annotate/` (mirrors via adapters), doctor (REQUIRED_COMMANDS + REQUIRED_CODEX_SKILLS), `user_guide/01`,`02`,`11`, AGENTS/CLAUDE. Tests: `tests/test_annotate.py` (validación, merge+origin+trazabilidad+status, round-trip en `/gaps`, skip de duplicados, gap agéntico resoluble, rechazo de evidencia fabricada, y la prueba falsable del fixture). Eval: fixture `expense-approval/annotation.json` + `run_discovery_evals.py` con `apply_annotation` opt-in (default intacto → baseline léxico sin regresión) y nueva métrica aditiva `avg_target_recall_with_annotations`; con `/annotate`, `target_recall` de expense-approval pasa de 0.00 a 1.00 (los 5 gaps semánticos). `test_core_flow` actualizado (21 comandos, 19 tools MCP).
- Nota de cierre Codex: se mantuvo el diseño original de agente-propone/runtime-valida; el cambio contra el plan fue acotar la persistencia a gaps con evidencia verbatim y `origin: agent`, sin permitir escritura libre del agente en artefactos finales.
- Problema: el escrutinio sigue siendo léxico (`detect_gaps()` decide por presencia/ausencia de tokens); el agente que opera el framework es el único componente con capacidad semántica pero no tiene canal sancionado para persistir su análisis. El techo del enfoque por keywords ya se alcanzó (`target_fire` semántico en 0.00).
- Alcance: nuevo comando que recibe del agente un análisis estructurado del input crudo (gaps semánticos propuestos con cita textual de evidencia, lente, severidad, pregunta; ambigüedades; supuestos implícitos). El CLI valida contra `gap.schema.json`, marca `origin: agent` (vs `origin: checklist`), mergea en `gaps.md` y registra en trazabilidad. Equivalente Ignite del `/clarify` de spec-kit. El runtime sigue siendo la autoridad que valida, persiste y gobierna; local-first se mantiene.
- Aceptación: un análisis agéntico válido se mergea en `gaps.md` con `origin: agent` y aparece en trazabilidad y `/status`; uno inválido (sin cita textual, lente inexistente, severidad fuera de rango) es rechazado con error claro; los gaps agénticos respetan el lifecycle normal (resolve/maturity/gates); evals previos sin regresión y al menos un fixture pasa de `target_fire` 0 a >0.
- Afecta: `sentinel/discovery.py`, `cli.py`, `gap.schema.json`, `commands_manifest.json` + regeneración de adapters, `mcp.py` (tool `sentinel_annotate`), skill `sentinel-annotate`, tests, evals, `user_guide/01`, `02`, `11`.

### IMP-022 — Gaps como elicitación, no como enunciado
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-022-gaps-as-elicitation`, PR #13, merge `2297969`). `.\verify.ps1` en verde; roundtrip render→parse confirmado.
- Implementado: dos funciones nuevas en `discovery.py` — `unblocks_for_gap(gap_id, language)` (mapea cada gap a la sección de brief/PRD/spec que consume la respuesta, invirtiendo lo que vivía implícito en las tablas "PRD Coverage Readiness"/"Backlog Readiness Signals" de `maturity.py`) y `expected_format_for_gap(gap_id, language)` (forma esperada de una respuesta que cierra el gap, distinta del ejemplo trabajado). Ambas con dict EN/ES por gap + default. `render_gap_response_section` (ES+EN) ahora expone por gap los tres factores de elicitación: **por qué importa (riesgo si queda abierto)** (reusa `why_gap_matters`), **qué desbloquea esta respuesta** y **formato de respuesta esperado**, además de la pregunta y el ejemplo. `context_requests.lens_checks_section` enriquece cada check del lente con `Unblocks:`/`Desbloquea:` y `Expected format:`/`Formato esperado:` (el `why` del lens JSON ya estaba). La tabla de trazabilidad NO cambia, así que `parse_gap_rows` (posicional) queda intacto y `/resolve-gaps` sigue parseando sin cambios para el usuario. Tests nuevos en `tests/test_gap_elicitation.py` (secciones exponen los 3 factores EN/ES, roundtrip render→parse intacto EN/ES, mapeo específico vs default, context-request incluye unblocks+formato).
- Nota de cierre Codex: no se cambió el contrato de parseo de `/resolve-gaps`; el enriquecimiento quedó en render y context-request para mejorar la respuesta humana sin romper tablas existentes.
- Problema: `gaps.md` y los context-request packs formulan la pregunta pero no explican por qué importa, qué desbloquea downstream ni qué formato de respuesta cierra el gap — los tres factores que más determinan la calidad de respuesta del cliente.
- Alcance: enriquecer el render de `gaps.md` y los context-request packs: por gap, además de la pregunta, *por qué importa* (riesgo si queda abierto), *qué desbloquea* (qué sección de brief/PRD/spec lo consume) y *formato de respuesta esperado*. El mapeo gap→sección ya existe implícito en las tablas "PRD Coverage Readiness"/"Backlog Readiness Signals"; se invierte y mueve al origen. Atención: `parse_gap_rows` es posicional — actualizar parser y render juntos.
- Aceptación: cada gap en `gaps.md` y en los context-requests expone por-qué/qué-desbloquea/formato-esperado; `/resolve-gaps` sigue parseando respuestas sin cambios para el usuario; tests de roundtrip render→parse verdes.
- Afecta: `discovery.py` (render_gaps), `context_requests.py`, plantillas, tests.

### IMP-023 — Técnicas de elicitación avanzada (`/challenge`)
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-023-challenge`, PR #16, merge `e1ee989`). Verificación en Windows: `python -m sentinel.adapters` + `.\verify.ps1` en verde (suite OK, doctor PASS, evals sin regresión).
- Implementado: comando `/challenge PROJECT_ID --source FINDINGS.json`. El runtime reutiliza la validación de IMP-021 (`validate_agent_gaps` ahora parametrizado con `origin`, default `agent`): `apply_challenge` valida cada hallazgo (lente declarado, severidad, evidencia verbatim), lo tagea `origin: challenge`, lo mergea en `gaps.md` y escribe un `01_discovery/challenge_report.md` versionable que agrupa hallazgos por lente con la técnica que los disparó (pre-mortem, role-play, assumption-inversion) + narrativa de pre-mortem y supuestos invertidos. Trazabilidad: nodo `challenge_report` (DISC), edges `challenged_by` (raw→nodo) y `raises` (nodo→gap_report); indexado en memoria; `gap_counts.challenge_origin` en `/status`. Source archivado en `01_discovery/challenges/`. Las técnicas se ejecutan por lente (invariante #1); el agente propone con evidencia, nunca escribe directo (invariante #5). Superficies alineadas: `discovery.py` (apply_challenge + render_challenge_report + origin param), `cli.py` (comando + dispatch), `protocols.py` (MUTATING), `commands_manifest.json` (+ adapters a regenerar), `mcp.py` (`sentinel_challenge`, 20 tools), `doctor.py` (REQUIRED_COMMANDS + REQUIRED_CODEX_SKILLS), skill canónica `.codex/skills/sentinel-challenge/`, `user_guide/01`,`02`,`11`. Tests: `tests/test_challenge.py` (validación origin challenge, rechazo de evidencia fabricada, merge+report+trazabilidad+counts, origin sobrevive a `/gaps`, CLI) + conteos actualizados en `test_core_flow` (22 comandos, 20 tools MCP).
- Nota de cierre Codex: se implementó como extensión del canal validado de IMP-021, no como comando que escribe conclusiones directo; esto preserva el control BA/runtime y evita bypass de evidencia.
- Depende de: IMP-021.
- Problema: falta materializar el "entender lo que no se está mencionando" con técnicas BMAD-style aplicadas al requirement maduro-en-progreso.
- Alcance: comando + skill que aplica pre-mortem ("el proyecto falló a 6 meses: ¿qué no preguntamos?"), role-play por lente (operador, auditor, atacante) e inversión de supuestos. Output: `01_discovery/challenge_report.md` versionable, cuyas conclusiones entran como gaps `origin: challenge` vía el protocolo de IMP-021. Las técnicas se ejecutan por lente (invariante #1), no como personas genéricas.
- Aceptación: `/challenge` produce `challenge_report.md` trazado e indexado; sus hallazgos entran como gaps `origin: challenge` vía la validación de IMP-021 (nunca escritura directa); ejecución por lente.
- Afecta: módulo nuevo o extensión de `discovery.py`, `cli.py`, `commands_manifest.json` + regeneración, `mcp.py` (tool `sentinel_challenge`), skill de elicitación, trazabilidad e indexación, tests, `user_guide/02`, `03`, `11`.

### IMP-033 — Base de conocimiento de lentes versionada y editable
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-033-lens-knowledge-base`, PR #11, merge `f9b4ba4`). Verificación final en Windows integrada al cierre del Frente A-C.
- Implementado: (a) fuente declarativa `sentinel/lenses/*.json` (7 lentes: business, product, quality, technical, compliance, delivery, design; 26 checks) con schema por check (`id`, `severity`, `rule`, `evidence_scope`, `tokens`/`triggers`+`counterparts`/`suppressors`, `why`). (b) Loader `sentinel/lens_registry.py` (orden de lentes determinista, cache, override de directorio para tests). (c) `detect_gaps()` refactorizado para consumir el registry vía dispatch por `rule` (`absent_tokens` / `mention_without_counterpart` / `metric_without_source`) — **output idéntico** al checklist hardcodeado verificado celda a celda (id, lente, severidad, evidence_mention) sobre los 4 fixtures. (d) `render_context_request` lista los checks del lente del dominio desde la misma fuente (`lens_checks_section`), cumpliendo "un check nuevo aparece en gaps.md y en el context-request". (e) `pyproject.toml` incluye `lenses/*.json` como package-data. (f) Test `tests/test_lens_registry.py` (4 tests) incluye el de aceptación: agregar un check editando solo el JSON lo hace aparecer en `detect_gaps` y en el context-request sin tocar Python. (g) `user_guide/02` documenta la base y el apartado "cómo agregar conocimiento a un lente".
- Verificación (2026-06-11, filesystem escribible): suite 41 tests (los 4 nuevos verdes; único fallo el CRLF de skills-sync, preexistente de IMP-001), `/doctor` PASS (0 failures, 4 warnings), eval harness sin regresión (`avg_target_recall=0.75`, baseline intacto → comportamiento idéntico). Sin dependencias nuevas, sin red: JSON stdlib.
- Nota de cierre Codex: se eligió JSON versionado en `sentinel/lenses/*.json` en vez de YAML para evitar dependencias nuevas y sostener local-first estricto.
- Recomendación de orden: hacerlo antes de IMP-021/022/023 (las skills agénticas consumen esta fuente única).
- Problema: el conocimiento de los lentes vive hardcodeado en `discovery.py::detect_gaps()` (checks, severidades, tokens, reglas inquisitivas) y en prompts de `context_requests.py`; el equipo no puede volcar experiencia sin tocar Python y las skills de agente pueden divergir del checklist determinista.
- Alcance: externalizar a una fuente declarativa versionada (`sentinel/lenses/*.yaml` o `.json`): por lente, qué se escruta, por qué, con qué severidad, qué evidencia lo cierra y qué pregunta dispara. Runtime y skills agénticas (IMP-021/022/023) consumen la misma fuente. Materialización técnica del invariante #1 de la sección 0.b.
- Aceptación: agregar un check nuevo a un lente editando solo el archivo del lente (sin tocar Python) y verlo aparecer en `gaps.md` y en el context-request del dominio; evals del checklist actual sin regresión (el checklist actual se convierte en fixture-baseline de la nueva fuente).
- Afecta: `discovery.py`, `context_requests.py`, nueva carpeta de definiciones de lentes, skills, tests, evals, `user_guide/02` + nuevo apartado "cómo agregar conocimiento a un lente".

### Frente B — Project brief compilado desde evidencia

### IMP-024 — Brief compiler
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-024-brief-compiler`, PR #14, merge `fa9c5b8`). `.\verify.ps1` en verde; evals con `avg_brief_target_coverage=1.00` y `baseline_ok=True`.
- Implementado: `materialize_project_brief` carga el raw input (`raw_input_text`) y las respuestas confirmadas de gaps cerrados (`parse_gap_answers` sobre las tablas Gap Resolution Seeds/Decisions) y las pasa a `render_project_brief`, que ahora delega las secciones narrativas 1–6 en `compile_brief_sections`. La compilación extrae con cita desde el input: nombre de iniciativa (H1), dolor (`primary_requirement`), objetivo/resultado (cue-based), métrica (`extract_metric_signals`), actores (`extract_personas`), as-is (cues today/hoy/a mano…), to-be (`extract_functional_signals`), y scope in/out. Cada afirmación cita la evidencia textual + `00_raw/`; una sub-parte sin evidencia referencia su gap (`GAP-METRIC-SOURCE`, `GAP-PRODUCT-ASIS-TOBE`, `GAP-SCOPE`) sin marcador; una sección sin ancla de evidencia (4–6 en discovery) renderiza `[PENDING INPUT]` explícito apuntando al gap que la rastrea. Las respuestas de gaps cerrados se rutean a su sección vía el nuevo mapa estructurado `BRIEF_SECTION_FOR_GAP`/`brief_section_for_gap` en `discovery.py` (inverso del prosa-mapping de IMP-022); `/resolve-gaps` taggea cada seed de resolución con su "Brief Section" (sinergia IMP-022). Las secciones 7–11 (seeds, decisiones, cobertura, radar de gaps, readiness tables) quedan intactas. Sin texto inventado: evidencia citada o pending explícito.
- Métrica: el eval harness de IMP-027 mide `brief_target_coverage`; con el compilador, las secciones target 1,2,3 pasan de `pending` a `populated` en los 4 fixtures → `avg_brief_target_coverage` 0.00 → 1.00, sin tocar la detección (must_fire / false positives intactos, `baseline_ok` se mantiene). `test_evals_brief.py` actualizado (expense-approval coverage 0→1) + nuevo `tests/test_brief_compiler.py` (1–3 pobladas con cita EN/ES, 4–6 `[PENDING INPUT]`, ruteo de respuestas de gaps, parser de las tablas de resolución).
- Nota de cierre Codex: se compiló solo con evidencia citada o `[PENDING INPUT]`; no se agregó síntesis libre sin fuente, aunque eso deja algunas secciones menos fluidas por diseño.
- Problema: `render_project_brief()` rellena seeds/decisions/gaps como tablas pero las secciones 1–6 (identidad, actores, as-is/to-be, diseño, técnica, gobernanza) salen como "TBD" aunque la evidencia exista en gaps cerrados, seeds y context folders. El artefacto base de la fase 2 es el menos sintetizado del pipeline.
- Alcance: reemplazar el render template-céntrico por compilación sección a sección desde evidencia real (respuestas de gaps cerrados, seeds confirmadas, context folders indexados, análisis de IMP-021). Cada afirmación con cita (`trace_id` o path); lo sin evidencia queda `[PENDING INPUT]` explícito — nunca TBD genérico ni texto inventado.
- Aceptación: con el fixture más rico de `tests/fixtures/evals/` + respuestas de gaps, el brief puebla secciones 1–6 con afirmaciones citadas; ninguna afirmación sin fuente; lo no evidenciado como `[PENDING INPUT]`; la estructura por lentes se conserva.
- Afecta: `maturity.py`, `gap_resolution.py` (taggear respuestas con la sección de brief que alimentan — sinergia con IMP-022), tests, evals de brief.

### IMP-025 — Readiness score por sección + gate de `/brief`
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-025-brief-readiness-gate`, PR #15, merge `b458919`). `.\verify.ps1` en verde; gate blando validado sin endurecer el flujo por defecto.
- Implementado: `brief_section_readiness(brief_text)` en `maturity.py` clasifica las secciones narrativas 1–6 como `populated`/`pending` (mismos markers que el eval), calcula `coverage_score` (pobladas/6), cuenta `evidence_citations` por sección y, por cada sección pobre, nombra los `feeding_gaps` (inverso del mapa `BRIEF_SECTION_FOR_GAP` de IMP-024). Se agrega a `maturity_metrics` cuando el brief existe → expuesto en `/maturity` y `/status` sin cambios extra (status ya surfacea `maturity_metrics`). `brief_gate_warnings` arma advertencias EN/ES nombrando sección + gaps. Gate blando en `generate_project_brief`: lee `config.brief_gate {threshold=0.5, strict=False}`; bajo umbral agrega `warnings` (default no bloqueante); en `strict` no avanza a `READY_FOR_SPECS` (queda `BRIEF_BELOW_THRESHOLD`, `blocked: True`). Default no endurece gates (opt-in). Tests: `tests/test_brief_readiness.py` (score, status por sección, feeding gaps, sección vacía, warnings EN/ES, brief full sin warnings). Docs: `user_guide/01` (`/brief`).
- Nota de cierre Codex: el gate quedó opt-in para bloqueo estricto; por defecto advierte y reporta secciones pobres, evitando un cambio de comportamiento sorpresivo para workspaces existentes.
- Problema: `readiness_stage_for_counts()` cuenta open/blocking pero no distingue evidencia rica de mínima; no hay score por sección del brief.
- Alcance: score de cobertura de evidencia por sección (claims con fuente / claims totales), expuesto en `/maturity` y `/status` (extiende IMP-008). `/brief` gana gate blando configurable: por debajo del umbral advierte (o bloquea en modo estricto) indicando qué secciones están pobres y qué gaps las alimentan. "Definition of Ready" cuantificada del discovery.
- Aceptación: `/maturity` y `/status` muestran score por sección; `/brief` bajo umbral advierte nombrando secciones pobres y gaps que las alimentan; modo estricto bloquea; default no-bloqueante (gates no se endurecen sin opt-in).
- Afecta: `maturity.py`, `status.py`, `validation.py`, config de workspace, tests, docs.

### IMP-026 — Normalización EARS de requirements y reglas de negocio
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-026-ears`, PR #17, merge `c810d77`; follow-up `imp-026-ears-followup-citations`, PR #24, merge `4e9e4ae`). `.\verify.ps1` en verde en ambos cierres.
- Implementado: módulo nuevo `sentinel/ears.py` con los 5 patrones EARS (ubicuo, event-driven `when/cuando`, state-driven `while/mientras`, unwanted `if…then/si…entonces`, optional `where/donde`; verbo `shall/must/should/debe…`) — `classify_ears(text)` devuelve el patrón o `None`, `is_ears(text)`. En `/resolve-gaps`, `materialize_ears_requirements` toma las respuestas CONFIRMADAS (CLOSED) que el agente ya escribió en sintaxis EARS y las acumula en `02_requirements/requirements.md` bajo `## Normalized Requirements (EARS)` (tabla `REQ-EARS-NNN | Pattern | Statement | Source(gap/change)`, numeración estable entre corridas); las respuestas en prosa NO se normalizan (invariante #3 — el agente propone, el runtime valida estructura, nunca inventa). Cada statement agrega nodo `ears_requirement` (REQ) con edge `normalizes` desde el CHG. Tests: `tests/test_ears.py` (clasificación EN+ES + prosa; integración resolve→requirements.md con EARS normalizado y prosa excluida).
- Nota de cierre Codex: el follow-up cerró el cambio pendiente del plan: `REQ-EARS-*` se cita desde PRD/specs/backlog/context packs y `requirement.schema.json` acepta IDs/metadatos EARS. No se cambió la regla central: solo respuestas confirmadas y ya escritas en sintaxis EARS se normalizan; la prosa no se reescribe automáticamente.
- Problema: los requirements downstream consumen prosa en vez de statements testeables y parseables por agentes.
- Alcance: al cerrar gaps funcionales, `requirements.md` acumula statements normalizados a sintaxis EARS (ubicuo, event-driven, state-driven, unwanted behavior, opcional), cada uno con fuente. El agente propone la normalización (vía protocolo IMP-021), el CLI valida estructura. EARS solo sobre lo confirmado (invariante #3); hipótesis/no-confirmado permanecen como prosa/gaps.
- Aceptación: tras cerrar gaps funcionales con respuestas sustantivas, `requirements.md` contiene statements EARS válidos con fuente; specs/backlog los citan; los no confirmados permanecen como prosa/gaps.
- Afecta: `discovery.py`/`gap_resolution.py`, `requirement.schema.json`, plantillas de specs/backlog, tests.

### Frente C — Medir la maduración

### IMP-027 — Evals de brief y de gaps semánticos
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-027-brief-semantic-evals`, PR #10, merge `3f00355`). Evals incorporados al baseline del Horizonte 5.
- Implementado: (a) el runner corre `init → ingest → brief` por fixture, clasifica las secciones narrativas 1–6 del brief como `populated`/`pending` (`brief_section_status`) y emite `brief_target_coverage` por fixture + `avg_brief_target_coverage` (métrica de progreso de IMP-024). (b) Cada answer key gana un bloque `brief.target_populated` con las secciones que tienen evidencia confirmada (1,2,3 en los 4 fixtures) y deben poblarse con cita. (c) Fixture nuevo `expense-approval`: requerimiento lleno de buzzwords tranquilizadores ("security and performance are important", "compliance obligations", "quality matters", "successful once approvers are happy", "business rules") que **suprimen 5 gaps reales por presencia de token** (GAP-ACCEPTANCE, GAP-BUSINESS-RULES, GAP-GOVERNANCE-CONSTRAINTS, GAP-QUALITY, GAP-TECH-NFR) → demuestra el techo léxico que IMP-021 debe romper. (d) Test de regresión `tests/test_evals_brief.py` (4 tests) que bloquea el baseline. README de fixtures actualizado.
- Baseline registrado (2026-06-11): `baseline_ok=True`, `avg_recall_must_fire=1.00`, `avg_target_recall=0.75` (expense-approval 0.00; los otros 3 ya en 1.00 por IMP-015), `avg_brief_target_coverage=0.00` (las secciones 1–3 con evidencia se renderizan como TBD en los 4 fixtures — punto de partida de IMP-024). Suite unittest 37 tests, los nuevos 4 verdes; `/doctor` PASS en filesystem escribible. (Nota de entorno: en el mount OneDrive de la sesión, `/doctor` da FAIL por "repo write access" y 4 tests de doctor + 1 de skills-sync fallan por CRLF sin normalizar — ambos preexistentes (IMP-001 IN PROGRESS), ajenos a este ítem.)
- Nota de cierre Codex: el ítem quedó como harness de medición, no como mejora de detección; el fixture `expense-approval` conserva el fallo léxico para que IMP-021 sea falsable.
- Problema: no hay answer keys de brief ni fixtures donde el checklist léxico falle pero el análisis semántico deba disparar.
- Alcance: extender `tests/evals/` con answer keys de brief (qué secciones deben quedar pobladas y con qué evidencia, por fixture) y fixtures con `target_fire` > 0 donde el léxico falla.
- Aceptación: el runner reporta cobertura de brief por fixture contra answer keys; al menos un fixture nuevo con casos donde el léxico falla; baseline documentado aquí. ✓ los tres cumplidos.
- Afecta: `tests/fixtures/evals/`, `tests/evals/run_discovery_evals.py`, README de fixtures, `tests/test_evals_brief.py`.

### IMP-028 — Telemetría del ciclo de maduración
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-028-telemetry`, PR #18, merge `31216f9`; follow-up `imp-028-telemetry-followup-sync-reopened`, PR #25, merge `ea0d19c`). `.\verify.ps1` en verde en ambos cierres. **Frente A–C completo y mergeado.**
- Implementado: `maturation_telemetry(project_id)` en `maturity.py`, incluido en `maturity_metrics` → expuesto en `/status` y `/maturity` sin cambios extra. Campos (todos aditivos/opcionales): `resolve_iterations` (rondas de `/resolve-gaps`, contadas del `gap_resolution_log.md`), `closed_total`, `closed_by_origin` + `closed_by_origin_pct` (cierre por procedencia del gap: checklist/agent/challenge), `open_blocking_gaps`, y `oldest_blocking_age_rounds` (proxy de antigüedad: un gap blocking aún abierto sobrevivió todas las rondas). Tests: `tests/test_telemetry.py` (2 rondas → iterations=2, cierre por origen, edad proxy; surface en `/status`).
- Nota de cierre Codex: el follow-up completó los refinamientos abiertos: la telemetría distingue cierres `client/domain/inference`, `/sync` reporta `Reopened Closed Gaps` y `/status` expone `reopened_by_sync_*`. No se cambió el formato base de `maturity_metrics`; todo quedó aditivo para workspaces existentes.
- Problema: el BA no tiene visibilidad de dónde se estanca la maduración.
- Alcance: en `/status` y el maturity report: número de iteraciones de `/resolve-gaps`, % de gaps cerrados por cliente vs. dominio vs. inferencia controlada, gaps reabiertos por `/sync`, y edad del gap blocking más viejo.
- Aceptación: tras un lifecycle con ≥2 rondas de `/resolve-gaps` sobre un fixture, `/status` muestra iteraciones, % de cierre por origen y edad del blocking más viejo; sin cambios para workspaces existentes (campos nuevos opcionales en state).
- Afecta: `status.py`, `maturity.py`, `gap_resolution.py`, tests.

### Frente D — Arquitectura de memoria (que LanceDB cumpla su promesa, transversal)

Principio rector: la memoria sigue siendo ayuda reconstruible (nunca autoridad), 100% local, sin red en runtime; `json-hybrid` sigue siendo de primera clase para VDIs restringidas.

### IMP-029 (D1) — Embeddings semánticos locales opcionales
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-029-semantic-embeddings`, PR #21, merge `34732c7`). `.\verify.ps1` en verde. Implementa `Embedder` local opcional con autodetección `model2vec` → `sentence-transformers` → `hash_embedding`; agrega extra `[memory-semantic]`; registra `embedder`/`embedding_version` en memoria/context packs; `/doctor` reporta el nivel activo. Sin modelo semántico instalado, el fallback determinista `json-hybrid`/`hash_embedding` queda intacto y de primera clase.
- Nota de cierre Codex: se implementó la abstracción local-first sin descarga en runtime. Cambio contra lo planteado: la golden cross-lingual queda condicionada a tener modelo local autorizado/configurado; en el entorno fallback de VDI sigue corriendo como métrica sin romper la suite.
- Problema: `hash_embedding()` es bag-of-words hasheado (no semántico): LanceDB almacena vectores que solo replican el matching léxico que ya hace el scoring JSON. Sin cross-lingual ES/EN, sinónimos ni paráfrasis.
- Alcance: abstracción `Embedder` con tres niveles autodetectados: (1) `model2vec` estático multilingüe (~30 MB, sin torch, ideal VDI), (2) `sentence-transformers` multilingüe (`bge-m3`/`multilingual-e5-small`), (3) fallback `hash_embedding` (determinista, tests). Nuevo extra `[memory-semantic]`; modelo descargado una vez (documentar instalación offline air-gapped). Registrar `embedder`/`embedding_version` en metadata y context pack; `/doctor` reporta nivel activo.
- Aceptación: con `[memory-semantic]` instalado, una golden query en ES recupera un chunk equivalente escrito en EN (hoy falla); sin instalar, todo opera igual.
- Afecta: `memory.py` (clase `Embedder`, dimensiones variables), `pyproject.toml`, `doctor.py`, `user_guide/05` y `09`, tests (suite pasa en los 3 niveles; CI usa fallback).

### IMP-030 (D2) — Retrieval nativo LanceDB: FTS + hybrid + RRF, upsert incremental
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-030-native-lancedb-retrieval`, PR #22, merge `d6e539f`). `.\verify.ps1` en verde. Implementa upsert incremental por artefacto sin recrear tabla completa, FTS local sobre `text`, RRF sobre ranks vector/FTS, scoring `json-hybrid` normalizado, causa de degradación visible en `/doctor`, `/health` y context packs, y `why_retrieved` con ranks de señales.
- Nota de cierre Codex: LanceDB pasó a ser un backend real cuando está disponible, pero la ruta `json-hybrid` quedó explícita y testeada como primera clase. El cambio práctico contra el plan fue exponer la degradación también en context packs, además de `/doctor` y `/health`.
- Problema: las tres señales del score (lexical/semantic/vector) son redundantes y sin normalizar; LanceDB no es el motor real (ranking itera todos los chunks en Python); upsert reescribe la tabla entera por artefacto (O(n²)); degradación silenciosa por `except Exception`.
- Alcance: con backend LanceDB, índice FTS nativo (BM25/Tantivy) sobre `text`, `table.search(query_type="hybrid")` + Reciprocal Rank Fusion en vez de la suma ad hoc; filtros como `where` pre-filter; `merge_insert` keyed por `chunk_id` + delete de huérfanos en vez de reescritura total. En `json-hybrid`, scoring normalizado (las dos señales lexicales colapsan en una). Loggear causa de degradación y exponerla en `/doctor` y `/health`. `why_retrieved` extendido con el rank de cada señal.
- Aceptación: `/reindex` de un workspace con N artefactos no reescribe la tabla N veces (verificable por tiempo/log); `/retrieve` igual o mejor en las golden queries de IMP-032; suite verde sin lancedb instalado.
- Afecta: `memory.py` (`_connect_lancedb`, `_upsert_lancedb_chunks`, `retrieve`, `_lancedb_candidates`), `doctor.py`, `health.py`, tests.

### IMP-031 (D3) — Chunking estructural, anchors de sección y reindexación incremental
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-031-structural-chunking`, PR #23, merge `9bf4998`). `.\verify.ps1` en verde. Implementa chunking heading-aware, tablas Markdown indivisibles, anchors `line_start`/`line_end`, `chunking_version`, `/reindex` incremental por `source_hash` + `embedding_version` + `chunking_version`, y `/reindex --full` con adapters regenerados.
- Nota de cierre Codex: el resultado convierte retrieval en puntero preciso (`source_path`, `section_path`, líneas) más que en volcado de contexto. Cambio contra lo previsto: `/reindex --full` sí exigió regenerar adapters porque se agregó la opción de CLI.
- Problema: chunking plano (corta por párrafos a 900 chars sin overlap ni jerarquía de headings; parte tablas por la mitad); `source_hash` existe pero el reindex re-procesa todo igual.
- Alcance: chunking heading-aware (chunks heredan ruta completa de headings calculada en el split; tablas markdown no se parten; overlap configurable ~10–15% para prosa). Objetivo "retrieval como router": cada resultado es un puntero preciso (`source_path` + `section_path` + líneas aprox.) para que el agente lea la sección exacta en vez de recibir contenido volcado. Reindexación incremental: si `source_hash` no cambió, `/reindex` y `/sync` saltan re-chunking y re-embedding; `/reindex --full` fuerza reconstrucción total.
- Aceptación: un chunk de `gaps.md` nunca contiene media tabla; reindexar dos veces seguidas el mismo workspace hace 0 trabajo de embedding la segunda vez.
- Afecta: `memory.py` (`chunk_texts`, `section_path_for_chunk`, `reindex_workspace`, `index_context_folders`), `sync.py`, tests.

### IMP-032 (D4) — Eval de retrieval
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-032-retrieval-evals`, PR #19, merge `d5da3ec`; follow-up `imp-032-retrieval-evals-followup`, PR #26, merge `6d9478f`). `.\verify.ps1` en verde en ambos cierres. Primer ítem del Frente D.
- Implementado: golden queries en `tests/fixtures/evals/support-dashboard/answer_key.json` (`golden_queries`: query → `expected_artifacts`, `workflow`, `kind`), con 2 same-language y 1 cross-lingual ES→EN. Harness `tests/test_evals_retrieval.py`: corre init+ingest por fixture con golden queries, llama `ContextBroker.retrieve(query, workflow, limit=5)`, computa recall@5 y MRR por `kind`, y escribe `tests/evals/reports/retrieval_eval_<fecha>.json`. Same-language tiene gate de baseline (≥0.5); cross-lingual se registra como métrica de progreso (no falla) — es el target falsable que IMP-029 debe mover sobre 0 (hoy el hash-embedding no tiene semántica cross-lingual). El target del match es el **artefacto** (`source_path`), robusto al cambio de chunking de IMP-031.
- Nota de cierre Codex: el follow-up completó el pendiente menor: golden queries quedaron en los 4 fixtures y el reporte JSON agrega `summary.by_backend` para comparar `json-hybrid` y `lancedb-hybrid` según el backend activo. No se fuerza instalación de LanceDB ni modelo semántico para que la verificación siga verde en VDI.
- Recomendación de orden: primero del Frente D (junto con IMP-027). Sin esto, D1–D3 no son falsables.
- Problema: no existen golden queries; no se puede afirmar que `lancedb-hybrid` recupere mejor que `json-hybrid` ni medir mejoras.
- Alcance: extender el eval harness con golden queries por fixture (query → chunk_ids/artefactos esperados), métricas recall@k y MRR, corridas comparativas por backend/embedder (`json-hybrid` vs `lancedb+hash` vs `lancedb+semantic`). Incluir queries cross-lingual ES↔EN y de paráfrasis para demostrar el delta de IMP-029.
- Aceptación: reporte JSON por corrida con recall@5 y MRR por backend; baseline documentado aquí al cerrar el ítem.
- Afecta: `tests/fixtures/evals/` (golden_queries por fixture), `tests/evals/`, README de fixtures.

## Horizonte 6 — Cierre documental y reconciliación post-merge

Estos ítems registran trabajo necesario que apareció al cerrar el Horizonte 5 pero no estaba modelado como IMP funcional: alinear documentación de usuario, README y el propio backlog con lo ya implementado.

### IMP-034 — Sincronización de user guide post Horizonte 5
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `docs-user-guide-post-imp-sync`, PR #27, merge `fa075a7`). `.\verify.ps1` en verde.
- Problema: después de IMP-026/028/029/030/031/032, la guía de usuario todavía podía describir memoria, telemetría, EARS y evals como capacidades parciales o no documentadas.
- Alcance: actualizar las guías de uso para reflejar EARS citados, telemetría de maduración/reapertura, backends de memoria (`json-hybrid`/`lancedb-hybrid`), embeddings semánticos locales opcionales, chunking estructural y evals de retrieval.
- Implementado por Codex: se alinearon las secciones operativas del user guide con los comandos y salidas actuales, sin agregar comandos nuevos ni cambiar runtime. Cambio contra lo planteado: fue un IMP documental creado post hoc, no parte del backlog original.
- Aceptación: guías coherentes con el runtime mergeado; `.\verify.ps1` verde; sin outputs generados editados a mano.
- Afecta: `user_guide/`.

### IMP-035 — Sincronización de README post Horizonte 5
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `docs-readme-post-imp-sync`, PR #28, merge `d866e2a`). `.\verify.ps1` en verde.
- Problema: el README público no reflejaba todavía las decisiones finales sobre memoria local, embeddings opcionales, EARS downstream, reindex incremental, reapertura por `/sync` y evals de retrieval.
- Alcance: actualizar el README sin mezclar cambios funcionales, manteniendo el mensaje local-first y la degradación determinista como camino soportado.
- Implementado por Codex: se documentó `[memory-semantic]`, `SENTINEL_MODEL2VEC_MODEL`, `json-hybrid`/`lancedb-hybrid`, FTS/RRF, chunking estructural, EARS citados, `Reopened Closed Gaps` y reportes de evals por backend. Cambio contra lo planteado: se separó en PR propio después del merge del user guide para no contaminar la rama documental previa.
- Aceptación: README coherente con user guide/runtime; `.\verify.ps1` verde; PR separado y mergeado.
- Afecta: `README.md`.

### IMP-036 — Reconciliación de backlog y notas de cierre Codex
- Estado: VERIFIED & PUSHED (2026-06-12, branch `docs-backlog-imp-status-notes`; pendiente de merge). `.\verify.ps1` en verde.
- Problema: tras los merges, el handoff superior decía que Horizonte 5 estaba completo, pero secciones individuales todavía contenían estados `IMPLEMENTED`, `VERIFIED & PUSHED`, pendientes menores o verificaciones pendientes.
- Alcance: actualizar estados de los IMP cerrados, agregar notas breves de qué implementó Codex y registrar cambios contra lo planificado para que el modelo que diseñó el plan pueda auditar el cierre sin leer todos los PRs.
- Implementado por Codex: se normalizan estados de IMP-021/022/024/025/026/027/028/029/030/031/032/033, se explicitan follow-ups de IMP-026/028/032, se corrige el handoff que todavía listaba IMP-029/030/031 como pendientes y se agregan IMP-034/035/036 para trazabilidad documental.
- Aceptación: este backlog no contiene contradicciones de estado para los IMP cerrados del Horizonte 5; los cambios post-backlog quedan modelados como IMPs; `.\verify.ps1` verde antes de PR.
- Afecta: `docs/evolution/02-backlog-mejoras.md`.

## Horizonte 7 — Calidad y cobertura de tests post-Horizonte 5

Trabajo funcional (no documental) que apareció al cerrar el Horizonte 5: endurecer la cobertura de tests/evals sobre lo ya implementado. Se separa del Horizonte 6 (documental) porque toca runtime de pruebas y answer keys, no prosa.

### IMP-037 — Cobertura ampliada de evals de discovery
- Estado: VERIFIED & PUSHED & MERGED (2026-06-12, branch `imp-037-discovery-eval-coverage`, PR #29, merge `8a1bd3a`). `.\verify.ps1` en verde: 103 tests OK, `/doctor` sin failures, discovery evals OK.
- Problema: los evals de discovery ya cubrían recall de gaps, target semántico, `/annotate`, brief coverage y retrieval, pero todavía no verificaban varias casuísticas de uso de discovery: idioma detectado, metadata crítica de gaps, origen de detección y secciones que deben permanecer explícitamente pendientes por falta de evidencia.
- Alcance: ampliar el harness sin crear un comando nuevo ni sacar los evals de `verify.ps1`; enriquecer las answer keys de los fixtures existentes con expectativas opcionales para idioma, `lens`, `severity`, `origin`, y secciones de brief `target_pending`.
- Implementado por Codex: `tests/evals/run_discovery_evals.py` ahora parsea la tabla de trazabilidad con `parse_gap_rows`, lee `state.json`, valida `expected_language`, `expected_gap_details`, `annotate.expected_gap_details`, y calcula `avg_brief_expected_pending_coverage`. Las cuatro answer keys (`crm-billing-sync`, `expense-approval`, `portal-autogestion`, `support-dashboard`) declaran esas expectativas. `tests/test_evals_brief.py` agrega guards para que las secciones 4-6 sigan pending cuando no hay evidencia y para que `/annotate` recupere los cinco gaps semánticos de `expense-approval` con `origin: agent`.
- Cambio contra lo planteado: no se agregaron fixtures nuevos; se eligió profundizar el contrato de los fixtures existentes para cubrir más dimensiones de discovery sin aumentar demasiado el costo de `verify.ps1`.
- Aceptación: `verify.ps1` sigue encapsulando la corrida completa; el runner falla si el idioma detectado, metadata de gaps u obligación de pending explícito regresan; reporte JSON conserva métricas previas y agrega cobertura de pending.
- Afecta: `tests/evals/run_discovery_evals.py`, `tests/test_evals_brief.py`, `tests/fixtures/evals/*/answer_key.json`, `tests/fixtures/evals/README.md`.

## Horizonte 8 — Fase PRD/Specs y preparación upstream

Ítems promovidos desde `docs/evolution/04-propuesta-prd-specs.md` (APROBADA 2026-06-12). Fuente de diseño obligatoria: propuesta 04 completa, especialmente protocolo de sección 0 y DoD de sección 5. Orden estricto: IMP-038 → IMP-046 → IMP-047 → IMP-039 → IMP-042 → IMP-040 → IMP-041 → IMP-043 → IMP-045. IMP-044 puede intercalarse en paralelo después de IMP-038.

### IMP-038 — Evals de PRD y specs (medir primero)
- Estado: VERIFIED & PUSHED (2026-06-12, branch `imp-038-prd-specs-evals`; pendiente de merge). `verify.ps1` verde: 106 tests OK, `/doctor` sin failures, discovery evals OK con baseline `avg_prd_target_coverage=0.06` y `avg_specs_scaffolding=11.00`.
- Prioridad: 1 de 9 (bloquea la falsabilidad de todo el horizonte)
- Depende de: nada; reutiliza `tests/evals/run_discovery_evals.py` y answer keys en `tests/fixtures/evals/*/answer_key.json`.
- Problema: no hay answer keys de PRD ni de specs; sin baseline, IMP-039/040/042 no son falsables. Hoy el harness corre hasta `/brief`; la fase 2 no se mide.
- Alcance: extender el runner para correr `init → ingest → (resolve-gaps con respuestas del fixture si existen) → brief → specs` por fixture y clasificar: secciones narrativas del PRD como `populated`/`pending` contra un bloque nuevo `prd.target_populated`; presencia de scaffolding inventado en specs (`CAP-001..003`, `JTBD-001`, `US-001..005` fijos) como métrica `specs_scaffolding_count`; métricas agregadas `avg_prd_target_coverage` y `avg_specs_scaffolding`; test de regresión estilo `tests/test_evals_brief.py`.
- Implementado por Codex: el runner ahora llega a fase 2 por el lifecycle real (`init → ingest → resolve-gaps` si el fixture trae `gap_responses.md` → `brief → specs`), clasifica secciones PRD 1-13, cuenta IDs scaffold fijos en `specs.md`, agrega métricas de resumen `avg_prd_target_coverage`, `avg_specs_scaffolding` y `total_specs_scaffolding`, y conserva la pasada anotada de IMP-021 solo para target recall. Los 4 answer keys agregan `prd.target_populated`; 3 fixtures agregan respuestas sintéticas mínimas para cerrar gaps bloqueantes sin forzar gates; `tests/test_evals_prd.py` bloquea la nueva baseline.
- Cambio contra lo planificado: se agregaron `gap_responses.md` sintéticos porque `/specs` respeta el gate de madurez y algunos fixtures tenían gaps críticos/high abiertos. No se modificó el runtime ni se relajaron gates.
- Aceptación: el runner reporta cobertura de PRD por fixture contra answer keys y cuenta scaffolding de specs; los 4 fixtures tienen `prd.target_populated`; baseline documentado al cerrar; `verify.ps1` sigue encapsulando la corrida; no hay regresión de métricas previas.
- Afecta: `tests/evals/run_discovery_evals.py`, `tests/fixtures/evals/*/answer_key.json`, `tests/test_evals_prd.py`, README de fixtures.

### IMP-046 — Checks de lentes "grado PRD"
- Estado: VERIFIED & PUSHED (2026-06-12, branch `imp-046-prd-grade-lens-checks`). `.\verify.ps1` verde: 109 tests OK, `/doctor` PASS con warnings opcionales esperados y evals sin regresión (`avg_recall_must_fire=1.00`, `avg_prd_target_coverage=0.06`, `avg_specs_scaffolding=11.00`).
- Implementado por Codex: calibrados los checks PRD declarativos para que `GAP-PRD-PERSONA-DETAIL` no se cierre por tokens genéricos de objetivo y `GAP-PRD-NFR-KPI` no se cierre por métricas sin método/plazo; agregado `GAP-PRD-ROLLOUT-ENVIRONMENTS` en el lente delivery para ambientes, rollout, restricciones de release y rollback; extendidos los textos EN/ES de elicitación (`why`, `unblocks`, `expected_format`, pregunta y ejemplos); answer keys de los 4 fixtures cubren los gaps PRD y un test nuevo fija falsabilidad de los casos calibrados.
- Cambio contra lo planificado: se agregó un check nuevo y se endurecieron dos existentes, evitando multiplicar gaps redundantes sobre señales PRD ya cubiertas. No hubo cambios de comandos ni skills, por lo que no se regeneraron adapters.
- Prioridad: 2
- Depende de: IMP-038. Reusa IMP-033 (base declarativa `sentinel/lenses/*.json`) e IMP-022 (`why_gap_matters`, `unblocks_for_gap`, `expected_format_for_gap`).
- Problema: los 7 lentes elicitan a nivel brief, pero el PRD exige detalle que hoy nadie pregunta durante la maduración: KPI con baseline/target/plazo, personas con proficiencia/frecuencia de uso, NFRs medibles y señales de plan de ejecución. Sin esto, IMP-039 compilará `[PENDING INPUT]` legítimo pero evitable.
- Alcance: auditar checks existentes contra `prd.target_populated`; agregar checks faltantes editando solo JSON de lentes, con severidad, why, tokens/triggers y counterparts/suppressors calibrados contra los 4 fixtures; extender dicts EN/ES de IMP-022 en `discovery.py` para `unblocks_for_gap` y `expected_format_for_gap`; actualizar answer keys `must_fire`/`must_not_fire`. Calibración obligatoria: cero falsos positivos nuevos.
- Aceptación: cada check nuevo dispara donde falta evidencia y no dispara donde hay evidencia real; cada gap nuevo expone por-qué/qué-desbloquea(sección PRD)/formato-esperado en `gaps.md` y context-requests; round-trip de IMP-022 intacto; `avg_recall_must_fire` 1.00 sin regresión; agregar checks editando solo JSON sigue probado.
- Afecta: `sentinel/lenses/*.json`, `sentinel/discovery.py`, `tests/fixtures/evals/*/answer_key.json`, tests, `user_guide/02-artifact-reference.md`.

### IMP-047 — Elicitación orientada a EARS en gaps funcionales
- Estado: VERIFIED
- Prioridad: 3
- Depende de: IMP-046. Reusa IMP-022 (`expected_format_for_gap`), IMP-026 (`sentinel/ears.py`, `materialize_ears_requirements`) y skill `sentinel-gap-response`.
- Problema: IMP-026 solo normaliza a `REQ-EARS-*` las respuestas confirmadas que ya llegaron escritas en sintaxis EARS; las respuestas en prosa no generan statements. Sin elicitación orientada a EARS, las spec units de IMP-042 quedan sin insumo en proyectos reales.
- Alcance: hacer que `expected_format_for_gap` devuelva plantillas EARS concretas EN/ES para gaps funcionales y reglas de negocio; actualizar la skill `sentinel-gap-response` para guiar al agente a proponer reformulación EARS junto a la respuesta original, siempre con confirmación del BA y validación de `classify_ears`; marcar en `/resolve-gaps` respuestas funcionales confirmadas en prosa como `EARS-eligible, not normalized`; exponer conteo aditivo en telemetría de `/status`.
- Aceptación: gaps funcionales en `gaps.md` y context-requests muestran plantilla EARS EN/ES correcta; respuesta confirmada en EARS se acumula en `requirements.md`; respuesta confirmada en prosa queda marcada `EARS-eligible` y contada en `/status`, sin reescritura automática; round-trip render→parse intacto; tests EN/ES de los tres casos.
- Afecta: `sentinel/discovery.py`, `gap_resolution.py`, `maturity.py`, skill `sentinel-gap-response` + `python -m sentinel.adapters`, tests (`test_ears_elicitation.py`), `user_guide/03-workflows.md`, `user_guide/11-chat-commands.md`.

### IMP-039 — PRD compiler: secciones compiladas desde evidencia
- Estado: PENDING
- Prioridad: 4
- Depende de: IMP-038; se beneficia de IMP-046/047. Reusa IMP-024 (`compile_brief_sections`), IMP-005, IMP-026 e IMP-007.
- Problema: `render_prd_full` emite prosa de plantilla y cita `REQ-001` fijo; no consume las secciones compiladas del brief ni rutea respuestas de gaps cerrados a secciones del PRD.
- Alcance: crear `PRD_SECTION_FOR_GAP` en `discovery.py`; implementar `compile_prd_sections` para poblar secciones narrativas solo desde evidencia (brief compilado citado por `section_path`, gaps cerrados, extracciones, EARS y decisiones); exigir fuente por afirmación; dejar `[PENDING INPUT]` con referencia a `GAP-*` cuando falte evidencia; reemplazar anchors fijos por IDs reales del grafo; respetar `project_language`.
- Aceptación: con fixture rico + respuestas, `avg_prd_target_coverage` sube contra baseline de IMP-038; no hay afirmaciones sin fuente; lo no evidenciado queda `[PENDING INPUT]` apuntando a gap; evals de brief/discovery sin regresión; `/validate` clasifica el PRD como `evidence-backed` o `mixed`, no `scaffolding`.
- Afecta: `sentinel/generation.py`, `sentinel/discovery.py`, `gap_resolution.py`, tests (`test_prd_compiler.py`), evals de IMP-038, `user_guide/02-artifact-reference.md`.

### IMP-040 — Canal agéntico de redacción del PRD (`/compose`)
- Estado: PENDING
- Prioridad: 6
- Depende de: IMP-039. Reusa patrón IMP-021/023 de validación, evidencia verbatim, archivado de source y trazabilidad.
- Problema: el PRD es para humanos y la compilación determinista no produce narrativa fluida; el agente puede redactarla, pero no tiene canal sancionado en fase 2 y eso tienta a editar artefactos a mano.
- Alcance: nuevo comando `/compose PROJECT_ID --source DRAFT.json`; el agente propone bloques narrativos por sección del PRD y cada párrafo declara citas verbatim; el runtime valida sección existente, citas en fuente SSoT y ausencia de contradicción con `[PENDING INPUT]`; bloques válidos se mergean con `origin: agent`; inválidos se rechazan por bloque; source archivado en `03_specs/compositions/`; nodo `prd_composition`, indexación y conteo en `/status`; regeneración preserva bloques con citas aún válidas y descarta reportando los inválidos.
- Aceptación: draft válido se mergea con origen visible y trazado; draft con cita no-verbatim, sección inexistente o narrativa sobre pending se rechaza con razón; tras `/sync` que invalida fuente, el bloque afectado se descarta y queda reportado; gates/lifecycle intactos; evals sin regresión.
- Afecta: `sentinel/generation.py` o `sentinel/prd.py`, `cli.py`, `protocols.py`, `commands_manifest.json` + adapters, `mcp.py`, `doctor.py`, skill `sentinel-compose`, schema `composition.schema.json`, `ids.py`, tests (`test_compose.py`), `user_guide/01-command-reference.md`, `user_guide/02-artifact-reference.md`, `user_guide/11-chat-commands.md`.

### IMP-041 — Readiness por sección + gate blando de `/specs`
- Estado: PENDING
- Prioridad: 7
- Depende de: IMP-039; mejora con IMP-042. Reusa IMP-025 (`brief_section_readiness`, patrón `config.brief_gate`).
- Problema: `/specs` genera con el único gate `readiness != BLOCKED`; no hay score por sección del PRD ni advertencia que nombre qué gap alimenta cada sección pobre.
- Alcance: implementar `prd_section_readiness(prd_text)` con estado `populated`/`pending`, `coverage_score`, `evidence_citations` y `feeding_gaps`; integrarlo a `maturity_metrics`, `/maturity` y `/status`; agregar gate blando en `generate_specs` con `config.specs_gate {threshold, strict}`, default no bloqueante; en estricto bloquear con estado `SPECS_BELOW_THRESHOLD`.
- Aceptación: `/maturity` y `/status` muestran score por sección del PRD; `/specs` bajo umbral advierte con secciones pobres y gaps; modo estricto bloquea; default no endurece gates; tests estilo `test_brief_readiness.py`.
- Afecta: `maturity.py`, `generation.py`, `status.py`, config de workspace, tests (`test_specs_readiness.py`), `user_guide/01-command-reference.md`.

### IMP-042 — Spec units: descomposición en unidades trazables
- Estado: PENDING
- Prioridad: 5
- Depende de: IMP-038, IMP-047, IMP-039. Reusa IMP-031, IMP-026 e IMP-007.
- Problema: `render_specs` emite un monolito con `CAP-001..003`, `JTBD-001`, seeds `US-001..005` y `ASM-001/002` idénticos para todo proyecto; es estructura inventada presentada como contrato para agentes y obliga a cargar el spec entero.
- Alcance: convertir `specs.md` en índice y descomponer contenido en `03_specs/units/SPEC-U-NNN.md`; una unidad por requerimiento/capacidad derivada de evidencia real (`REQ-EARS-*`, `FR-E*`, CAP/JTBD solo si hay señal); frontmatter parseable con id estable, status, trace_ids, EARS citados y fuentes con anchors; cuerpo como puntero a brief/PRD/requirements; numeración estable; nodos `spec_unit` y edges PRD→unidad→EARS; indexación individual; `/backlog` consume unidades sin cambiar comportamiento externo.
- Aceptación: fixture con EARS confirmados genera una unidad por statement con frontmatter válido y punteros con anchors; `specs_scaffolding_count` cae a 0 sin perder secciones de contrato del índice; IDs estables entre dos corridas; `/trace` muestra PRD→unidades→EARS; evals y suite sin regresión.
- Afecta: `sentinel/generation.py`, `traceability.py`, `ids.py`, schema `spec_unit.schema.json`, tests (`test_spec_units.py`), `user_guide/02-artifact-reference.md`, skill `sentinel-specs`.

### IMP-043 — Delta-specs en regeneración
- Estado: PENDING
- Prioridad: 8
- Depende de: IMP-042. Reusa IMP-011 (`record_regeneration_diff`).
- Problema: el diff de regeneración actual reporta líneas y secciones por artefacto entero; tras `/sync`, ni el BA ni un agente de backlog saben qué unidades cambiaron.
- Alcance: al regenerar specs, emitir delta por unidad (`ADDED`/`MODIFIED`/`REMOVED`/`UNCHANGED`) con resumen de cambios de frontmatter, EARS citados y punteros en `07_changes/04_regeneration/`; trazar al `CHG`; agregar campo aditivo `stale_spec_units` en `implementation_readiness.json`.
- Aceptación: tras `/sync` con impacto y regeneración, el delta nombra la unidad afectada y solo esa; delta trazado e indexado; suite y evals sin regresión.
- Afecta: `sentinel/generation.py`, `sync.py`, tests, `user_guide/02-artifact-reference.md`.

### IMP-044 — Retrieval plans declarativos por sección, con punteros y presupuesto
- Estado: PENDING
- Prioridad: paralelizable después de IMP-038
- Depende de: IMP-038. Reusa IMP-031 e IMP-033.
- Problema: `PRD_SECTION_QUERIES` y `BACKLOG_CONTEXT_QUERIES` viven hardcodeadas en `generation.py`; el contexto se arma con truncados fijos y los packs descartan anchors precisos. El equipo no puede mejorar recuperación sin tocar Python y el agente no recibe un plan de lectura preciso.
- Alcance: externalizar planes en `sentinel/retrieval_plans/*.json` por workflow/sección con query base, dominio, filtros, límite, presupuesto y lentes asociados; loader con cache y override para tests; reemplazar truncado fijo por selección por relevancia y anchors; agregar `read_plan` por resultado con `source_path`, `section_path`, `line_start` y `line_end`.
- Aceptación: editar una query tocando solo JSON y verla reflejada en el pack; outputs idénticos o mejores en evals de retrieval y coverage; packs incluyen `read_plan` con anchors válidos verificados contra archivo; `verify.ps1` verde.
- Afecta: `sentinel/generation.py`, `sentinel/retrieval_plans/`, loader nuevo o extensión de `lens_registry.py`, `pyproject.toml`, `memory.py` si hace falta, tests (`test_retrieval_plans.py`), `user_guide/05-traceability-and-memory.md`, skill `sentinel-specs`.

### IMP-045 — Consistencia cross-artefacto en `/validate`
- Estado: PENDING
- Prioridad: 9 (cierre del horizonte)
- Depende de: IMP-039 + IMP-042. Reusa IMP-006 (`validation.py` warnings no bloqueantes).
- Problema: nada verifica coherencia entre capas: secciones pobladas del brief que el PRD no consume, `REQ-EARS-*` confirmados sin cita en specs, `FR-E*` sin unidad de spec, o unidades con punteros colgantes.
- Alcance: agregar bloque `cross_artifact_consistency` a `/validate`: brief→PRD, EARS→specs, extracciones→specs, punteros/anchors resolubles y huérfanos con artefacto, capa y comando correctivo sugerido; todo como warnings no bloqueantes sin cambiar verdict estructural.
- Aceptación: fixture completo reporta consistencia limpia; al inyectar inconsistencia sintética el warning nombra capa y corrección; no bloquea; documentado en `user_guide/01`; tests con ambos casos.
- Afecta: `sentinel/validation.py`, tests (`test_cross_consistency.py`), `user_guide/01-command-reference.md`, skill `sentinel-health`.

## Horizonte 8 — Backlog gobernado

Ítems promovidos desde `docs/evolution/05-propuesta-backlog.md` (APROBADA 2026-06-13). Fuente de diseño obligatoria: propuesta 05 completa, especialmente diagnóstico de sección 1, modelo conceptual, restricciones de sección 6 y secuencia obligatoria de sección 5. Orden estricto por PR: IMP-048 → IMP-061 → IMP-049 → IMP-057 → IMP-058 → IMP-059 → IMP-050 → IMP-051 → IMP-052 → IMP-053 → IMP-056 → IMP-055 → IMP-060 → IMP-054. IMP-054 queda como frontera opcional/deferred hasta demanda downstream real.

### IMP-048 — Derivación dinámica de épicas e historias desde la evidencia
- Estado: VERIFIED
- Problema: `BACKLOG_STORY_SEEDS` produce 5 historias genéricas sin importar el contenido real del PRD/specs; las AC y trazas son plantilla.
- Alcance: reemplazar la generación basada en seeds por una derivación desde las Spec Units confirmadas (`03_specs/units/SPEC-U-NNN.md`) y sus `REQ-EARS-*`, `FR-E*`, JTBD y personas de discovery. Agrupar unidades por tema de valor/outcome/JTBD, generar una historia por slice vertical de Spec Unit coherente, derivar AC desde la unidad real y mantener intactos la tabla "Slicing Strategy", el render de historia, el `execution_contract`, AC clasificadas, DoR/DoD y el boundary de enablers (`EPIC-002`). Lo faltante queda como stub `[PENDING INPUT]` + gap, nunca como historia inventada.
- Aceptación: con un fixture de 6 o más Spec Units, `/backlog` genera una historia por unidad, no 5 fijas; AC y trazas salen de `SPEC-U-*`/`REQ-EARS-*`; un fixture sin unidades funcionales emite stubs/gaps sin inventar; trazabilidad spec→épica→historia→AC intacta; IDs estables entre dos corridas; evals sin regresión.
- Afecta: `sentinel/generation.py`, `sentinel/retrieval_plans/backlog_generation.json`, `tests/`, `tests/evals/`, skill `sentinel-backlog`, `user_guide/02-artifact-reference.md`, `user_guide/03-workflows.md`.
- Nota 2026-06-13: implementada la derivación de historias desde `SPEC-U-*` confirmadas, con una `US-NNN` por unidad, AC derivadas de la unidad/EARS, traza `SPEC-U-* → US-*`, `source_unit` en `implementation_readiness.json` y limpieza de historias obsoletas en regeneraciones. Si no hay unidades funcionales, `/backlog` emite un único stub `[PENDING INPUT]` ligado a gaps de slicing sin inventar alcance. El boundary de `EPIC-002` queda protegido: no se generan enablers si no hay historias de valor reales. Se agregó el fixture eval `ops-risk-backlog` con 6 rondas EARS, soporte de `gap_response_rounds` en el runner y tests de derivación/pending stub; docs y skill `sentinel-backlog` actualizadas sin reemplazar la tabla "Slicing Strategy".

### IMP-049 — Externalizar el modelo de slicing existente a fuente declarativa + selección por forma de unidad
- Estado: VERIFIED
- Problema: el modelo de slicing del equipo es correcto y deliberado, pero vive hardcodeado en el render del epic y la asignación SPIDR/Lawrence hereda del seed fijo en vez de derivar de la unidad.
- Alcance: mover fielmente la tabla "Slicing Strategy" completa (INVEST con `Small` = small but valuable, Vertical slicing, SPIDR, Lawrence, small-but-valuable, agent readiness) a una fuente declarativa versionada con loader estilo `lens_registry.py`. Usar solo la taxonomía existente; no tocar ni diluir "Cross-Cutting Enabler Boundary" ni el flujo de `EPIC-002`. La derivación de IMP-048 selecciona patrón SPIDR/Lawrence según la forma de la Spec Unit y registra `slicing` + `slicing_rationale`.
- Aceptación: el epic generado reproduce idéntica la estrategia de slicing y boundary actuales leyendo desde la fuente declarativa; una heurística puede ajustarse editando solo ese archivo; cada historia justifica su patrón; boundary de enablers intacto; suite y evals sin regresión.
- Afecta: nueva fuente de slicing + loader, `pyproject.toml`, `sentinel/generation.py`, `tests/`, skill `sentinel-backlog`, `user_guide/02-artifact-reference.md`.
- Nota 2026-06-13: externalizado el modelo a `sentinel/slicing/backlog_slicing_model.json` con loader `sentinel/slicing_model.py` (cache + override para tests). El render de `EPIC-001` lee desde esa fuente y reproduce la tabla "Slicing Strategy" y el "Cross-Cutting Enabler Boundary" sin cambiar criterios. Las historias derivadas de `SPEC-U-*` ahora seleccionan un patrón existente por forma de unidad y registran `slicing_rationale` en `EPIC-001`, `US-NNN.md` e `implementation_readiness.json`. El fixture `ops-risk-backlog` actualiza su answer-key de slicing y `tests/test_slicing_model.py` cubre externalización, override y selección. Skill `sentinel-backlog`, mirrors y guías actualizadas. No se tocó el flujo de `EPIC-002`.

### IMP-050 — Lifecycle de historia con estados gobernados + owner
- Estado: VERIFIED
- Problema: el runtime no modela estado de historia ni responsable; no hay seguimiento humano ni accountability por historia.
- Alcance: agregar `status` y `owner` por historia en frontmatter de `US-NNN.md` y `state.json`, mutados solo vía CLI. Implementar `/story-status PROJECT_ID --story US-NNN --set STATE [--owner NAME]` o equivalente, con estados `Draft → Ready → In Progress → In Review → Done`, más `Blocked` y `Stale`, validación de transiciones, trazabilidad y preservación entre regeneraciones.
- Aceptación: una transición válida actualiza `US-NNN.md`, `state.json` y trazabilidad; una transición ilegal se rechaza con mensaje claro; `/backlog` preserva estados/owners existentes; sin estados asignados, comportamiento igual al actual; tests de transición y preservación.
- Afecta: `sentinel/generation.py`, nuevo módulo o extensión de backlog status, `sentinel/cli.py`, `sentinel/workspace.py`, `sentinel/templates/commands_manifest.json`, adapters regenerados, `sentinel/mcp.py`, `sentinel/traceability.py`, `tests/`, `user_guide/01-command-reference.md`, `user_guide/02-artifact-reference.md`, `user_guide/11-chat-commands.md`.
- Nota 2026-06-13: implementado `sentinel/backlog_status.py` y comando `/story-status PROJECT_ID --story US-NNN --set STATE [--owner NAME]`. El lifecycle vive en `state.json#story_lifecycle`, se refleja en frontmatter y sección `Lifecycle` de `US-NNN.md`, agrega `04_backlog/status_log.md`, nodo `story_status_change` y edge `updates_story_status`; `postflight` refresca trace/matrix y command protocol. `/backlog` aplica `apply_lifecycle_to_stories` para preservar status/owner y propaga `story_status`/`owner` en `implementation_readiness.json` sin reemplazar el campo `status` de readiness. Tests cubren transición válida, transición ilegal `Draft → Done` y preservación tras regeneración; eval `ops-risk-backlog` mueve `US-004` a `Ready` con owner y valida state/frontmatter. DoR/DoD gates quedan fuera de scope para IMP-051.

### IMP-051 — Convertir los checklists DoR/DoD ya existentes en un gate evaluable
- Estado: PENDING
- Problema: las historias ya renderizan Definition Of Ready y Definition Of Done, pero son checklists estáticos sin evaluación ni conexión con estado o handoff.
- Alcance: conservar los checklists actuales y agregar evaluación por historia usando señales existentes: AC presentes y clasificadas, `readiness_score`, ausencia de `GAP-*` blocking sobre la traza, patrón de slicing y owner. DoD exige evidencia de aceptación trazada desde downstream. Reusar el patrón `config.specs_gate {threshold, strict}` como `config.backlog_gate`, default advertencia, modo estricto opt-in.
- Aceptación: una historia incompleta no alcanza `Ready` en modo estricto y en default lista faltantes exactos; una historia completa pasa DoR; DoD solo cierra con evidencia trazada; default no bloqueante.
- Afecta: nuevo módulo de backlog status/validación, `sentinel/maturity.py`, config de workspace, `tests/`, `user_guide/01-command-reference.md`, `user_guide/05-traceability-and-memory.md`.
- Nota 2026-06-13: implementado `sentinel/backlog_gates.py` con evaluación DoR/DoD por historia, `config.backlog_gate {threshold, strict}` blando por default, persistencia en `state.json#story_gates`, render `[x]/[ ]` de checklists existentes y campos `dor`/`dod` en `implementation_readiness.json`. `/story-status` ahora devuelve warnings de gate, bloquea `Ready`/`Done` solo con strict opt-in y acepta `--evidence PATH` para registrar evidencia local trazada (`story_acceptance_evidence` + edge `acceptance_evidence_for`). Tests cubren default no bloqueante, strict block, DoR passing con contexto de dominio y DoD con evidencia; eval `ops-risk-backlog` valida DoR/DoD persistidos.

### IMP-052 — Rollup por épica + tablero de backlog para el BA
- Estado: VERIFIED
- Problema: el BA no tiene una vista versionable de progreso para seguimiento y accountability.
- Alcance: computar rollup por épica (historias por estado, porcentaje `Ready`/`Done`, `avg readiness_score`, owners y blockers), emitir `04_backlog/BACKLOG.md`, exponer resumen en `/status` y agregar `/backlog-status PROJECT_ID`.
- Aceptación: con historias en varios estados, `BACKLOG.md` y `/backlog-status` muestran rollup correcto por épica y estado; `/status` incluye resumen; el tablero se regenera sin pisar estados; tests de rollup.
- Afecta: `sentinel/generation.py` o nuevo módulo de rollup, `sentinel/status.py`, `sentinel/cli.py`, `commands_manifest.json`, adapters regenerados, `sentinel/mcp.py`, `tests/`, `user_guide/01-command-reference.md`, `user_guide/02-artifact-reference.md`, `user_guide/11-chat-commands.md`.
- Nota 2026-06-13: implementado `sentinel/backlog_rollup.py` y comando `/backlog-status PROJECT_ID` para generar `04_backlog/BACKLOG.md` desde `state.json#story_lifecycle`, `state.json#story_gates`, `04_backlog/US-NNN.md` e `implementation_readiness.json`. `/backlog` y `/story-status` refrescan el tablero, `/status` expone `backlog_rollup`, MCP y adapters quedan alineados, y el board cuenta historias por estado/épica, incluyendo `EPIC-002` cuando hay enablers concretos materializados. Tests cubren rollup, status y surfaces; eval `ops-risk-backlog` valida tablero/estado persistido tras mover `US-004` a `Ready`. El tablero es vista generada, no SSoT editable.

### IMP-053 — Plan de slice e implementación (handoff contract determinístico)
- Estado: VERIFIED
- Problema: no hay plan ordenado por épica/release que explicite enablers, paralelismo, dependencias y checkpoints; el bridge a tasking queda implícito.
- Alcance: emitir `04_backlog/SLICE-PLAN.md` y JSON espejo en `08_context_packs/` con fase de enablers (`EPIC-002`), olas paralelizables de historias, checkpoints y handoff pack por historia (`execution_contract` + `retrieval_plan` + anchors + posición + estado DoR). Mantener vocabulario Ignite; no copiar `T001/[P]` ni ejecutar tasking.
- Aceptación: `/backlog` o `/handoff` produce slice plan con enablers primero, olas paralelizables y checkpoints derivados de dependencias reales; handoff pack valida campos o marca `[PENDING ...]`; un agente downstream puede ordenar implementación leyendo slice plan + packs; tests de estructura y orden topológico.
- Afecta: `sentinel/generation.py`, `sentinel/retrieval_plans/backlog_generation.json`, `tests/`, skill `sentinel-backlog`, `user_guide/02-artifact-reference.md`, `user_guide/03-workflows.md`.
- Nota 2026-06-13: implementado `sentinel/slice_plan.py` y wiring en `/backlog` para emitir `04_backlog/SLICE-PLAN.md` + `08_context_packs/slice_plan.json`. El plan deriva una fase de enablers concretos `EPIC-002`, olas de historias paralelizables por dependencias reales/enabler links, checkpoints y `handoff_packs.US-NNN` con posición, estado, DoR/DoD, `execution_contract`, `retrieval_plan`, anchors, validación y trazas. No introduce task IDs, estimates ni ejecución downstream. Tests cubren orden topológico/enablers primero y core flow; eval `ops-risk-backlog` valida artefactos, conteo, handoff pack y contenido mínimo. Docs y skill `sentinel-backlog` actualizadas.

### IMP-054 — Contrato de tareas-semilla por historia (opcional / frontera de scope)
- Estado: VERIFIED
- Problema: algunos agentes downstream pueden necesitar un punto de partida de tasking más explícito, pero Ignite no debe convertirse en herramienta de tasking.
- Alcance: agregar emisión opt-in (`/backlog --with-task-seeds` o `/handoff --task-seeds`) de un contrato mínimo de tareas-semilla por historia, trazado a AC y `critical_surfaces`, ordenado y con paralelismo indicado. No ejecuta, no estima, no gestiona tareas y documenta explícitamente el límite de scope.
- Aceptación: con el flag, cada historia emite contrato de tareas-semilla trazado y con nota de frontera; sin flag no se emite nada; el artefacto deja claro que Ignite no ejecuta tasking.
- Afecta: `sentinel/generation.py`, `sentinel/cli.py`, manifest/adapters si se agrega flag, `tests/`, `user_guide/02-artifact-reference.md`.
- Nota 2026-06-14: implementado `/backlog --with-task-seeds` como contrato opt-in por historia. El modo default no emite `Task Seed Contract`; con flag, cada `US-NNN.md` y `implementation_readiness.json` incluyen semillas `TSEED-US-NNN-*` derivadas de AC y `Agent Execution Contract.critical_surfaces`, con orden, paralelismo y dependencias. La nota de frontera aclara que Ignite no ejecuta, estima, asigna, agenda ni gestiona tareas, y que downstream puede expandir/reordenar/descartar las semillas preservando scope y trazabilidad. Se actualizó CLI, MCP, manifest/adapters, skills, README y user guide. Tests cubren ausencia por default y emisión opt-in; eval `ops-risk-backlog` valida contrato, AC trazada y nota de frontera.

### IMP-055 — Hooks de ciclo vivo: staleness por historia, pre-handoff (DoR) y privacy scan
- Estado: VERIFIED
- Problema: el ciclo vivo del backlog se gobierna a grano grueso; no hay staleness por historia, pre-handoff DoR ni privacy scan específico de backlog.
- Alcance: agregar hooks deterministas y locales al protocolo Sentinel: marcar `Stale` solo historias afectadas por `stale_spec_units`, advertir/bloquear handoff según DoR y modo de gate, y escanear artefactos de `04_backlog/` contra identificadores sensibles, endpoints, credenciales o datos privados antes de escribir.
- Aceptación: `/sync` que cambia una Spec Unit marca `Stale` solo historias derivadas; handoff sin DoR advierte o bloquea según modo; un artefacto de backlog con dato sensible inyectado se detecta y bloquea; sin novedades, comportamiento intacto; tests verdes.
- Afecta: `sentinel/protocols.py`, `sentinel/sync.py`, `sentinel/health.py`, `sentinel/generation.py`, `tests/`, `user_guide/05-traceability-and-memory.md`, `user_guide/09-secure-environments.md`.
- Nota 2026-06-13: implementado `sentinel/backlog_hooks.py` con hooks locales y determinísticos. `/sync` detecta `SPEC-U-*` en la fuente del cambio y marca `Stale` solo las historias cuyo `implementation_readiness.json` deriva de esas unidades, actualizando `state.json#story_lifecycle`, frontmatter, `status_log.md`, board y trazabilidad `story_staleness`. `SLICE-PLAN.md`/`slice_plan.json` incluyen `pre_handoff_gate`: warning por default y bloqueo solo con `backlog_gate.strict: true`. `protocols` y `/backlog` ejecutan privacy scan de `04_backlog/` contra credenciales, auth headers, endpoints no-ejemplo, emails e identificadores privados; `/health` reporta stories stale y findings de privacidad. Tests nuevos cubren staleness selectivo, gate blando/estricto y bloqueo por dato sensible; eval `ops-risk-backlog` valida pre-handoff WARN y stale por `SPEC-U-001`.

### IMP-056 — `/quality` verifica el cumplimiento del modelo INVEST/SPIDR que hoy es solo guía
- Estado: VERIFIED
- Problema: el modelo INVEST/SPIDR/Lawrence ya existe como guía, pero `/quality` no verifica si una historia lo cumple; el `backlog_readiness_audit.md` tiene verdict/status hardcodeados.
- Alcance: extender `/quality` para puntuar solo el modelo vigente: slice vertical e independiente, `Small` como small but valuable, AC presentes/clasificadas y derivadas de la unidad, trazabilidad `SPEC-U`/`REQ-EARS`/épica y cobertura de AC. Poblar `05_quality/backlog_readiness_audit.md` con evaluación real por historia y warnings no bloqueantes que alimenten DoR.
- Aceptación: `/quality` reporta score INVEST y cobertura de AC por historia con verdict/status dinámicos; distingue historia bien sliceada de técnica sin comportamiento; warnings se reflejan en DoR; no bloquea por default; tests de niveles.
- Afecta: `sentinel/quality.py`, `sentinel/validation.py`, `tests/`, skill `sentinel-quality`, `user_guide/01-command-reference.md`.
- Nota 2026-06-13: implementado scoring determinístico de story quality en `/quality` contra el modelo vigente INVEST/SPIDR/Lawrence sin modificar la tabla "Slicing Strategy" ni el boundary `EPIC-002`. `backlog_readiness_audit.md` ahora emite verdict dinámico, score por historia, checks `slicing_pattern_governed`, `vertical_slice`, `small_but_valuable`, `acceptance_criteria_coverage`, `traceability_chain` e `independent_dependencies`; `state.json#story_quality` persiste resultados y `state.json#story_gates` recibe el ítem DoR `story_quality_invest` solo después de `/quality`. Warnings blandos por default; strict sigue opt-in vía `config.backlog_gate`. Tests cubren historia técnica sin comportamiento vs. historia evaluada y preservación de owner/DoR; eval `ops-risk-backlog` ejecuta `/quality` y valida score, audit y gate.

### IMP-057 — Contexto y cobertura de dominio por historia/Spec Unit
- Estado: DONE
- Problema: `build_backlog_story_specs` asigna el mismo `domain_coverage` y `execution_contract` a todas las historias desde el pack global del epic.
- Alcance: que cada historia derivada de su Spec Unit arme mini-contexto focalizado con `ContextBroker.retrieve`, planes declarativos y query de su unidad, manteniendo el pack global como índice agregado. Computar `execution_contract` y `domain_coverage` por historia, respetando budgets, `summary_only`, local-first y fallback `json-hybrid`.
- Aceptación: en un fixture con al menos dos Spec Units de dominios distintos, dos historias obtienen `critical_surfaces`/`domain_coverage` distintos y acordes a su unidad; pack global conserva cobertura agregada; budgets respetados; evals de retrieval y suite sin regresión; modo `json-hybrid` intacto.
- Afecta: `sentinel/generation.py`, `sentinel/retrieval_plans/backlog_generation.json`, `08_context_packs/`, `tests/`, skill `sentinel-backlog`, `user_guide/02-artifact-reference.md`, `user_guide/05-traceability-and-memory.md`.
- Nota 2026-06-13: implementado mini-contexto por historia en `build_backlog_story_specs`: cada `US-NNN` derivada de `SPEC-U-*` ejecuta el plan declarativo `backlog_generation` con query enriquecida por su unidad, guarda el resultado bajo `08_context_packs/backlog_generation.json#per_story.US-NNN`, y calcula desde ahí `domain_coverage` y `execution_contract`. El pack global mantiene `sections` y `domain_context_coverage` agregados. `implementation_readiness.json` ahora incluye `execution_contract`, `context_pack` y `context_pack_section` por historia. El runner de evals copia fixtures de contexto de dominio a carpetas `00_raw/*_context` antes de `/ingest`, y `ops-risk-backlog` valida `critical_surfaces` distintos para al menos dos Spec Units. Tests y docs actualizados; adapters regenerados desde `python -m sentinel.adapters`. No se modificó el modelo de slicing ni el boundary de `EPIC-002`.

### IMP-058 — Propagar anchors (`read_plan`) al contrato y al handoff por historia
- Estado: DONE
- Problema: los anchors existen en `backlog_generation.json`, pero no llegan al `execution_contract`, al `US-NNN.md` ni a `implementation_readiness.json`.
- Alcance: propagar `source_path`, `section_path`, `line_start` y `line_end` de cada evidencia usada por historia al contrato, render de historia y handoff JSON, como campos aditivos compatibles con consumidores actuales.
- Aceptación: el `execution_contract` y `implementation_readiness.json` incluyen anchors válidos por superficie citada; un test abre el archivo y verifica que el rango contiene la sección citada; consumidores actuales intactos; suite y evals sin regresión.
- Afecta: `sentinel/generation.py`, `tests/`, `user_guide/02-artifact-reference.md`, `user_guide/05-traceability-and-memory.md`.
- Nota 2026-06-13: implementado como campos aditivos `anchor` dentro de las señales confirmadas del `execution_contract` (`commands`, `critical_surfaces`, `design_match`, `engineering_practices` cuando hay evidencia recuperada). Cada anchor propaga `source_path`, `section_path`, `line_start` y `line_end` desde `read_plan`; `US-NNN.md` renderiza el puntero inline y `implementation_readiness.json` lo conserva dentro del contrato completo. El fixture `ops-risk-backlog` activa `anchors.require_valid`; `tests/test_backlog_dynamic_derivation.py` abre el archivo citado y verifica que el rango contiene la evidencia de la superficie crítica. Docs y skill `sentinel-backlog` actualizadas; adapters regenerados. Campos existentes (`status`, `source`, `summary`) quedan intactos.

### IMP-059 — Canal agéntico de refinamiento del backlog
- Estado: VERIFIED
- Problema: el backlog no tiene canal sancionado para propuestas agénticas de slicing, historias o enablers; el criterio queda en chat.
- Alcance: nuevo comando + skill, por ejemplo `/refine-backlog PROJECT_ID --source ANALYSIS.json`, que recibe propuestas estructuradas con cita textual verbatim local. Reusar validación de `/compose`: validar existencia, rechazar unidades `[PENDING]`, verificar citas, archivar source en `04_backlog/refinements/`, mergear con `origin: agent`, trazar y respetar boundary de enablers.
- Aceptación: una propuesta válida se mergea con `origin: agent` y trazabilidad; una inválida se rechaza con razón clara; historias/enablers refinados respetan lifecycle y gates; el modelo SPIDR/Lawrence/INVEST no se altera; suite y evals sin regresión.
- Afecta: nuevo módulo o extensión de `generation.py`, `cli.py`, schema `backlog_refinement.schema.json`, `commands_manifest.json`, adapters regenerados, `mcp.py`, skill `sentinel-backlog-refine`, `traceability.py`, `tests/`, `user_guide/01-command-reference.md`, `user_guide/02-artifact-reference.md`, `user_guide/11-chat-commands.md`.
- Nota 2026-06-13: implementado `/refine-backlog PROJECT_ID --source ANALYSIS.json` con `sentinel/backlog_refinement.py`, schema JSON, skill `sentinel-backlog-refine`, MCP manual y adapters regenerados. El runtime valida `proposals[]` (`reslice`, `split-story`, `merge-stories`, `missing-story`, `enabler-candidate`), exige citas verbatim locales, rechaza historias stub/unidades pendientes, archiva el source en `04_backlog/refinements/`, persiste `accepted_refinements.json`, reporta aceptadas/rechazadas, agrega overlay `Agent Backlog Refinements` en épica/historias con `origin: agent`, traza `backlog_refinement` y no reescribe el modelo INVEST/SPIDR/Lawrence ni el boundary de `EPIC-002`. Tests nuevos cubren merge válido, cita fabricada y enabler loose; eval `ops-risk-backlog` agrega propuesta BREF citada y el runner la valida.

### IMP-060 — Loop de feedback downstream → backlog
- Estado: VERIFIED
- Problema: cuando implementación descubre dependencias, gaps, AC inválidas o superficies no contempladas, no hay canal sancionado que vuelva al backlog.
- Alcance: agregar canal de feedback de implementación, por ejemplo `/implementation-feedback PROJECT_ID --source FINDINGS.json` o modo especializado de `/sync`, donde cada hallazgo declara tipo, historia/AC afectada y evidencia. El runtime convierte hallazgos en `GAP-*` o `CHG` trazados ligados a historia, puede marcar `Stale` o bloquear DoD, y no permite reescritura directa del backlog.
- Aceptación: feedback estructurado produce gaps/CHG ligados a la historia correcta y, si corresponde, la marca `Stale` y bloquea DoD; downstream solo abre gaps/decisiones, no reescribe historias; sin feedback, comportamiento idéntico; tests verdes.
- Afecta: `cli.py`, `sync.py` o módulo nuevo, schema `implementation_feedback.schema.json`, `traceability.py`, `commands_manifest.json`, adapters regenerados, `mcp.py`, `tests/`, `user_guide/05-traceability-and-memory.md`, `user_guide/11-chat-commands.md`.
- Nota 2026-06-13: implementado `/implementation-feedback PROJECT_ID --source FINDINGS.json` con `sentinel/implementation_feedback.py` y schema JSON. El canal valida `findings[]` (`new-dependency`, `gap`, `ac-challenge`, `surface-not-covered`), exige historia/AC existente y evidencia, archiva el source en `07_changes/05_implementation_feedback/`, escribe `feedback_report.md`, abre `GAP-FEEDBACK-*` cuando corresponde, traza nodos `implementation_feedback`/`implementation_feedback_gap`, marca solo historias afectadas como `Stale` vía `source_units`, refresca `story_gates` y agrega DoD `implementation_feedback_resolved`. No reescribe scope, slicing ni boundary de `EPIC-002`; gates siguen blandos por default y estricto bloquea `Done`. MCP/manual, manifest/adapters, skills, README y user guide actualizados. Tests nuevos cubren feedback válido, story inexistente y bloqueo DoD; eval `ops-risk-backlog` agrega `IFB-OPS-001`; `.\verify.ps1` verde.

### IMP-061 — Evals/answer-keys propios del backlog
- Estado: VERIFIED
- Problema: Discovery y Specs tienen harness, pero Backlog no tiene answer keys estructurados para falsar derivación, no-invención, slicing, contexto por historia ni anchors.
- Alcance: extender `tests/fixtures/evals/` y `tests/evals/run_discovery_evals.py` o crear `run_backlog_evals.py` con answer keys de backlog por fixture: historias esperadas desde Spec Units, no-invención, patrón de slicing esperado, contexto/critical surfaces distintos por historia y anchors válidos. Registrar baseline en este backlog.
- Aceptación: el runner reporta cobertura de derivación, tasa de no-invención, acierto de slicing pattern y validez de anchors; baseline documentado; integrado a `verify.ps1`; falla solo ante regresión nueva.
- Afecta: `tests/fixtures/evals/`, `tests/evals/`, README de fixtures, `docs/evolution/02-backlog-mejoras.md`.
- Nota 2026-06-13: implementado como extensión del runner existente `tests/evals/run_discovery_evals.py`, integrado a `verify.ps1` sin comando nuevo. Los answer keys `backlog` ahora miden `expected_story_ids`, `expected_source_units`, stub pendiente/no-invención, `expected_slicing_by_source_unit`, anchors opt-in y contexto opt-in. Baseline local: 5 fixtures OK; `ops-risk-backlog` cubre 6 historias derivadas de `SPEC-U-001`…`SPEC-U-006`; los otros 4 fixtures cubren stub `[PENDING INPUT]` sin invención; `avg_backlog_derivation_coverage=1.00`, `avg_backlog_no_invention=1.00`, `avg_backlog_slicing=1.00`, `avg_backlog_anchors=1.00`. Agregado `tests/test_backlog_eval_metrics.py` para falsar stub, historia inventada y mismatch de slicing. No toca runtime de backlog ni el modelo "Slicing Strategy"/boundary de `EPIC-002`.

---

## Horizonte 9 — Dashboard

Ítems promovidos desde `docs/evolution/07-propuesta-dashboard.md` (PROPUESTA PARA IMPLEMENTAR 2026-06-14). Fuente de diseño obligatoria: propuesta 07 completa, especialmente protocolo de sección 0, tablas declarativas de sección 4 y aceptación de sección 5. Referencia visual exacta: `docs/evolution/07-dashboard-prototype-reference.html`. Orden estricto por PR: IMP-063 → IMP-064; no iniciar IMP-064 hasta que IMP-063 esté mergeado en `main`.

### IMP-063 — Runtime + comando `/dashboard` (engine determinístico)
- Estado: VERIFIED & PUSHED & MERGED (2026-06-15, branch `imp-063-dashboard-runtime`, PR #61: https://github.com/jmatzkin1980/ignite-sentinel/pull/61; merge manual confirmado por el usuario; `powershell -ExecutionPolicy Bypass -File .\verify.ps1` verde: 164 tests OK, `/doctor` PASS con warnings opcionales esperados, discovery evals OK).
- Implementado por Codex: `sentinel/dashboard.py` agrega el modelo de cartera, `LIFECYCLE_STAGES`, `SECTION_REGISTRY`, render HTML autocontenido y `generate_dashboard`; `/dashboard` quedó registrado sin `PROJECT_ID` con `--root`/`--open`; `dashboard.html` quedó git-ignored y `/doctor` incluye un chequeo suave de política; adapters Kilo/Claude se regeneraron desde `commands_manifest.json`; MCP expone `sentinel_dashboard`; tests sintéticos cubren workspaces en discovery/backlog, secciones omitidas, documentos embebidos, gaps copiables y read-only.
- Prioridad / orden: 1 de 2 — implementar primero. Sin dependencias.
- Problema: no hay una vista de cartera local-first para ver de un vistazo la fase, health, gaps, siguiente paso, documentos y backlog de todos los workspaces sin navegar archivos `.md`.
- Alcance: crear `sentinel/dashboard.py` con `collect_dashboard_model`, `LIFECYCLE_STAGES`, `SECTION_REGISTRY`, `render_html` y `generate_dashboard`; registrar `/dashboard` en `sentinel/cli.py` sin `project_id` y con flags `--root`/`--open`; agregar el comando al manifest y regenerar adapters; agregar `dashboard.html` a `.gitignore`; chequeo suave en `/doctor`; tests con workspaces sintéticos; actualizar README, `user_guide/01-command-reference.md` y CHANGELOG. Render stdlib-only, read-only, local-first y sin tocar `/status`.
- Aceptación: `python -m sentinel /dashboard` genera `dashboard.html` en la raíz con todos los workspaces reales excepto `_template`, fecha/hora visible, HTML autocontenido offline, portfolio + drawer + pipeline + gaps copiables + documentos en modal markdown, secciones sin datos omitidas, adapters sincronizados y `.\verify.ps1` verde antes del commit.
- Afecta: `sentinel/dashboard.py`, `sentinel/cli.py`, `sentinel/templates/commands_manifest.json`, adapters regenerados, `sentinel/doctor.py`, `.gitignore`, `tests/test_dashboard.py`, fixtures/evals sintéticos, README, `user_guide/01-command-reference.md`, CHANGELOG.
- Depende de: nada.

### IMP-064 — Skill `sentinel-dashboard` + reference de evolución + docs de usuario
- Estado: VERIFIED & PUSHED (2026-06-15, branch `imp-064-dashboard-skill`, PR #62: https://github.com/jmatzkin1980/ignite-sentinel/pull/62; `powershell -ExecutionPolicy Bypass -File .\verify.ps1` verde: 164 tests OK, `/doctor` PASS con warnings opcionales esperados, discovery evals OK). Pendiente: merge manual del usuario.
- Prioridad / orden: 2 de 2 — implementar segundo, recién con IMP-063 mergeado en `main`.
- Problema: el comando necesita una skill para que un BA/PM lo pueda pedir en lenguaje natural e interpretar, y una referencia mantenedora para extender el registry sin stale UI.
- Alcance: crear `.codex/skills/sentinel-dashboard/SKILL.md` y `references/section-registry.md`; regenerar mirrors `.agents/skills/` y `.claude/skills/`; agregar página de dashboard al user guide, fila en `user_guide/11-chat-commands.md`, mención en README y CHANGELOG.
- Implementado por Codex: skill canónica `.codex/skills/sentinel-dashboard/` con workflow por intención natural, reglas read-only/local-first e interpretación de señales; reference `references/section-registry.md` con contrato para agregar secciones y readiness stages; `sentinel-command-router` reconoce `/dashboard`; `/doctor` exige el skill canónico; mirrors `.agents/skills/sentinel-dashboard/` y `.claude/skills/sentinel-dashboard/` regenerados; test de sync de skills ampliado; nueva guía `user_guide/14-dashboard.md`, Intent-To-Command Map, README y CHANGELOG alineados.
- Aceptación: la skill dispara por intención natural, corre `/dashboard`, presenta/resume el HTML generado, documenta read-only/local-first y deja pasos concretos para agregar secciones o readiness stages. Skills regeneradas, test de sync verde y `.\verify.ps1` verde antes del commit.
- Afecta: `.codex/skills/sentinel-dashboard/`, mirrors regenerados, `user_guide/`, README, CHANGELOG.
- Depende de: IMP-063 mergeado.

---

## Registro de cambios del backlog

| Fecha | Cambio |
|---|---|
| 2026-06-15 | IMP-064 VERIFIED & PUSHED (branch `imp-064-dashboard-skill`, PR #62): skill `sentinel-dashboard`, reference de registry para secciones/stages, mirrors `.agents/.claude` regenerados, doctor/test de sync ampliados y docs de usuario alineadas. `verify.ps1` verde. |
| 2026-06-15 | IMP-063 confirmado MERGED por el usuario y arranque de IMP-064 en branch `imp-064-dashboard-skill`: skill `sentinel-dashboard`, reference de registry, docs de usuario y mirrors a regenerar. |
| 2026-06-14 | IMP-063 VERIFIED & PUSHED (branch `imp-063-dashboard-runtime`, PR #61): agregado `/dashboard` portfolio read-only, HTML autocontenido `dashboard.html` git-ignored, registry declarativo de lifecycle/secciones, adapters regenerados, MCP local, tests sintéticos y docs públicas. `verify.ps1` verde. |
| 2026-06-14 | Horizonte 9 "Dashboard" promovido desde `docs/evolution/07-propuesta-dashboard.md`: creados IMP-063 e IMP-064 como ítems `PENDING`, con orden estricto IMP-063 → IMP-064 y referencia visual obligatoria `07-dashboard-prototype-reference.html`. |
| 2026-06-13 | IMP-055 VERIFIED (branch `imp-055-lifecycle-hooks`): hooks locales de backlog para staleness por Spec Unit en `/sync`, pre-handoff DoR en `SLICE-PLAN` blando/strict opt-in, privacy scan bloqueante sobre `04_backlog/`, hallazgos en `/health` y eval `ops-risk-backlog` ampliado. |
| 2026-06-13 | IMP-056 VERIFIED (branch `imp-056-story-quality`): `/quality` ahora puntúa story quality contra INVEST/SPIDR/Lawrence vigente, persiste `state.json#story_quality`, alimenta DoR con `story_quality_invest` y vuelve dinámico `backlog_readiness_audit.md`; eval `ops-risk-backlog` ampliado. |
| 2026-06-13 | IMP-053 VERIFIED (branch `imp-053-slice-plan`): agregado `SLICE-PLAN.md` y `slice_plan.json` como handoff determinístico de backlog, con fase de enablers, olas paralelizables, checkpoints y handoff packs por historia. Sin tasking ni cambios al modelo de slicing/EPIC-002; eval `ops-risk-backlog` ampliado. |
| 2026-06-13 | IMP-052 VERIFIED (branch `imp-052-backlog-rollup`): agregado `/backlog-status`, `04_backlog/BACKLOG.md`, rollup por épica/estado/owners/blockers, resumen en `/status`, refresh automático desde `/backlog` y `/story-status`, MCP/adapters/docs actualizados y eval `ops-risk-backlog` ampliado. |
| 2026-06-13 | IMP-051 VERIFIED (branch `imp-051-dor-dod-gates`): DoR/DoD evaluable sobre los checklists existentes, `backlog_gate` blando/strict opt-in, warnings en `/story-status` y `/status`, bloqueo estricto de Ready/Done, evidencia local `--evidence` para DoD con trazabilidad, handoff JSON y eval `ops-risk-backlog` ampliados. |
| 2026-06-13 | IMP-050 VERIFIED (branch `imp-050-story-lifecycle`): agregado `/story-status` con máquina de estados gobernada, owner en `state.json`/frontmatter, status log, trazabilidad y preservación por `/backlog`; eval `ops-risk-backlog` valida `US-004 → Ready`. DoR/DoD estricto queda para IMP-051. |
| 2026-06-13 | IMP-059 VERIFIED (branch `imp-059-backlog-refine`): agregado `/refine-backlog` como canal agéntico sancionado para propuestas citadas de reslicing/split/merge/missing story/enabler candidate. Source archivado, accepted/report, overlay `origin: agent`, trazabilidad y eval fixture `ops-risk-backlog`; el modelo de slicing y boundary `EPIC-002` quedan preservados. |
| 2026-06-13 | IMP-049 VERIFIED (branch `imp-049-slicing-model`): modelo de slicing externalizado a `sentinel/slicing/backlog_slicing_model.json`, loader con override, selección de patrón/rationale por Spec Unit, answer-key de backlog actualizado y docs/skills alineadas. Tabla "Slicing Strategy" y boundary de `EPIC-002` preservados. |
| 2026-06-13 | IMP-061 VERIFIED (branch `imp-061-backlog-evals`): answer-keys de backlog formalizados en los 5 fixtures, runner extendido con métricas de derivación/no-invención/slicing/anchors/contexto, baseline `avg_backlog_* = 1.00`, tests unitarios del evaluador y documentación actualizada. Sin runtime ni adapters nuevos. |
| 2026-06-13 | Horizonte 8 "Backlog gobernado" promovido desde `docs/evolution/05-propuesta-backlog.md` (APROBADA): creados IMP-048…IMP-061 como ítems `PENDING`, con Problema/Alcance/Aceptación/Afecta y orden obligatorio de implementación. Cambio documental puro; sin runtime ni evals nuevos en este paso administrativo. |
| 2026-06-12 | IMP-046 VERIFIED & PUSHED (branch `imp-046-prd-grade-lens-checks`): checks PRD calibrados en lentes declarativos, nuevo `GAP-PRD-ROLLOUT-ENVIRONMENTS`, dicts de elicitación EN/ES extendidos, answer keys PRD actualizadas en los 4 fixtures, `test_prd_grade_lens_checks.py` y guía de artefactos actualizada. `verify.ps1` verde (109 tests OK), doctor PASS con warnings opcionales esperados y evals sin regresión. |
| 2026-06-12 | IMP-038 VERIFIED & PUSHED (branch `imp-038-prd-specs-evals`): eval harness extendido hasta PRD/specs, answer keys con `prd.target_populated`, respuestas sintéticas de fixture para atravesar gates reales, test `test_evals_prd.py` y baseline documentado: `avg_prd_target_coverage=0.06`, `avg_specs_scaffolding=11.00`. `verify.ps1` verde; sin cambios de runtime. |
| 2026-06-12 | Horizonte 8 promovido desde `docs/evolution/04-propuesta-prd-specs.md` (APROBADA): creados IMP-038…IMP-047 como "Fase PRD/Specs y preparación upstream", todos `PENDING`, con Problema/Alcance/Aceptación/Afecta/Depende/Prioridad y orden obligatorio de implementación. Cambio documental puro; sin runtime ni evals nuevos en este paso administrativo. |
| 2026-06-12 | Revisión post-Codex del handoff: reconciliadas 3 sub-secciones que IMP-036 dejó en futuro/desactualizadas — paso 4 del protocolo (afirmaba que IMP-029/030/031 no regeneraban adapters, falso porque IMP-031 agregó `/reindex --full`), nota de `lancedb` opcional, y "Mapa de superficies" (decía "hoy solo support-dashboard"; ahora son los 4 fixtures con `summary.by_backend`). Además: IMP-037 recategorizado a un **Horizonte 7 — Calidad y cobertura de tests** (era funcional, no documental como el H6); agregado al handoff un resumen "Qué dejó el Frente D" con el estado de la memoria (embedders, lancedb-hybrid+FTS+RRF, chunking estructural, evals por backend). Sin cambios de runtime. |
| 2026-06-12 | IMP-037 VERIFIED & PUSHED & MERGED (branch `imp-037-discovery-eval-coverage`, PR #29, merge `8a1bd3a`): evals de discovery ampliados para validar idioma detectado, metadata de gaps (`lens`/`severity`/`origin`), `origin: agent` en `/annotate`, y secciones de brief que deben quedar pending por falta de evidencia. `.\verify.ps1` verde (103 tests OK). |
| 2026-06-12 | IMP-036 VERIFIED & PUSHED (branch `docs-backlog-imp-status-notes`): reconciliación de estados del Horizonte 5, notas de cierre Codex por ítem y creación de IMP-034/035 para los cambios documentales fuera del backlog original. `.\verify.ps1` verde; pendiente de merge. |
| 2026-06-12 | IMP-035 VERIFIED & PUSHED & MERGED (branch `docs-readme-post-imp-sync`, PR #28, merge `d866e2a`): README alineado con EARS, telemetría de reapertura, memoria `json-hybrid`/`lancedb-hybrid`, extra `[memory-semantic]`, chunking/reindex incremental y evals de retrieval por backend. `.\verify.ps1` verde. |
| 2026-06-12 | IMP-034 VERIFIED & PUSHED & MERGED (branch `docs-user-guide-post-imp-sync`, PR #27, merge `fa075a7`): user guide alineada con las implementaciones cerradas del Horizonte 5. `.\verify.ps1` verde. |
| 2026-06-12 | IMP-031 VERIFIED & PUSHED & MERGED (branch `imp-031-structural-chunking`, PR #23, merge `9bf4998`): chunking heading-aware, tablas Markdown indivisibles, anchors `line_start`/`line_end`, `chunking_version`, `/reindex` incremental y `/reindex --full`; adapters regenerados. `.\verify.ps1` verde. Frente D (memoria) completo: IMP-032 → IMP-029 → IMP-030 → IMP-031. |
| 2026-06-12 | Toque menor IMP-032 VERIFIED & PUSHED & MERGED (branch `imp-032-retrieval-evals-followup`, PR #26, merge `6d9478f`): golden queries agregadas a los 4 fixtures de retrieval y reporte JSON con métricas por backend (`summary.by_backend`) para comparar `json-hybrid` vs `lancedb-hybrid`. `.\verify.ps1` verde. |
| 2026-06-12 | Toque menor IMP-028 VERIFIED & PUSHED & MERGED (branch `imp-028-telemetry-followup-sync-reopened`, PR #25, merge `ea0d19c`): telemetría distingue cierres por `client/domain/inference`, `/sync` reporta `Reopened Closed Gaps` y `/status` expone `reopened_by_sync_*`. `.\verify.ps1` verde. |
| 2026-06-12 | Toque menor IMP-026 VERIFIED & PUSHED & MERGED (branch `imp-026-ears-followup-citations`, PR #24, merge `4e9e4ae`): `REQ-EARS-*` ahora se cita en PRD/specs/backlog/context packs, `requirement.schema.json` acepta IDs/metadatos EARS y `.\verify.ps1` quedó verde. |
| 2026-06-12 | IMP-030 VERIFIED & PUSHED & MERGED (branch `imp-030-native-lancedb-retrieval`, PR #22, merge `d6e539f`): retrieval nativo LanceDB con upsert incremental por artefacto, FTS local sobre `text`, RRF vector/FTS, scoring `json-hybrid` normalizado, causa de degradación visible en `/doctor`, `/health` y context packs. `.\verify.ps1` verde. Próximo: IMP-031 (chunking estructural e incremental). |
| 2026-06-12 | IMP-029 VERIFIED & PUSHED & MERGED (branch `imp-029-semantic-embeddings`, PR #21, merge `34732c7`): embeddings semánticos locales opcionales con `Embedder` autodetectado (`model2vec` → `sentence-transformers` → `hash_embedding`), extra `[memory-semantic]`, metadata `embedder`/`embedding_version`, `/doctor` con nivel activo y fallback determinista intacto. `.\verify.ps1` verde. Próximo: IMP-030 (retrieval nativo LanceDB). |
| 2026-06-10 | Creación inicial con IMP-001..IMP-014 desde baseline y handoff §21. |
| 2026-06-10 | IMP-002 cerrado (handoffs viven fuera del repo). Agregados IMP-015 (discovery inquisitivo, prioridad #1) e IMP-016 (fixtures sintéticos) según prioridades del usuario. IMP-013 elevado a Horizonte 1 con decisión orientadora: lancedb opcional. |
| 2026-06-10 | Auditoría de adapters: Codex/Kilo/Claude validados sin issues (formatos, cobertura 1:1, referencias, doctor alineado, 17 tests OK, gates verificados con smoke lifecycle). Agregado Horizonte 4 con IMP-017 (MCP server local), IMP-018 (estándar Agent Skills), IMP-019 (fuente única de adapters), IMP-020 (eval harness de discovery). |
| 2026-06-11 | IMP-017 DONE: servidor MCP stdio local con 18 tools y gates estructurados. HORIZONTES 3 Y 4 COMPLETOS — roadmap inicial cerrado salvo verificación final de IMP-001. |
| 2026-06-11 | IMP-018 DONE: skills espejadas a .agents/skills y .claude/skills desde fuente canónica con test de drift. |
| 2026-06-11 | IMP-019 DONE: manifest único + generador + test de drift; doctor lee el manifest. |
| 2026-06-11 | IMP-012 DONE: Intent-To-Command Map en guía 11 referenciado por adapters. |
| 2026-06-11 | IMP-011 DONE: diffs de regeneración visibles, trazados e indexados. HORIZONTE 2 COMPLETO. |
| 2026-06-11 | IMP-010 DONE: cierre seguro con matices — ANSWERED, confirmed-but-vague y ambiguous visibles y trazables. |
| 2026-06-11 | IMP-009 DONE: staleness testeado E2E con dominio nombrado en el finding; fix de IDs estables en regeneración de backlog (upsert en add_node). |
| 2026-06-11 | IMP-008 DONE: maturity_score con tendencia entre corridas en /maturity y /status. HORIZONTE 1 COMPLETO. |
| 2026-06-11 | IMP-007 DONE: context packs con coverage_map, readiness_score y summary por dominio. |
| 2026-06-11 | IMP-006 DONE: /validate con score semántico no bloqueante por artefacto. |
| 2026-06-11 | IMP-005 DONE: PRD con personas/FRs/KPIs citando evidencia textual; [PENDING INPUT] sin señal. IMP-013 DONE: lancedb opcional con modo degradado json-hybrid. docs/ pasó a memoria local git-ignored (recuperada tras pull que la borró del worktree). |
| 2026-06-11 | IMP-015 DONE: tier inquisitivo con anclas de evidencia; target_recall 1.00; answer keys promovidos a must_fire. |
| 2026-06-10 | Ejecución del plan: IMP-003, IMP-004, IMP-016 y IMP-020 DONE; IMP-001 IN PROGRESS (falta renormalización local). Handoffs eliminados de la raíz (IMP-002 cerrado físicamente). Baseline de evals: recall 1.00, target_recall 0.00 — métrica de progreso para IMP-015. |
| 2026-06-11 | Horizonte 5 abierto: promovidos IMP-021…IMP-033 (13 ítems, Frentes A-D) desde la propuesta `03-propuesta-discovery-to-brief.md` (APROBADA). Todos PENDING. Ejecuta el paso 4 del protocolo de la sección 0. Orden A–C: IMP-027→IMP-033→IMP-021→IMP-022→IMP-024→IMP-025→IMP-023→IMP-026→IMP-028; Frente D: IMP-032→IMP-029→IMP-030→IMP-031. |
| 2026-06-11 | IMP-027 implementado (branch `imp-027-brief-semantic-evals`, pendiente de merge): cobertura de brief en el eval harness + answer keys de brief + fixture `expense-approval` que demuestra el techo léxico (target_recall 0.00) + test de regresión. Baseline: avg_target_recall 0.75, avg_brief_target_coverage 0.00. Primer ítem del Horizonte 5. |
| 2026-06-11 | IMP-027 MERGED a main. |
| 2026-06-11 | IMP-033 implementado (branch `imp-033-lens-knowledge-base`, pendiente de merge): conocimiento de lentes externalizado a `sentinel/lenses/*.json` (7 lentes, 26 checks) + loader `lens_registry.py` + `detect_gaps` declarativo (output idéntico verificado) + context-request consume la fuente + test de aceptación. Materializa el invariante #1. Suite 41 tests, doctor PASS, evals sin regresión. |
| 2026-06-12 | IMP-026 VERIFIED & PUSHED & MERGED (`verify.ps1` verde en Windows). |
| 2026-06-12 | IMP-032 implementado (branch sugerida `imp-032-retrieval-evals`, pendiente Windows+merge): golden queries + harness de retrieval (`test_evals_retrieval.py`) con recall@5/MRR y reporte JSON; same-language con gate ≥0.5, cross-lingual ES→EN como métrica de progreso (target de IMP-029). **Arranca el Frente D.** Próximo: IMP-029 (embeddings semánticos locales) → IMP-030 (retrieval nativo LanceDB) → IMP-031 (chunking estructural). |
| 2026-06-12 | IMP-028 implementado (branch sugerida `imp-028-telemetry`, pendiente Windows+merge): `maturation_telemetry` en `maturity_metrics` → `/status` y `/maturity` muestran `resolve_iterations`, cierre por procedencia (checklist/agent/challenge), `open_blocking_gaps` y `oldest_blocking_age_rounds`. `test_telemetry.py`. No requiere adapters. **Con esto el Frente A–C queda IMPLEMENTADO completo** (021,022,023,024,025,026,027,028,033). Pendiente: mergear IMP-028; arrancar **Frente D — arquitectura de memoria** en orden IMP-032 (eval de retrieval) → IMP-029 (embeddings semánticos) → IMP-030 (retrieval nativo LanceDB) → IMP-031 (chunking estructural). Toques menores anotados: cita EARS en specs/backlog (IMP-026), reabiertos-por-sync (IMP-028). |
| 2026-06-12 | IMP-026 implementado (branch sugerida `imp-026-ears`, pendiente Windows+merge): módulo `sentinel/ears.py` (5 patrones EN+ES) + acumulación EARS en `/resolve-gaps` → `requirements.md` (`REQ-EARS-*` con fuente y nodo `ears_requirement`). Solo respuestas confirmadas en sintaxis EARS; prosa queda como está. `test_ears.py`. No requiere regenerar adapters. Touch menor pendiente: cita explícita en specs/backlog + campo en requirement.schema.json. Próximo en orden A–C: **IMP-028 — Telemetría del ciclo de maduración** (último de Frente C; Frente A–C quedaría completo salvo merges). |
| 2026-06-12 | IMP-023 VERIFIED & PUSHED & MERGED (`python -m sentinel.adapters` + `verify.ps1` verde en Windows). |
| 2026-06-12 | IMP-023 implementado (branch sugerida `imp-023-challenge`, pendiente Windows+merge): comando `/challenge` (elicitación avanzada). Reutiliza la validación de `/annotate` (origin parametrizado) → hallazgos `origin: challenge` + `challenge_report.md` por lente con técnica (pre-mortem/role-play/inversión). Superficies: discovery, cli, protocols, manifest, mcp (20 tools), doctor, skill `sentinel-challenge`, guías 01/02/11, `test_challenge.py`. **Verificación Windows: correr `python -m sentinel.adapters` antes de `verify.ps1`** (materializa adapters del comando + mirrors de skill). Primer ítem post IMP-025; próximo en orden A–C: **IMP-026 — Normalización EARS**. |
| 2026-06-11 | **Cierre de sesión.** IMP-022 e IMP-024 VERIFIED & PUSHED (`verify.ps1` verde en Windows). IMP-025 IMPLEMENTED en el working tree (aún sin branch/commit; ver más abajo). Estado git: branches apiladas `main ← imp-021-annotate ← imp-022-gaps-as-elicitation ← imp-024-brief-compiler`, en origin, ninguna mergeada (faltan PRs, cada uno con base en la branch previa). **IMP-025 pendiente de empaquetar:** crear `git checkout -b imp-025-brief-readiness-gate` (apilada sobre imp-024), `git add sentinel/maturity.py tests/test_brief_readiness.py user_guide/01-command-reference.md`, commit, `.\verify.ps1`, push. **Próximo ítem nuevo (orden A–C): IMP-023 — Técnicas de elicitación avanzada (`/challenge`)** (depende de IMP-021; comando + skill que vuelca hallazgos como gaps `origin: challenge` vía el protocolo de `/annotate`). Recordatorio de entorno: mount de bash degradado en Cowork → implementar con file tools y verificar con `.\verify.ps1`; `python` cae en el alias de Store, usar `py`/`verify.ps1` (en CLAUDE.md). |
| 2026-06-11 | IMP-024 implementado (branch `imp-024-brief-compiler`, pendiente de verificación Windows + merge): brief compiler — las secciones 1–6 se compilan desde evidencia citada (raw input + respuestas de gaps cerrados) en vez de TBD. Nuevo `compile_brief_sections` en `maturity.py`, mapa `BRIEF_SECTION_FOR_GAP`/`brief_section_for_gap` en `discovery.py` (inverso de IMP-022), tagging de "Brief Section" en `/resolve-gaps`. Métrica `avg_brief_target_coverage` 0.00→1.00 en los 4 fixtures sin tocar detección. Tests: `test_evals_brief.py` actualizado + `test_brief_compiler.py`. Segundo ítem del Frente B (orden A–C). |
| 2026-06-11 | IMP-022 implementado (branch `imp-022-gaps-as-elicitation`, pendiente de verificación Windows + merge): gaps como elicitación — cada gap en `gaps.md` y en los context-requests expone por-qué (riesgo si queda abierto), qué-desbloquea (sección downstream que consume la respuesta, invirtiendo el mapeo de PRD Coverage/Backlog Readiness) y formato-esperado. Funciones `unblocks_for_gap`/`expected_format_for_gap` (EN/ES) en `discovery.py`; render de secciones y `lens_checks_section` enriquecidos. Trace table intacta → `parse_gap_rows` y `/resolve-gaps` sin cambios. Tests `test_gap_elicitation.py` (3 factores EN/ES, roundtrip, context-request). |
| 2026-06-11 | IMP-021 implementado (branch `imp-021-annotate`, pendiente de verificación Windows + merge): comando `/annotate` (protocolo de análisis agéntico). El agente propone gaps semánticos con cita textual; el runtime valida (lente declarado, severidad, evidencia verbatim), etiqueta `origin: agent`, mergea en `gaps.md` (columna `Origin`) y traza (`agent_annotation`). Rompe el techo léxico: `target_recall` de `expense-approval` 0.00 → 1.00 vía `/annotate` (métrica aditiva `avg_target_recall_with_annotations`, baseline léxico intacto). Superficies alineadas (cli, protocols, schema, mcp 19 tools, manifest+adapters, skill `sentinel-annotate`, doctor, user_guide 01/02/11, AGENTS/CLAUDE). Tests nuevos en `test_annotate.py`. Implementado bajo mount Cowork degradado: verificación obligatoria (`python -m sentinel.adapters` + unittest + doctor + evals) pendiente en la máquina del usuario. |
