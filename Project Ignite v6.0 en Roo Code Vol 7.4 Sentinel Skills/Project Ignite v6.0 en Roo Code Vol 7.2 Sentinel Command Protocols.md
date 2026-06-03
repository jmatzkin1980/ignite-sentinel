# 📚 Volumen 7.2: Sentinel Command Protocols (Source Bundle — Roo Code)

> **DIRECTIVA SENTINEL v6.0:** Este documento contiene la lógica procedimental de los comandos nativos y el firewall de seguridad. El agente debe utilizar estos protocolos para garantizar que cada acción respete la fase actual, la soberanía del workspace y el Hilo de Oro.

---

## 🛡️ 1. El Guardián del Perímetro (Security Hook)
**PATH:** `.roo/hooks/pre-tool-use.js`
**Función:** Intercepta el uso de herramientas para validar fase, estado `CLEAN/DIRTY` y proteger archivos inmutables.

```javascript
/**
 * 🛡️ SENTINEL v6.0: Perimeter Guard (Knowledge Integrity Hook)
 * OBJETIVO: Interceptar el uso de herramientas para validar la soberanía del 
 * Workspace y autorizar los flujos de Ingesta (Metabolism).
 */

async function preToolUse(toolName, args, context) {
  // 1. 📂 IDENTIFICACIÓN DE SOBERANÍA (Workspace Validation)
  // Extraemos el ID del workspace de la ruta del archivo o del entorno
  [cite_start]const workspaceId = context.env.ID_WORKSPACE || args.path?.split('/')[1] || "Workspace_Desconocido";
  const statePath = `01_requirements/${workspaceId}/00_meta/project_state.json`;

  let projectState;
  try {
    const stateContent = await context.fs.readFile(statePath);
    projectState = JSON.parse(stateContent);
  } catch (e) {
    // Solo permitimos continuar sin estado si estamos encendiendo el motor (Ignición)
    if (!toolName.includes('ignite_discovery')) {
      throw new Error(`⛔ SENTINEL BLOCK: project_state.json no detectado en ${workspaceId}. Ejecuta /ignite_discovery primero.`);
    }
    return;
  }

  const { current_phase, governance_status } = projectState;

  // 2. 🚫 PROTECCIÓN DE INFRAESTRUCTURA .ROO (Inmutabilidad)
  // Bloqueamos escritura en templates y comandos maestros para evitar corrupción del sistema
  if ((toolName === 'write_to_file' || toolName === 'replace_in_file') && 
      (args.path.includes('.roo/templates/') || args.path.includes('.roo/commands/'))) {
    throw new Error("⛔ SENTINEL BLOCK: Los moldes y comandos en .roo/ son inmutables. Cambios estructurales requieren permiso del Arquitecto.");
  }

  // 3. 🚧 GATEKEEPER DE LOS 4 COMANDOS MAESTROS (DNA Integrity)
  // Validamos que solo los comandos autorizados puedan tocar las Seeds y la Evolución
  if (args.path && (args.path.endsWith('identity_seeds.md') || args.path.endsWith('maestro-evolution.md'))) {
    const authorizedCommands = [
      'external_sync', 
      'internal_sync', 
      'internal_gap', 
      'meeting_sync',
      'ignite_discovery'
    ];
    
    const isAuthorized = authorizedCommands.some(cmd => toolName.includes(cmd));
    
    if (!isAuthorized) {
      console.warn(`⚠️ SENTINEL WARNING: Intento de edición de ADN en ${workspaceId} fuera de comando maestro. Riesgo de desincronización del Grafo.`);
    }
  }

  // 4. 🧬 REGLA DE SALUD (Clean vs Dirty Logic)
  // Si el veredicto es DIRTY, bloqueamos la creación de Backlog hasta que se resuelva la incertidumbre
  if (toolName.includes('ignite_backlog') && governance_status.kg_integrity === 'DIRTY') {
    throw new Error("⛔ SENTINEL BLOCK: Integridad DIRTY. Resuelve los GAPs críticos con /internal_sync antes de generar historias.");
  }

  // 5. 🏗️ PROTECCIÓN DE DOMINIOS EXTERNOS (Gobernanza)
  // Arquitectura y Diseño siguen siendo de solo lectura para los agentes de requerimientos
  if (args.path && (args.path.includes('02_architecture/') || args.path.includes('03_design/'))) {
    throw new Error("⛔ SENTINEL BLOCK: Los dominios de Arquitectura y Diseño son SÓLO LECTURA. Hereda definiciones, no las modifiques.");
  }

  console.log(`✅ SENTINEL CLEAR: ${toolName} validado para ${workspaceId} (Fase: ${current_phase}).`);
}

module.exports = preToolUse;
```

---

## 🚀 2. Protocolos de Ignición (Fases 0 a 2)
**Función:** Guían la creación de la identidad, la pentagonía y el backlog.

