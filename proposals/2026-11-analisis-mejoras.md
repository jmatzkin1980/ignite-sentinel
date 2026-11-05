# Análisis de mejoras — Ignite Sentinel vNext (noviembre 2026)

> Documento de trabajo para mantenedores. Consolida un análisis hecho en una sesión de Claude Code en la nube, para continuarlo en una sesión local. No es documentación de producto ni cambia comportamiento del framework.
>
> Convención: **[V]** = verificado en el código o ejecutando comandos; **[E]** = inspiración externa (fuentes al final); **[P]** = pendiente de verificar.

---

## 0. Estado de partida (verificado)

- 586 archivos versionados; unas 27.700 líneas de Python en `sentinel/`; 32 comandos; 24 skills canónicas en `.codex/skills/` espejadas a `.agents/skills/` y `.claude/skills/`; adapters Kilo, Claude, Codex y MCP generados desde `sentinel/templates/commands_manifest.json`.
- `/doctor`: PASS (solo WARN por LanceDB y embeddings opcionales; modo `json-hybrid`).
- Suite: 823 tests en unos 170 s, **1 error**: `test_core_flow.test_mcp_server_exposes_lifecycle_tools`. Causa: `mcp` 2.x renombró `mcp.server.fastmcp.FastMCP` a `MCPServer`, y `sentinel/mcp.py:187` importa la ruta vieja. `pyproject.toml` declara `mcp` sin acotar versión.
- Smoke test: `/init` y `/ingest` con `tests/fixtures/evals/crm-billing-sync` produjeron 19 gaps (1 crítico), health `DIRTY` y etapa `CLIENT_RESPONSE_NEEDED`.

---

## 1. Mejoras funcionales (requirements engineering)

### Diagnóstico [V]
1. Detección de gaps léxica: 33 checks en 7 lenses, mayormente `absent_tokens`. Si la palabra aparece, el gap se suprime aunque falte la sustancia. El propio eval `expense-approval` documenta `target_recall` 0.00.
2. `sentinel/iso29148/characteristics.json` declara 5 de 9 características como `heuristic_gap`: appropriate, unambiguous, singular, verifiable y conforming.
3. `sentinel/drift.py` detecta drift por archivo (brief/requirements → specs; specs → backlog), no por ítem.
4. Volumen de gaps sin priorizar: 19 gaps para un input de dos frases.
5. La validación por cita controla la procedencia, no que el aporte del agente sea correcto.

### Propuestas
| # | Propuesta | Inspiración [E] | Encaje |
|---|---|---|---|
| F1 | Implementar los `heuristic_gap` de ISO 29148 como smells deterministas: fuga de implementación (appropriate), enunciados compuestos (singular), sin criterio medible (verifiable), desvío de plantilla EARS (conforming) | Femmer et al., *requirements smells* (Smella: 59% precisión, 82% recall); INCOSE GtWR v4 | Registro `sentinel/smells/`; warnings no bloqueantes en `/validate` y `/maturity` |
| F2 | Regla `token_without_substance`: palabra presente sin actor, número o condición cerca → gap `weakly_evidenced` en vez de suprimirlo | Techo léxico documentado en los evals | Medible con `target_recall` |
| F3 | Ronda de clarificación priorizada con tope (`--top N`): severidad × secciones de brief/PRD que alimenta × incertidumbre | `/speckit.clarify` de GitHub Spec Kit | Usa `_GAPS_FOR_BRIEF_SECTION` y `_GAPS_FOR_PRD_SECTION` de `maturity.py` |
| F4 | Suspect links por ítem: hash del nodo padre guardado en cada arista; si el padre cambia, la arista queda `suspect` hasta una `DEC-*` del BA | Doorstop, StrictDoc, Sphinx-Needs | Generaliza el `Stale` por Spec Unit a toda la cadena RAW → TC |
| F5 | Example Mapping por historia: reglas (EARS), ejemplos (citados o `[PENDING INPUT]`) y preguntas (→ `GAP-*`); muchas preguntas ⇒ dividir | Example Mapping (Cucumber); checklists de Spec Kit | Alimenta INVEST y SPIDR en `/quality` |
| F6 | Glosario gobernado y smell de sinónimos → `GAP-TERM-*` | INCOSE; steering de Kiro | Cubre *conforming*; alimenta la sección 13 del PRD |
| F7 | Disposición del BA (aceptado, rechazado o irrelevante) sobre aportes agénticos; tasa de falsas alarmas por canal en `/maturity`; eval con aportes citados pero incorrectos | Evidencia de que el soporte de LLM empeora la inspección de requisitos, sobre todo en novatos | Refuerza "el agente propone, el humano decide" |
| F8 | Change proposals unificadas `07_changes/proposals/CHG-NNN/` (ADDED, MODIFIED, REMOVED) con `/sync --apply` | OpenSpec (deltas y archive) | Consolida CHG, `--digest` y deltas de specs y AC |
| F9 | `/baseline --label --approver` con snapshot de hashes y grafo, más diff entre baselines | Baselines de herramientas de gestión de requisitos | Extiende la congelación de AC en `Ready` |
| F10 | Export ReqIF con `xml.etree` (stdlib) | Estándar ReqIF; exporter de StrictDoc | Interoperabilidad con DOORS, Polarion, etc. |
| F11 | Checks NFR por ISO/IEC 25010:2023 (9 características, incluida safety) | ISO 25010:2023 | `mention_requires_counterpart` en lenses quality y technical |

