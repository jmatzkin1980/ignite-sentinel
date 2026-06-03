# 📚 Volumen 0: Fundamentos y Arquitectura General (Sentinel v6.0 — Roo Code)

> **Versión:** 6.0 (Agentic Graph-Driven Mastery for Roo Code)
> **Objetivo:** Estandarización de Agentes de Razonamiento mediante el Agentic Knowledge Graph, Comandos de Metabolismo y Vertical Slicing.
> **Filosofía:** Densidad Innegociable, Estado Persistente, Soberanía de Workspace e Integridad de Grafo.

---

# 📚 Volumen 0: Fundamentos y Arquitectura General (Sentinel v6.0 — Roo Code)

> **Versión:** 6.0 (Agentic Graph-Driven Mastery for Roo Code)
> **Objetivo:** Estandarización de Agentes de Razonamiento mediante el Agentic Knowledge Graph, Comandos de Metabolismo y Vertical Slicing.
> **Filosofía:** Densidad Innegociable, Estado Persistente, Soberanía de Workspace, Integridad de Grafo y **Censura de Fidelidad**.

---

## 🛡️ 1. Resumen Ejecutivo: La Revolución del "Hilo de Oro" en Roo Code

**Sentinel v6.0** no es simplemente una metodología de documentación o un conjunto de plantillas estáticas; es un **Sistema Operativo Agéntico** implementado nativamente en Roo Code para erradicar definitivamente la brecha entre la intención de negocio y la ejecución técnica. Su propósito fundamental es blindar el conocimiento del proyecto frente a la entropía, la fragmentación y el olvido agéntico.

En el desarrollo de software tradicional, el conocimiento se erosiona en silos (emails, minutas, código, diagramas) que pierden sincronía rápidamente. Sentinel resuelve esto forjando un **Hilo de Oro (Gold Thread)**: una conexión inquebrantable y bidireccional, validada físicamente por motores de Python, que vincula cada regla de negocio con su implementación técnica y su validación funcional. Si una pieza del Hilo se altera, el sistema entero detecta el impacto de forma determinista, garantizando que el software sea siempre un reflejo fiel de la verdad del negocio.

**La ventaja soberana de Roo Code:** A diferencia de versiones anteriores que dependían de la memoria volátil del chat o de prompts genéricos, Sentinel v6.0 en Roo adopta un sistema de **Comandos Nativos (`.roo/commands/`)** y **Motores Deterministas (`.roo/scripts/`)**. Todo el sistema opera bajo un `ID_WORKSPACE` mandatorio, lo que garantiza una **Soberanía de Datos** absoluta: el agente puede gestionar múltiples proyectos complejos en el mismo repositorio con "ADNs" y reglas de blindaje totalmente aisladas. Además, esta versión introduce la **Censura de Fidelidad Cuantitativa**, un protocolo de seguridad innegociable que prohíbe al agente alucinar, inferir o "redondear" métricas (ROI, porcentajes, montos) que no nazcan de una semilla de identidad validada, protegiendo al Arquitecto de decisiones basadas en datos ficticios o suposiciones agénticas.

---

## 👁️‍🗨️ 2. Visión General del Sistema: El Viaje de la Información

La metamorfosis de un requerimiento crudo en un backlog ejecutable y un grafo de conocimiento vivo es una **destilación alquímica de la información**, dividida en fases estrictas y gobernada por un metabolismo determinista:

### 🔍 Fase 0: Discovery (Censura del Caos)
Todo comienza con la ingesta de insumos crudos (transcripciones de reuniones, PDFs de requerimientos, correos). Sentinel activa su **Triple Auditoría Forense** (BA, Tech, Design) para identificar **Identity Seeds (Semillas de Identidad)**: átomos de verdad innegociables que definen el proyecto. En esta fase, el agente actúa como un **Censor de Conocimiento**: detecta vacíos de información (GAPs) y bloquea físicamente el avance si se detectan "alucinaciones métricas". Si el cliente no proveyó un número exacto de ahorro o performance, el sistema lo registra como un `[GAP_FIDELITY]` y el estado del proyecto permanece en `DIRTY` hasta que la verdad sea capturada y validada.

### 🔱 Fase 1: Specs (La Pentagonía de la Verdad)
Una vez que el veredicto de integridad es `CLEAN`, se orquesta la redacción sincronizada de la **Pentagonía**: los 5 documentos maestros de ingeniería (BRD, PRD, FRD, Tech Specs y Design Specs). Sentinel no redacta en el vacío; consume el **Project DNA** (`project-dna.md`) como su "genoma técnico" para **inyectar obligatoriamente** los estándares de **Architectural Armor P5** (blindaje de datos, performance y seguridad) y **UX Resilience P3** (estados de resiliencia visual: Idle, Loading, Error, Empty) en cada plano de ingeniería. Esta fase asegura que la solución sea técnica y funcionalmente indestructible antes de escribir una sola línea de código.