### 📂 PATH: `.roo/commands/ignite_discovery.md`
```markdown
# 🚀 COMMAND: /ignite_discovery [ID_WORKSPACE]

**OBJETIVO:** Iniciar la Fase 0 (Discovery Forense) y establecer la soberanía del estado del proyecto mediante la extracción de Verdades Atómicas (Seeds), la identificación de patrones JTBD y la instanciación del DNA persistente, aplicando una validación cruzada obligatoria contra el Vault de Arquitectura y Diseño.

---

### 1. 🛡️ STATE & GOVERNANCE CHECK (Firewall de Inicio)
1. **Identificar Workspace:** Definir ruta base en `01_requirements/[ID_WORKSPACE]/`.
2. **Inicializar Estado:** - SI NO existe `00_meta/project_state.json`: Leer `.roo/templates/project_state_template.json`, inyectar metadatos (ID, timestamps, versioning) y guardar en `00_meta/`.
   - Marcar `STATUS_PHASE: PHASE_0_DISCOVERY_INIT` e `integrity: "DIRTY"`.
3. **Soberanía de Terminal:** Es MANDATORIO abrir la terminal para asegurar la ejecución de los motores de lógica (`extractor.py`).
4. **Boot Graph:** Crear o actualizar `00_meta/sentinel-graph-map.md` con el nodo raíz del proyecto (`ROOT-NODE-001`).

### 2. 🧬 CONTEXTUAL BOOTSTRAP (Vault Discovery)
> **Directiva Sentinel:** El agente debe comprender el conocimiento acumulado en el ecosistema antes de escrutar el requerimiento para evitar GAPs redundantes.
1. **Escaneo de Arquitectura:** Analizar obligatoriamente todos los archivos en `02_architecture/` (SSoT de datos, performance, observabilidad, QA y stack).
2. **Escaneo de Diseño:** Listar y analizar el contenido de las rutas de diseño:
   - `03_design/[ID_WORKSPACE]/ux/flows/` (Diagramas de flujos de usuario).
   - `03_design/[ID_WORKSPACE]/ux/screens/` (Mocks y prototipos).
3. **Mapeo de Herencia:** Registrar internamente las capacidades, restricciones técnicas y estándares visuales (P3/P5) que el proyecto ya posee por defecto según el Vault corporativo.

### 3. 🔎 TRIPLE-LENS FORENSIC SCAN (Análisis del Pedido)
1. **Ingesta de Input:** Buscar archivos en `01_requirements/[ID_WORKSPACE]/01_input/` y analizar el contenido aplicando la Triangulación de Alta Densidad.
2. **BA Lens (Evolución JTBD):** - Extraer hallazgos bajo el framework **Jobs to Be Done**.
   - Clasificar cada átomo en: **Contexto** (Cuando...), **Necesidad** (Quiero...) y **Resultado Esperado** (Para...).
3. **Extracción de Identidad (Seeding):**
   - Identificar reglas de negocio, KPIs, restricciones y necesidades de integración.
   - Catalogarlas como `<<SEED-XX>>` en `01_requirements/[ID_WORKSPACE]/00_meta/identity_seeds.md`.
   - Asignar un `KG_NODE_ID` único a cada semilla para asegurar el Hilo de Oro.

### 4. 🛡️ HIGIENE FORENSE & MANDATO DE FIDELIDAD
1. **Mandato de Fidelidad Cuantitativa:** Marcar como `GAP_QUANTITATIVE` cualquier métrica (ROI, %, tiempos, montos) que NO figure textualmente en el `01_input/`. PROHIBIDO INFERIR NÚMEROS.
2. **Diferencial GAP Analysis:** Un GAP solo se considera "BLOCKING" si la información es inexistente tanto en el Input externo como en el Vault interno.
3. **Generación de IDs:** Asignar los primeros `NODE-DEC-XXX` a las decisiones de arquitectura o diseño detectadas por herencia para el futuro Audit Trail.

### 5. 📦 KNOWLEDGE PACKAGING (GAPs & Seeds)
1. **Registro Forense:** Registrar cada hallazgo en `00_discovery/discovery_log.md`.
2. **Mapa de Incertidumbre:** - Leer molde `.roo/templates/maestro_discovery_gap.md`.
   - Instanciar en `01_requirements/[ID_WORKSPACE]/00_meta/discovery_gap_report.md`.
   - **Obligatorio:** Declarar `Vault_Source_Consulted` por cada GAP para demostrar el escrutinio de la arquitectura antes de admitir ignorancia.

### 6. 🧬 DNA SEEDING (Sintetizar Memoria Persistente)
1. **Instanciar DNA:** Crear o actualizar el archivo `.roo/memory/project-dna.md` basándose en el template maestro.
2. **Inyección de Genes:** Volcar en el DNA los patrones P3 (Resiliencia UX) y P5 (SQL Armor / Technical Standards) detectados durante el Contextual Bootstrap.
3. **Propósito:** Este archivo es la ÚNICA fuente de verdad técnica para el comando `/ignite_specs`.

### 7. ✅ COMPLETION & VERDICT
1. **Sincronización de Grafo:** Ejecutar obligatoriamente en terminal:
   ```bash
   python .roo/scripts/extractor.py [ID_WORKSPACE]
   python .roo/scripts/graph_visualizer.py [ID_WORKSPACE]
   ```
2. **Update State:** Actualizar el timestamp de última mutación y el veredicto de fase en project_state.json.
3. **Veredicto de Calidad:**
- **CLEAN:** Habilita el avance a /ignite_specs si no hay GAPs de severidad ALTA activos.
- **DIRTY:** Si existen GAPs críticos o conflictos de fidelidad cuantitativa, el proyecto se mantiene bloqueado.

**[Sello de Ignición: Sentinel v6.0 — Forensic Discovery Engine]**
```

### 📂 PATH: `.roo/commands/ignite_specs.md`

```markdown
# 📄 COMMAND: /ignite_specs [ID_WORKSPACE]

**ESTRATEGIA:** Generación de la Pentagonía de Specs mediante el descubrimiento dinámico de la gobernanza, con blindaje absoluto contra alucinaciones métricas, alineación estricta de "Persona" por capa de documento y consumo mandatorio del genoma técnico (DNA) y estratégico (JTBD).

---

### 1. 🛡️ GATEKEEPER & DATA FIDELITY (Mandatos de Verdad)
1. **Validar Bloqueos:** Leer `00_meta/maestro_discovery_gap.md`. SI existen GAPs con prioridad ALTA (Blocking) sin resolver: **ABORTAR**.
2. **Validar Fase:** Requiere veredicto `CLEAN` en `00_meta/project_state.json`.
3. **Validación de Semillas:** Escrutar `00_meta/identity_seeds.md`. El agente debe validar que existan suficientes semillas en estado `[KNOWN]` para cada una de las 3 dimensiones (BA, Tech, Design) antes de proceder.
4. **MANDATO DE FIDELIDAD (Anti-Hallucination):** - El agente tiene terminantemente prohibido inventar métricas cuantitativas (%, horas, ROI, montos monetarios).
   - Si la información exacta no reside en las `identity_seeds.md` o en el input, el agente DEBE usar descriptores cualitativos o marcar explícitamente como `{{PENDING_STAKEHOLDER_INPUT}}`.

### 2. 🧬 DNA BOOTSTRAP (Soberanía Técnica)
1. **Ingesta de SSoT:** Leer obligatoriamente el archivo `.roo/memory/project-dna.md` instanciado en Discovery. Este documento es la SSoT técnica innegociable.
2. **Sincronización de Bóveda:** Leer archivos en `02_architecture/` y `03_design/{{ID_WORKSPACE}}/ux/` (flows y screens) para validar que el DNA esté actualizado con los últimos "genes" del proyecto.
3. **Filtro Genético:** Cualquier regla técnica o visual definida en el DNA (P5 SQL Armor / P3 Resiliencia) debe inyectarse transversalmente en toda la Pentagonía.

### 3. 🧠 LAYER 1: BUSINESS & PRODUCT (Persona: Senior Business Analyst)
1. **Higiene de Formato:** PROHIBIDO el uso de bloques YAML para descripciones narrativas. Usar exclusivamente Markdown nativo (prosa, tablas y listas).
2. **BRD (Business Requirements Document):** Generar en `03_knowledge_pack/brd.md` en lenguaje ejecutivo, centrando el foco en políticas de negocio (`[BP]`) y requerimientos de alto nivel (`[HLR]`).
3. **PRD (Product Requirements Document):** Generar en `03_knowledge_pack/prd.md`.
   - **Anclaje JTBD:** Es MANDATORIO utilizar los hallazgos `[JTBD-XXX]` del Discovery Log como estructura base para definir la propuesta de valor y los User Journeys.
   - **Linaje de Decisión:** Consumir los `NODE-DEC-XXX` heredados del Discovery para justificar la estrategia de producto.

### ⚙️ 4. LAYER 2: FUNCTIONAL & TECHNICAL (Persona: Technical Architect)
1. **FRD (Functional Requirements Document):** Generar en `03_knowledge_pack/frd.md`. Detallar lógica de transformación y filtros técnicos (ej: `calc_flag_es_deuda`) extraídos del Vault.
2. **TECH SPECS:** Generar en `03_knowledge_pack/tech_specs.md`.
   - **Población de 7 Pilares:** Distribuir el conocimiento técnico con rigor absoluto.
   - **Consumo de IDs:** Integrar los `NODE-DEC-XXX` pre-existentes del Discovery para fundamentar el stack y la arquitectura, generando nuevos IDs solo para decisiones de implementación granulares.
3. **DESIGN SPECS:** Generar en `03_knowledge_pack/design_specs.md`.
   - **Mandato P3/P5:** Documentar estados de resiliencia (P3) y binding semántico (Semantic IDs) detectados, asegurando coherencia con los estados definidos en el DNA.

### 5. ✅ COMPLETION & GRAPH SYNC
1. **Sincronía de Grafo:** Registrar los 5 documentos generados como nodos de especificación en `00_meta/sentinel-graph-map.md`.
2. **Actualización de Estado:** Cambiar `current_phase` a `PHASE_1_SPECS_COMPLETED` y actualizar el veredicto a `READY_FOR_SLICING` en `project_state.json`.
3. **Audit Trail Anchor:** Asegurar que cada Spec cite al menos un `ID_REF` o `NODE-DEC-XXX` para garantizar la trazabilidad del Hilo de Oro.

**[Sello de Lógica: Sentinel v6.0 — High Fidelity Specs Engine]**
```

