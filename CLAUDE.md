# CLAUDE.md - Ignite Sentinel vNext

Instrucciones para sesiones de Claude (Cowork, Claude Code o similar) operando sobre este repositorio. Complementa, no reemplaza, a `AGENTS.md`: leer ambos antes de tocar nada.

> **Audiencia: mantenedores.** Este archivo es para sesiones que **evolucionan el framework** (runtime, tests, adapters, docs). Si solo querés **usar** Ignite para madurar requerimientos en tu propio proyecto, no necesitás nada de acá: alcanzan el [README](README.md) y el [User Guide](user_guide/00-user-guide.md). Las convenciones de evolución de este repo (branches, mantener superficies sincronizadas, manejo de ejemplos/datos) viven en [MAINTAINERS.md](MAINTAINERS.md) y no condicionan tu propio repo ni tus datos.

## Qué es este proyecto

Framework repo-local y local-first para que un BA/Product madure requerimientos crudos de cliente hasta convertirlos en artefactos trazables: discovery, gaps, project brief, PRD, specs, backlog, test cases y trazabilidad. No es un generador de documentos: es un sistema de maduración de requerimientos con lifecycle gobernado.

## Orden de lectura al iniciar una sesión

1. `AGENTS.md` (reglas operativas y working agreements).
2. `docs/evolution/00-baseline-2026-06-10.md` (estado validado del repo; carpeta local git-ignored — si no existe, pedirla al usuario).
3. `docs/evolution/01-roadmap.md` y `02-backlog-mejoras.md` (qué evolucionar y en qué orden).
4. `user_guide/00-user-guide.md` y `01-command-reference.md` para uso del CLI.

Nota: los handoffs históricos (`general-proyecto.md`, `ignite_vnext_final_handoff.md`) viven fuera del repo, en la carpeta personal de handoffs del usuario. No forman parte del proyecto ni deben versionarse; ante conflicto con ellos, prevalece el código actual.

## Comandos esenciales

Desde la raíz del repo:

```text
python -m sentinel /doctor
python -m sentinel /dashboard
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input/client_requirement/archivo.md
python -m sentinel /gaps | /annotate --source ANALYSIS.json | /resolve-gaps | /maturity | /brief | /context-request
python -m sentinel /sync | /reindex | /retrieve
python -m sentinel /specs | /self-review --source FILE | /backlog | /backlog-status | /story-status --story US-NNN --set STATE [--evidence FILE] | /refine-backlog --source FILE | /quality | /trace | /health | /validate
python -m sentinel /status PROJECT_ID | /export PROJECT_ID --artifact gaps|brief|context-request|prd --format md|mdx
python -m sentinel /view PROJECT_ID --artifact gaps|brief|prd|specs|backlog [--open]
```

Fallback Windows sin Python en PATH: `.\installers\sentinel.ps1 /COMMAND PROJECT_ID`.

## Chat commands en Claude

Este repo incluye el adapter `.claude/commands/` con un slash command por comando Sentinel (`/init`, `/ingest`, `/gaps`, etc.) más `/sentinel` como forma genérica. En Claude Code (VS Code o CLI) se invocan directamente desde el chat; cada comando ejecuta el CLI desde la raíz del repo y resume artefactos generados, gaps y próximo paso.

Reglas de routing (aplican también en Claude Desktop/Cowork, donde no hay slash commands nativos):

- Si el usuario escribe un comando estilo `/COMMAND PROJECT_ID [OPTIONS]`, `sentinel /COMMAND ...` o `ignite /COMMAND ...`, ejecutar `python -m sentinel /COMMAND PROJECT_ID [OPTIONS]` desde la raíz del repo.
- `/dashboard` es de cartera y no lleva `PROJECT_ID`: ejecutar `python -m sentinel /dashboard [--root PATH] [--open]`. Genera `dashboard.html` local, read-only y git-ignored.
- `/view PROJECT_ID --artifact ARTIFACT` genera una vista HTML local y read-only de un artefacto bajo `08_context_packs/views/`; es derivada del Markdown source-of-truth y no se edita a mano.
- `/self-review PROJECT_ID --source FILE` registra una revisión escéptica de PRD/specs: valida gaps y decisiones `DEC-*` contra citas verbatim locales, escribe `03_specs/self_review/` y no reescribe PRD/specs automáticamente.
- Si el usuario describe la situación en lenguaje natural, mapear la intención al flujo correcto (tabla completa en `user_guide/11-chat-commands.md`, sección Intent-To-Command Map): input nuevo de cliente → `/init` + `/ingest` + `/status`; respuestas a gaps → `/resolve-gaps` + `/maturity` + `/status`; contexto de dominio actualizado → `/sync` + `/reindex` + `/health`; handoff downstream → `/specs` + `/backlog` + `/backlog-status` + `/quality` + `/trace` + `/health` + `/validate` cuando los gates lo permitan.
- Nunca editar artefactos generados a mano: siempre mutar vía CLI.
- Respetar los gates; si un comando se bloquea, explicar por qué y recomendar el paso previo correcto.
- Tras cada comando, resumir resultado, artefactos generados y próximo paso recomendado.