### 🔪 Fase 2: Backlog (Vertical Slicing E2E)
Los planos de la Pentagonía se someten a una fragmentación quirúrgica mediante **Vertical Slicing**. El agente genera Historias de Usuario que no son simples tareas, sino **Cápsulas de Ejecución Autónoma**. Cada US posee inyección textual de ADN (reglas P3/P5 específicas), criterios de aceptación en Gherkin y un vínculo físico al Grafo (`KG_NODE_ID`). El resultado es un backlog "AI-Ready", diseñado para que cualquier desarrollador (humano o IA) pueda codificar con una tasa de error cercana a cero.

### 🧬 Fase 3: Mantenimiento y Metabolismo (Sincronía Determinista)
El proyecto es un organismo vivo que evoluciona. Ante nuevas reuniones o feedback del cliente, Sentinel activa sus comandos de **Metabolismo** (`/ignite_meeting`, `/external_sync`). El agente procesa la novedad, calcula el **Blast Radius** (Impacto) mediante la ejecución de scripts en la terminal y parchea quirúrgicamente la Pentagonía y el Backlog. Cada mutación queda registrada forensemente en el `backlog_evolution_report.md` dentro de la **Bóveda de Meta**, asegurando que el Hilo de Oro permanezca intacto y auditable durante todo el ciclo de vida del producto.

---

## 🗺️ 3. Topología del Sistema (Tree View Roo Code)

Esta es la estructura canónica y soberana del ecosistema Sentinel v6.0, mapeada al 100% con los artefactos físicos.

