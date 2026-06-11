# Backlog de Mejoras del Framework - Ignite Sentinel vNext

Backlog ejecutable del roadmap (`01-roadmap.md`). Cada ítem tiene ID estable `IMP-*`, estado y criterios de aceptación verificables. Estados: `PENDING | IN PROGRESS | DONE | DEFERRED`.

Convención de trabajo: branch propio por ítem, PR a `main`, actualizar el estado aquí en el mismo PR. Al cerrar un ítem, registrar fecha y commit/PR en su sección.

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
- Estado: PENDING
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
- Estado: PENDING
- Problema: `/doctor` falla sin `lancedb` aunque el broker tiene fallback JSON funcional. El usuario confirmó que en algunas VDIs de cliente NO puede instalarlo, por lo que el modo degradado debe ser un escenario soportado de primera clase, no un edge case.
- Decisión orientadora: lancedb pasa a opcional; `/doctor` lo reporta como WARN con capacidades degradadas explícitas y el broker opera en modo JSON determinístico. Alinear `pyproject.toml`, doctor, tests y `user_guide/09-secure-environments.md`.
- Aceptación: comportamiento definido, documentado y testeado en ambos entornos (con y sin lancedb); los 17 tests pasan en ambos modos o el modo sin lancedb tiene suite propia.
- Afecta: `sentinel/doctor.py`, `sentinel/memory.py`, `pyproject.toml`, `tests/`, guías.

### IMP-005 — Extracción mejorada de FRs, personas y KPIs
- Estado: PENDING
- Problema: PRD/specs caen en scaffolding genérico aun cuando la evidencia ingestada trae señales reales (handoff §21).
- Alcance: mejorar `discovery.py`/`generation.py` para extraer y citar FRs, personas y KPIs desde evidencia; mantener `[PENDING INPUT]` cuando no hay señal (nunca inventar).
- Aceptación: con fixture realista, el PRD generado contiene FRs/personas/KPIs citando evidencia fuente; tests nuevos cubren extracción positiva y caso sin evidencia.
- Afecta: `sentinel/discovery.py`, `sentinel/generation.py`, `tests/`, skills `sentinel-specs`, guías.

### IMP-006 — Validación semántica profunda en `/validate`
- Estado: PENDING
- Problema: `/validate` revisa estructura, prefijos y secciones, pero no completitud semántica (handoff §21).
- Alcance: detectar secciones con contenido placeholder/genérico vs. pobladas con evidencia; reportar score por artefacto; no bloquear, advertir.
- Aceptación: `/validate` distingue un PRD scaffolding de uno poblado en fixtures; salida documentada en `user_guide/01-command-reference.md`.
- Afecta: `sentinel/validation.py`, `tests/`, guías, skill `sentinel-health`.

### IMP-007 — Scoring y coverage en context packs
- Estado: PENDING
- Problema: `specs_generation.json` e `implementation_readiness.json` carecen de scoring, coverage map y evidencia rica por sección (handoff §21).
- Alcance: agregar por sección/story: score de evidencia, fuentes citadas, contexto pendiente cuantificado.
- Aceptación: ambos JSON incluyen los campos nuevos; agentes downstream pueden filtrar stories por readiness score; tests de esquema.
- Afecta: `sentinel/generation.py`, `sentinel/schemas/`, `tests/`, skill `sentinel-backlog`.

### IMP-008 — Métricas de madurez cuantificadas
- Estado: PENDING
- Problema: `/maturity` y `/status` informan estado cualitativo; falta una medida de cuánta evidencia respalda el brief/PRD.
- Alcance: porcentaje de secciones con evidencia vs. pendientes, conteo de gaps por severidad, tendencia entre corridas.
- Aceptación: `/status` muestra métricas; documentado en command reference; tests.
- Afecta: `sentinel/maturity.py`, `sentinel/status.py`, `tests/`, guías.

## Horizonte 2 — Robustez del lifecycle vivo

### IMP-009 — Tests de staleness de backlog
- Estado: PENDING
- Problema: la regla "contexto de dominio cambió después del backlog → `/health` marca stale" existe, pero su cobertura de test es limitada.
- Alcance: tests que simulen cambio de contexto post-backlog y verifiquen detección, mensaje y recomendación de `/reindex` + `/backlog`.
- Aceptación: tests nuevos verdes; regresión protegida.
- Afecta: `tests/`, posiblemente `sentinel/health.py`.

