# Handoff para la sesión local — Ignite Sentinel vNext (noviembre 2026)

> **CONGELADO 2026-11-05.** Por decisión de Jose, este documento se movió a la memoria local del mantenedor (`docs/evolution/`, git-ignored) y la versión vigente vive allí. Esta copia no se actualiza más y la rama no se mergea a `main`. Las propuestas accionables quedaron como Horizonte 13 en el backlog local.

> Leé este archivo primero. Resume el trabajo hecho en una sesión de Claude Code en la nube y deja todo listo para continuar en una sesión local.
> El análisis completo, con propuestas, evidencia y fuentes, está en [`2026-11-analisis-mejoras.md`](2026-11-analisis-mejoras.md). Este archivo **no lo repite**: agrega el contexto de la sesión, un mapa del repo, las decisiones tomadas, los pendientes y cómo seguir.

---

## 1. Dónde estamos

| Ítem | Estado |
|---|---|
| Branch | `claude/laughing-pasteur-uwkr3y`, derivado de `main` en `85ad22a` (PR #230) |
| Commits del branch | `0dc628c` análisis inicial → `846c8a5` sección 8 completada en la sesión local → `4ee83c2` corrección de dos contradicciones de la sección 8 → `3a8c002` este handoff → sección 9 (evals, fixtures y disco) en la sesión local |
| Archivos tocados | Solo `proposals/`. **No se modificó runtime, tests, skills ni adapters.** |
| PR | Ninguno abierto. No abrir un PR sin pedido explícito, y nunca mergear sin revisión (`MAINTAINERS.md`). |
| Tipo de trabajo hasta ahora | Análisis y propuestas, no implementación |

Para traer lo último:

```bash
git pull origin claude/laughing-pasteur-uwkr3y
```

---

## 2. Qué pidió el usuario, en orden

1. Un análisis exhaustivo del repositorio.
2. Mejoras funcionales sin perder el espíritu del proyecto, inspiradas en fuentes de autoridad (web y repos).
3. Mejoras técnicas, además de las funcionales.
4. Flujo más claro y sin huecos; modernizar las skills; comparar llm-wiki con LanceDB; optimizar procesos.
5. Distribución por marketplace, y skills preparadas para varios harness (Claude, Codex y Kilo), no solo para Claude.
6. Artefactos HTML navegables con visual inspirada en globant.com, tomando ideas de las skills en `C:\dev\.claude\skills`. Se completó en la sesión local porque la nube no tenía acceso al disco ni a globant.com.
7. Seguir todo en la sesión local (este archivo).

Preferencias del usuario:
- Explicaciones en español, con pasos concretos.
- Los agentes que se lancen deben ser **anidados a la sesión principal** (subagentes), no sesiones hermanas separadas.

---

## 3. Mapa rápido del repositorio

**Qué es.** Un framework repo-local y local-first para que un BA o Product madure requerimientos crudos hasta tener brief, PRD, specs, backlog, test cases y trazabilidad. Python 3.10+ sin dependencias obligatorias. LanceDB, embeddings y MCP son opcionales.

**Reglas que no se negocian** (`AGENTS.md` y `CLAUDE.md`):
- La fuente de verdad es `workspaces/<ID>/`; la memoria es reconstruible.
- Local-first.
- No inventar: lo que falta es `GAP-*` o `[PENDING INPUT]`.
- Mutar solo por CLI.
- `main` limpio.
- Evolucionar runtime, tests, skills, adapters, docs y `/doctor` juntos.
- De material confidencial, solo patrones genéricos.

**Estructura y módulos clave**

| Zona | Contenido |
|---|---|
| `sentinel/cli.py` | argparse con 32 comandos y despacho por if/elif |
| `sentinel/protocols.py` | Preflight (gates), postflight (trazabilidad, `command_log`, hashes de artefactos gobernados) y `command_protocol_log.md` |
| `sentinel/discovery/workflow.py` | 3.467 líneas: detección de gaps por lenses, render de `gaps.md`, entrevista y FAQ, canales agénticos (annotate, challenge, scrutiny) |
| `sentinel/maturity.py` | Métricas, readiness del brief y del PRD, `/brief` |
| `sentinel/compilers/` | `prd`, `specs`, `backlog`, `slicing` |
| `sentinel/backlog/` | Gates, hooks (privacy scan), refinement, rollup, status |
| `sentinel/knowledge/` | Ledger (`CONFIRMED`/`ASSUMED`/`OPEN`/`INFERRED`) y metabolismo |
| `sentinel/memory.py` | `ContextBroker`, LanceDB o `json-hybrid`, chunking con anclas |
| `sentinel/core/` | Markdown, IO JSON (caché y escritura atómica), rutas (`repo_root()` = `cwd`), state, grafo, tiempo |
| `sentinel/view.py`, `dashboard.py` | Los HTML de hoy, con dos sistemas visuales distintos |
| `sentinel/doctor.py` | Paridad de adapters, pureza stdlib, `SURFACE_CONTRACTS` |
| `sentinel/adapters.py` | Genera `.kilo/commands`, `.claude/commands` y los espejos de skills desde `templates/commands_manifest.json` |
| `sentinel/mcp.py` | Servidor MCP stdio (roto con `mcp` 2.x) |
| Registros JSON | `lenses/` (7), `techniques/` (7), `schemas/` (19), `smells/`, `slicing/`, `iso29148/`, `risk_categories/`, `retrieval_plans/`, `handoff_contracts/` |
| Skills | 24 canónicas en `.codex/skills/`, espejadas byte a byte a `.agents/skills/` y `.claude/skills/` |
| Hooks | `.claude/hooks/deny-governed-artifact-write.py`, `.codex/hooks/*`; la lógica está en `sentinel/hooks_logic.py` |
| Tests | 127 archivos; evals sintéticos en `tests/fixtures/evals/` |

**Gates que hay que respetar:**
- `/specs` y `/backlog` requieren ingest previo y se bloquean con maturity `BLOCKED`.
- `/backlog`, `/quality` y `/refine-backlog` se bloquean con health `DIRTY`.
- `/quality` requiere historias existentes.

---

## 4. Verificación: estado medido al empezar

| Comando | Resultado |
|---|---|
| `python -m sentinel /doctor` | PASS (WARN solo por LanceDB y embeddings opcionales) |
| `python -m unittest discover -s tests` | 823 tests en unos 170 s, **1 error**: `test_core_flow.test_mcp_server_exposes_lifecycle_tools` (con `mcp` 2.3.0 instalado; `FastMCP` pasó a `MCPServer`) |
| `python tests/evals/run_discovery_evals.py` | No se corrió |
| Smoke `/init` + `/ingest` (`crm-billing-sync`) | 19 gaps (1 crítico), health `DIRTY`, `CLIENT_RESPONSE_NEEDED`; `/status` imprime unos 65 KB y `/maturity` unos 35 KB |

**Línea base local (2026-11-05, Windows, `.venv` con Python 3.14.6 y LanceDB):**

| Comando | Resultado |
|---|---|
| `.\verify.ps1 -SkipEvals` | OK: 823 tests en 665 s; `/doctor` con 0 fallas y 3 WARN opcionales; `mcp` no instalado, así que el error de MCP 2.x no aparece |
| `run_discovery_evals.py` | `baseline_ok=True`, 8/8 en 79 s |
| `run_faithfulness_claim_evals.py` | `falsable_ok=True` en 0,55 s (no está cableado a la suite) |

Detalle en la sección 9 del análisis.

En Windows, la forma recomendada es `.\verify.ps1` (tests, `/doctor` y evals) o `.\verify.ps1 -SkipEvals`. Si `python` abre la Microsoft Store, es el alias de App Execution: usar `py`.

---

## 5. Hallazgos verificados más importantes

Para el detalle y la evidencia, ver el análisis. Estos son los que conviene atacar primero:

| Prioridad | Hallazgo | Dónde |
|---|---|---|
| Alta | MCP roto con `mcp` 2.x | `sentinel/mcp.py:187`; `pyproject.toml` sin acotar la versión |
| Alta | `packages = ["sentinel"]` omite los subpaquetes, así que un `pip install .` no editable probablemente rompe | `pyproject.toml` |
| Alta | Path traversal: `/init ../../escape` crea un workspace fuera de `workspaces/` | `sentinel/core/paths.py:11` |
| Alta | Sin CI (no existe `.github/`) | — |
| Media | `/stakeholders` fuera del protocolo de comandos | `sentinel/protocols.py` |
| Media | `phase` registra el último evento, no la etapa; dos lógicas de próximo paso | `status.py:81`, `dashboard.py` (`_next_action`) |
| Media | Las context requests no tienen ciclo de vida | `sentinel/context_requests.py` |
| Media | La salida de `/status` y `/maturity` es enorme (unos 16.000 tokens) | `status.py`, `maturity.py` |
| Media | Escrituras sin lock; cachés globales en el proceso MCP; grafo guardado por cada arista; `state.json` mezcla durable y derivado; memoria con rutas absolutas y duplicados | `core/io.py`, `core/state.py`, `core/graph.py`, `memory.py` |
| Media | No hay manifiestos de marketplace; las skills dependen de `python -m sentinel` | — |

---

## 6. Decisiones y conclusiones de la sesión

1. **llm-wiki no reemplaza a LanceDB.** Un artículo sintetizado no puede ser evidencia. Sí se adopta su patrón: un `_index.md` determinista por carpeta en `/reindex`. llm-wiki puede usarse como fuente externa de dominio que entra por `/sync`.
2. **Skills para varios harness.** Un núcleo canónico portable más capas por superficie, que el generador fusiona. Lo específico de Claude (`` !`cmd` ``, `${CLAUDE_PLUGIN_ROOT}`, `$ARGUMENTS`, `context: fork`) va **solo** en la capa de Claude. La doctrina y los gates siguen en el runtime. Esto corrige una sugerencia inicial de usar esos mecanismos directamente en el cuerpo de las skills.
3. **Marketplace.** Un paquete generado `plugins/ignite-sentinel/` con dos manifiestos (`.claude-plugin/plugin.json` y `.codex-plugin/plugin.json`), dos catálogos (`.claude-plugin/marketplace.json` y `.agents/plugins/marketplace.json`) y un launcher `bin/sentinel`. Modelo de referencia: nvk/llm-wiki. Kilo no tiene marketplace: se resuelve con `/setup`.
4. **HTML.** Un único sistema de diseño con temas por tokens. El tema inspirado en Globant vive **local** (no en el repo público) y sin logo. Todo HTML es derivado y reproducible.
5. **Correcciones aplicadas en `4ee83c2`:**
   - La procedencia embebida no lleva fecha de build, para que la salida sea reproducible; el aviso de antigüedad se calcula en el navegador.
   - El estado del lector en `localStorage` usa como clave el proyecto y la versión del esquema; el hash del grafo se guarda aparte y solo sirve para avisar, sin descartar notas.

---

## 7. Pendientes abiertos

**Del análisis:**
- [ ] Verificar layout, grilla y motion de globant.com (el sitio bloqueó todos los accesos).
- [ ] Confirmar las licencias de Heebo, Open Sans y Roboto antes de vendorizar fuentes en el tema local.
- [ ] Validar con el dueño de marca los tintes derivados del tema, si llega a ser oficial.
- [ ] Verificar la sintaxis oficial de los plugins de Codex: `developers.openai.com` no fue accesible desde la nube; se tomó la de llm-wiki.
- [ ] Verificar los identificadores de arXiv 2608.21298 y 2609.03230 antes de citarlos.
- [ ] Probar el wheel con `pip install .` no editable en un entorno sano (en la nube falló por un problema de setuptools ajeno al repo).
- [ ] Evals y disco (sección 9 del análisis):
  - [ ] cablear `run_faithfulness_claim_evals.py` a la suite y a `verify.ps1`;
  - [ ] arreglar los tempdirs que deja `test_momtest.py`;
  - [ ] sacar del repo el reporte que escribe `test_evals_retrieval.py` en cada unittest;
  - [ ] retención de reportes (últimos 5 por tipo);
  - [ ] comando de limpieza local con `--dry-run`;
  - [ ] evals en dos niveles (rápido y completo);
  - [ ] deduplicar el modelo de `/view` y regenerar los goldens.
- [ ] Medir los tiempos por test para separar rápidos y lentos, y confirmar si LanceDB explica los 665 s locales frente a los 170 s de la nube.
- [ ] Estimar el recupero real de `git gc` y el tamaño de un `.venv` con solo `.[dev]`.

**Decisiones que tiene que tomar el usuario:**
- [ ] Qué fase implementar primero (recomendado abajo).
- [ ] Si `proposals/` queda en el repo o se mueve a `docs/evolution/` (git-ignored, memoria local del mantenedor).
- [ ] Si se registran los ítems como IMP en el backlog local (`docs/evolution/02-backlog-mejoras.md`).
- [ ] Qué hacer con los workspaces locales (`H10PARITY` y otros 3; 4,4 MB) y si se mantiene el `.venv` con LanceDB (≈ 290 MB).

---

## 8. Próximos pasos recomendados

Orden sugerido, de mayor a menor relación entre impacto y riesgo:

1. **Correcciones (nivel 0)**, cada una con su test:
   - compatibilidad con MCP 2.x (import doble o acotar `mcp<2`);
   - `packages.find` en `pyproject.toml` más un test que instala el wheel;
   - validar `PROJECT_ID` (regex y contención dentro de `workspaces/`);
   - `/stakeholders` dentro de `MUTATING_COMMANDS` o `READ_ONLY_COMMANDS`.
2. **Higiene de tests y evals** (sección 9.6 del análisis), barata y de bajo riesgo:
   - cablear el eval de faithfulness;
   - arreglar `test_momtest` y el reporte que escribe `test_evals_retrieval`;
   - retención de reportes;
   - script de limpieza con `--dry-run`.
3. **CI en GitHub Actions** (Windows y Linux, Python 3.10 y 3.13, con y sin LanceDB, `mcp` 1 y 2) y `verify.sh`, con evals en dos niveles: rápido en cada push y completo antes de mergear.
4. **Mejoras de uso para agentes:** `--summary` en `/status` y `/maturity`; `--dry-run` en los canales agénticos; una única función de próximo paso.
5. **Prototipo del motor de temas** sobre `/dashboard`: esquema de tema, `base.css` y flujo modelo → validar → render (sección 8.3, puntos 1 a 3). Junto con eso, deduplicar el modelo de `/view` y regenerar los goldens (sección 9.4).
6. Después, seguir la hoja de ruta de la sección 10 del análisis.

**Cómo trabajar cada ítem** (de `MAINTAINERS.md`):
- Un branch por ítem desde `main`, o seguir en este branch si el usuario lo prefiere.
- Tocar juntos runtime, tests, skills, adapters (regenerar con `python -m sentinel.adapters`), docs y `/doctor`.
- Verificar con `.\verify.ps1`.
- No pushear con tests o `/doctor` en rojo.
- Revisar el diff en busca de datos sensibles.
- Si un ítem toca un contrato de superficie (`kilo.jsonc`, `.claude/`, `.agents/`, manifiestos de plugin), registrarlo en `SURFACE_CONTRACTS` y probarlo en la herramienta real, con auto-approve apagado.

---

## 9. Prompts sugeridos para la sesión local

Para retomar:
> Leé `proposals/2026-11-handoff-sesion-local.md` y después `proposals/2026-11-analisis-mejoras.md`. Confirmá el estado del branch y corré `.\verify.ps1 -SkipEvals` para tener una línea base.

Para arrancar con el nivel 0:
> Implementá los ítems de nivel 0 de la sección 8 del handoff, uno por commit, con test en cada uno. Corré `.\verify.ps1` al final y mostrame el resultado antes de pushear.

Para el prototipo de temas:
> Prototipá el motor de temas sobre `/dashboard` según la sección 8.3 (puntos 1 a 3) del análisis: esquema de tema, tema `neutral` claro y oscuro, `base.css` y flujo modelo → validar → render, con test golden. El tema inspirado en Globant va como tema local git-ignored.
