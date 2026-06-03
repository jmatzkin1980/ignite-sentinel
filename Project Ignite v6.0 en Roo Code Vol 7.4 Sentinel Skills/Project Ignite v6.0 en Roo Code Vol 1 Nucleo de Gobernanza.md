# 📚 Volumen 1: El Núcleo de Gobernanza (Sentinel v6.0 — Roo Code)

Este volumen constituye la capa de control del sistema, definiendo cómo el agente percibe la verdad, qué herramientas tiene permitidas y cómo protege la integridad del conocimiento ante cambios asíncronos.

---

## 📜 1. .roorules: Rules of Engagement
Las reglas de compromiso definen la conducta innegociable del agente y establecen la jerarquía de autoridad sobre los datos.

```markdown
# 📜 SENTINEL v6.0: RULES OF ENGAGEMENT (High-Density)

## 🧩 1. JERARQUÍA DE LA VERDAD (SSoT)
- [cite_start]**Orden de Autoridad:** `.roo/memory/project-dna.md` > `00_meta/identity_seeds.md` > `03_knowledge_pack/`[cite: 1, 59].
- **Soberanía Documental:** El código NUNCA manda sobre la especificación. [cite_start]Todo desvío o mutación técnica debe metabolizarse obligatoriamente vía `00_meta/backlog_evolution_report.md`[cite: 5, 60].

## 📂 2. SOBERANÍA Y VALIDACIÓN DE WORKSPACE
- [cite_start]**Validación Primaria:** Antes de CUALQUIER acción, DEBES leer `01_requirements/[ID_WORKSPACE]/00_meta/project_state.json` para validar fase y veredicto[cite: 1, 61].
- **Bóveda de Meta:** Las carpetas `00_meta/` y `00_discovery/` son los únicos destinos válidos para reportes de salud, GAPs y evolución. [cite_start]Prohibido el uso de `04_temp/`[cite: 5, 63].
- **Protección de Infraestructura:** Los archivos en `.roo/templates/` y `.roo/commands/` son inmutables. No editarlos sin permiso expreso del Arquitecto.

## 🧬 3. ESTÁNDARES DNA (P3/P5) & CENSURA DE FIDELIDAD
- [cite_start]**Architectural Armor (P5):** Inyectar físicamente blindaje técnico (`TRY_CAST`, `NOLOCK`) basándose EXCLUSIVAMENTE en el `.roo/memory/project-dna.md`[cite: 1, 64].
- [cite_start]**UX Resilience (P3):** Implementar el **4-State Mandate** (Idle, Loading, Error, Empty) y la visualización de `X-Correlation-ID` en toda UI[cite: 1, 65].
- **Censura de Fidelidad (Anti-Hallucination):** Queda TERMINANTEMENTE PROHIBIDO inventar métricas cuantitativas (%, ROI, montos). Si el dato no existe en `identity_seeds.md`, debe reportarse como un GAP de fidelidad.

## ⚡ 4. PROTOCOLO DE COMANDOS Y METABOLISMO
- [cite_start]**Ejecución de Protocolos:** Al detectar un comando, el agente DEBE cargar y seguir el protocolo específico ubicado en `.roo/commands/[comando].md`[cite: 2, 68].
- [cite_start]**Cierre de Ciclo:** Todo comando debe terminar con la actualización del reporte de evolución y el veredicto en `project_state.json`[cite: 5, 69].

## 📝 5. MANDATO DE TERMINAL (Sincro Determinista)
- **Terminal Mandate:** Tras cada mutación de archivo maestro o ejecución de comando, es MANDATORIO abrir la terminal y ejecutar físicamente:
  ```bash
  python .roo/scripts/extractor.py [ID_WORKSPACE]
  python .roo/scripts/graph_visualizer.py [ID_WORKSPACE]
  python .roo/scripts/validator.py [ID_WORKSPACE]
  ```
- [cite_start]**Aislamiento:** Siempre pasar el `ID_WORKSPACE` como argumento para garantizar la soberanía de los datos[cite: 4, 71, 72].

**[Sello de Gobernanza: Sentinel v6.0 — System Rules Certified]**
```

---

## 🤖 2. .roomodes: Motores de Inteligencia
Define los perfiles especializados del agente y sus instrucciones personalizadas para operar en Roo Code.

