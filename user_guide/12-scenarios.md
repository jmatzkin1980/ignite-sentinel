# Escenarios Operativos

Este documento describe situaciones concretas que pueden ocurrir durante el uso de Ignite Sentinel vNext. La idea es que una persona nueva en el framework pueda leer un escenario, reconocer su caso y entender que comando ejecutar, que artefactos se generan y que significa el resultado.

Los escenarios estan agrupados por etapa del ciclo de vida. No todos los proyectos van a pasar por todos los escenarios, pero todos comparten la misma regla: la verdad vive en `workspaces/[PROJECT_ID]/` y la memoria local es una ayuda de recuperacion, no una fuente final.

## Bloque A: Discovery E Identidad

### Escenario 1: Inicio Del Proyecto Desde Cero

**Contexto:** El cliente envia el primer paquete de informacion. Puede ser un markdown, una nota de negocio, pantallazos, diagramas, referencias de sistemas o una mezcla incompleta de todo eso. Todavia no existe workspace para el proyecto.

**Comandos:**

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\initial-requirement.md
```

**Que hace Sentinel:** Crea la estructura fisica del workspace, copia el input crudo, detecta idioma, inicializa configuracion local-first, genera el primer registro de requerimiento, analiza el material con lentes de Producto, Tecnologia, Diseno y Calidad, y crea gaps cuando la informacion no alcanza para avanzar responsablemente.

**Input esperado:** Documentacion inicial del cliente en Markdown. Si hay informacion adicional de arquitectura, diseno o calidad, puede guardarse en las carpetas de contexto antes del ingest.

**Output principal:**

- `00_raw/[source].md`
- `01_discovery/raw_input_digest.md`
- `01_discovery/gaps.md`
- `01_discovery/identity_seeds.md`
- `01_discovery/decisions.md`
- `01_discovery/lens_review.md`
- `02_requirements/requirements.md`
- `06_traceability/traceability_graph.json`

**Como interpretar el resultado:** Si el proyecto queda `DIRTY`, no es un fracaso. Significa que Sentinel detecto incertidumbres que deben resolverse antes de generar specs o backlog.

### Escenario 2: Inyeccion De Contexto De Dominio Antes Del Analisis

**Contexto:** Antes o despues del primer ingest, el equipo tiene informacion de Tecnologia, Diseno, Calidad o Negocio que no vino en el documento principal. Por ejemplo: arquitectura vigente, endpoints conocidos, capturas de pantalla, reglas de QA o restricciones de compliance.

**Comandos:**

```powershell
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\initial-requirement.md
python -m sentinel /retrieve PROJECT_ID --query "architecture endpoints design states" --workflow discovery --write-pack
```

**Que hace Sentinel:** Durante `/ingest`, tambien indexa carpetas de contexto dentro del workspace, como `00_raw/02_technology_context/`, `00_raw/03_design_context/` y `00_raw/04_quality_context/`. Luego `/retrieve` permite traer solo el contexto relevante para revisar una decision o gap.

**Input esperado:** Archivos `.md` o `.txt` en carpetas como:

- `workspaces/PROJECT_ID/00_raw/01_business_context/`
- `workspaces/PROJECT_ID/00_raw/02_technology_context/`
- `workspaces/PROJECT_ID/00_raw/03_design_context/`
- `workspaces/PROJECT_ID/00_raw/04_quality_context/`

**Output principal:**

- Chunks indexados en `memory.lancedb/memory.json`
- Manifest local en `memory.lancedb/artifact_manifest.json`
- Context pack si se usa `--write-pack`

**Como interpretar el resultado:** El contexto de dominio ayuda a cerrar ambiguedades, pero no convierte automaticamente una suposicion en verdad. Si algo sigue sin fuente o decision, debe quedar como gap.

### Escenario 3: Documento De Gaps Para Compartir Con Cliente

**Contexto:** El analisis inicial detecta informacion faltante. El equipo necesita enviar un documento claro al cliente para que responda sin conocer Sentinel.

**Comando:**

```powershell
python -m sentinel /gaps PROJECT_ID
```

**Que hace Sentinel:** Regenera `01_discovery/gaps.md` en el idioma del proyecto. El documento contiene titulo, metadata, instrucciones, secciones por gap, ejemplos de respuesta y una tabla tecnica que Sentinel puede volver a procesar.

**Input esperado:** Workspace ya creado e ingest inicial ejecutado.

**Output principal:**

- `01_discovery/gaps.md`

**Como interpretar el resultado:** Este archivo es tanto humano como tecnico. El cliente puede responder debajo de cada `### GAP-ID`, y Sentinel podra leer esas respuestas despues con `/resolve-gaps`.