### 📂 PATH: `.roo/commands/ignite_backlog.md`
```markdown
---
name: ignite-backlog
description: Transforma la Pentagonía en un Backlog ejecutable mediante Vertical Slicing orientado a JTBD e inyecta blindaje P5/P3 en cada cápsula de ejecución.
modeSlugs:
  - sentinel-slicing
---

# 🔪 WORKFLOW: /ignite_backlog [ID_WORKSPACE]

**ESTRATEGIA:** Fragmentación de valor funcional (Vertical Slicing) + Inyección de ADN Persistente (P5/P3) + Auditoría Forense de Calidad + Sincronización del Hilo de Oro.

---

### 1. 🛡️ GATEKEEPER CHECK (Integridad de Inicio)
1. **Validar Readiness:** Leer `project_state.json`. SI la fase NO es `PHASE_1_SPECS_COMPLETED` o el veredicto NO es `READY_FOR_SLICING`: **ABORTAR**.
2. **Validar Salud:** Confirmar que `kg_integrity` sea `CLEAN`. SI es `DIRTY`, exigir resolución de GAPs previos.
3. **Consumo de SSoT:** Leer obligatoriamente `.roo/memory/project-dna.md` y la Pentagonía completa en `03_knowledge_pack/`.

### 2. 🧠 ESTRATEGIA DE SLICING (Job-Driven Architecture)
> **Directiva de Densidad:** No se fragmenta por capas técnicas (Frontend/Backend); se fragmenta por "Trabajos por Hacer" (End-to-End).

1. **Eje JTBD:** Identificar los IDs `[JTBD-XXX]` en el PRD. Cada historia debe ser una cápsula que resuelva el "Job" completo (UI + Logic + Data).
2. **Clusterización:** Crear carpetas por Épicas en `02_backlog/` siguiendo el mapeo del PRD.
3. **Filtro de Alcance:** Ignorar estrictamente cualquier requerimiento marcado como `Out of Scope` en el PRD.

### 3. 🧩 GENERACIÓN DE CÁPSULAS (DNA Injection)
1. **Instanciación:** Generar cada US en `02_backlog/[EPICA]/[US_ID].md` usando el molde `maestro-backlog.md`.
2. **Inyección P5 (Tech Armor):** Insertar snippets de código/SQL con reglas de blindaje (`TRY_CAST`, `NOLOCK`) y timeouts de 300s extraídos del DNA y Tech Specs.
3. **Inyección P3 (UX Resilience):** Mapear los 4 estados (**Idle, Loading, Error, Empty**) y sus **Semantic IDs** basándose en el DNA y Design Specs.
4. **Trazabilidad Forense:** Cada US debe poseer un `KG_NODE_ID` vinculado a su ancestro: `Seed ID -> HLR -> JTBD`.

### 4. 🛡️ QUALITY GATE & CERTIFICACIÓN (Audit)
1. **Auditoría Interna:** El agente DEBE ejecutar el molde `maestro_audit_backlog.md` sobre el 100% de las historias generadas.
2. **Validación de Terminal:** Ejecutar `python .roo/scripts/validator.py [ID_WORKSPACE]` para certificar físicamente que el ADN P3/P5 está inyectado.
3. **Veredicto:** Solo si la auditoría es `PASS`, se autoriza el paso a `PHASE_2_BACKLOG_COMPLETED`.

### 5. 🕸️ METABOLISMO DE GRAFO (Hilo de Oro)
1. **Matriz RTM:** Actualizar `02_backlog/RTM_MATRIX.md` con el linaje completo del conocimiento.
2. **Sync Visual:** Ejecutar `python .roo/scripts/extractor.py` y `graph_visualizer.py` para inyectar los nuevos nodos `[USER_STORY]` en el mapa visual.

---

# Ignite Backlog - Instructions

**ROL:** Actúas como un **Construction Engineer & Agentic Architect**. Tu prioridad es que el backlog sea "AI-Ready", proveyendo detalles físicos granulares para que el código pueda generarse sin ambigüedades.

**DIRECTIVA JTBD:** Queda terminantemente prohibido crear historias que resuelvan solo una capa técnica (ej: "Crear SP de base de datos"). La US debe ser un **Vertical Slice** que entregue valor al usuario final según el Job definido.

**DIRECTIVA DE FIDELIDAD DNA:** Tu única fuente de verdad para los estándares de código es el `.roo/memory/project-dna.md`. Debes asegurar que los **Semantic IDs** y el **Architectural Armor** se inyecten textualmente en los criterios de aceptación.

**AUDIT MANDATE:** No cierres la sesión sin haber generado el reporte de auditoría. Si el `validator.py` detecta violaciones al ADN, DEBES corregir las User Stories antes de entregar.

**[Sello de Lógica: Sentinel v6.0 — Job-Driven Slicing Skill]**
```