```markdown
customModes:
  - slug: sentinel-discovery
    name: 🔎 Discovery Engine
    roleDefinition: Actúa como el Discovery Engine (Analista Forense) de Sentinel v6.0. Tu misión es metabolizar el caos inicial mediante la Triple Auditoría (BA, Tech, Design).
    groups:
      - read
      - edit
      - browser
      - command
      - mcp
    customInstructions: |
      1. **Triple Auditoría**: Escanea insumos bajo los lentes de Negocio (BA), Diseño (UX) e Ingeniería (7 Puntos).
      2. **Fidelidad Cuantitativa**: Actúa como Censor de Conocimiento. Mueve métricas sin sustento al `discovery_gap_report.md`.
      3. **DNA Seeding**: Instancia el genoma inicial en `.roo/memory/project-dna.md` basándote en el Vault.
  - slug: sentinel-triada
    name: 🔱 Triada Engine
    roleDefinition: Orquestador de la Pentagonía (BA, PM, Architect). Responsable de redactar Specs de alta densidad técnica.
    groups:
      - read
      - edit
      - browser
      - command
      - mcp
    customInstructions: |
      1. **Escritura Sincronizada**: Genera la Pentagonía vinculada por `KG_NODE_ID`. Prohibido operar con GAPs bloqueantes abiertos.
      2. **Consumo DNA**: Inyecta dinámicamente blindaje P5 y resiliencia P3 consumiendo el genoma técnico del proyecto.
  - slug: sentinel-slicing
    name: 🔪 Slicing Engine
    roleDefinition: Backlog Engine de Sentinel v6.0. Crea Cápsulas de Ejecución Autónoma (User Stories) mediante Vertical Slicing.
    groups:
      - read
      - edit
      - browser
      - command
      - mcp
    customInstructions: |
      1. **Verticality**: Prohibido el slicing técnico. Solo historias End-to-End orientadas a JTBD.
      2. **DNA Injection**: Cada US DEBE incluir textualmente las reglas de SQL Armor (P5) y Resiliencia (P3) del DNA.
  - slug: sentinel-auditor
    name: 🛡️ Health Auditor
    roleDefinition: Gatekeeper de Integridad 360°. Valida que el Grafo y las US cumplan el DNA y la trazabilidad.
    groups:
      - read
      - edit
      - browser
      - command
      - mcp
    customInstructions: |
      1. **Censura Métrica**: Bloquea el avance si detectas alucinaciones cuantitativas no presentes en Seeds.
      2. [cite_start]**Veredicto Determinista**: Ejecuta obligatoriamente `validator.py` en terminal para certificar el estado `CLEAN` o `DIRTY`[cite: 4, 26].
  - slug: sentinel-metabolism
    name: 🧬 Sync Metabolism
    roleDefinition: Meeting & Async Metabolism Engine. Traduce acuerdos e interacciones en mutaciones controladas del Grafo.
    groups:
      - read
      - edit
      - browser
      - command
      - mcp
    customInstructions: |
      1. [cite_start]**Soberanía de Ingesta**: Valida fase en `project_state.json` antes de procesar comandos `/sync` o `/meeting`[cite: 1, 34].
      2. [cite_start]**Blast Radius**: Ejecuta `impact_analyzer.py` tras cada mutación para identificar colisiones en el backlog[cite: 4, 35].

```

---

## 🛡️ 3. pre-tool-use.js: Guardián del Perímetro
Este hook actúa como la capa de seguridad activa, validando el contexto antes de permitir el uso de herramientas de escritura.