```text
ROOT/
├── .roo/                               # 🧠 CEREBRO DEL AGENTE (Gobernanza y Sistema)
│   ├── .roorules                       # Reglas de jerarquía de verdad y SSoT
│   ├── .roomodes                       # Definición de los motores cognitivos (Skills)
│   ├── custom_modes.json               # Configuración base de Roo Code
│   ├── mcp.json                        # Configuración de herramientas MCP
│   │
│   ├── commands/                       # ⚡ COMANDOS DE EJECUCIÓN (Protocolos)
│   │   ├── external_sync.md            # Metabolismo: Ingesta de cliente
│   │   ├── ignite_backlog.md           # Fase 2: Vertical Slicing
│   │   ├── ignite_discovery.md         # Fase 0: Cacería de identidad
│   │   ├── ignite_gap_solve.md         # Gobernanza: Cierre de incertidumbres
│   │   ├── ignite_meeting.md           # Ingesta asíncrona de transcripciones
│   │   ├── ignite_specs.md             # Fase 1: Redacción de Pentagonía
│   │   ├── ignite_health.md           # Auditoría forense 360° (Preserva errata de sistema)
│   │   ├── internal_gap.md             # Corregido: Registro de riesgos de equipo
│   │   ├── internal_sync.md            # Metabolismo: Refinamiento técnico/diseño general
│   │   ├── meeting_sync.md             # Metabolismo: Procesamiento de reuniones
│   │   ├── sync_design.md              # Sincroniza cambios visuales aislados
│   │   └── sync_tech.md                # Sincroniza cambios técnicos aislados
│   │
│   ├── hooks/ 
│   │   └── pre-tool-use.js             # 🛡️ Guardrail: Valida soberanía de Workspace y Fases
│   │
│   ├── scripts/                        # ⚙️ MOTORES DETERMINISTAS (Validación Física)
│   │   ├── extractor.py                # Convierte Markdown en Grafo de Conocimiento
│   │   ├── graph_visualizer.py         # Genera el mapa visual en Mermaid
│   │   ├── impact_analyzer.py          # Calcula el "Blast Radius" de las mutaciones
│   │   └── validator.py                # Audita orfandad y cumplimiento de P5/P3
│   │
│   ├── memory/                         # 🧬 ADN GLOBAL (Leyes Genéticas)
│   │   └── project-dna.md              # Blueprint y estándares físicos (P3/P5) instanciados
│   │
│   └── templates/                      # 📝 BÓVEDA DE PLANTILLAS (Alta Densidad)
│       ├── decision_log_template.md    # Registro histórico de justificaciones
│       ├── maestro_audit_backlog.md    # Checklist de QA para Historias de Usuario
│       ├── maestro_brd.md              # Template: Business Requirements Document
│       ├── maestro_design.md           # Template: Design Specifications
│       ├── maestro_discovery_gap.md    # Tablero de control de riesgos e incertidumbre
│       ├── maestro_discovery_log.md    # Diario de cacería forense
│       ├── maestro_frd.md              # Template: Functional Requirements Document
│       ├── maestro_health_report.md    # NUEVO: Molde para veredictos de salud
│       ├── maestro_prd.md              # Template: Product Requirements Document
│       ├── maestro_rtm_matrix.md       # NUEVO: Matriz de trazabilidad requerimiento-código
│       ├── maestro_semantic_mapping.md # Mapeo físico entre UI Component y Seeds
│       ├── maestro_tech.md              # Template: Technical Specifications
│       ├── maestro-backlog.md          # Estructura canónica de User Story Ejecutable
│       ├── maestro-evolution.md        # Historial forense de mutaciones de ADN
│       ├── maestro-seeds.md            # Matriz de verdades atómicas (Identidad)
│       ├── meeting_metabolism_template.md # Mapeo de decisiones NODE-DEC-XXX
│       ├── meeting-digest-template.md  # Molde para resumen de acuerdos humanos
│       ├── project_state_template.json # Máquina de estados operativa
│       ├── project-dna_template.md     # Estándares físicos y blueprint estratégico
│       └── sentinel-graph-map-template.md # Molde para mapa visual Mermaid
│
├── 01_requirements/                    # 🏭 FÁBRICA DE ESPECIFICACIONES (El Proyecto)
│   └── [ID_WORKSPACE]/                 # Aislamiento por Soberanía de Proyecto
│       ├── 00_meta/                    # 🛡️ BÓVEDA DE META (ESTADO, SALUD Y GRAFO)
│       │   ├── backlog_evolution_report.md
│       │   ├── health_report.json      # Movido: Veredicto estructurado
│       │   ├── health_report.md        # Movido: Veredicto forense humano
│       │   ├── identity_seeds.md       
│       │   ├── maestro_discovery_gap.md
│       │   ├── project_state.json      
│       │   └── sentinel-graph-map.md   
│       │
│       ├── 00_discovery/               # REGISTRO FORENSE
│       │   ├── discovery_gap_report.md
│       │   ├── discovery_log.md        
│       │   └── meeting_metabolism_[FECHA].md 
│       │
│       ├── 01_input/                   # INSUMOS CRUDOS (Alimentación)
│       │   └── (PDFs, Mails, Requerimientos)
│       │
│       ├── 02_backlog/                 # SALIDA DE FASE 2 (Ejecución)
│       │   ├── 00_critical_path/       
│       │   ├── [EPICA]/
│       │   │   └── [US-XXX].md     
│       │   └── RTM_MATRIX.md           
│       │
│       └── 03_knowledge_pack/          # SALIDA DE FASE 1 (Planos)
│           ├── brd.md                  # Visión de Negocio
│           ├── design_specs.md         # Resiliencia UX y Binding Semántico
│           ├── frd.md                  # Lógica Funcional
│           ├── prd.md                  # Definición de Producto
│           └── tech_specs.md           # Plano Técnico
│
├── 02_architecture/                    # 🏛️ LIBRERÍA DE ESTÁNDARES CORPORATIVOS (Solo Lectura)
├── 03_design/                          # 🎨 ARTEFACTOS VISUALES (Solo Lectura)
│   └── [ID_WORKSPACE]/                 # Aislamiento visual por proyecto
│       └── ux/
│           ├── flows/                  # Diagramas de flujo funcionales
│           └── screens/                # Mocks y Wireframes de interfaces
│
└── 07_meetings/                        # 🗣️ MEMORIA DE REUNIONES CRUDAS
    └── [ID_WORKSPACE]/                 # Aislamiento de transcripts por proyecto
        └── (Transcripts y Digests de minutas)
```

---

### 🚦 4. Escenarios Operativos (Guía Práctica del Ciclo de Vida)

Esta sección constituye el manual de campo soberano de Sentinel v6.0. Define la respuesta táctica ante cada hito del proyecto, garantizando que el agente actúe como un **Knowledge Engineer** y no como un simple redactor, utilizando la ejecución determinista de la terminal para materializar el Grafo y el Hilo de Oro.

---

#### 🏗️ BLOQUE A: GÉNESIS E IDENTIDAD (Fase 0 - Discovery)

