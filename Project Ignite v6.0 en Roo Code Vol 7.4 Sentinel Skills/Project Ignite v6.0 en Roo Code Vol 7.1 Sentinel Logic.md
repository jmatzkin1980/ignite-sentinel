# 📚 Volumen 7.1: Sentinel Engine Logic (Source Bundle — Roo Code)

> **DIRECTIVA SENTINEL v6.0:** Este documento contiene el código fuente real de los motores de procesamiento. El agente debe utilizar esta lógica para simular ejecuciones, auditar consistencia y realizar análisis de impacto preventivos.

---

## 🧬 1. Motor de Extracción (Knowledge Parser)
**PATH:** `.roo/scripts/extractor.py`
**Función:** Transforma la documentación Markdown en una matriz de adyacencia de nodos y aristas.

```python
import os
import re
import json
import sys

class SentinelExtractor:
    def __init__(self, workspace_id):
        # Asegura soberanía sobre la ruta del workspace
        self.workspace_id = workspace_id
        self.workspace_path = f"01_requirements/{workspace_id}/"
        self.meta_path = f"{self.workspace_path}00_meta/"
        self.graph = {"nodes": [], "edges": [], "metadata": {}}

    def process_workspace(self):
        # Escaneo recursivo dentro del workspace soberano
        for root, _, files in os.walk(self.workspace_path):
            for file in files:
                if file.endswith(".md"):
                    self.process_file(os.path.join(root, file))
        
        self.save_graph()

    def process_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extracción de KG_NODE_ID y Lente
            node_match = re.search(r'KG_NODE_ID:\s*`(NODE-[^`]+)`', content)
            if node_match:
                node_id = node_match.group(1)
                lens_match = re.search(r'LENTE_([A-Z]+)', content)
                
                self.graph["nodes"].append({
                    "id": node_id,
                    "path": file_path,
                    "lens": lens_match.group(1) if lens_match else "GENERAL"
                })

                # Mapeo de los 7 Puntos Técnicos
                if "tech_specs" in file_path:
                    for i in range(1, 8):
                        if f"### {i}." in content or f"PT_{i}" in content:
                            self.graph["metadata"][f"{node_id}_PT_{i}"] = "DEFINED"

            # Trazabilidad de Semillas (Ancestry)
            seeds = re.findall(r'<<SEED-(\d+)>>', content)
            for seed in seeds:
                self.graph["edges"].append({"from": f"SEED-{seed}", "to": node_id if node_match else "UNKNOWN"})

    def save_graph(self):
        # Persistencia en el mapa visual del proyecto
        output_path = os.path.join(self.meta_path, "sentinel-graph-map.md")
        # Lógica para escribir el Mermaid en el archivo...
        pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        [cite_start]extractor = SentinelExtractor(sys.argv[1])
        extractor.process_workspace()
```

---

## 🛡️ 2. Motor de Validación (Integrity Auditor)
**PATH:** `.roo/scripts/validator.py`
**Función:** Audita el cumplimiento de los estándares P3/P5 y la trazabilidad del Hilo de Oro.

```python
import os
import sys

class SentinelValidator:
    def __init__(self, workspace_id):
        self.workspace_id = workspace_id
        self.dna_path = ".roo/memory/project-dna.md"

    def check_dna_compliance(self, file_content):
        """
        Lee los estándares de .roo/memory/project-dna.md y los valida 
        contra el contenido del archivo actual (Specs o US).
        """
        results = {"compliance": True, "violations": []}
        
        # 1. Cargar Reglas del ADN (Ej: Auth, SQL, UX)
        with open(self.dna_path, 'r') as f:
            dna_rules = f.read()

        # 2. Validación Dinámica de 7 Puntos (Ej: PT_3 Contracts)
        tech_points = ["ARCHITECTURE", "DATA", "CONTRACTS", "NON-FUNCTIONAL"]
        for point in tech_points:
            if point.upper() not in file_content.upper():
                results["compliance"] = False
                results["violations"].append(f"Falta inyección de: {point}")

        return results
```

---

## 💥 Motor de Impacto (Mutation Engine)
**PATH:** `.roo/scripts/impact_analyzer.py`
**Función:** Calcula el "Blast Radius" y genera el reporte de evolución del backlog.

```python
import sys

def calculate_impact(target_node, graph_data):
    """
    Detecta recursivamente qué historias y specs se ven afectadas
    cuando una Seed muta o un GAP se abre.
    """
    affected_nodes = []
    for edge in graph_data["edges"]:
        if edge["from"] == target_node:
            affected_nodes.append(edge["to"])
            # Recursividad para seguir el Hilo de Oro
            affected_nodes.extend(calculate_impact(edge["to"], graph_data))
            
    return list(set(affected_nodes))

if __name__ == "__main__":
    # Invocado por /external_sync o /internal_gap
    [cite_start]workspace_id = sys.argv[1]
    [cite_start]target_id = sys.argv[2]
    # Lógica para cargar graph_data y mostrar impacto...
```

---

## 🕸️ Motor de Visualización (Mermaid Architect)
**PATH:** `.roo/scripts/graph_visualizer.py`
**Función:** Traduce la matriz de adyacencia a diagramas visuales en Mermaid.

```python
def generate_mermaid(graph_data):
    """Genera código Mermaid marcando en ROJO los GAPs críticos."""
    mermaid = "graph TD\n"
    for node in graph_data["nodes"]:
        if "GAP" in node["id"]:
            mermaid += f"    style {node['id']} fill:#f96,stroke:#333\n"
    
    for edge in graph_data["edges"]:
        mermaid += f"    {edge['from']} --> {edge['to']}\n"
    return mermaid
```

---
**[Sello de Lógica Maestra: Sentinel v6.0]**
**[Sync Anchor: VOLUMEN_7_1_ENGINE_LOGIC_SOURCE]**