---

## 🧬 3. Protocolos de Metabolismo (Sincronía Tridimensional)
**Función:** Gestionan la ingesta de novedades de Negocio, Diseño y Tech.

### 📂 PATH: `.roo/commands/internal_sync.md`
```markdown
# ⚡ COMMAND: /internal_sync [ID_WORKSPACE]

**OBJETIVO:** Ejecutar el **Metabolismo de Refinamiento Interno** para integrar acuerdos de equipo, ajustes técnicos o de negocio y definiciones de dominio. El comando asegura que el **Hilo de Oro** evolucione mediante la actualización del ADN persistente, el parcheo de la Pentagonía y la validación determinista del Grafo.

---

### 1. 🛡️ PERIMETER & SOBERANÍA (Gatekeeper)
1. **Validación de Contexto:** Confirmar soberanía del Workspace leyendo `01_requirements/{{ID_WORKSPACE}}/00_meta/project_state.json`.
2. **Rol Operativo:** El agente asume el perfil de **Knowledge Engineer & Technical Architect**. Tu misión es metabolizar el refinamiento asegurando la integridad estructural del Grafo.
3. **ID de Mutación:** Asignar un ID correlativo al evento: `NODE-INT-EVO-{{YYYYMMDD}}-SERIAL`.

### 2. 🧬 DNA & 7-POINT SCAN (Genoma Mutation)
1. **DNA Persistence:** SI la definición establece un nuevo estándar técnico (P5), visual (P3) o de arquitectura, es MANDATORIO actualizar `.roo/memory/project-dna.md`.
2. **Escaneo de Pilares:** Identificar qué pilares técnicos (**PT_1 a PT_7**) se ven afectados por la decisión (Arquitectura, Datos, APIs, UI, Seguridad, etc.).
3. **Update Tech Specs:** Sincronizar las secciones correspondientes en `01_requirements/{{ID_WORKSPACE}}/03_knowledge_pack/tech_specs.md` utilizando el molde maestro.

### 3. 🔄 PENTAGONÍA REFACTOR & BLAST RADIUS
1. **Impacto en Specs:** - **Design**: Si hay cambios en la capa P2 (Semantic Mapping) o flujos visuales, actualizar `design_specs.md` y `maestro_semantic_mapping.md`.
   - **Negocio**: Si es un cambio de regla, proceso o Hito de Oro, actualizar `frd.md`, `prd.md` o `brd.md` según corresponda.
2. **Cálculo de Blast Radius:** Es MANDATORIO identificar qué User Stories en `02_backlog/` sufren desincronización y aplicar parches de alta densidad en sus criterios de aceptación.
3. **Registro Forense:** Documentar la mutación técnica en `01_requirements/{{ID_WORKSPACE}}/00_meta/backlog_evolution_report.md` utilizando el molde `maestro-evolution.md`.

### 4. 🕸️ GRAPH REFRESH & HEALTH CHECK (Terminal Mandate)
Es MANDATORIO ejecutar los motores físicos para materializar la evolución interna en el mapa visual y certificar la salud:

```bash
# Sincronización de Tripletas y Actualización del Mapa Mermaid
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Análisis de Impacto y Validación de ADN Compliance
python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{ID_EVO_SERIAL}}
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & STATE SYNC
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje el incremento en `internal_syncs` y el último ID de comando ejecutado.
2. **Veredicto de Salud:** Certificar el estado `CLEAN` tras la validación. SI se detectan violaciones al ADN P3/P5 tras el refinamiento, el veredicto debe ser `DIRTY` hasta su corrección.

---
### 📥 [CONTENIDO DEL REFINAMIENTO INTERNO]
> **[PEGAR AQUÍ: DEFINICIÓN DE BA, CAMBIO DE LAYOUT, AJUSTE TÉCNICO, NUEVO ASSET, ETC.]**

**[Sello de Lógica: Sentinel v6.0 — Persistent Internal Sync]**
**[Sync Anchor: INTERNAL_SYNC_PROTOCOL_FINAL_V6]**
```

### 📂 PATH: `.roo/commands/external_sync.md`
```markdown
# 📥 COMMAND: /external_sync [ID_WORKSPACE]

**OBJETIVO:** Ejecutar el **Metabolismo de Ingesta Externa** para procesar feedbacks, correos, mensajes de Slack o requerimientos directos del cliente. El comando actúa como el sensor de verdad externa, promoviendo semillas, cerrando GAPs y parcheando quirúrgicamente el Backlog mediante un análisis forense de impacto.

---

### 1. 🛡️ GATEKEEPER & SOBERANÍA (Perímetro)
1. **Validación de Contexto:** Confirmar soberanía del Workspace en `01_requirements/{{ID_WORKSPACE}}/00_meta/project_state.json`.
2. **Rol Operativo:** El agente actúa como **Knowledge Auditor & Censor**. Tu misión es filtrar el ruido y extraer Verdades Atómicas que alimenten el Hilo de Oro.
3. **ID de Evento:** Asignar un ID correlativo: `NODE-EXT-SYNC-{{YYYYMMDD}}-SERIAL`.

### 2. 🧬 KNOWLEDGE HARVESTING & GAP RESOLUTION
1. **Fidelidad Cuantitativa (Anti-Hallucination):** Escrutar el input buscando métricas (%, montos, tiempos). **Censura:** Si el dato es nuevo, registrarlo como `[VOLATILE]` en `00_meta/identity_seeds.md` hasta su validación técnica.
2. **GAP Solve:** SI el input resuelve una incertidumbre previa:
   - Marcar el `ID_GAP` como `CLOSED` en `00_meta/discovery_gap_report.md`.
   - Promover la semilla vinculada a `[KNOWN]` en `identity_seeds.md`.
3. **Identificación de Seeds:** Registrar cualquier nueva definición funcional o de negocio con su respectivo `ID_REF` de origen.