### IMP-010 — Matices en cierre de gaps
- Estado: PENDING
- Problema: `/resolve-gaps` cierra solo confirmado/no-aplica; los estados intermedios (respuesta ambigua, confirmación pendiente, respuesta parcial) merecen representación más rica.
- Alcance: estados intermedios visibles en `gaps.md` y `state.json`; reglas de qué bloquea maturity y qué no.
- Aceptación: fixture con respuestas mixtas produce estados correctos; `/maturity` respeta los bloqueos; tests.
- Afecta: `sentinel/gap_resolution.py`, `sentinel/maturity.py`, `tests/`, templates de gaps, skill `sentinel-gap-response`.

### IMP-011 — Diff visible de regeneración
- Estado: PENDING
- Problema: tras `/sync` + regeneración, no queda un resumen legible de qué cambió en artefactos downstream.
- Alcance: al regenerar un artefacto impactado, registrar resumen de cambios (secciones agregadas/modificadas/eliminadas) en `07_changes/` y referenciarlo en el impact report.
- Aceptación: tras un sync con impacto, existe artefacto de diff legible y trazado al nodo `CHG`; tests.
- Afecta: `sentinel/sync.py`, `sentinel/generation.py`, `tests/`, guías.

## Horizonte 3 — Experiencia y adopción

### IMP-012 — Chat-first refinado
- Estado: PENDING
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
- Estado: PENDING
- Problema: cada IDE nuevo requiere un adapter de chat commands propio. MCP es ya el protocolo estándar para que cualquier cliente (Claude Desktop, Claude Code, VS Code, Cursor, Codex) invoque herramientas.
- Alcance: servidor MCP stdio repo-local (`python -m sentinel.mcp`) que exponga los comandos del lifecycle como tools con schemas (init, ingest, gaps, resolve_gaps, maturity, brief, sync, specs, backlog, quality, trace, health, validate, status, retrieve). 100% local: stdio, sin red, compatible con local-first privacy. Los gates se devuelven como errores estructurados con next-step.
- Aceptación: configurable en Claude Desktop/Code y al menos otro cliente MCP; smoke test del lifecycle vía MCP; documentado en user guide; `/doctor` lo verifica.
- Afecta: `sentinel/` (módulo nuevo), `pyproject.toml` (dependencia opcional `mcp`), tests, guías, doctor.

### IMP-018 — Converger skills al estándar abierto Agent Skills
- Estado: PENDING
- Problema: las 12 skills viven solo en `.codex/skills/`. El formato SKILL.md ya es estándar multi-herramienta, pero cada agente las busca en su directorio (`.agents/skills/` Codex y otros, `.claude/skills/` Claude Code).
- Alcance: definir fuente canónica única de skills y materializarlas en los directorios estándar (copia generada o referencia, según soporte de cada tool). Las skills quedan utilizables por Claude Code, Codex, Cursor, Gemini CLI y demás lectores del estándar sin trabajo extra.
- Aceptación: misma skill visible y funcional desde Claude Code y Codex; sin divergencia de contenido entre directorios (verificado por test o script); doctor actualizado.
- Afecta: `.codex/skills/`, `.claude/skills/`, `.agents/skills/`, doctor, tests, guías.

### IMP-019 — Fuente única para adapters de comandos
- Estado: PENDING
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

---

## Registro de cambios del backlog

| Fecha | Cambio |
|---|---|
| 2026-06-10 | Creación inicial con IMP-001..IMP-014 desde baseline y handoff §21. |
| 2026-06-10 | IMP-002 cerrado (handoffs viven fuera del repo). Agregados IMP-015 (discovery inquisitivo, prioridad #1) e IMP-016 (fixtures sintéticos) según prioridades del usuario. IMP-013 elevado a Horizonte 1 con decisión orientadora: lancedb opcional. |
| 2026-06-10 | Auditoría de adapters: Codex/Kilo/Claude validados sin issues (formatos, cobertura 1:1, referencias, doctor alineado, 17 tests OK, gates verificados con smoke lifecycle). Agregado Horizonte 4 con IMP-017 (MCP server local), IMP-018 (estándar Agent Skills), IMP-019 (fuente única de adapters), IMP-020 (eval harness de discovery). |
| 2026-06-10 | Ejecución del plan: IMP-003, IMP-004, IMP-016 y IMP-020 DONE; IMP-001 IN PROGRESS (falta renormalización local). Handoffs eliminados de la raíz (IMP-002 cerrado físicamente). Baseline de evals: recall 1.00, target_recall 0.00 — métrica de progreso para IMP-015. |
