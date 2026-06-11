# Roadmap de Evolución - Ignite Sentinel vNext

Prioriza la evolución del framework a partir del baseline 2026-06-10 (`00-baseline-2026-06-10.md`). El detalle ejecutable de cada ítem vive en `02-backlog-mejoras.md` con IDs `IMP-*`. Cada horizonte asume el principio rector: al cambiar el lifecycle, runtime + tests + skills Codex + adapters Kilo + docs + `/doctor` evolucionan juntos.

## Horizonte 0 — Higiene del repo (antes de cualquier mejora funcional)

Objetivo: que el working tree y la portabilidad dejen de generar ruido y riesgo.

- IMP-001 Normalizar line endings con `.gitattributes` (elimina los 79 archivos "modificados" fantasma).
- IMP-002 Definir destino de los handoffs copiados en la raíz del repo (versionar en `docs/`, ignorar o eliminar).
- IMP-003 Política para `.7z` y launchers no trackeados.
- IMP-004 Smoke test de onboarding desde clon limpio/ZIP en carpeta nueva, documentado.

Criterio de salida: `git status` limpio tras clon + `/doctor` PASS + suite verde, con el procedimiento documentado.

## Horizonte 1 — Calidad de discovery y generación (el corazón del valor)

Objetivo: que el discovery sea profundamente inquisitivo sobre lo no mencionado (dolor #1 declarado por el usuario) y que PRD, specs y backlog reflejen evidencia real en lugar de scaffolding genérico. Toda validación se hace con data sintética hasta que el framework sea sólido y agnóstico.

- IMP-016 Suite de fixtures sintéticos realistas con answer keys de gaps esperados (prerrequisito para medir el resto).
- IMP-015 Motor de discovery más inquisitivo: preguntas ancladas a la evidencia específica del input, no checklist genérica.
- IMP-013 Modo degradado sin LanceDB (elevado desde Horizonte 3: hay VDIs donde no se puede instalar).
- IMP-005 Extracción mejorada de FRs, personas y KPIs desde evidencia ingestada.
- IMP-006 Validación semántica profunda en `/validate` (completitud, no solo estructura).
- IMP-007 Scoring, coverage map y evidencia por sección en `specs_generation.json` e `implementation_readiness.json`.
- IMP-008 Métricas de madurez cuantificadas en `/maturity` y `/status` (qué porcentaje del brief/PRD tiene evidencia vs. pendiente).

Criterio de salida: con un fixture de requerimiento realista, PRD/specs generados citan evidencia por sección y `/validate` distingue secciones pobladas de scaffolding.

## Horizonte 2 — Robustez del lifecycle vivo

Objetivo: fortalecer sync, staleness y cierre seguro de gaps en proyectos largos.

- IMP-009 Cobertura de tests para staleness de backlog ante cambio de contexto de dominio.
- IMP-010 Mejoras de `/resolve-gaps`: cierres parciales, ambigüedad y confirmaciones pendientes con más matices.
- IMP-011 Trazabilidad de regeneración: diff visible de qué cambió en artefactos regenerados tras `/sync` + `/reindex`.

## Horizonte 3 — Experiencia y adopción

Objetivo: bajar la fricción para usuarios nuevos y entornos restringidos.

- IMP-012 Experiencia chat-first refinada: mapeo de intención en lenguaje natural a secuencias de comandos, con ejemplos en guías y adapters.
- IMP-014 Adapter/guía para Claude (Cowork/Claude Code) como tercer entorno soportado junto a Codex y Kilo.

Nota: el objetivo de adopción es que cualquier BA/PM pueda clonar el repo y usarlo en su propio proyecto, por lo que el onboarding agnóstico (IMP-004) y las guías para usuarios que no conocen el framework son parte del criterio de "sólido y robusto".

## Horizonte 4 — Alineación con estándares de agentes AI (2026)

Objetivo: que Ignite deje de mantener un adapter artesanal por IDE y se apoye en los estándares que la industria consolidó (Agent Skills/SKILL.md, AGENTS.md, MCP, evals con answer keys), reduciendo mantenimiento y ampliando compatibilidad a cualquier herramienta que los lea.

- IMP-020 Eval harness de discovery (puede adelantarse a Horizonte 1 junto a IMP-016: es cómo se mide IMP-015).
- IMP-017 Servidor MCP local stdio: un solo punto de integración para todos los clientes MCP, local-first.
- IMP-019 Fuente única de adapters de comandos con generador y test de sincronía.
- IMP-018 Skills convergidas al estándar Agent Skills (`.agents/skills/` + `.claude/skills/`).

Regla de interacción con otros horizontes: IMP-020 conviene ejecutarlo junto con IMP-016 (Horizonte 1); IMP-017/018/019 pueden esperar a que Horizonte 1 demuestre valor, porque reducen costo de mantenimiento pero no mejoran el corazón del framework.

## Reglas de gestión del roadmap

- No iniciar Horizonte 1 sin cerrar el criterio de salida de Horizonte 0.
- Dentro de un horizonte el orden es sugerido, no estricto; entre horizontes sí.
- Todo ítem se trabaja en branch propio con PR; el estado se actualiza en `02-backlog-mejoras.md`.
- Si un ítem revela trabajo nuevo, se agrega como `IMP-*` nuevo, no se infla el ítem en curso.