**No importar:** `/implement` y tareas ejecutables (Ignite se detiene en el handoff), personas de agente estilo BMAD (vocabulario paralelo), LLM-as-judge remoto (rompe local-first), priorización calculada (WSJF o RICE; a lo sumo un MoSCoW opcional y citado).

---

## 2. Mejoras técnicas

### Hallazgos [V]
| # | Hallazgo | Evidencia |
|---|---|---|
| T1 | Empaquetado incompleto | `pyproject.toml`: `packages = ["sentinel"]` omite `core`, `discovery`, `backlog`, `compilers`, `knowledge` y carpetas de datos; setuptools avisa. Probable rotura en `pip install .` no editable [P: falta probar el wheel en un entorno sano] |
| T2 | Path traversal en `PROJECT_ID` | `core/paths.py:11` no valida; `/init ../../escape` creó un workspace fuera de `workspaces/` |
| T3 | `/stakeholders` fuera del protocolo | No está en `READ_ONLY_COMMANDS` ni en `MUTATING_COMMANDS` (`protocols.py`): sin preflight, log ni snapshot |
| T4 | Sin CI | No existe `.github/`; solo `verify.ps1`, sin equivalente `.sh` |
| T5 | Escrituras concurrentes sin lock | `update_state` hace leer-modificar-escribir; tmp con nombre fijo; el conflicto solo emite un warning; sin `fsync` |
| T6 | Cachés globales en un proceso largo | `core/io.py`: caché con clave mtime + tamaño, persistente en el servidor MCP (`run_cli` ejecuta en el mismo proceso) |
| T7 | Grafo leído y escrito completo por cada arista | `add_edge` y `add_node` |
| T8 | Memoria `json-hybrid` inflada y no portable | 69 chunks y 411 KB para dos frases; texto triplicado; rutas absolutas |
| T9 | `state.json` mezcla estado durable con datos derivados | 38 KB tras un solo `/ingest`; ruido y conflictos de merge cuando el workspace se versiona |
| T10 | Firma de comandos en varias fuentes | argparse, `TOOL_SPECS` de MCP, manifest y conjuntos de `protocols.py` |
| T11 | Errores no tipados | `cli.py:434`: `except Exception` → exit 1 |
| T12 | YAML casero sin validar | `parse_simple_yaml` lee mal en silencio lo que está fuera del subconjunto |
| T13 | Tests lentos y ruidosos | 170 s y unas 69.000 líneas de stdout |
| T14 | Deuda estructural | `discovery/workflow.py` con 3.467 líneas y textos por gap hardcodeados; 7 shims; sin ruff ni mypy |

### Propuestas
- **Nivel 0:** corregir T1 (`packages.find` más un test que instala el wheel); validar `PROJECT_ID` con regex y contención; poner `/stakeholders` en el protocolo; compatibilidad con MCP 2.x (import doble y argumentos por nombre, o acotar `mcp<2`); CI en GitHub Actions (Windows y Linux, 3.10 y 3.13, con y sin LanceDB, `mcp` 1 y 2); `verify.sh`.
- **Nivel 1:** lock por workspace, `mkstemp` y `fsync`, y error en conflictos sobre artefactos gobernados; `workspace_session()` transaccional y limpieza de caché por comando; separar `state.json` (durable) de `.cache/` (derivado) y `command_log.jsonl`; memoria con rutas relativas, sin duplicados y embeddings compactos; validar la configuración.
- **Nivel 2:** registro único de comandos que genere argparse, MCP, manifest y protocolos; errores tipados con exit codes y JSON (`GATE_DIRTY` más `next_step`); catálogos i18n para los textos por gap; validador stdlib del subconjunto de JSON Schema usado; ruff, mypy y coverage como extras `[dev]`; deprecación de shims.
- **Nivel 3:** capturar stdout en tests; separar unit de lifecycle; tests de propiedades con semilla para el parser Markdown y el YAML; test de concurrencia.
- **Nivel 4:** escaneo de privacidad también en exports y vistas, con detección por entropía; rangos acotados y `pip-audit` para los extras opcionales.