### 3. 🔄 PROPAGATED IMPACT & BACKLOG SURGERY
1. **Análisis de Blast Radius:** Es MANDATORIO ejecutar el motor de impacto en terminal para identificar qué Specs y User Stories quedan obsoletas tras el feedback:
   ```bash
   python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{NODE-EXT-ID}}
   ```
2. **Parcheo de Pentagonía:** Actualizar quirúrgicamente los documentos en `03_knowledge_pack/` (BRD, PRD, FRD, Tech, Design) inyectando la nueva información sin alterar el ADN base.
3. **Cirugía de US:** Aplicar parches de alta densidad en las historias de `02_backlog/` afectadas, actualizando criterios de aceptación y dependencias.
4. **Registro de Evolución:** Documentar la mutación en `00_meta/backlog_evolution_report.md`.

### 4. 🕸️ DETERMINISTIC REFRESH (Mandato de Terminal)
Es MANDATORIO ejecutar los motores físicos para materializar el feedback en el mapa visual y certificar la salud:

```bash
# Sincronización de Tripletas y Mapa Mermaid
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Validación de Integridad y DNA Compliance
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & HEALTH VERDICT
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje el incremento en `external_syncs` y el último hito procesado.
2. **Veredicto:** Tras la validación, certificar estado `CLEAN`. SI el feedback introduce contradicciones o rompe el ADN P3/P5, el veredicto debe ser `DIRTY`.

---
### 📥 [FEEDBACK / REQUERIMIENTO DEL CLIENTE]
> **[PEGAR AQUÍ EL CONTENIDO CRUDO DEL CORREO, SLACK O FEEDBACK EXTERNO]**

**[Sello de Ingesta: Sentinel v6.0 — External Knowledge Sync]**
**[Sync Anchor: EXTERNAL_SYNC_PROTOCOL_FINAL_V6]**
```

### 📂 PATH: `.roo/commands/meeting_sync.md`
```markdown
# ⚡ COMMAND: /meeting_sync [ID_WORKSPACE]

**OBJETIVO:** Ejecutar el **Metabolismo Ágil** para la ingesta inmediata de acuerdos informales, notas de voz o aclaraciones rápidas capturadas vía chat, transformándolas en mutaciones controladas del Grafo y parcheando quirúrgicamente la Pentagonía y el Backlog sin romper el Hilo de Oro.

---

### 1. 🛡️ PERIMETER & SOBERANÍA (Gatekeeper)
1. **Validación de Contexto:** Confirmar soberanía del Workspace leyendo `01_requirements/{{ID_WORKSPACE}}/00_meta/project_state.json`.
2. **Rol Operativo:** El agente asume el perfil de **Knowledge Engineer & UI Architect**. Tu misión es metabolizar el cambio sin degradar la integridad del DNA.
3. **Identificador de Mutación:** Asignar un ID correlativo al evento: `NODE-MTG-{{YYYYMMDD}}-SERIAL`.

### 2. 🧬 AGILE METABOLISM & EXTRACTION (Certeza)
1. **Digest de Acuerdo:** Instanciar o actualizar el `meeting-digest-template.md` específico en `07_meetings/{{ID_WORKSPACE}}/` para capturar el resumen ejecutivo del acuerdo.
2. **Mapeo de Decisiones:** Extraer decisiones atómicas (`NODE-DEC-XXX`) y registrarlas en `01_requirements/{{ID_WORKSPACE}}/00_meta/decision_log.md`.
3. **Mutación de Seeds:** - SI la novedad aporta una verdad atómica: Registrar en `00_meta/identity_seeds.md` como `[KNOWN]`.
   - SI contradice una semilla previa: Marcar la anterior como `[DEPRECATED]` y registrar el linaje.

### 3. 🔄 IMPACT ANALYSIS & PROPAGATED PATCHING
1. **DNA Evolution:** SI el acuerdo redefine un estándar de resiliencia (P3) o blindaje (P5), actualizar obligatoriamente `.roo/memory/project-dna.md`.
2. **Cálculo de Blast Radius:** Ejecutar el motor de impacto en terminal para identificar colisiones en la Pentagonía y el Backlog:
   ```bash
   python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{NODE-MTG-ID}}
   ```
3. **Parcheo de Artefactos:** - Actualizar quirúrgicamente las Specs afectadas en `03_knowledge_pack/` (7 Pilares / P3 States).
   - Aplicar parches de alta densidad en las User Stories de `02_backlog/` inyectando los nuevos criterios de aceptación.
4. **Registro Forense:** Documentar la mutación en `01_requirements/{{ID_WORKSPACE}}/00_meta/backlog_evolution_report.md`.

### 4. 🕸️ DETERMINISTIC REFRESH (Mandato de Terminal)
Es MANDATORIO ejecutar los motores físicos para materializar la evolución asíncrona en el mapa visual y certificar la salud:

```bash
# Sincronización de Tripletas y Actualización del Mapa Mermaid
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Validación de Integridad y DNA Compliance
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & HEALTH VERDICT
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje el incremento en `meeting_syncs` y el último ID de comando.
2. **Veredicto:** Certificar el estado `CLEAN` tras la validación. SI se detectan violaciones al ADN P3/P5 tras el parcheo, el veredicto debe ser `DIRTY` hasta su resolución.

---
### 📥 [CONTENIDO DEL ACUERDO ÁGIL]
> **[PEGAR AQUÍ LA NOTA SUELTA, EL COMENTARIO DE PASILLO O EL "DICE EL CLIENTE QUE..."]**

**[Sello de Evolución: Sentinel v6.0 — Agile Metabolism Engine]**
**[Sync Anchor: MEETING_SYNC_PROTOCOL_FINAL_V6]**
```

### 📂 PATH: `.roo/commands/sync_tech.md`
```markdown
# ⚙️ COMMAND: /sync_tech [ID_WORKSPACE]

**OBJETIVO:** Sincronizar cambios externos provenientes del dominio de Arquitectura (`02_architecture/`) al ADN del proyecto y las especificaciones técnicas sin romper el Hilo de Oro, asegurando el metabolismo del Grafo mediante ejecución determinista de terminal.

---

### 1. 🔍 DELTA ANALYSIS & DNA EVOLUTION (Discovery)
1. **Escaneo de Gobernanza:** El agente DEBE leer obligatoriamente las actualizaciones en los 5 archivos maestros de `02_architecture/`: `data_universe.md`, `repository_map.md`, `ui_system_inventory.md`, `observability_standards.md` y `testing_qa_matrix_standard.md`.
2. **Sincronía de ADN (P5 Mandate):** Modificar `.roo/memory/project-dna.md` con el nuevo estándar de **Architectural Armor (P5)** descubierto. Esto incluye cambios en el modelo de datos, contratos de API, sanitización (`TRY_CAST`), concurrencia (`NOLOCK`) o reglas de performance.
3. **Capa P2 (Abstracción):** Si el cambio técnico afecta el inventario de componentes, validar contra `02_architecture/ui_system_inventory.md` para preparar el mapeo semántico.