Gates implementados (no forzarlos): `/specs` y `/backlog` requieren ingest previo y fallan con maturity `BLOCKED`; `/backlog`, `/refine-backlog` y `/quality` se bloquean con health `DIRTY`; `/quality` requiere user stories existentes. `/story-status` es el único canal para estado/owner de historias y evidencia local de DoD; evalúa DoR/DoD con `backlog_gate` blando por default y strict opt-in. `/backlog-status` regenera `04_backlog/BACKLOG.md` como tablero BA desde estado gobernado/readiness; no editar `BACKLOG.md`, `US-NNN.md`, `state.json` ni evidencia de gate a mano. `/refine-backlog` solo acepta propuestas agénticas citadas y las registra como overlay `origin: agent`; no reescribe historias ni el boundary de enablers.

## Verificación obligatoria al cambiar runtime

Forma recomendada (resuelve el intérprete solo y corre los tres pasos):

```powershell
.\verify.ps1            # tests + /doctor + evals
.\verify.ps1 -SkipEvals # solo tests + /doctor
```

Equivalente manual:

```text
python -m unittest discover -s tests
python -m sentinel /doctor
python tests/evals/run_discovery_evals.py
```

Nota de entorno (Windows — `python` no encontrado / abre Microsoft Store): es el alias stub de App Execution Aliases; `python` real no está en el PATH. Soluciones, en orden: (1) usar el launcher `py` en vez de `python` (`py -m unittest discover -s tests`); (2) usar `.\verify.ps1`, que prueba `.venv`, `python` y `py` automáticamente; (3) crear venv una vez (`py -m venv .venv` y `.\.venv\Scripts\python -m pip install -e .`), que `verify.ps1` e `installers\sentinel.ps1` detectan; (4) apagar los alias en Configuración > Aplicaciones > Alias de ejecución de aplicaciones (`python.exe`, `python3.exe`) o reinstalar Python desde python.org con "Add to PATH". Nunca asumir que `python` falla por un problema del repo: primero descartar el alias.

Nota de entorno: `lancedb` es opcional (IMP-013). Sin él, el framework opera en modo degradado `json-hybrid`, `/doctor` da WARN (no FAIL) y la suite completa debe pasar igual. Habilitar retrieval vectorial con `pip install -e .[memory]` cuando el entorno lo permita.

## Reglas no negociables (resumen de AGENTS.md)

- SSoT: archivos versionables bajo `workspaces/[PROJECT_ID]/`. La memoria LanceDB/JSON es ayuda reconstruible, nunca autoridad.
- Local-first privacy: nada de contenido de cliente/código a servicios externos, embeddings remotos ni MCP remotos sin aprobación explícita.
- No inventar: faltantes se expresan como `GAP-*`, `[PENDING INPUT]` o `[PENDING DOMAIN CONTEXT]`.
- Mutar artefactos generados solo vía comandos Sentinel, nunca editando outputs downstream a mano.
- `main` limpio: sin workspaces reales, datos de cliente ni outputs de prueba. Cambios vía branch + PR; no asumir push directo a `main`.
- Al evolucionar el framework, mantener alineados juntos: runtime (`sentinel/`), tests, skills Codex (`.codex/skills/`), agentes/comandos Kilo (`.kilo/`), `kilo.jsonc`, README, `user_guide/` y `/doctor`.
- De documentos confidenciales solo se extraen patrones genéricos; jamás persistir nombres de cliente, sistemas, endpoints o datos identificables en artefactos versionados.
- Explicaciones de comportamiento del framework preferentemente en español.

## Estructura clave

```text
sentinel/          runtime Python (cli, discovery, generation, memory, sync, health, validation, protocols...)
sentinel/core/     primitivas compartidas: markdown, IO JSON, rutas de workspace, state.json y tiempo UTC
tests/             unittest suite (17 tests)
.codex/ .kilo/     adapters Codex y Kilo Code
user_guide/        documentación de usuario (00-12)
input/             staging local de inputs (no versionado)
workspaces/        workspaces por proyecto (solo _template versionado)
docs/evolution/    memoria operativa local (baseline, roadmap, backlog) — git-ignored, NO se publica
installers/        launchers PowerShell
```

Nota para mantenedores: `sentinel/workspace.py` conserva shims de compatibilidad (`read_json`, `write_json`, `workspace_path`, `state_path`, `update_state`, etc.) para no romper imports existentes. Las nuevas primitivas compartidas deben nacer en `sentinel/core/` y luego, si hace falta, reexportarse desde fachadas históricas.

## Cómo trabajar una mejora del framework

1. Elegir un ítem `IMP-*` de `docs/evolution/02-backlog-mejoras.md` (respetando prioridades del roadmap).
2. Crear branch de trabajo desde `main`.
3. Implementar tocando runtime + tests + adapters + docs según aplique.
4. Correr suite de tests y `/doctor`; smoke test de lifecycle si cambió runtime.
5. Actualizar el estado del ítem en `02-backlog-mejoras.md`.
6. Abrir PR; no mergear sin revisión.