---

## 3. Flujo funcional: huecos [V]

- **A1.** `phase` registra el último evento (19 valores, como `change_synced`), no la etapa: `/sync` borra que había backlog.
- **A2.** `recommend_next_step` (`status.py:81`) se queda en la mitad del ciclo; `dashboard.py` tiene otra lógica (`_next_action`).
- **A3.** Las context requests (`CTX`) no tienen ciclo de vida (abierta, respondida, cerrada).
- **A4.** Dos semáforos (maturity `BLOCKED` frente a health `DIRTY`) sin una vista única.
- **A5.** `/trace` es casi redundante con el postflight.
- **A6.** `/stakeholders` no deja traza.

**Propuestas:** máquina de estados `lifecycle_stage` calculada (DISCOVERY → CLARIFYING → BRIEF_READY → SPECS_READY → BACKLOG_READY → IN_DELIVERY, más CHANGE_PENDING), separada de `last_event`; una única función de próximo paso para status, dashboard, MCP y skills; matriz de gates en `/status`; ciclo de vida de `CTX-NNN`; rondas `ROUND-N` como unidad; absorber `/trace` en `/validate`.

---

## 4. Skills

### Estado [V]
24 skills de 23 a 117 líneas; descripciones de 236 a 503 caracteres; 6 con `references/` y 0 con `scripts/`; el bloque "Agentic Spirit" está copiado en 7 skills; la granularidad es una skill por comando; además hay 33 commands en Claude, 33 en Kilo y 7 agentes de Kilo.

### Contexto de plataforma [E]
En Claude Code, los commands se fusionaron con las skills. Frontmatter nuevo: `disable-model-invocation`, `user-invocable`, `allowed-tools`, `context: fork` con `agent`, `arguments`, `paths` y `when_to_use`. Inyección `` !`cmd` ``. `SKILL.md` por debajo de 500 líneas y descripción por debajo de 1.536 caracteres. Revelación progresiva en tres niveles. Sección de *gotchas* como contenido de mayor valor.

