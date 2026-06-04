# Ignite Sentinel vNext - Guia de Usuario

Ignite Sentinel vNext es un framework local-first para madurar requerimientos de negocio y producto dentro de AI PODs. Su objetivo no es reemplazar el criterio de una persona de Producto, Tecnologia, Diseno o Calidad, sino ordenar el trabajo para que ningun requerimiento crudo salte directo a implementacion sin contexto, trazabilidad y preguntas explicitas.

La idea central es simple: el cliente suele traer una necesidad en un estado incompleto. A veces llega como un markdown breve, a veces con pantallazos, diagramas, correos, notas de reunion o referencias tecnicas. Sentinel toma ese material como evidencia inicial, lo analiza criticamente, detecta gaps, registra decisiones y va construyendo un entendimiento maduro hasta producir un `project-brief.md`. Ese brief funciona como el puente entre discovery y los artefactos downstream: PRD, specs, backlog, criterios de aceptacion, pruebas y pedidos de analisis profundo a dominios como Tecnologia o Diseno.

Esta guia esta escrita para personas que no conocen el framework. Si sos BA, Product Owner, Product Manager, Tech Lead, UX/UI, QA, Delivery o trabajas con agentes de IA, la guia busca responder tres preguntas:

- Que problema resuelve Sentinel.
- Que hay que hacer en cada momento del ciclo.
- Que artefactos se generan y como se usan sin perder trazabilidad.

## La Historia Completa En Una Frase

Sentinel convierte informacion cruda en requerimientos maduros mediante ciclos de discovery, gap response, trazabilidad y health checks, manteniendo siempre los archivos versionables del workspace como fuente de verdad y usando memoria local solo como ayuda de recuperacion de contexto.

## Que Hace Sentinel

Sentinel acompana el ciclo de vida de un requerimiento:

1. Se crea un workspace para un proyecto.
2. Se ingiere la documentacion inicial del cliente.
3. Se analiza la informacion desde lentes de Producto, Negocio, Funcional, Tecnologia, Diseno, Calidad, Delivery y Compliance.
4. Se generan requerimientos iniciales, seeds, decisiones, gaps y trazabilidad.
5. Se comparte `gaps.md` con el cliente o con dominios internos para completar informacion.
6. Se procesan respuestas estructuradas con `/resolve-gaps`.
7. Se itera hasta tener suficiente madurez para generar `project-brief.md`.
8. Se generan specs, backlog y artefactos de calidad solo cuando el estado permite avanzar.
9. Se procesan cambios posteriores como eventos trazables.
10. Se audita salud, trazabilidad y consistencia antes de handoffs.

Sentinel no asume que una frase del cliente es automaticamente una verdad final. La trata como evidencia. Cuando la evidencia es suficiente, puede promoverse a seed o decision. Cuando falta informacion, se convierte en gap.

## Conceptos Clave

### Workspace

Cada proyecto vive en:

```text
workspaces/[PROJECT_ID]/
```

Ese directorio contiene raw input, discovery, requirements, specs, backlog, quality, traceability, cambios, context packs y memoria local. La separacion por proyecto evita mezclar informacion de clientes o iniciativas distintas.

### Fuente De Verdad

La fuente de verdad son los archivos versionables del workspace. La memoria local, incluyendo LanceDB, es solo un indice de recuperacion. Si un resultado de memoria contradice un markdown del workspace, gana el markdown.

Esto es importante para privacidad y auditoria: el conocimiento relevante queda en archivos revisables, versionables y exportables.

### Seeds

Una seed es una afirmacion atomica que representa una verdad conocida o una verdad pendiente de confirmacion. Por ejemplo:

- "Los usuarios primarios son analistas de operaciones."
- "El MVP no incluye reportes historicos."
- "La fuente de verdad del riesgo SLA es Case Management."

Las seeds ayudan a que los agentes no tengan que reinterpretar todo el input crudo cada vez.

### Gaps

Un gap es informacion faltante, ambigua, riesgosa o no verificable. Un gap no es un error: es una forma saludable de no inventar. Si no sabemos que usuario usa una pantalla, que endpoint existe, que metrica tiene baseline o que estado UX debe cubrirse, Sentinel lo marca como gap.