### Escenario 4: Resolucion Estructurada De Gaps

**Contexto:** El cliente devuelve el documento de gaps respondido. Algunas respuestas estan confirmadas, otras son parciales o siguen pendientes.

**Comando:**

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
```

**Que hace Sentinel:** Busca bloques `### GAP-ID`, extrae respuesta, owner, evidencia y estado de decision. Cierra automaticamente solo cuando hay respuesta no vacia y estado `confirmed`, `not applicable`, `confirmado` o `no aplica`.

**Input esperado:** Markdown con campos como:

```text
### GAP-USERS

- Answer: Primary users are operations analysts.
- Owner / source: Product owner
- Evidence or reference: Workshop notes
- Decision status: confirmed
```

**Output principal:**

- `07_changes/00_client_responses/[source].md`
- `07_changes/00_client_responses/[source]_gap_resolution_report.md`
- `01_discovery/gap_resolution_log.md`
- `01_discovery/gaps.md` actualizado
- Seeds y decisiones confirmadas cuando aplica
- Edges `CHG -> GAP`, `CHG -> SEED`, `CHG -> DEC`

**Como interpretar el resultado:** `CLOSED` significa que la respuesta puede usarse como verdad confirmada. `PARTIALLY_CLOSED` significa que hay informacion, pero no alcanza para desbloquear madurez si el gap es critico o alto.

### Escenario 5: La Respuesta Del Cliente Trae Un Requerimiento Nuevo

**Contexto:** El cliente responde un gap, pero agrega algo que no estaba contemplado. Por ejemplo, "ademas del dashboard, necesitamos exportacion historica mensual".

**Comandos recomendados:**

```powershell
python -m sentinel /resolve-gaps PROJECT_ID --source input\interactions\answered-gaps.md
python -m sentinel /sync PROJECT_ID --source input\interactions\answered-gaps.md --note "client answer introduced new requirement"
```

**Que hace Sentinel:** `/resolve-gaps` procesa lo que puede mapear a gaps existentes. `/sync` registra el nuevo contenido como evento de cambio y genera un impact report para revisar alcance, posibles nuevos gaps y artefactos afectados.

**Input esperado:** Respuesta de cliente con informacion adicional no mapeada.

**Output principal:**

- Gap resolution report
- Change impact report
- `CHG` node
- Posibles nuevos gaps detectados

**Como interpretar el resultado:** No todo feedback debe cerrar gaps. Si aparece alcance nuevo, conviene tratarlo como cambio o nuevo requerimiento para no contaminar silenciosamente el brief o backlog.

## Bloque B: Madurez Y Project Brief

### Escenario 6: Evaluacion De Madurez Bloqueada

**Contexto:** Se quiere avanzar a specs, pero todavia hay gaps criticos o altos abiertos/parciales.