### Propuestas
1. Reagrupar a unas 10 skills por trabajo del BA: discovery; deepening (annotate, challenge, scrutiny y assume, con las técnicas en `references/`); clarification-round; maturity-brief; specs (más compose y self-review); backlog (más refine y quality); delivery-loop; change; governance; router.
2. `--dry-run` en todos los canales agénticos (en el runtime, portable).
3. Boilerplate compartido en `references/agentic-contract.md` (generado) y sección de gotchas por skill.
4. **Portabilidad entre harness** (Claude, Codex y Kilo):
   - Los campos de frontmatter de vendor son inertes en otros harness (seguros, pero sin comportamiento crítico).
   - El contenido del cuerpo (`` !`cmd` ``, `${CLAUDE_PLUGIN_ROOT}`, `$ARGUMENTS`) **no es inerte**: va solo en capas por superficie.
   - Render de skills por superficie: núcleo canónico portable más overlays (`surfaces/claude.yaml`, etc.), como ya se hace con los commands.
   - Invocación abstracta del CLI (`sentinel /cmd`), traducida en el render a `python -m sentinel`, `bin/sentinel` o `.pyz`.
   - `/doctor` pasa de exigir "espejos idénticos" a exigir "núcleo idéntico más overlays sin reglas"; un test garantiza que la variante de Codex no contiene `${CLAUDE_`, `` !` `` ni `$ARGUMENTS`.
   - La doctrina y los gates siguen en el runtime.

---

## 5. llm-wiki frente a LanceDB

- **llm-wiki** (nvk/llm-wiki, idea de Karpathy): `raw/` inmutable, artículos **sintetizados por el LLM**, `_index.md` por carpeta, recuperación por índices más búsqueda de texto, cero dependencias, verificación humana; recomienda `qmd` a partir de unos 100 artículos; tiene investigación web y opción de hub en iCloud.
- **LanceDB en Ignite:** índice de chunks con anclas, consumido **de forma determinista** por el runtime (planes de retrieval); sin él, `json-hybrid` con hash, cuyo recall entre idiomas es casi 0 según los evals.

**Conclusión:** no reemplazar (un artículo sintetizado no puede ser evidencia en Ignite). Adoptar el **patrón**:
1. `/reindex` genera un `_index.md` determinista por carpeta del workspace a partir del grafo y los `section_path`, sin LLM, para navegar índice → sección.
2. Niveles: sin dependencias (índices más texto) y con LanceDB (búsqueda híbrida para proyectos grandes o multilingües).
3. llm-wiki como fuente externa de conocimiento de dominio u organización, que entra a `00_raw/0x_context/` vía `/sync`, marcada como síntesis; sin investigación web ni hub en iCloud cuando hay datos de cliente.

---

## 6. Optimización de procesos

- [V] `/status` imprime 65.781 bytes (unos 16.000 tokens) y `/maturity` 35.081 bytes en un proyecto de dos frases. Es el mayor costo oculto para los agentes.
- Propuestas: `--summary` por defecto para agentes, con el JSON completo a archivo; flujos compuestos deterministas `/next`, `/round` y `/handoff` (cada paso con su preflight); postflight solo si el grafo cambió; verificar los gates baratos antes de cargar la memoria; documentar el circuito `/view` → comentarios → `/resolve-gaps`; tests rápidos y lentos en CI.

---

## 7. Distribución por marketplace

### Por qué falló [V]
No hay ningún manifiesto: faltan `.claude-plugin/marketplace.json` (Claude Code) y `.agents/plugins/marketplace.json` más `.codex-plugin/plugin.json` (Codex).

### Problemas de fondo [V]
- Las skills llaman `python -m sentinel`, que no existe fuera del clon.
- Los hooks viven en `.claude/settings.json`, que un plugin no aplica: hace falta `hooks/hooks.json`.
- `CLAUDE.md` y `AGENTS.md` no se cargan desde un plugin.
- `/doctor` asume el repo del framework.
- A favor: `repo_root()` es `Path.cwd()`.

### Propuesta
```text
.claude-plugin/marketplace.json      -> source ./plugins/ignite-sentinel
.agents/plugins/marketplace.json     -> path   ./plugins/ignite-sentinel
plugins/ignite-sentinel/   (GENERADO por python -m sentinel.adapters)
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
  skills/        (render por superficie)
  hooks/hooks.json
  bin/sentinel  bin/sentinel.cmd   (launcher que resuelve Python 3.10+)
  runtime/sentinel/  o  sentinel.pyz
```
- Modos repo y plugin; `/doctor --mode plugin`; `/setup` para crear el andamiaje en el proyecto del usuario (incluido Kilo, que no tiene marketplace).
- Validación: `claude plugin validate . --strict` en CI.
- Cada manifiesto se registra en `SURFACE_CONTRACTS` con su prueba real de instalación (auto-approve apagado).
- Instalación prevista: `claude plugin marketplace add jmatzkin1980/ignite-sentinel` + `claude plugin install ignite-sentinel@ignite-sentinel`; `codex plugin marketplace add jmatzkin1980/ignite-sentinel` + `codex plugin add ignite-sentinel@ignite-sentinel` [P: sintaxis de Codex tomada de llm-wiki; la documentación oficial no fue accesible].
- Modelo de referencia: llm-wiki (dos marketplaces en un repo, scripts de sync por harness, 3 skills por tarea).

---

## 8. Artefactos HTML navegables

### Estado [V]
`/view` (`view.py`, 1.180 líneas; claro, acento `#0f766e`, sin modo oscuro) y `/dashboard` (`dashboard.py`, 416 líneas; oscuro, acento `#828dff`) son dos sistemas visuales distintos con HTML y CSS dentro de strings de Python.

### 8.1 Patrones genéricos de las skills locales [V]
Fuente: cuatro skills de un workspace de BA que generan HTML derivado desde JSON curado. Están documentadas en un contrato común (`derivados-html.md`) y comparten una carpeta de temas JSON. Acá van solo los patrones; no se copian datos, nombres de proyecto ni temas de cliente.