Estados relevantes:

- `OPEN`: falta respuesta.
- `PARTIALLY_CLOSED`: hay respuesta, pero no esta confirmada o falta decision.
- `CLOSED`: la respuesta estructurada permite cerrar el gap.
- `NEW_REQUIREMENT` o `NEW_GAP`: la respuesta trae algo nuevo que requiere otro ciclo.

### Project Brief

`02_requirements/project-brief.md` es el cierre maduro de discovery. No es un PRD completo ni una especificacion tecnica detallada. Es el documento que deja el requerimiento suficientemente claro para que:

- Producto genere PRD/specs con buen contexto.
- Tecnologia profundice arquitectura, repositorios, endpoints, eventos, contratos y riesgos.
- Diseno profundice journeys, flujos, prototipos, estados y accesibilidad.
- Frontend y Backend entiendan superficies, reglas, integraciones y fallas.
- Calidad derive escenarios, riesgos, datos de prueba y evidencia esperada.

El brief debe encontrar un punto medio: completo para guiar, pero sin intentar reemplazar los context packs especializados de cada dominio.

### Traceability

Cada artefacto importante tiene un ID:

| Prefix | Meaning |
| --- | --- |
| `RAW` | Raw input |
| `REQ` | Requirement |
| `GAP` | Gap report or blocker |
| `DEC` | Decision, impact report, or resolution report |
| `SEED` | Identity seed |
| `SPEC` | Specification |
| `EPIC` | Epic |
| `US` | User story |
| `AC` | Acceptance criteria |
| `TC` | Test case |
| `CHG` | Change event |
| `CTX` | Context request |

La linea de tiempo esperada se parece a esto:

```text
RAW -> REQ -> GAP/DEC/SEED -> project-brief -> SPEC -> EPIC -> US -> AC -> TC
                    |
                   CHG -> impacted artifacts
```

La trazabilidad permite contestar preguntas como:

- De donde salio esta historia de usuario?
- Que decision cerro este gap?
- Que cambio puede afectar este spec?
- Que test cubre esta acceptance criteria?

### Health

`/health` no reemplaza aprobaciones humanas. Es un control deterministicamente ejecutable que revisa senales como gaps bloqueantes, metricas sin fuente, nodos huerfanos o memoria desactualizada.

Un proyecto puede estar:

- `CLEAN`: no se detectaron bloqueos estructurales.
- `DIRTY`: hay gaps, problemas de trazabilidad, metricas sin fuente o artefactos no indexados.

`CLEAN` significa "estructuralmente listo para avanzar", no "aprobado por el cliente".

## Flujo Basico

### 1. Verificar El Framework

```powershell
python -m sentinel /doctor
```

Usalo para confirmar que el entorno local puede ejecutar Sentinel, que existe la estructura esperada y que las dependencias estan disponibles.

### 2. Crear El Workspace

```powershell
python -m sentinel /init ACME_DASHBOARD
```

Esto crea carpetas, `state.json`, `sentinel.config.yaml`, grafo de trazabilidad vacio, manifest de fuentes y memoria local.

### 3. Ingerir El Requerimiento Inicial

```powershell
python -m sentinel /ingest ACME_DASHBOARD --source input\client_requirement\client-note.md
```

Sentinel copia el input al workspace, genera requerimientos iniciales, gaps, seeds, decisiones y revisiones multi-lente. Tambien indexa la informacion en memoria local para recuperacion posterior.

### 4. Compartir Gaps

```powershell
python -m sentinel /gaps ACME_DASHBOARD
```

El archivo `01_discovery/gaps.md` esta pensado para humanos. Cada gap tiene ID, descripcion, pregunta, ejemplo de respuesta y campos para que el cliente o un dominio respondan. Ese archivo puede compartirse sin exigirle al cliente conocer el framework.

### 5. Procesar Respuestas

Cuando vuelve el documento respondido:

```powershell
python -m sentinel /resolve-gaps ACME_DASHBOARD --source input\interactions\answered-gaps.md
```

Sentinel cierra automaticamente solo los gaps con respuesta estructurada confirmada. Si hay respuesta pero la decision sigue pendiente, deja el gap en `PARTIALLY_CLOSED`.