**Escenario 1: Ignición Inicial (The Big Bang Forense)**
* **Contexto:** Se recibe el primer paquete de requerimientos crudos. No existe estructura física en el repositorio.
* **Comando:** `/ignite_discovery [ID_WORKSPACE]`
* **Acción Agéntica:** El agente activa la **Triple Auditoría Forense** (BA, Tech, Design). Escruta el Vault corporativo para heredar estándares. Aplica la **Censura de Fidelidad**, capturando Seeds y bloqueando métricas sin sustento.
* **Insumo (Input):** Carpeta `01_input/` y Vaults globales (`02_architecture`, `03_design`).
* **Producto (Output):** `project_state.json` (Phase 0), `identity_seeds.md` (Seeds [KNOWN]), `discovery_gap_report.md` (GAPs iniciales) y `project-dna.md` instanciado.
* **Mandato de Terminal:** Ejecución obligatoria de `extractor.py` para mapear el Grafo raíz.

**Escenario 2: Sincronía Inicial de Bóveda (Herencia de Leyes)**
* **Contexto:** Tras la ignición, es necesario inyectar los estándares específicos de arquitectura o diseño que rigen la compañía.
* **Comando:** `/sync_tech` o `/sync_design`
* **Acción Agéntica:** El agente mapea los 7 Pilares Técnicos o el Binding Semántico P2 del Vault global hacia el ADN local del proyecto.
* **Insumo (Input):** Documentación técnica y visual en `02_architecture/` y `03_design/`.
* **Producto (Output):** Actualización del `.roo/memory/project-dna.md` con las restricciones físicas (P3/P5) finales.
* **Mandato de Terminal:** `extractor.py` para registrar las nuevas aristas de herencia.

**Escenario 3: Resolución de GAPs (Higiene de Incertidumbre)**
* **Contexto:** Se obtiene información que cierra un vacío detectado en el Discovery (ej. "El cliente confirma que el ahorro esperado es del 15%").
* **Comando:** `/ignite_gap_solve [ID_GAP]`
* **Acción Agéntica:** Transforma el GAP en certeza atómica. Promueve semillas de `[VOLATILE]` a `[KNOWN]`. Actualiza el estado de integridad global.
* **Insumo (Input):** Respuesta del stakeholder y `discovery_gap_report.md`.
* **Producto (Output):** `identity_seeds.md` (Seed validada) y GAP marcado como `CLOSED` en `00_meta/`.
* **Mandato de Terminal:** `validator.py` para verificar si el estado puede pasar de `DIRTY` a `CLEAN`.

---

#### 🔱 BLOQUE B: INGENIERÍA Y PLANOS (Fase 1 - Specs)

**Escenario 4: Orquestación de la Pentagonía (Redacción de Planos)**
* **Contexto:** El estado es `CLEAN`. Es momento de generar la documentación de ingeniería de alta densidad.
* **Comando:** `/ignite_specs [ID_WORKSPACE]`
* **Acción Agéntica:** Redacción sincronizada de BRD, PRD, FRD, Tech y Design Specs. **Inyección Mandatoria:** El agente lee el DNA e inyecta físicamente SQL Armor (P5) y Resiliencia UX (P3) en los documentos.
* **Insumo (Input):** Seeds validadas y el `project-dna.md` local.
* **Producto (Output):** Carpeta `03_knowledge_pack/` completa y alineada por `KG_NODE_ID`.
* **Mandato de Terminal:** `extractor.py` y `graph_visualizer.py` para visualizar la densidad de la Pentagonía.

---

#### 🔪 BLOQUE C: VERTICAL SLICING Y CONSTRUCCIÓN (Fase 2 - Backlog)

**Escenario 5: Generación de Backlog (Execution Ready)**
* **Contexto:** Pentagonía aprobada. Se requiere el backlog fragmentado para el desarrollo del primer sprint.
* **Comando:** `/ignite_backlog [ID_WORKSPACE]`
* **Acción Agéntica:** Aplica **Vertical Slicing** orientado a JTBD. Genera Historias de Usuario "End-to-End". Inyecta en cada US el código de blindaje (P5) y los estados visuales (P3) correspondientes.
* **Insumo (Input):** La Pentagonía en `03_knowledge_pack/`.
* **Producto (Output):** Carpeta `02_backlog/` con Historias de Usuario y la `RTM_MATRIX.md` (Matriz de Trazabilidad).
* **Mandato de Terminal:** `validator.py` para certificar que cada US tiene un ancestro en el Grafo.

---

#### 🧬 BLOQUE D: METABOLISMO Y CAMBIO DE RUMBO (Fase 3 - Mantenimiento)