**Pipeline**
| Patrón | Qué es | Encaje en Ignite |
|---|---|---|
| Datos → validar → construir | Solo se edita el JSON a mano. Un validador de solo lectura (ERROR/WARN; exit 1, y también en WARN con `--estricto`) corre antes de cada build. El HTML nunca se edita. | `view.py` se parte en `views/model.py` (vista derivada del grafo y los bloques), `views/validate.py` y `views/render.py`. |
| Un solo archivo autocontenido | CSS, JS, datos (`const ITEMS=…`) e imágenes (base64) van inline; las librerías de terceros, vendorizadas. | Ya es la restricción VDI; se formaliza como test (cero `http(s)://` en `src` o `href` de recursos). |
| Salida reproducible | Misma entrada ⇒ mismos bytes. La fecha de corte sale de los datos y nunca del reloj. | Test golden por vista; desbloquea versionar los HTML o compararlos entre baselines (F9). |
| Ningún número hardcodeado | Los conteos se calculan en el build o en el navegador; la prosa usa `{n_total}` y un placeholder desconocido corta el build. | Elimina el drift entre `/status` y lo que muestra el HTML. |
| Procedencia embebida | Una sección final con fecha de corte, fecha de build, sha256 (12 caracteres) de los datos y de cada fuente (`FALTA` si no está) y el comando para regenerar. Avisa si el corte supera un umbral de antigüedad. | Se reutilizan los hashes del grafo; es la base visual de los *suspect links* (F4). |
| Validaciones del derivado | Esquema e ids únicos usables como ancla; cada cita apunta a un documento y una sección que existen y el id aparece en esa sección; prohibido citar por número de línea; huérfanos en los dos sentidos (citado sin registro, registrado sin cita); grafo sin ciclos y con dependencias simétricas; campos calculados ausentes de los datos. | Casi todo existe en `/validate`; falta aplicarlo a la vista antes de escribir el HTML. |

**Navegación**
- Shell común: barra superior sticky, sidebar sticky con conteos por grupo, menú hamburguesa por debajo de unos 900 px con `aria-expanded`, skip link.
- Dos modelos, con una regla para elegir:
  - Un panel visible a la vez, ruteado por `#hash` (`hashchange` + `history.replaceState`), para explorar.
  - Una página larga con scroll-spy (IntersectionObserver), cuando hay que leer de corrido el resultado filtrado.
- Todo link `#id` interno pasa por el router, así los deep links funcionan siempre. Breadcrumbs en vistas jerárquicas.
- Búsqueda de texto sobre un `data-text` precalculado, más selects por enum, un checkbox "solo no resueltos" y el conteo de resultados con `aria-live`.

**Componentes**
- Chips de estado salidos de un único mapa `enum → (etiqueta, clase de color)`.
- Leyenda de colores **obligatoria**, generada desde la `semantica` del tema.
- Tiles KPI y cards en grilla `auto-fit`.
- Callouts con iconos SVG inline.
- `<details>` para colapsar.
- Tablas dentro de un contenedor con scroll horizontal.
- Tarjetas de veredicto por grupo: barra de progreso, "N de M" y un botón que aplica el filtro correspondiente. Contadas, no puntuadas.
- Mapa de dependencias con grilla CSS por profundidad calculada, sin coordenadas SVG.
- Matriz de trazabilidad: una fila por elemento, columnas por paso y un chip de nivel.
- Visor de diagramas con cadena de degradación: SVG pre-renderizado → SVG con ids namespaced → imagen base64 → mermaid vendorizado → fuente con aviso de "degradado". Zoom y pan, pestañas antes/después, export a SVG (con las variables CSS resueltas) y a PNG.

**Interacción**
- Estado del lector en `localStorage` con clave por proyecto y versión: checkbox y nota por id, que sobrevive al rebuild.
- Export del estado a JSON y CSV (con BOM), import desde JSON, reset con confirmación por doble clic.
- Copiar al portapapeles con confirmación.
- CSS de impresión: oculta la navegación, expande todo y hace salto de página por sección.

**Evidencia y huecos**
- La cita es un objeto `{doc, seccion, id}`. Se muestra como "Fuentes (n)" colapsable por ítem o se concentra en la sección de procedencia.
- Lo desconocido se declara y nunca se rellena:
  - El centinela `[SIN FUENTE]` se ve como una marca roja.
  - "No declarado en las fuentes" se ve atenuado.
  - Una lista `declarados_ausentes[]` de `{campo, por_que}` exigida por el validador.
  - Niveles `establecido / inferido / sin-sustento`: `inferido` dice de qué se infiere y `sin-sustento` abre un pendiente.
- Un estado vacío nunca se pinta verde.
- Si se fuerza el build saltando el validador, el HTML lleva un banner de error.