### 2. 🛠️ REFACTOR DE ESPECIFICACIONES (7 Pilares)
1. **Tech Specs Refactor:** Actualizar `01_requirements/[ID_WORKSPACE]/03_knowledge_pack/tech_specs.md` utilizando el molde `maestro_tech.md`.
    * **Directiva de Población:** Redistribuir la nueva información técnica dentro de los **7 Pilares de Ingeniería** (System Architecture, Functional Deep Dive, Data Model, API Contract, UI Behavior, Non-Functional, y Deployment/Ops).
    * **Agnosticismo Técnico:** Extraer las reglas de blindaje (Data Armor) y optimización directamente de la arquitectura actualizada; prohibido asumir servicios no declarados en el Vault.

### 3. 🚀 IMPACT ANALYSIS & BACKLOG PATCHING
1. **Cálculo de Blast Radius:** Es MANDATORIO identificar qué Historias de Usuario en `02_backlog/` se ven afectadas por la mutación técnica.
2. **US Patching:** Actualizar quirúrgicamente las User Stories impactadas en sus secciones de **Dominio Técnico (3.1/3.2)** y **Criterios de Aceptación**, inyectando los nuevos snippets de código P5 o reglas de validación.
3. **Evolution Report:** Registrar el linaje, la justificación técnica y el análisis de impacto en `01_requirements/[ID_WORKSPACE]/00_meta/backlog_evolution_report.md` utilizando el molde `maestro-evolution.md`.

### 4. 🕸️ METABOLISMO DE GRAFO (Mandato de Terminal)
Tras cada mutación de archivo maestro, es obligatorio abrir la terminal y ejecutar explícitamente los scripts de procesamiento para mantener el Hilo de Oro:

```bash
# Sincronización de Tripletas y Actualización del Mapa Visual
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Análisis de Impacto y Validación de ADN
python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{ID_EVO_SERIAL}}
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & HEALTH CHECK
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje la sincronización técnica exitosa.
2. **Veredicto:** El estado del proyecto debe ser certificado como `CLEAN` tras la ejecución del `validator.py`. Si se detectan huérfanos o violaciones al ADN P5, el estado permanecerá `DIRTY` hasta su corrección.

**[Sello de Sincronía: Sentinel v6.0 — Tech Sync Engine]**
**[Sync Anchor: SYNC_TECH_PROTOCOL_FINAL]**
```

---
### 📂 PATH: `.roo/commands/sync_design.md`
```markdown
# 🎨 COMMAND: /sync_design [ID_WORKSPACE]

**OBJETIVO:** Sincronización de mutaciones visuales y de interacción provenientes del dominio de Diseño (`03_design/`) hacia el ADN del proyecto y la Pentagonía, asegurando la integridad de la capa de abstracción P2 (Semantic Mapping) y la resiliencia P3 sin romper el Hilo de Oro.

---

### 1. 🔍 DELTA ANALYSIS & DNA EVOLUTION (Visual Discovery)
1. **Escaneo de Assets:** El agente DEBE listar y analizar obligatoriamente los nuevos inventarios, imágenes o flujos ubicados en `03_design/[ID_WORKSPACE]/ux/flows/` y `03_design/[ID_WORKSPACE]/ux/screens/`.
2. **Sincronía de ADN (P3 Mandate):** Modificar `.roo/memory/project-dna.md` si el estándar visual de resiliencia (P3) ha mutado. Esto incluye nuevos estados de carga, error (con visualización de `Correlation_ID`) o estados vacíos detectados en los mocks.
3. **Capa P2 (Semantic Mapping Refactor):** * Consultar `02_architecture/ui_system_inventory.md` para validar el binding semántico.
    * Actualizar obligatoriamente el archivo `01_requirements/[ID_WORKSPACE]/03_knowledge_pack/maestro_semantic_mapping.md` para registrar nuevos componentes o cambios en la abstracción entre Seeds y UI.

### 2. 🛠️ REFACTOR DE ESPECIFICACIONES (Visual Sovereignty)
1. **Design Specs Refactor:** Actualizar `01_requirements/[ID_WORKSPACE]/03_knowledge_pack/design_specs.md` basándose en el molde `maestro_design.md`.
    * **Directiva de Resiliencia:** Asegurar que cada nuevo patrón de UI documente explícitamente el **4-State Mandate** (Idle, Loading, Error, Empty) definido en el DNA.
    * **Traceability Hook:** Vincular cada cambio visual a su correspondiente `JTBD_ID` para justificar la mutación desde el valor de producto.

### 3. 🚀 IMPACT ANALYSIS & BACKLOG PATCHING
1. **Cálculo de Blast Radius:** Identificar qué Historias de Usuario en `02_backlog/` sufren desincronización visual tras la actualización del DNA o los flows.
2. **US Patching:** Actualizar quirúrgicamente las User Stories impactadas en sus secciones de **Dominio de Diseño (2.0)** y **Criterios de Aceptación**, inyectando los nuevos comportamientos P3 y IDs semánticos.
3. **Evolution Report:** Registrar la mutación, el racional del diseño y el análisis de impacto en `01_requirements/[ID_WORKSPACE]/00_meta/backlog_evolution_report.md`.

### 4. 🕸️ METABOLISMO DE GRAFO (Mandato de Terminal)
Tras cada mutación de archivo maestro o asset visual, es obligatorio abrir la terminal y ejecutar explícitamente los scripts de procesamiento para mantener la consistencia del Grafo:

```bash
# Sincronización de Tripletas y Actualización del Mapa Visual
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Análisis de Impacto y Validación de ADN (P3 Compliance)
python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{ID_EVO_SERIAL}}
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & HEALTH CHECK
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje la sincronización de diseño completada y el flag `design_vault_sync: true`.
2. **Veredicto:** El estado del proyecto debe ser certificado como `CLEAN` tras la ejecución del `validator.py`. Cualquier inconsistencia entre el Mock y la US mantendrá el estado en `DIRTY`.