**Escenario 6: Metabolismo Pesado (Acuerdos de Reunión)**
* **Contexto:** Una reunión formal con stakeholders cambia una regla de negocio o añade un requerimiento funcional.
* **Comando:** `/ignite_meeting [ID_WORKSPACE] [FILE_NAME]`
* **Acción Agéntica:** Ingesta del transcript. Extrae `NODE-DEC-XXX`. Identifica el **Blast Radius**: qué Specs y qué US en el backlog deben ser parcheadas por este cambio.
* **Insumo (Input):** Transcripción en `07_meetings/`.
* **Producto (Output):** `meeting_metabolism_[FECHA].md` y actualización quirúrgica de Docs y US afectadas.
* **Mandato de Terminal:** `impact_analyzer.py` para certificar que el cambio no rompió el Hilo de Oro.

**Escenario 7: Ingesta de Feedback Externo (Ajuste de Cliente)**
* **Contexto:** El cliente envía un correo o mensaje con un cambio de prioridad o un feedback sobre una pantalla.
* **Comando:** `/external_sync [ID_WORKSPACE]`
* **Acción Agéntica:** Actúa como **Knowledge Auditor**. Valida si el feedback contradice semillas previas. Si es válido, parchea el backlog y registra la mutación.
* **Insumo (Input):** Texto crudo del feedback.
* **Producto (Output):** `backlog_evolution_report.md` actualizado y parches en las US de `02_backlog/`.
* **Mandato de Terminal:** `validator.py` para asegurar que el ADN P3/P5 sigue cumpliéndose.

**Escenario 8: Refinamiento Interno (Evolución Técnica/Negocio)**
* **Contexto:** El equipo decide un cambio en la lógica interna o una mejora en el stack técnico sin intervención externa.
* **Comando:** `/internal_sync [ID_WORKSPACE]`
* **Acción Agéntica:** Integra la novedad técnica. Si afecta el genoma del proyecto, actualiza el `project-dna.md` y propaga el cambio a las Tech Specs y al Backlog.
* **Insumo (Input):** Definición técnica del equipo.
* **Producto (Output):** Actualización de `tech_specs.md` y US relacionadas.
* **Mandato de Terminal:** `extractor.py` para sincronizar el mapa visual con la nueva lógica interna.

**Escenario 9: Metabolismo Ágil (Sincronía de Chat)**
* **Contexto:** Un acuerdo rápido o aclaración "al vuelo" que requiere registro pero no es una reunión formal.
* **Comando:** `/meeting_sync [ID_WORKSPACE]`
* **Acción Agéntica:** Captura la decisión inmediata. Genera un Digest ejecutivo y actualiza la semilla o el backlog correspondiente.
* **Insumo (Input):** Nota rápida o acuerdo de chat.
* **Producto (Output):** `meeting-digest-template.md` y actualización de `identity_seeds.md`.

---

#### 🛡️ BLOQUE E: GOBERNANZA Y SALUD (Sistema Inmune)

**Escenario 10: Detección de Bloqueo Interno (Stopper)**
* **Contexto:** El equipo encuentra un impedimento técnico o de negocio que impide avanzar con una US.
* **Comando:** `/internal_gap [ID_WORKSPACE]`
* **Acción Agéntica:** El agente degrada las Seeds afectadas a `[VOLATILE]`. Cambia el veredicto del proyecto a `DIRTY` y registra el GAP para impedir la generación de más deuda técnica.
* **Insumo (Input):** Descripción del bloqueo.
* **Producto (Output):** GAP activo en `maestro_discovery_gap.md` y estado `DIRTY` en `project_state.json`.
* **Mandato de Terminal:** `graph_visualizer.py` para marcar en rojo el nodo bloqueante.

**Escenario 11: Auditoría de Salud 360° (Health Check)**
* **Contexto:** Antes de un cierre de fase, de un sprint review o de un pase a producción.
* **Comando:** `/igntine_health [ID_WORKSPACE]`
* **Acción Agéntica:** Escaneo forense de todo el Grafo. Busca nodos huérfanos, desvíos del DNA P3/P5 y alucinaciones métricas.
* **Insumo (Input):** Todo el Workspace y el `project_state.json`.
* **Producto (Output):** `health_report.md` detallado en `00_meta/`.
* **Mandato de Terminal:** Ejecución innegociable de `validator.py`. No hay veredicto sin ejecución de terminal.

---
**[Sello Fundacional: Sentinel v6.0]**
**[Sync Anchor: VOLUMEN_0_FOUNDATION_MASTER]**