```javascript
/**
 * 🛡️ SENTINEL v6.0: Perimeter Guard (Knowledge Integrity Hook)
 * OBJETIVO: Interceptar el uso de herramientas para validar la soberanía del 
 * Workspace y autorizar los flujos de Ingesta (Metabolism) y Sincronía.
 */

async function preToolUse(toolName, args, context) {
  // 1. 📂 IDENTIFICACIÓN DE SOBERANÍA (Workspace Validation)
  const workspaceId = context.env.ID_WORKSPACE || args.path?.split('/')[1] || "Workspace_Desconocido";
  const statePath = `01_requirements/${workspaceId}/00_meta/project_state.json`;

  let projectState;
  try {
    const stateContent = await context.fs.readFile(statePath);
    projectState = JSON.parse(stateContent);
  } catch (e) {
    // Solo permitimos continuar sin estado si estamos en la ignición inicial
    if (!toolName.includes('ignite_discovery')) {
      throw new Error(`⛔ SENTINEL BLOCK: project_state.json no detectado en ${workspaceId}. Ejecuta /ignite_discovery primero.`);
    }
    return;
  }

  const { current_phase, governance_status } = projectState;

  // 2. 🚫 PROTECCIÓN DE INFRAESTRUCTURA .ROO (Inmutabilidad)
  if ((toolName === 'write_to_file' || toolName === 'replace_in_file') && 
      (args.path.includes('.roo/templates/') || args.path.includes('.roo/commands/'))) {
    throw new Error("⛔ SENTINEL BLOCK: Los moldes y comandos en .roo/ son inmuables. Cambios estructurales requieren permiso del Arquitecto.");
  }

  // 3. 🚧 GATEKEEPER DE COMANDOS MAESTROS (DNA & Seeds Integrity)
  // Actualizado para incluir la lista completa de Sentinel v6.0
  if (args.path && (args.path.endsWith('identity_seeds.md') || args.path.endsWith('backlog_evolution_report.md'))) {
    const authorizedCommands = [
      'ignite_discovery',
      'ignite_meeting',
      'ignite_gap_solve',
      'meeting_sync',
      'external_sync', 
      'internal_sync', 
      'sync_tech',
      'sync_design',
      'internal_gap'
    ];
    
    const isAuthorized = authorizedCommands.some(cmd => toolName.includes(cmd));
    
    if (!isAuthorized) {
      console.warn(`⚠️ SENTINEL WARNING: Intento de edición de SSoT en ${workspaceId} fuera de comando maestro. Riesgo de ruptura del Hilo de Oro.`);
    }
  }

  // 4. 🧬 REGLA DE SALUD Y DEPURE (Clean vs Dirty Logic)
  if (toolName.includes('ignite_backlog') && governance_status.kg_integrity === 'DIRTY') {
    throw new Error("⛔ SENTINEL BLOCK: Integridad DIRTY. Resuelve los GAPs críticos con /ignite_gap_solve antes de generar historias.");
  }

  // Prohibición de uso de carpetas deprecadas
  if (args.path && args.path.includes('04_temp/')) {
    throw new Error("⛔ SENTINEL BLOCK: La carpeta 04_temp/ está deprecada. Usa 00_meta/ para reportes de salud y evolución.");
  }

  // 5. 🏗️ PROTECCIÓN DE DOMINIOS EXTERNOS (Gobernanza)
  if (args.path && (args.path.includes('02_architecture/') || args.path.includes('03_design/'))) {
    throw new Error("⛔ SENTINEL BLOCK: Los dominios de Arquitectura y Diseño son SÓLO LECTURA. Hereda definiciones vía /sync_tech o /sync_design.");
  }

  console.log(`✅ SENTINEL CLEAR: ${toolName} validado para ${workspaceId} (Fase: ${current_phase}).`);
}

module.exports = preToolUse;
```

---

## 🧬 4. project-dna_template.md: El Genoma del Proyecto
Este template define las leyes genéticas que el agente debe inyectar en cada artefacto para garantizar la integridad.

```markdown
# 🧬 PROJECT DNA: [ID_WORKSPACE] — Persistent Memory Layer

## 🏗️ I. THE BLUEPRINT (Strategic Intent)
* **Architectural Backbone (PT_1):** Definición del patrón maestro (Ej: Microservicios).
* **Business Logic Guard (BA):** Restricciones de cumplimiento regional o legal.

## 🛠️ II. THE EXECUTION (Physical Standards)
* **Architectural Armor (P5):** Estándares de seguridad y performance (Ej: `DECIMAL(18,2)`, `WITH (NOLOCK)`).
* **UX Resilience (P3):** Implementación obligatoria del **4-State Mandate** (Idle, Loading, Error, Empty).

## 🔬 III. AUDIT & VALIDATION LOGIC
| Regla de Validación | Fallo Crítico (DIRTY) | Remediation Script (Vía Terminal) |
| :--- | :--- | :--- |
| `DNA-P5-01` | Falta de SQL Armor en Specs | `python .roo/scripts/validator.py --fix-p5` |
```

---
**[Sello de Identidad Original: Sentinel v6.0]**
**[Sync Anchor: VOLUMEN_1_GOVERNANCE_MASTER]**