# 📚 Volumen 4: El Cerebro del Grafo (Sentinel v6.0 — Roo Code)

Este volumen documenta la lógica algorítmica y los scripts de Python que transforman la documentación estática en un Grafo de Conocimiento vivo, permitiendo auditorías de integridad y análisis de impacto en tiempo real.

---

## ⚙️ 1. Motores de Procesamiento (The Scripts)
Localizados en `.roo/scripts/`, estos motores **no corren en segundo plano**. Son ejecutados explícitamente en la terminal por el agente, siguiendo las instrucciones de los comandos maestros para validar la soberanía y la salud del proyecto.

### 🧬 extractor.py (Knowledge Parser)
* **Objetivo:** Escanear el Workspace buscando tags de identidad y relaciones.
* **Lógica:** Utiliza RegEx para identificar `KG_NODE_ID: NODE-XXX`, `SEED_REF: <<SEED-XX>>` e `ID_REF`.
* **Output:** Construye la matriz de adyacencia (nodos y aristas) que alimenta al resto de los motores.

### 🛡️ validator.py (Integrity Auditor)
* **Regla de Oro:** Valida que toda User Story en `02_backlog/` tenga un camino trazable hacia al menos una `Identity Seed`.
* **Cumplimiento DNA:** Verifica físicamente la presencia de blindaje **SQL Armor P5** (`WITH (NOLOCK)`, `TRY_CAST`) y **Resiliencia P3** (4-State Mandate).
* **Veredicto:** Calcula el % de integridad para emitir el estado `CLEAN` o `DIRTY` en el `ignite_health_report.md`.

### 💥 impact_analyzer.py (Mutation Engine)
* **Objetivo:** Ante una mutación (Reunión o Cambio Externo), calcular el "Blast Radius".
* **Lógica:** Identifica qué artefactos del Backlog quedan desincronizados cuando una Semilla cambia de estado a `[VOLATILE]`.
* **Output:** Genera la data para el `backlog_evolution_report.md`.

### 🕸️ graph_visualizer.py (Mermaid Architect)
* **Objetivo:** Traducir la complejidad del Grafo a un mapa visual legible por humanos.
* **Lógica:** Genera diagramas Mermaid categorizando nodos por capas: Seeds (Azul), Specs (Naranja) y Backlog (Verde).

---

## 🔬 2. Lógica de Auditoría y Veredictos
El cerebro del sistema utiliza tres niveles de validación para certificar la salud del proyecto:

1.  **Integridad Estructural:** ¿Existen nodos huérfanos o Seeds sin cobertura en las Specs?.
2.  **Cumplimiento de ADN:** ¿El código y las especificaciones técnicas respetan las leyes del `project-dna.md`?.
3.  **Sincronía Forense:** ¿Cada cambio en el Grafo tiene un `ID_REF` vinculado a un evento de evolución?.

---

## 🛠️ 3. Ejecución por Parámetro (Mandato de Terminal)
Para operar en Roo Code, el agente tiene la **directiva innegociable de abrir la terminal** y ejecutar estos scripts pasando el `ID_WORKSPACE` como argumento mandatorio. Esto asegura el aislamiento absoluto de los datos y materializa la acción del metabolismo.

```bash
# Ejemplo de invocación mandatoria en la terminal del sistema
python .roo/scripts/extractor.py {{ID_WORKSPACE}}
python .roo/scripts/validator.py {{ID_WORKSPACE}}
```

---
**[Sello de Inteligencia: Sentinel v6.0 — Deterministic Logic]**
**[Sync Anchor: VOLUMEN_4_GRAPH_BRAIN_FINAL]**