**Reglas de tema**
- El tema es un dato con `tokens`, `semantica`, `tipografia` e `isotipo` opcional, y todos los temas tienen las mismas claves.
- Se elige así: flag, después dato del proyecto, después `generico`. Si falta un token que el CSS usa, el build falla.
- El tema se elige, no se extrae: el prototipo replica un design system pero no es el design system, y extraer los colores da tonos aproximados y sin significado.
- Sin isotipo la barra lleva texto: no se inventa un logo. Nunca se rellena con el branding de otro cliente.

**Recurrencia**
- En las 4 skills (base compartida): cargador de tema con tokens y leyenda; escape HTML con mini-markup; archivo único; validar antes de construir; salida reproducible; conteos calculados; sha y fecha de corte; citas por sección e id; shell con barra superior y sidebar; chips; ARIA.
- En 2 o 3: router por hash, pestañas, CSS de impresión, KPIs, scroll-spy, registro central de pendientes con chequeo de huérfanos, veredicto contado.
- **Ausente en las 4:** modo oscuro y atajos de teclado. Ignite debería tener los dos desde el inicio.

### 8.2 Tema corporativo inspirado en Globant
**Fuente.** globant.com respondió 403 (Imperva, "Error 15") por IP desde el navegador integrado, desde Chrome y desde WebFetch, así que no se pudo inspeccionar el sitio. Los tokens salen del brand guide público: `brand.globant.com/color` y `/typography` **[E]**.

**Paleta oficial [E]**
| Grupo | Colores |
|---|---|
| Primarios | `#BFD732` (verde lima, firma) · `#FFFFFF` · `#00292E` (teal casi negro) · `#38EFA0` |
| Secundarios | `#39B54A` · `#63E3CF` · `#662D91` · `#E61587` · `#F5F6F7` · `#666666` |
| Safety | `#00A99D` |
| Especiales | `#9E005D` · `#F7931E` · `#29ABE2` |
| Gradientes (solo complemento, máximo uno por pieza, 40°) | `#38EFA0→#96F887→#C0FB73` · `#25F198→#15C9C3` · `#D9E021→#8CC63F` |

Reglas del guide: predomina el blanco; no usar colores fuera de la paleta; no alterar los colores con efectos ni modos de fusión; no abusar de secundarios en una misma composición.

**Contraste WCAG (calculado) [V]**
| Par | Ratio | Uso permitido |
|---|---|---|
| `#00292E` sobre blanco | 15,5 | Texto principal en claro |
| `#666666` sobre blanco / `#F5F6F7` | 5,7 / 5,3 | Texto secundario |
| `#662D91` sobre blanco | 8,9 | Links y foco en claro |
| `#E61587` sobre blanco | 4,4 | Solo texto grande o relleno (no llega a AA normal) |
| `#BFD732` · `#39B54A` · `#00A99D` sobre blanco | 1,6 · 2,7 · 2,9 | **Nunca como texto en claro**: solo rellenos, bordes y subrayados |
| `#BFD732` · `#38EFA0` · `#63E3CF` sobre `#00292E` | 9,6 · 10,3 · 9,9 | Texto y acentos en oscuro |
| `#F7931E` · `#29ABE2` · `#00A99D` sobre `#00292E` | 6,7 · 5,9 · 5,3 | Estados en oscuro |
| `#E61587` sobre `#00292E` | 3,6 | Solo texto grande o íconos |

**Consecuencia de diseño.**
- El modo **oscuro** (fondo `#00292E`) es donde la paleta funciona de forma natural como texto.
- En modo **claro** predomina el blanco: el lima va como acento de superficie (barra activa, subrayado de título, foco). Los estados usan fondo suave, texto `#00292E` y borde o punto de color.
- El significado nunca depende solo del color: siempre hay etiqueta o ícono, y está la leyenda.

**Mapeo a roles (`semantica`) [propuesta]**
| Rol | Claro | Oscuro |
|---|---|---|
| `bg` / `surface` / `surface-2` | `#FFFFFF` / `#F5F6F7` / `#FFFFFF` + borde | `#00292E` / tinte de `#00292E` / tinte más claro |
| `text` / `text-muted` | `#00292E` / `#666666` | `#FFFFFF` / `#F5F6F7` atenuado |
| `accent` (marca) | `#BFD732` como relleno o borde | `#BFD732` |
| `link` / `focus` | `#662D91` | `#63E3CF` |
| `ok` (listo, resuelto) | borde `#39B54A` | `#38EFA0` |
| `info` | borde `#29ABE2` | `#29ABE2` |
| `warn` (débil, pendiente) | borde `#F7931E` | `#F7931E` |
| `block` (crítico, bloqueante) | borde `#E61587` | `#E61587` + ícono |
| `governance` (DEC, ASM) | `#00A99D` (safety) | `#00A99D` |