### 6. Evaluar Madurez

```powershell
python -m sentinel /maturity ACME_DASHBOARD
python -m sentinel /status ACME_DASHBOARD
```

Si quedan gaps criticos o altos abiertos/parciales, el proyecto sigue bloqueado. Si la madurez alcanza `READY_FOR_SPECS`, Sentinel puede materializar o refrescar el project brief.

### 7. Generar El Brief

```powershell
python -m sentinel /brief ACME_DASHBOARD
```

El brief consolida discovery y sirve como handoff maduro.

### 8. Pedir Context Packs A Dominios

```powershell
python -m sentinel /context-request ACME_DASHBOARD --domain technology
python -m sentinel /context-request ACME_DASHBOARD --domain design
python -m sentinel /context-request ACME_DASHBOARD --domain quality
```

Estos pedidos no inventan arquitectura, prototipos o test plans. Preparan una solicitud clara para que cada dominio profundice su parte.

### 9. Generar Specs, Backlog Y Calidad

```powershell
python -m sentinel /specs ACME_DASHBOARD
python -m sentinel /backlog ACME_DASHBOARD
python -m sentinel /quality ACME_DASHBOARD
```

Estos comandos deben ejecutarse cuando el proyecto tiene suficiente madurez. `/backlog` y `/quality` se bloquean si la salud esta `DIRTY`.

### 10. Auditar Y Validar

```powershell
python -m sentinel /trace ACME_DASHBOARD
python -m sentinel /health ACME_DASHBOARD
python -m sentinel /validate ACME_DASHBOARD
```

Usa estos comandos antes de handoffs, cierres de fase o cambios importantes.

## Layout Del Workspace

```text
workspaces/[PROJECT_ID]/
  00_raw/             Evidencia original y contexto de dominios
    00_client_requirement/
    01_business_context/
    02_technology_context/
    03_design_context/
    04_quality_context/
    05_interactions/
  01_discovery/       Gaps, seeds, decisiones, reportes de madurez
  02_requirements/    Requirements y project brief
  03_specs/           PRD/spec AI-friendly
  04_backlog/         Epics, user stories, acceptance criteria
  05_quality/         Test cases y auditorias de calidad
  06_traceability/    Grafo, matriz, Mermaid, health reports
  07_changes/         Cambios, respuestas de cliente, reuniones
  08_context_packs/   Retrieval packs, requests y exports
  memory.lancedb/     Indice local reconstruible
  state.json
  sentinel.config.yaml
```

## Privacidad Local-First

Sentinel esta pensado para entornos donde el cliente no quiere que codigo o informacion sensible viaje por canales externos. Por defecto:

- `privacy_mode` es `local-only`.
- LanceDB vive dentro del workspace local.
- Los embeddings son locales/deterministicos cuando se usa fallback hash.
- No se requiere MCP remoto.
- Los archivos versionables siguen siendo la fuente de verdad.

## Como Leer El Resto De La Guia

- [Command Reference](01-command-reference.md): que hace cada comando.
- [Artifact Reference](02-artifact-reference.md): para que sirve cada archivo generado.
- [Workflows](03-workflows.md): secuencias operativas recomendadas.
- [Codex Skills Guide](04-codex-skills-guide.md): como interactuan los skills con Codex.
- [Traceability And Memory](05-traceability-and-memory.md): como funciona la memoria local y el progressive disclosure.
- [Escenarios Operativos](12-scenarios.md): situaciones concretas de trabajo, de discovery a cambios y health checks.

## Reglas Practicas Para BAs Y Producto

- No escondas incertidumbre: converti la duda en gap.
- No inventes metricas, usuarios, endpoints, reglas o acceptance criteria.
- No cierres gaps criticos con inferencias.
- No generes backlog desde un requerimiento inmaduro.
- Usa `/resolve-gaps` para respuestas estructuradas y `/sync` para informacion nueva no estructurada.
- Usa `/retrieve` para traer contexto puntual en vez de cargar todo el workspace.
- Usa `/health` y `/validate` antes de handoffs.
- Mantené `main` como framework limpio; los proyectos reales deberian correr en branches dedicadas.