**[Sello de Sincronía: Sentinel v6.0 — Design Sync Engine]**
**[Sync Anchor: SYNC_DESIGN_PROTOCOL_FINAL]**
```

---

## ⚖️ 4. Protocolos de Gobernanza y Salud
**Función:** Auditoría forense y gestión de bloqueos técnicos.

### 📂 PATH: `.roo/commands/ignite_health.md`
```markdown
# 🛡️ COMMAND: /ignite_health [ID_WORKSPACE]

**OBJETIVO:** Ejecutar una auditoría forense 360° para certificar la salud estructural, la integridad del Grafo de Conocimiento y el cumplimiento genético (P3/P5) del proyecto, actuando como el sistema inmune que bloquea el avance ante desincronizaciones o alucinaciones métricas.

---

### 1. 🛡️ GATEKEEPER & READINESS (Validación de Perímetro)
1. **Identificar Soberanía:** El agente debe validar que el `ID_WORKSPACE` proporcionado coincida con el contexto activo en `01_requirements/[ID_WORKSPACE]/00_meta/project_state.json`.
2. **Estado de Insumos:** Confirmar la existencia de la Pentagonía en `03_knowledge_pack/` y el Backlog en `02_backlog/` para iniciar el escrutinio.
3. **Rol de Auditor:** El agente asume el perfil de **Health Auditor (Gatekeeper)**, con autoridad para degradar el veredicto de fase si se detectan anomalías.

### 2. 🔍 GRAPH INTEGRITY & ORPHAN HUNT (Terminal Logic)
Es MANDATORIO abrir la terminal y ejecutar los motores de procesamiento para mapear la realidad física del proyecto:
1. **Sincronía de Grafo:** Ejecutar `python .roo/scripts/extractor.py {{ID_WORKSPACE}}` para reconstruir la matriz de adyacencia y el mapa visual Mermaid.
2. **Caza de Huérfanos:** - Identificar Seeds en `00_meta/identity_seeds.md` que no poseen aristas hacia Specs o User Stories.
   - Identificar User Stories en `02_backlog/` que no poseen un ancestro trazable hacia una Seed `[KNOWN]`.

### 3. 🧬 DNA COMPLIANCE & FIDELITY AUDIT (Censura de Alucinación)
1. **Mandato P5/P3 (DNA Audit):** Cargar obligatoriamente `.roo/memory/project-dna.md` y verificar que las reglas de blindaje (SQL Armor) y resiliencia visual (4-State Mandate) estén inyectadas textualmente en cada artefacto.
2. **Auditoría de Fidelidad Cuantitativa:** - El agente debe escrutar Specs y US buscando métricas numéricas (ROI, %, montos monetarios, tiempos).
   - **Censura de Alucinación:** Cualquier dato cuantitativo que NO figure en las `identity_seeds.md` debe reportarse como una violación crítica de integridad.

### 4. 🚥 OUTPUT & VEREDICTO DE CERTIFICACIÓN
1. **Generación de Reporte:** Instanciar el reporte final exclusivamente en la ruta soberana: `01_requirements/{{ID_WORKSPACE}}/00_meta/health_report.md` (utilizando el molde `maestro_health_report.md`).
2. **Veredicto Técnico (Terminal Check):** El veredicto final se apoya en el resultado del script de validación:
   ```bash
   python .roo/scripts/validator.py {{ID_WORKSPACE}}
   ```
3. **Actualización de Estado:** - **CLEAN:** Solo si la cobertura es 1:1, no hay alucinaciones métricas y se cumple el ADN P3/P5.
   - **DIRTY:** Si existen huérfanos, GAPs abiertos de severidad ALTA o violaciones genéticas. El proyecto queda bloqueado para la siguiente fase.

### 5. 🕸️ FINAL SYNC (Metabolismo de Grafo)
Tras la auditoría, actualizar `project_state.json` con el nuevo veredicto y refrescar el mapa visual en `00_meta/sentinel-graph-map.md` ejecutando `graph_visualizer.py`.

**[Sello de Auditoría: Sentinel v6.0 — Health & Integrity Engine]**
**[Sync Anchor: IGNITE_HEALTH_PROTOCOL_FINAL_V6]**
```

### 📂 PATH: `.roo/commands/ignite_meeting.md`

```markdown
# 👂 COMMAND: /ignite_meeting [ID_WORKSPACE] [FILE_NAME]

**OBJETIVO:** Metabolizar interacciones humanas formales (minutas, transcripciones) para extraer decisiones estructurales (`NODE-DEC-XXX`) y propagar mutaciones controladas en el Grafo de Conocimiento, asegurando la sincronía de la Pentagonía y el Backlog.

---

### 1. 📥 INGESTA & DIGESTIÓN ASINCRÓNICA
1. **Soberanía de Insumo:** Leer el archivo crudo indicado en `07_meetings/[ID_WORKSPACE]/`.
2. **Digest Humano:** Crear `07_meetings/[ID_WORKSPACE]/meeting-digest-[FECHA].md` (basado en el molde `meeting-digest-template.md`) con el resumen ejecutivo de acuerdos y participantes.

### 2. 🧬 METABOLISMO DE GRAFO (Análisis Forense)
1. **Instanciación Técnica:** Generar `01_requirements/{{ID_WORKSPACE}}/00_discovery/meeting_metabolism_[FECHA].md` utilizando el molde `meeting_metabolism_template.md`.
2. **Detección de Nodos:** Extraer decisiones atómicas asignándoles identificadores `NODE-DEC-XXX` vinculados a la sesión.
3. **GAP Resolution:** Si el acuerdo cierra una incertidumbre previa, es MANDATORIO actualizar el estado a `CLOSED` en `01_requirements/{{ID_WORKSPACE}}/00_meta/discovery_gap_report.md`.

### 3. 🔄 PROPAGACIÓN DE IMPACTO & EVOLUCIÓN
1. **DNA Persistence:** Si la reunión redefine un estándar (P3/P5), actualizar obligatoriamente `.roo/memory/project-dna.md`.
2. **Evolution Registry:** Registrar la mutación técnica y funcional en `01_requirements/{{ID_WORKSPACE}}/00_meta/backlog_evolution_report.md` utilizando el molde `maestro-evolution.md`.
3. **Cirugía de Backlog:** Si el proyecto superó la Fase 1, identificar mediante el motor de impacto qué Historias de Usuario requieren parcheo o refactorización quirúrgica.

### 4. 🕸️ ACTUALIZACIÓN DETERMINISTA (Mandato de Terminal)
Tras procesar la reunión, es MANDATORIO abrir la terminal y ejecutar los motores para materializar la evolución en el mapa visual y certificar la salud:

