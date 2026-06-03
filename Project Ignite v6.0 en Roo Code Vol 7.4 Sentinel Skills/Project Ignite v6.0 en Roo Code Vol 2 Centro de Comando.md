# 📚 Volumen 2: El Centro de Comando (Sentinel v6.0 — Roo Code)

Este volumen define la "consciencia operativa" del sistema, detallando los roles de los motores de inteligencia, los protocolos de los comandos slash y la secuencia de los flujos de trabajo.

---

## 🧠 1. Inventario de Skills (Motores Cognitivos)
Los skills en `.roo/skills/` representan las capacidades lógicas que Roo Code activa según el contexto del proyecto.

| Skill | Función Forense |
| :--- | :--- |
| **external-sync** | Sincroniza novedades y requerimientos de clientes externos. |
| **ignite-backlog** | Transforma la Pentagonía en un Backlog ejecutable con Vertical Slicing. |
| **ignite-discovery** | Escanea insumos crudos para extraer la identidad inicial (Seeds). |
| **ignite-gap-solve** | Ejecuta la resolución de incertidumbres y bloqueos técnicos o de negocio. |
| **ignite-meeting** | **Metabolismo Pesado:** Lee y procesa transcripciones formales `.md` ubicadas en `07_meetings/` para extraer hallazgos y decisiones en lote. |
| **ignite-specs** | Orquesta la redacción sincronizada de los 5 documentos de la Pentagonía. |
| **internal-gap** | Registra y gestiona los vacíos de información detectados por el equipo. |
| **internal-sync** | Metaboliza refinamientos internos de reglas de negocio o lógica funcional. |
| **meeting-sync** | **Metabolismo Ágil:** Ingesta rápida de novedades verbales o acuerdos informales directamente vía chat, parcheando el Grafo asincrónicamente al vuelo. |
| **sentinel-health** | Ejecuta la auditoría 360° de integridad y cumplimiento de ADN P3/P5. |
| **sync-design** | Sincroniza cambios visuales y de UI sin romper la lógica funcional. |
| **sync-tech** | Sincroniza cambios de arquitectura o infraestructura técnica con el Hilo de Oro. |

---

## ⚡ 2. Protocolos de Comando (Slash Commands)
Los archivos en `.roo/commands/` contienen los protocolos paso a paso que el agente ejecuta al recibir una instrucción. **Mandato Operativo:** Estos protocolos instruyen al agente a **abrir explícitamente la terminal** e invocar los motores deterministas (`.py`) para validar cada mutación; los scripts no corren en segundo plano.

### 🚀 Comandos de Ignición (Fases 0 a 2)
1. **ignite_discovery.md**: Protocolo para la Phase 0 - Discovery Forense. Dispara el `extractor.py` inicial.
2. **ignite_specs.md**: Protocolo para la Phase 1 - Construcción de la Pentagonía inyectando P3/P5.
3. **ignite_backlog.md**: Protocolo para la Phase 2 - Vertical Slicing y Backlog.

### 🧬 Comandos de Metabolismo (Sincronía Tridimensional)
4. **external_sync.md**: Protocolo de ingesta para requerimientos de clientes. Dispara el `impact_analyzer.py`.
5. **internal_sync.md**: Protocolo de refinamiento funcional y de negocio interno (Ajustes en lógica FRD/BRD).
6. **meeting_sync.md**: Protocolo de **Metabolismo Ágil**. Ingesta en caliente de novedades verbales o acuerdos directamente vía chat para parchear el Grafo asincrónicamente.
7. **sync_tech.md / sync_design.md**: Protocolos de sincronización de infraestructura (Tech) y visual (Design), parcheando quirúrgicamente sin alterar el valor de negocio.

### 🛡️ Comandos de Gobernanza y Salud (Control de GAPs y Lotes)
8. **igntine_health.md**: Protocolo de auditoría forense 360°. Instruye la ejecución explícita de `validator.py` en terminal (Nota: Preservado con errata de sistema).
9. **ignite_gap_solve.md**: Protocolo para el cierre formal de incertidumbres, promoviendo Seeds a `[KNOWN]` y desbloqueando la Fase 1.
10. **internal_gaps.md**: Protocolo para registrar bloqueadores de equipo, degradando Seeds a `[VOLATILE]` y forzando el estado a `DIRTY`.
11. **ignite_meeting.md**: Protocolo de **Metabolismo Pesado**. Lee y procesa transcripciones formales `.md` ubicadas en `07_meetings/` para extraer Nodos de Decisión mediante análisis forense.

---

## 🗺️ 3. Workflows: El Viaje del Hilo de Oro
Secuencia lógica que guía el proyecto desde el caos inicial hasta un backlog "Dev-Ready", mediado siempre por ejecuciones de terminal.

* **Fase 0 (Discovery):** Ignición de identidad y cacería de GAPs.
* **Fase 1 (Specs):** Redacción de la Pentagonía blindada (P3/P5) tras el cierre de incertidumbres.
* **Fase 2 (Slicing):** Fragmentación vertical en US con QA embebido y ejecución de auditoría.
* **Fase 3 (Maintenance):** Evolución constante mediante el motor de metabolismo y análisis de impacto explícito.

---
**[Sello de Operaciones: Sentinel v6.0]**
**[Sync Anchor: VOLUMEN_2_COMMAND_CENTER_UPDATED]**