**Comandos:**

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /status PROJECT_ID
```

**Que hace Sentinel:** Evalua `gaps.md`, revisa severidades bloqueantes y genera `requirement_maturity_report.md`. `/status` resume fase, health, idioma, gap counts y proximo paso recomendado.

**Output principal:**

- `01_discovery/requirement_maturity_report.md`
- Status JSON por consola

**Como interpretar el resultado:** Si readiness es `BLOCKED`, no conviene generar specs ni backlog. El siguiente paso normal es compartir gaps, procesar respuestas o pedir contexto de dominio.

### Escenario 7: Cierre De Discovery Y Generacion Del Project Brief

**Contexto:** Los gaps bloqueantes fueron cerrados o el equipo acepta que los restantes son no bloqueantes. Ya hay suficiente informacion para producir el documento maduro de requerimiento.

**Comandos:**

```powershell
python -m sentinel /maturity PROJECT_ID
python -m sentinel /brief PROJECT_ID
```

**Que hace Sentinel:** Materializa o refresca `02_requirements/project-brief.md` usando requerimientos, gaps, seeds, decisiones, lens review y contexto disponible.

**Output principal:**

- `02_requirements/project-brief.md`

**Como interpretar el resultado:** El brief es el cierre de discovery. No debe ser una coleccion de deseos ni una especificacion final de tecnologia. Debe ser suficientemente claro para que otros dominios puedan profundizar sin reinventar el problema.

### Escenario 8: Pedido Formal De Contexto A Tecnologia

**Contexto:** El brief ya tiene suficiente senal funcional, pero Tecnologia necesita profundizar arquitectura, repositorios, endpoints, eventos, source of truth, riesgos o NFRs.

**Comando:**

```powershell
python -m sentinel /context-request PROJECT_ID --domain technology
```

**Que hace Sentinel:** Genera un pedido dirigido en `08_context_packs/requests/technology_context_request.md`.

**Output principal:**

- `08_context_packs/requests/technology_context_request.md`
- Nodo `CTX` trazable

**Como interpretar el resultado:** Este documento no reemplaza el analisis tecnico. Le dice a Tecnologia que debe profundizar y con que referencias del brief/gaps debe trabajar.

### Escenario 9: Pedido Formal De Contexto A Diseno

**Contexto:** Diseno necesita saber que journeys, pantallas, estados, copy, accesibilidad o prototipo debe trabajar.

**Comando:**

```powershell
python -m sentinel /context-request PROJECT_ID --domain design
```

**Que hace Sentinel:** Genera un pedido dirigido en `08_context_packs/requests/design_context_request.md`.

**Output principal:**

- `08_context_packs/requests/design_context_request.md`
- Nodo `CTX` trazable

**Como interpretar el resultado:** El framework no produce el prototipo final. Ayuda a que el pedido a Diseno sea concreto, trazable y basado en discovery maduro.

## Bloque C: Specs, Backlog Y Calidad

### Escenario 10: Generacion De PRD Y Specs AI-Friendly

**Contexto:** El proyecto esta maduro y existe un `project-brief.md`. Se necesita generar un PRD para audiencia humana/negocio y una spec preparada para agentes.

**Comando:**

```powershell
python -m sentinel /specs PROJECT_ID
```

**Que hace Sentinel:** Genera `03_specs/prd.md` y `03_specs/specs.md`, tomando el project brief como fuente madura cuando existe. Mantiene trazabilidad desde requirement/brief hacia PRD y desde PRD hacia spec. La spec incluye un plan de retrieval para que agentes de backlog recuperen contexto puntual sin releer toda la documentacion.

**Output principal:**

- `03_specs/prd.md`
- `03_specs/specs.md`
- Edges `REQ/project_brief -> PRD -> SPEC`

**Como interpretar el resultado:** El PRD debe narrar que se implementa y por que. La spec debe funcionar como contrato operativo para agentes y como puente trazable hacia backlog. Ambos deben revisarse, no aceptarse ciegamente.

### Escenario 11: Generacion De Backlog Dev-Ready Inicial

**Contexto:** Ya existe spec y se quiere crear un primer backlog trazable.

**Comandos:**

```powershell
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
```

**Que hace Sentinel:** Genera epic, user story, acceptance criteria y test case inicial. Tambien crea edges `SPEC -> EPIC -> US -> AC -> TC`.

**Output principal:**

- `04_backlog/EPIC-001.md`
- `04_backlog/US-001.md`
- `05_quality/TC-001.md`

**Como interpretar el resultado:** Es un backlog inicial y trazable, no necesariamente la planificacion final de sprint. Sirve como base para refinamiento humano/agente.

### Escenario 12: Intento De Backlog Con Proyecto DIRTY

**Contexto:** Alguien intenta generar backlog o calidad cuando todavia hay gaps bloqueantes o problemas de salud.

**Comando:**

```powershell
python -m sentinel /backlog PROJECT_ID
```

**Que hace Sentinel:** El command protocol bloquea la ejecucion si el proyecto esta `DIRTY`.

**Output principal:** Error por consola indicando que el proyecto no esta listo.

**Como interpretar el resultado:** Este bloqueo protege al equipo de generar deuda documental o historias basadas en supuestos no confirmados.

## Bloque D: Cambios, Reuniones Y Feedback

### Escenario 13: Feedback Externo No Estructurado

**Contexto:** El cliente envia un correo, Slack, comentario de demo o nota suelta que cambia prioridad, alcance o comportamiento esperado.

**Comando:**

```powershell
python -m sentinel /sync PROJECT_ID --source input\interactions\client-feedback.md --note "client feedback after demo"
```

**Que hace Sentinel:** Copia el input a `07_changes/`, crea un `CHG`, genera impact report y relaciona el cambio con artefactos potencialmente afectados.

**Output principal:**

- `07_changes/[source].md`
- `07_changes/[source]_impact_report.md`
- `07_changes/metabolism_log.md`
- Edges `CHG -> impacted artifacts`

**Como interpretar el resultado:** `/sync` no parchea magicamente todo. Identifica impacto y deja evidencia para que el equipo actualice brief, specs o backlog con control.

### Escenario 14: Sincronizacion Autonoma De Novedades

**Contexto:** Hay varios archivos nuevos o modificados en `input/` o carpetas de contexto y no se quiere procesarlos uno por uno.

**Comando:**

```powershell
python -m sentinel /sync PROJECT_ID
```

**Que hace Sentinel:** Lee `00_raw/source_manifest.json`, compara hashes y detecta archivos nuevos o modificados. Cada novedad se procesa como cambio.

**Output principal:**

- Eventos `CHG`
- Impact reports
- Manifest actualizado

**Como interpretar el resultado:** Es util para barridos periodicos, pero si el archivo es un `gaps.md` respondido, conviene usar `/resolve-gaps` primero para aprovechar el cierre estructurado.

### Escenario 15: Reunion Formal Con Decisiones

**Contexto:** Hay una minuta o transcripcion donde stakeholders acuerdan reglas, cambios de alcance o decisiones relevantes.

**Comando:**

```powershell
python -m sentinel /sync PROJECT_ID --source input\interactions\meeting-notes.md --note "stakeholder meeting decisions"
```

**Que hace Sentinel:** Registra la reunion como cambio, genera impact report y ayuda a detectar que specs, gaps, decisions o backlog podrian necesitar actualizacion.

**Output principal:**

- Change event
- Impact report
- Posibles nuevos gaps o decisiones pendientes

**Como interpretar el resultado:** Una reunion no deberia quedar solo como memoria humana. Si cambia el entendimiento, debe quedar trazada.

### Escenario 16: Cambio Interno De Tecnologia O Negocio

**Contexto:** El equipo interno detecta una restriccion tecnica, cambia una decision de arquitectura o redefine una regla de negocio sin que venga del cliente.

**Comando:**

```powershell
python -m sentinel /sync PROJECT_ID --source input\technology_context\internal-decision.md --note "internal technical decision"
```

**Que hace Sentinel:** Trata la novedad como cambio trazable. Si afecta requirements, brief, specs o backlog, el impact report lo deja visible.

**Output principal:**

- `CHG`
- Impact report
- Contexto indexado para retrieval

**Como interpretar el resultado:** Las decisiones internas tambien pueden invalidar supuestos. Registrar el cambio evita que el proyecto conserve artefactos aparentemente correctos pero tecnicamente obsoletos.

## Bloque E: Memoria, Recuperacion Y Exports

### Escenario 17: Recuperar Contexto Sin Cargar Todo El Workspace

**Contexto:** Un agente o persona necesita entender un tema puntual, como "SLA risk", "usuarios", "estados UX" o "endpoint inventory", sin leer todos los archivos.

**Comando:**

```powershell
python -m sentinel /retrieve PROJECT_ID --query "SLA risk source of truth" --workflow discovery --max-chars 2000 --summary-only --write-pack
```

**Que hace Sentinel:** Consulta memoria local, aplica filtros, devuelve resultados con `why_retrieved` y puede escribir un context pack reproducible.

**Output principal:**

- Resultados por consola
- `08_context_packs/[workflow].json` si se usa `--write-pack`

**Como interpretar el resultado:** Retrieval es progressive disclosure. Sirve para traer lo necesario y cuidar contexto/tokens, pero siempre se puede volver al archivo fuente.

### Escenario 18: Reindexar Despues De Edicion Manual

**Contexto:** Alguien edito manualmente un `.md` del workspace. La memoria local puede haber quedado desactualizada.

**Comando:**

```powershell
python -m sentinel /reindex PROJECT_ID
```

**Que hace Sentinel:** Reconstruye memoria local desde el grafo, artefactos versionables y carpetas de contexto.

**Output principal:**

- `memory.lancedb/memory.json`
- `memory.lancedb/artifact_manifest.json`
- LanceDB local actualizado cuando esta disponible

**Como interpretar el resultado:** No cambia la fuente de verdad. Solo actualiza los indices de recuperacion.

### Escenario 19: Exportar Un Artefacto Compartible

**Contexto:** Se quiere compartir un `gaps.md`, `project-brief.md` o context request sin exponer rutas internas innecesarias.

**Comandos:**

```powershell
python -m sentinel /export PROJECT_ID --artifact gaps --format md
python -m sentinel /export PROJECT_ID --artifact brief --format md
python -m sentinel /export PROJECT_ID --artifact context-request --format md --domain technology
```

**Que hace Sentinel:** Copia el artefacto a `08_context_packs/exports/`.

**Output principal:**

- Archivo exportado en `08_context_packs/exports/`

**Como interpretar el resultado:** El export es una copia controlada. El workspace sigue siendo la fuente de verdad.

## Bloque F: Gobernanza Y Salud

### Escenario 20: Health Check Antes De Handoff

**Contexto:** El equipo quiere pasar el requerimiento a Tecnologia, Diseno, QA, specs, backlog o una revision de fase.

**Comandos:**

```powershell
python -m sentinel /trace PROJECT_ID
python -m sentinel /health PROJECT_ID
python -m sentinel /validate PROJECT_ID
```

**Que hace Sentinel:** Materializa vistas de trazabilidad, revisa health signals y valida integridad estructural del workspace.

**Output principal:**

- `06_traceability/traceability_matrix.md`
- `06_traceability/traceability_graph.md`
- `06_traceability/health_report.md`
- `06_traceability/health_report.json`

**Como interpretar el resultado:** `VALID` y `CLEAN` significan que el workspace esta estructuralmente sano. No significan aprobacion funcional final.

### Escenario 21: Deteccion De Bloqueo Interno

**Contexto:** El equipo descubre que una historia, regla o decision no puede avanzar por una restriccion tecnica, legal, de datos o de negocio.

**Comando recomendado:**

```powershell
python -m sentinel /sync PROJECT_ID --source input\interactions\blocker.md --note "internal blocker"
python -m sentinel /health PROJECT_ID
```

**Que hace Sentinel:** Registra el bloqueo como cambio, analiza impacto y permite que health marque el proyecto como `DIRTY` si aparecen gaps bloqueantes o inconsistencias.

**Output principal:**

- Change impact report
- Posibles gaps nuevos
- Health report actualizado

**Como interpretar el resultado:** Un bloqueo no deberia resolverse con una edicion silenciosa del backlog. Debe quedar como evidencia trazable y, si corresponde, degradar readiness hasta que se resuelva.

### Escenario 22: Validacion Antes De Subir Cambios Del Framework

**Contexto:** Se hicieron cambios al runtime, skills, docs o tests de Sentinel y se quiere asegurar que la version local esta sana antes de commit/push.

**Comando:**

```powershell
python -m unittest discover -s tests
```

**Que hace Sentinel:** En realidad este comando ejecuta la suite Python del repo. Verifica flujos core: init, ingest, gaps, resolve-gaps, brief, context-request, retrieve, sync, health, validate y aliases slash.

**Output principal:** Resultado de unittest.

**Como interpretar el resultado:** Si los tests fallan, no subas el framework. Si pasan, el cambio tiene una base minima de confianza local.

### Escenario 23: Laptop Nueva O Entorno Recien Clonado

**Contexto:** Una persona clona el repositorio en una laptop nueva y quiere saber si puede usar CLI, Kilo commands, skills, memoria local y LanceDB.

**Comandos:**

```powershell
python -m sentinel /doctor
python -m sentinel /init DEMO_PROJECT
python -m sentinel /status DEMO_PROJECT
```

**Que hace Sentinel:** `/doctor` funciona como checklist ejecutable. Verifica Python, estructura del repo, adapters de Codex/Kilo, permisos de escritura, dependencia `lancedb`, prueba local de LanceDB, comandos disponibles y dependencias opcionales.

**Input esperado:** Repositorio clonado o ZIP extraido en una carpeta escribible.

**Output principal:** Resultado JSON de `/doctor` con `PASS`, `WARN` o `FAIL` por cada chequeo.

**Como interpretar el resultado:** Si falla `lancedb`, instalar dependencias con `python -m pip install -e .` o usar el instalador local aprobado. Si falla Kilo, confirmar que VS Code abrio la raiz del repo y no una subcarpeta.

## Como Elegir Entre `/resolve-gaps` Y `/sync`

Usa `/resolve-gaps` cuando:

- el archivo tiene secciones `### GAP-ID`;
- el cliente o dominio respondio campos de respuesta;
- queres cerrar gaps de forma controlada;
- necesitas promover seeds o decisiones confirmadas.

Usa `/sync` cuando:

- el input trae informacion nueva no estructurada;
- hay una minuta, correo, Slack, decision interna o feedback general;
- necesitas evaluar impacto sobre brief, specs, backlog o tests;
- el contenido puede crear nuevos gaps o nuevos requerimientos.

En muchos casos se usan ambos: primero `/resolve-gaps` para cerrar lo estructurado, despues `/sync` para registrar novedades que exceden los gaps existentes.