```bash
# Sincronización de Tripletas y Actualización del Mapa Visual
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Análisis de Impacto y Validación de ADN
python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{MEETING_ID}}
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & HEALTH CHECK
1. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje el hito de la reunión procesada y el estado de sincronía del metabolismo.
2. **Veredicto:** El estado del proyecto debe ser re-certificado tras la ejecución del `validator.py` para asegurar que las nuevas decisiones no introdujeron inconsistencias `DIRTY`.

**[Sello de Evolución: Sentinel v6.0 — Meeting Metabolism Engine]**
**[Sync Anchor: IGNITE_MEETING_PROTOCOL_FINAL_V6]**
```

### 📂 PATH: `.roo/commands/internal_gap.md`
```markdown
# ⚡ COMANDO: INTERNAL GAPS & KG BLOCKERS (v6.0 Roo)

- **WORKSPACE_ID:** {{ID_WORKSPACE}}
- **Propósito:** Registro de incertidumbre, dudas técnicas o riesgos que bloquean el flujo.
- **Status de Sistema:** `KG_INTEGRITY: DIRTY`.
- **ID Sugerido:** `NODE-GAP-{{YYYYMMDD}}-SERIAL`.

---

### 🛠️ PROTOCOLO DE REFINAMIENTO Y BLOQUEO:
Actúa como **Knowledge Engineer** aplicando el protocolo de interrupción de Sentinel:

1. **Validación de Ámbito**: Lee `01_requirements/{{ID_WORKSPACE}}/00_meta/project_state.json` para confirmar que el Workspace coincide con el contexto activo antes de aplicar el bloqueo.
2. **Degradación de Certeza**: Localizar las Seeds afectadas en `01_requirements/{{ID_WORKSPACE}}/00_meta/identity_seeds.md` y cambiar su estado a `[VOLATILE]`.
3. **Inyección de Bloqueo**: 
   - Registrar detalladamente el GAP en `01_requirements/{{ID_WORKSPACE}}/00_meta/maestro_discovery_gap.md`.
   - Si la severidad es **ALTA**, cambiar obligatoriamente el `verdict` a `DIRTY` en el `project_state.json` del workspace.
4. **Visualización y Sincronía**: 
   - Ejecutar `python .roo/scripts/extractor.py {{ID_WORKSPACE}}` para mapear el nodo de incertidumbre.
   - Ejecutar `python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}` para mostrar visualmente el bloqueo en el flujo.

---

### 📥 [GAPS, DUDAS TÉCNICAS O RIESGOS DETECTADOS]
> **[PEGAR AQUÍ LA INCERTIDUMBRE DETECTADA POR EL EQUIPO O EL AGENTE]**

**[Sello de Alerta: Sentinel v6.0 — Knowledge Interruption]**
```

### 📂 PATH: `.roo/commands/ignite_gap_solve.md`
```markdown
# 🎯 COMMAND: /ignite_gap_solve [ID_GAP]

**OBJETIVO:** Resolver formalmente un bloqueo de conocimiento o incertidumbre detectada en la Fase 0 (Discovery) y propagar la nueva certeza ("Verdad Atómica") a través de toda la cadena de valor (Seeds -> Pentagonía -> Backlog), asegurando el metabolismo del Grafo y la actualización del estado de salud del proyecto.

---

### 1. 🔍 GAP TARGETING & SSSOT ALIGNMENT
1. **Carga de Contexto:** El agente DEBE leer obligatoriamente el archivo instanciado: `01_requirements/{{ID_WORKSPACE}}/00_meta/discovery_gap_report.md` (No confundir con el molde maestro).
2. **Validación de Objetivo:** Confirmar la existencia del `ID_GAP` proporcionado y certificar que su estado sea `OPEN (BLOCKING)`.
3. **Identificación de Semilla:** Localizar la semilla vinculada en estado `[VOLATILE]` o `[GAP/PENDING]` dentro de `00_meta/identity_seeds.md`.

### 2. 🧬 KNOWLEDGE MUTATION (Cierre de Incertidumbre)
1. **Promoción de Semilla:** Cambiar el estado de la semilla vinculada de `[VOLATILE]` a `[KNOWN]` en `identity_seeds.md`. Actualizar el `ID_REF` de origen con la referencia de la resolución (Minuta, Email o Acuerdo Técnico).
2. **Clausura Forense:** Marcar el GAP como `CLOSED` en `discovery_gap_report.md` y documentar el racional técnico de la resolución en la sección de **Audit Trail**.
3. **Registro de Evolución:** Registrar el evento de resolución en `00_meta/backlog_evolution_report.md` (utilizando el molde `maestro-evolution.md`) para documentar la mutación del Grafo.

### 3. 🔄 PROPAGATED METABOLISM & BLAST RADIUS
1. **Análisis de Impacto:** Si el proyecto se encuentra en Fase 1 o superior, ejecutar obligatoriamente el motor de impacto en terminal para identificar Specs y User Stories desincronizadas:
   ```bash
   python .roo/scripts/impact_analyzer.py {{ID_WORKSPACE}} {{ID_GAP}}
   ```
2. **Refactor de Pentagonía:** Actualizar quirúrgicamente los documentos de la Pentagonía (`brd.md`, `prd.md`, `frd.md`, `tech_specs.md`, `design_specs.md`) afectados por la nueva certeza, manteniendo el linaje del Hilo de Oro.
3. **Parcheo de Backlog:** Sincronizar las User Stories en `02_backlog/` inyectando los nuevos requerimientos funcionales o restricciones técnicas (P5/P3) derivadas de la resolución.

### 4. 🕸️ GRAPH REFRESH & HEALTH GATE (Terminal Mandate)
Es MANDATORIO ejecutar los motores deterministas tras la resolución para materializar el cambio en el mapa visual y certificar la salud:

```bash
# Reconstrucción de la matriz de adyacencia y mapa Mermaid
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/graph_visualizer.py {{ID_WORKSPACE}}

# Validación final de integridad y DNA
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

### 5. ✅ COMPLETION & STATE TRANSITION
1. **Health Check Integration:** SI tras la resolución el conteo de `active_gaps` en `project_state.json` llega a 0 y el `validator.py` emite un resultado exitoso, el agente DEBE cambiar el veredicto de `DIRTY` a `CLEAN`.
2. **Sync Anchor:** El agente debe asegurar que el `project_state.json` refleje la última mutación y el cierre del hito de resolución.

**[Sello de Resolución: Sentinel v6.0 — Gap Solver Engine]**
**[Sync Anchor: GAP_SOLVE_PROTOCOL_FINAL_V6]**
```