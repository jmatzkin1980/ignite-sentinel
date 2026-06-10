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
- Aceptación: con un fixture realista, los gaps generados incluyen preguntas ancladas a evidencia específica del input (citando qué disparó cada pregunta), no solo plantilla genérica; comparación antes/después documentada; tests con casos de detección.
- Afecta: `sentinel/discovery.py`, templates de gaps, `tests/`, skill `sentinel-discovery`, guías.

### IMP-016 — Suite de fixtures sintéticos realistas
- Estado: DONE (2026-06-10: 3 fixtures en `tests/fixtures/evals/` — dashboard EN, integración EN, portal ES — con answer keys empíricos que documentan `must_fire`, `must_not_fire`, `known_false_positives` y `target_fire`; README con criterio para agregar fixtures)
- Problema: la evolución se valida con data sintética hasta que el framework sea sólido y agnóstico, pero hoy los fixtures de test son mínimos. Sin requerimientos sintéticos realistas (con omisiones típicas de cliente real) no se puede medir si IMP-015/005/006 mejoran de verdad.
- Alcance: crear 2-3 requerimientos sintéticos de dominios distintos (p. ej. dashboard, integración, portal) con omisiones deliberadas y catalogadas; usarlos como banco de prueba de discovery y generación. Solo contenido inventado, sin rastro de clientes reales.
- Aceptación: fixtures versionados bajo `tests/fixtures/`, cada uno con su "answer key" de gaps esperados; tests que midan cobertura de detección contra ese answer key.
- Afecta: `tests/fixtures/`, `tests/`, posiblemente `docs/evolution/`.

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
- Afecta: `sentinel/gap_resolution.py`, `sentinel