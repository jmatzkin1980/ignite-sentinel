# 📚 Volumen 5: El Registro de Producción (Sentinel v6.0 — Roo Code)

Este volumen documenta la salida física total de Sentinel v6.0, incluyendo los artefactos del Workspace y los archivos de configuración de la gema. [cite_start]Todo output está anclado al Grafo de Conocimiento mediante un `KG_NODE_ID` único[cite: 66].

---

## 🧠 1. Carpeta .roo/ (System Memory & Config)
Archivos que rigen el comportamiento del agente y la persistencia de estándares.

* **memory/project-dna.md**: El genoma instanciado. [cite_start]Contiene las leyes P3/P5 activas que el auditor usa para certificar el estado `CLEAN`[cite: 59].
* [cite_start]**custom_modes.json / mcp.json**: Configuración de los motores de inteligencia y herramientas MCP para la soberanía del workspace[cite: 1].
* [cite_start]**pre-tool-use.js**: Hook de seguridad activo que valida la fase y protege el perímetro ante intentos de edición fuera de comandos maestros[cite: 1].

## 🏗️ 2. Carpeta 00_meta (Intelligence Core - Bóveda de Meta)
El centro de control soberano del proyecto. [cite_start]Esta carpeta es el único destino válido para reportes de estado y salud[cite: 63].

* [cite_start]**identity_seeds.md**: Átomos de verdad validados (`<<SEED-XX>>`) con linaje de origen[cite: 59].
* **project_state.json**: Máquina de estados operativa. [cite_start]Define la fase, el veredicto de salud y las métricas de metabolismo[cite: 61, 69].
* **backlog_evolution_report.md**: SSoT unificada de mutaciones. [cite_start]Registra el impacto de cambios externos e internos en el backlog[cite: 60, 69].
* **health_report.md / .json**: Veredictos de salud (humano y sistema) generados por el motor `validator.py`.
* [cite_start]**decision_log.md**: Registro histórico de justificaciones técnicas o de negocio (`NODE-DEC-XXX`)[cite: 3].
* [cite_start]**sentinel-graph-map.md**: Mapa visual Mermaid del "Hilo de Oro" actualizado por terminal[cite: 71].
* [cite_start]**maestro_discovery_gap.md**: Inventario activo de incertidumbres y riesgos detectados[cite: 5].

## 🔍 3. Carpeta 00_discovery (Forensic Diary)
Registros de la Fase 0 y el metabolismo de interacciones humanas.

* **discovery_log.md**: Registro de hallazgos mediante la triple auditoría (BA, Tech, Design).
* **discovery_gap_report.md**: Análisis de vacíos de información instanciado para el workspace.
* [cite_start]**meeting_metabolism_[FECHA].md**: Análisis técnico de reuniones y captura de decisiones estructurales[cite: 27].

## 🔱 4. Carpeta 03_knowledge_pack (The Pentagonia)
Planos de ingeniería de alta densidad sincronizados.

* [cite_start]**brd.md, prd.md, frd.md, tech_specs.md, design_specs.md**: Los 5 pilares de la verdad inyectados con el ADN P3/P5[cite: 59, 64].

## 🔪 5. Carpeta 02_backlog (Execution Layer)
Salidas de la Phase 2: Unidades de trabajo ejecutables "AI-Ready".

* **RTM_MATRIX.md**: Matriz de trazabilidad bidireccional requerimiento-código.
* [cite_start]**[EPICA]/[US-XXX].md**: User Stories con inyección textual de blindaje SQL Armor (P5) y resiliencia visual (P3)[cite: 65].
* **00_critical_path/CP-XX.md**: Ruta mínima de valor funcional identificada mediante Vertical Slicing.

---
**[Sello de Producción: Sentinel v6.0 — 100% Coverage]**
**[Sync Anchor: VOLUMEN_5_OUTPUT_LEDGER_FINAL_V6]**