Los tintes de fondo y los colores de oscuro que no son de la paleta salen de mezclas sobre `#00292E` o `#FFFFFF`, y se documentan en la `procedencia` del tema. Eso choca con la regla "no usar colores fuera de la paleta", así que, si el tema llega a ser oficial, hay que validarlo con el dueño de marca **[P]**.

**Tipografía [E]**
- Guide: Heebo como primaria (complementada con Roboto para caracteres especiales) y Open Sans como secundaria. Jerarquía por variante (peso o estilo), no solo por tamaño; no tocar el interletrado ni deformar las fuentes.
- Restricción VDI: sin Google Fonts. Propuesta: el tema declara `font-family: Heebo, "Open Sans", Roboto, system-ui, "Segoe UI", sans-serif` y se ve bien con la fuente instalada o sin ella. Los `.woff2` se pueden vendorizar en el tema local del usuario (Heebo y Open Sans son OFL; Roboto, Apache 2.0/OFL) **[P: confirmar licencias antes de vendorizar]**.
- Escala propuesta (no viene del guide): 12 / 14 / 16 / 20 / 24 / 32, con títulos en 600–700 y texto en 400.

**Componentes [E]**
- CTA: borde redondeado de 20 px, con estados hover y active definidos, según el guide.
- Radio de cards: 8–12 px (propuesta).

**Sin verificar [P]:** layout, grilla y motion del sitio (por el bloqueo). Se puede resolver con capturas o desde otra red. Mientras tanto, los defaults conservadores son: contenedor de 1200–1280 px, grilla de 12 columnas, transiciones de 150–200 ms con `ease-out` y `prefers-reduced-motion` respetado.

**Ubicación.** En el repo público solo van los temas `neutral` (claro y oscuro, default) y el esquema. El tema inspirado en Globant vive como **tema local del usuario** (`~/.ignite/themes/` o una carpeta git-ignored del workspace) con el nombre y la `procedencia` declarados. No se incluyen logo ni isotipo: la barra lleva texto.

### 8.3 Propuesta (actualizada)
1. **Esquema de tema** `sentinel/themes/schema.json`:
   - Claves: `tokens` (con bloques `light` y `dark`), `semantica` (rol → significado, para la leyenda), `tipografia`, `isotipo?` y `procedencia`.
   - Claves idénticas entre temas; si falta un token, el build falla.
   - Se elige así: `--theme`, después `theme:` del workspace, después `neutral`.
   - Modo con `prefers-color-scheme` más un toggle persistido.
2. **Base única** `sentinel/themes/base.css` y shell común (barra superior, sidebar, hamburguesa, router por hash o scroll-spy, skip link, impresión). `/view` y `/dashboard` migran a esa base y dejan de tener dos sistemas visuales.
3. **Pipeline de vistas** modelo → validar → render, con salida reproducible (test golden), conteos calculados, sección de procedencia (corte, sha del grafo y de las fuentes, comando) y banner si el grafo tiene *suspect links* o el health es `DIRTY`.
4. **Componentes como funciones Python puras** (chip, kpi, card, callout, legend, matrix, details) sobre `string.Template`. Sin JS de terceros salvo mermaid vendorizado y opcional.
5. **Evidencia visible:** "Fuentes (n)" por ítem con link a la sección del RAW; `[PENDING INPUT]` y `weakly_evidenced` (F2) con su estilo propio; un estado vacío nunca en verde.
6. **Circuito de vuelta:** estado del BA (marcas y notas por id) en `localStorage` con clave por proyecto y hash del grafo, exportable a JSON e importable por `/resolve-gaps`. Formaliza el circuito `/view` → comentarios → `/resolve-gaps` de la sección 6.
7. **Catálogo `/view --artifact`** sobre esos componentes:
   | Artefacto | Componentes |
   |---|---|
   | Brief en una página | Página larga, procedencia, callouts de huecos |
   | Guía de entrevista navegable | Router por hash, preguntas por `GAP-*`, checkbox y nota persistidos, export |
   | Scorecard de madurez | KPIs, tarjetas de veredicto contadas con filtro, matriz de gates (sección 3) |
   | Explorador de trazabilidad | Matriz RAW → TC, chips de nivel, *suspect* resaltado |
   | Story map y plan de entregas | Grilla por profundidad (dependencias), cards por SLICE |
   | Impacto de cambio | Antes/después, aristas afectadas, link a `CHG-*` |
8. **Atajos de teclado** (`/` para buscar, `j`/`k` para navegar, `?` para ayuda) y verificación de AA en un test que calcula el contraste de los pares de `semantica`.
9. **Skill portable `sentinel-visual-artifacts`:** elige la vista según la intención; el HTML lo genera el runtime.

### Pendiente
1. Verificar layout, grilla y motion de globant.com, con capturas o desde una red sin el bloqueo.
2. Aprobar el prototipo del motor de temas (puntos 1 a 3 de 8.3) sobre `/dashboard`, que es la vista más chica.
3. Decidir si se vendorizan las fuentes en el tema local, después de confirmar las licencias.

---

## 9. Hoja de ruta consolidada

| Fase | Contenido |
|---|---|
| **Ahora** | Fix de MCP 2.x; T1 empaquetado; T2 validación de `PROJECT_ID`; T3 `/stakeholders`; CI; `--summary`; `--dry-run`; una única lógica de próximo paso; F1, F2 y F3; launcher `bin/sentinel` |
| **Siguiente** | Locks y escritura atómica; separar `state.json`; memoria compacta; errores tipados; máquina de estados y matriz de gates; ciclo de vida de `CTX`; `/next`, `/round` y `/handoff`; índices `_index.md`; F4 a F7; paquete de plugin con dos manifiestos; render de skills por superficie; motor de temas HTML |
| **Después** | Registro único de comandos; catálogos i18n; F8 a F11; reagrupar a unas 10 skills; prueba real de los marketplaces; tema corporativo y artefactos HTML nuevos; puente con llm-wiki |

---

## 10. Fuentes

- GitHub Spec Kit: https://codemyspec.com/blog/github-spec-kit-guide · https://wiki.at.bitovi.com/wiki/spaces/AIEnabledDevelopment/pages/1799847940/Spec+Kit+-+Analysis
- OpenSpec: https://openspec.dev/docs/faq · https://codemyspec.com/blog/openspec-explained
- Kiro: https://kiro.dev/docs/specs/index
- StrictDoc / Doorstop / Sphinx-Needs: https://strictdoc.readthedocs.io/en/latest/strictdoc_02_faq.html
- INCOSE GtWR v4: https://www.incose.org/docs/default-source/working-groups/requirements-wg/gtwr/incose_rwg_gtwr_v4_040423_final_drafts.pdf
- Requirements smells (Femmer): https://ar5iv.labs.arxiv.org/html/1611.08847 · https://arxiv.org/pdf/2404.11106
- LLMs e inspección de requisitos: https://arxiv.org/pdf/2608.21298 · https://arxiv.org/pdf/2609.03230 (verificar identificadores)
- Ambigüedad con LLMs (ICSME 2025): https://conf.researchr.org/details/icsme-2025/icsme-2025-industry-track/8/Requirements-Ambiguity-Detection-and-Explanation-with-LLMs-An-Industrial-Study
- Example Mapping: https://static1.squarespace.com/static/59e39ba7268b9625f429cc67/t/5b95a2100ebbe8f03f569edb/1536533010502/example-mapping-20180829-bacon.pdf
- ReqIF: https://pypi.org/project/reqif · https://ibm.com/support/knowledgecenter/SSYMRC_7.0.2/com.ibm.rational.rrm.help.doc/topics/t_reqif_intro.html
- ISO/IEC 25010:2023: https://quality.arc42.org/articles/iso-25010-update-2023
- MCP Python SDK v2: https://py.sdk.modelcontextprotocol.io/v2/migration/
- Claude Code Skills: https://code.claude.com/docs/en/skills
- Claude Code plugins y marketplaces: https://code.claude.com/docs/en/plugin-marketplaces · https://code.claude.com/docs/en/plugins/manifest-reference
- Anthropic, Agent Skills: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Codex plugins: https://developers.openai.com/codex/plugins/build · https://github.com/openai/plugins · https://help.openai.com/en/articles/20001504-importing-and-syncing-plugin-marketplaces-from-github
- llm-wiki: https://github.com/nvk/llm-wiki
- Globant brand guide: https://brand.globant.com/color/ · https://brand.globant.com/typography/
