<!-- sentinel-artifact: v2 -->
# Project Brief — [PROJECT_ID]

## 0. Encabezado

### 0.1 Cómo leer este documento

- Cada afirmación es una de estas. Un hecho lleva una cita estructurada (documento, sección, id y qué sostiene) de la fuente que lo dice.
- `⏳` PENDIENTE (gap): el dato lo debe el cliente; bloquea.
- `⏳` PENDIENTE DOMINIO (gap): lo debe el contexto de dominio; puede diferirse.
- `N/A — motivo. Si condición, se abre.`: no aplica a este proyecto, y dice qué lo abriría.
- `(inferido)`: una inferencia, marcada en la misma frase.

### 0.2 Estado, vigencia y fuentes

#### Estado, vigencia y fuentes

- Perfil: UI
- Génesis: greenfield
- Dirección de validación: to-build

Fuentes:

- `F-01` `raw.md` (current)
- `F-02` `answer-1.md` (current)
- `F-03` `answer-2.md` (current)
- `F-04` `answer-3.md` (current)
- `F-05` `answer-4.md` (current)
- `F-06` `answer-5.md` (current)
- `F-07` `answer-6.md` (current)

Certeza por sección:

| Sección | Hechos | ⏳ cliente | ⏳ dominio | N/A |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 3 | 1 | 1 | 0 |
| 2 | 1 | 2 | 4 | 0 |
| 3 | 1 | 3 | 4 | 1 |
| 4 | 0 | 8 | 2 | 0 |
| 5 | 0 | 0 | 44 | 6 |
| 6 | 2 | 0 | 0 | 0 |
| 7 | 0 | 0 | 1 | 0 |
| 8 | 0 | 0 | 0 | 0 |
| 9 | 1 | 0 | 1 | 0 |
| A | 0 | 1 | 0 | 0 |

⚠ Confiabilidad baja: 72 de 80 lugares aplicables siguen pendientes.

#### Listo para construir

Listo para construir: no. Bloquean 15 marcas pendientes (§7).

## 1. Overview

### 1.1 Identidad y Valor

- Objetivo: que los lideres de operaciones revisen las colas de riesgo antes de la reunion diaria. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Identidad y Valor]]

### 1.2 El Dolor Principal

⏳ PENDIENTE (GAP-BRIEF-S1)

### 1.3 Métricas de Éxito / Scope

- Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Métricas de Éxito / Scope]]

### 1.4 Punto de Partida y Punto de Llegada

⏳ PENDIENTE DOMINIO (GAP-BRIEF-S1)

### 1.5 Criterios de Aceptación del Release

- Cuando haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-02 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]
- Cuando un caso incumpla el SLA, el sistema debe marcar la cola como riesgo alto. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-03 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]
- Cuando una cola no tenga casos abiertos, el sistema debe ocultar los indicadores de riesgo. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-04 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]
- Mientras los datos de riesgo esten desactualizados, el sistema debe mostrar una advertencia de datos obsoletos. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-05 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]
- Si el servicio de metricas no esta disponible, entonces el sistema debe mostrar estado de riesgo desconocido. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-06 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]
- Donde el registro de auditoria este habilitado, el sistema debe registrar el acceso al tablero. (`GAP-ACCEPTANCE`) [[sources § Registro de fuentes - [PROJECT_ID] # F-07 — sostiene: Criterios de Aceptación del Release (GAP-ACCEPTANCE)]]

#### Criterios de aceptación

→ 1.5

#### Verificación ejecutable

→ 1.5

## 2. Lente de Negocio

### 2.1 Actores y Objetivos por Rol

- Usuarios: lideres de operaciones. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Actores y Objetivos por Rol]]

### 2.2 Reglas de Negocio Críticas

#### Reglas de negocio críticas

⏳ PENDIENTE (GAP-BUSINESS-RULES)

#### Obligaciones normativas

⏳ PENDIENTE DOMINIO (GAP-BUSINESS-RULES)

#### Notificaciones

⏳ PENDIENTE DOMINIO (GAP-BUSINESS-RULES)

### 2.3 Caso de Uso Principal

⏳ PENDIENTE (GAP-BRIEF-S2)

### 2.4 Necesidad de Negocio

⏳ PENDIENTE DOMINIO (GAP-BRIEF-S2)

### 2.5 Fecha de Negocio y Calendario

⏳ PENDIENTE DOMINIO (GAP-BRIEF-S2)

## 3. Lente de Producto

### 3.1 Situación As-Is

- Metrica: reducir la preparacion manual un 30 por ciento en el primer mes de release. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Situación As-Is]]

### 3.2 Proceso To-Be

#### Proceso To-Be

⏳ PENDIENTE (GAP-PRODUCT-ASIS-TOBE)

#### Validaciones de entrada

⏳ PENDIENTE (GAP-PRODUCT-ASIS-TOBE)

#### Operación manual y backoffice

⏳ PENDIENTE DOMINIO (GAP-PRODUCT-ASIS-TOBE)

#### Corte, convivencia y reversión

N/A — no hay nada instalado que respetar: todo se crea en este proyecto. Si aparece un recurso, sistema o dato a reutilizar, extender o reemplazar, se abren.

### 3.3 Diagrama de Secuencia / Flujo To-Be

⏳ PENDIENTE DOMINIO (GAP-PRODUCT-ASIS-TOBE)

### 3.4 Máquina de Estados y Ciclo de Vida

⏳ PENDIENTE DOMINIO (GAP-PRODUCT-ASIS-TOBE)

### 3.5 Lógica de Transiciones

⏳ PENDIENTE DOMINIO (GAP-PRODUCT-ASIS-TOBE)

### 3.6 Manejo de Errores / Casos Borde

#### Casos borde y errores

⏳ PENDIENTE (GAP-QUALITY-HANDOFF)

#### Escenarios transversales

| Escenario | Lente | Dónde se especifica | Estado |
|---|---|---|---|
| T1 Permiso denegado | design, technical | §4.1 › Estados de pantalla, §5.11 › Autorización y permisos | pendiente allí |
| T2 Error | design, technical | §4.2 › Mensajes al usuario, §5.15 | pendiente allí |
| T3 Vacío | design | §4.1 › Estados de pantalla | pendiente allí |
| T4 Cargando | design | §4.1 › Estados de pantalla | pendiente allí |
| T5 Concurrencia | technical | §5.7 › Idempotencia y concurrencia | pendiente allí |
| T6 Duplicado | product, technical | §3.6 › Casos borde y errores, §5.7 › Idempotencia y concurrencia | pendiente allí |
| T7 Auditoría | technical | §5.11 › Auditoría | pendiente allí |
| T8 Internacionalización | design, technical | §4.1 › Idioma, locale y formatos, §5.21 | pendiente allí |
| T9 Accesibilidad | design | §4.4 | pendiente allí |
| T10 Flag | technical | §5.3 › Parámetros e interruptores | pendiente allí |
| T11 Migración | technical | §5.13 › Migración de datos | pendiente allí |
| T12 Sesión expirada | design, technical | §4.1 › Estados de pantalla, §5.11 › Autenticación y sesión | pendiente allí |
| T13 Dependencia caída | product, technical | §3.6 › Casos borde y errores, §5.6 › Resiliencia de integraciones | pendiente allí |
| T14 Evento duplicado | technical | §5.14 | pendiente allí |
| T15 Volumen | technical | §5.16 › Atributos de calidad y performance | pendiente allí |
| T16 Dato personal | technical, compliance | §5.4 › Datos personales: clasificación, propósito y retención | pendiente allí |

## 4. Lente de Diseño

### 4.1 Flujo de Pantalla

#### Ficha por pantalla

⏳ PENDIENTE (GAP-DESIGN-FLOW)

#### Design system y convenciones visuales

⏳ PENDIENTE (GAP-DESIGN-FLOW)

#### Mapa de pantallas y navegación

⏳ PENDIENTE (GAP-DESIGN-FLOW)

#### Estados de pantalla

⏳ PENDIENTE (GAP-DESIGN-FLOW) — estados: ideal; vacío de primer uso; sin resultados; cargando; parcial; error; 401 (y qué pasa con lo tipeado); 403 (vacío no es sin permiso; primer uso no es sin resultados)

#### Idioma, locale y formatos

⏳ PENDIENTE (GAP-DESIGN-FLOW)

### 4.2 Consideraciones UX

#### Decisiones de UX y no comprometidas

⏳ PENDIENTE DOMINIO (GAP-DESIGN-FLOW)

#### Mensajes al usuario

⏳ PENDIENTE (GAP-DESIGN-FLOW)

### 4.3 Prototipo y Precedentes de Diseño

⏳ PENDIENTE (GAP-DESIGN-PROTOTYPE-INPUT)

### 4.4 Accesibilidad

⏳ PENDIENTE (GAP-DESIGN-FLOW)

### 4.5 Ayuda y Capacitación

⏳ PENDIENTE DOMINIO (GAP-DESIGN-FLOW)

## 5. Lente Técnico

### 5.0 Apertura

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.1 Arquitectura e Integraciones

#### Arquitectura y componentes

⏳ PENDIENTE DOMINIO (GAP-FRONTEND-SURFACE)

#### Inventario de recursos existentes

N/A — ver 3.2/cutover.

#### Decisiones de arquitectura

⏳ PENDIENTE DOMINIO (GAP-FRONTEND-SURFACE)

### 5.2 Stack Tecnológico

#### Stack tecnológico

⏳ PENDIENTE DOMINIO (GAP-PRD-ROLLOUT-ENVIRONMENTS)

#### Ambientes, despliegue y rollback

⏳ PENDIENTE DOMINIO (GAP-PRD-ROLLOUT-ENVIRONMENTS)

### 5.3 Fuentes de Datos / Repositorios

#### Fuentes de datos

⏳ PENDIENTE DOMINIO (GAP-TECH-DATA-SOURCE)

#### Repositorios, configuración y secretos

⏳ PENDIENTE DOMINIO (GAP-TECH-DATA-SOURCE)

#### Parámetros e interruptores

⏳ PENDIENTE DOMINIO (GAP-TECH-DATA-SOURCE)

### 5.4 Modelo de Datos / ERD

#### Modelo de datos

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Datos personales: clasificación, propósito y retención

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.5 Query / Patrón Heredado

N/A — ver 3.2/cutover.

### 5.6 Mapa de Integraciones

#### Mapa de integraciones

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Resiliencia de integraciones

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.7 Contratos de API

#### Convenciones globales de API

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Idempotencia y concurrencia

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Versionado y compatibilidad

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Contratos por endpoint

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.8 Mapeo de Campos (DB → API → UI)

#### Mapeo de campos

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Impacto en lo instalado

N/A — ver 3.2/cutover.

### 5.9 Procesamiento Batch / Notificación de Novedades

#### Interfaces de archivo

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

#### Reinicio, re-ejecución y conciliación

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.10 Estrategia de Caché y Alta Disponibilidad

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.11 Gobernanza y Restricciones

#### Restricciones impuestas

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Autenticación y sesión

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Autorización y permisos

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Protección de datos

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Auditoría

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Normativa: controles y verificación

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

#### Límites para quien implementa

⏳ PENDIENTE DOMINIO (GAP-GOVERNANCE-CONSTRAINTS)

### 5.12 Servicios

#### Servicios

⏳ PENDIENTE DOMINIO (GAP-BACKEND-SURFACE)

#### Estado de cliente

⏳ PENDIENTE DOMINIO (GAP-BACKEND-SURFACE)

#### Jobs y calendario de ejecución

⏳ PENDIENTE DOMINIO (GAP-BACKEND-SURFACE)

### 5.13 Inventario y Reglas Heredadas del Legado (As-Is técnico)

#### Inventario y reglas heredadas del legado

N/A — ver 3.2/cutover.

#### Migración de datos

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.14 Eventos / Mensajería

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.15 Gestión de Errores y Códigos de Estado

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.16 Observabilidad

#### Atributos de calidad y performance

⏳ PENDIENTE DOMINIO (GAP-PRD-NFR-KPI)

#### SLI y SLO

⏳ PENDIENTE DOMINIO (GAP-PRD-NFR-KPI)

#### Observabilidad

⏳ PENDIENTE DOMINIO (GAP-PRD-NFR-KPI)

#### Alertas, runbooks y soporte

⏳ PENDIENTE DOMINIO (GAP-PRD-NFR-KPI)

### 5.17 Verificación de Paridad

N/A — no reemplaza un sistema cuyas salidas haya que igualar. Si aparece uno, se abren 5.17 y 5.13 como obligatorias.

### 5.18 Límites de Uso

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.19 Navegadores y Dispositivos

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.20 Ruteo y Protección de Rutas

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.21 Internacionalización Técnica

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.22 Seguridad del Cliente

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.23 Eventos de Analítica

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

### 5.24 Aislamiento entre Tenants

N/A — un solo cliente o tenant. Si se suma un segundo, se abren 5.24 y la columna de tenant en 5.4.

### 5.25 Abuso y Anti-automatización

⏳ PENDIENTE DOMINIO (GAP-TECH-DEEP-DIVE-INPUT)

## 6. Acuerdos del Release

### 6.1 Dentro del Scope

- Alcance: tablero de solo lectura de colas abiertas. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Dentro del Scope]]

### 6.2 Fuera del Scope

- Fuera de alcance: editar casos. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Fuera del Scope]]

### 6.3 Cascada — Estado de la Propagación a Otros Documentos

Primera compilación v2: todas las secciones son `ADDED`. PRD, specs y backlog se regeneran desde este brief.

## 7. Dependencias y Cuestiones a Confirmar

### 7.1 Tabla de Pendientes (forma pre-desarrollo)

#### Tabla de pendientes

28 gaps abiertos en `gaps.md`.

| Gap | Severidad | Origen |
|---|---|---|
| `GAP-BACKEND-SURFACE` | medium | checklist |
| `GAP-BACKLOG-ENABLERS` | medium | checklist |
| `GAP-BACKLOG-SLICING-READINESS` | medium | checklist |
| `GAP-BRIEF-S1` | medium | checklist |
| `GAP-BRIEF-S2` | medium | checklist |
| `GAP-BUSINESS-RULES` | medium | checklist |
| `GAP-CTP-EXCLUSION` | medium | checklist |
| `GAP-DELIVERY-READINESS` | medium | checklist |
| `GAP-DESIGN-FLOW` | medium | checklist |
| `GAP-DESIGN-PROTOTYPE-INPUT` | medium | checklist |
| `GAP-DESIGN-STATES` | medium | checklist |
| `GAP-FRONTEND-SURFACE` | medium | checklist |
| `GAP-GOVERNANCE-CONSTRAINTS` | medium | checklist |
| `GAP-METRIC-DEFINITION` | medium | checklist |
| `GAP-METRIC-SOURCE` | medium | checklist |
| `GAP-PRD-DEPENDENCIES-ROADMAP` | medium | checklist |
| `GAP-PRD-FR-AC` | medium | checklist |
| `GAP-PRD-GLOSSARY-GOVERNANCE` | medium | checklist |
| `GAP-PRD-GOVERNANCE` | medium | checklist |
| `GAP-PRD-NFR-KPI` | medium | checklist |
| `GAP-PRD-PERSONA-DETAIL` | medium | checklist |
| `GAP-PRD-ROLLOUT-ENVIRONMENTS` | medium | checklist |
| `GAP-PRODUCT-ASIS-TOBE` | medium | checklist |
| `GAP-QUALITY` | medium | checklist |
| `GAP-QUALITY-HANDOFF` | medium | checklist |
| `GAP-TECH-DATA-SOURCE` | medium | checklist |
| `GAP-TECH-DEEP-DIVE-INPUT` | medium | checklist |
| `GAP-TECH-NFR` | medium | checklist |

#### Riesgos, deuda y viabilidad

⏳ PENDIENTE DOMINIO (GAP-PRD-DEPENDENCIES-ROADMAP)

### 7.2 Pendientes sembrados en el cuerpo (⏳)

15 marcas de cliente (bloquean) y 57 de dominio (diferibles) en el cuerpo.

| Lugar | Clase | Gap |
|---|---|---|
| 1.2 | client | `GAP-BRIEF-S1` |
| 1.4 | domain | `GAP-BRIEF-S1` |
| 2.2/rules | client | `GAP-BUSINESS-RULES` |
| 2.2/regulatory | domain | `GAP-BUSINESS-RULES` |
| 2.2/notifications | domain | `GAP-BUSINESS-RULES` |
| 2.3 | client | `GAP-BRIEF-S2` |
| 2.4 | domain | `GAP-BRIEF-S2` |
| 2.5 | domain | `GAP-BRIEF-S2` |
| 3.2/process | client | `GAP-PRODUCT-ASIS-TOBE` |
| 3.2/validations | client | `GAP-PRODUCT-ASIS-TOBE` |
| 3.2/manual_ops | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.3 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.4 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.5 | domain | `GAP-PRODUCT-ASIS-TOBE` |
| 3.6/edge_cases | client | `GAP-QUALITY-HANDOFF` |
| 4.1/screens | client | `GAP-DESIGN-FLOW` |
| 4.1/design_system | client | `GAP-DESIGN-FLOW` |
| 4.1/screen_map | client | `GAP-DESIGN-FLOW` |
| 4.1/screen_states | client | `GAP-DESIGN-FLOW` |
| 4.1/locale | client | `GAP-DESIGN-FLOW` |
| 4.2/ux_decisions | domain | `GAP-DESIGN-FLOW` |
| 4.2/messages | client | `GAP-DESIGN-FLOW` |
| 4.3 | client | `GAP-DESIGN-PROTOTYPE-INPUT` |
| 4.4 | client | `GAP-DESIGN-FLOW` |
| 4.5 | domain | `GAP-DESIGN-FLOW` |
| 5.0 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.1/components | domain | `GAP-FRONTEND-SURFACE` |
| 5.1/decisions | domain | `GAP-FRONTEND-SURFACE` |
| 5.2/stack | domain | `GAP-PRD-ROLLOUT-ENVIRONMENTS` |
| 5.2/environments | domain | `GAP-PRD-ROLLOUT-ENVIRONMENTS` |
| 5.3/data_sources | domain | `GAP-TECH-DATA-SOURCE` |
| 5.3/repos | domain | `GAP-TECH-DATA-SOURCE` |
| 5.3/parameters | domain | `GAP-TECH-DATA-SOURCE` |
| 5.4/model | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.4/personal_data | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.6/map | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.6/resilience | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/conventions | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/idempotency | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/versioning | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.7/endpoints | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.8/mapping | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.9/file_interfaces | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.9/restart | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.10 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.11/constraints | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/authn | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/authz | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/data_protection | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/audit | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/regulatory_controls | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.11/implementer_limits | domain | `GAP-GOVERNANCE-CONSTRAINTS` |
| 5.12/services | domain | `GAP-BACKEND-SURFACE` |
| 5.12/client_state | domain | `GAP-BACKEND-SURFACE` |
| 5.12/jobs | domain | `GAP-BACKEND-SURFACE` |
| 5.13/data_migration | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.14 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.15 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.16/quality_attributes | domain | `GAP-PRD-NFR-KPI` |
| 5.16/sli_slo | domain | `GAP-PRD-NFR-KPI` |
| 5.16/observability | domain | `GAP-PRD-NFR-KPI` |
| 5.16/alerts | domain | `GAP-PRD-NFR-KPI` |
| 5.18 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.19 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.20 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.21 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.22 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.23 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| 5.25 | domain | `GAP-TECH-DEEP-DIVE-INPUT` |
| A.glossary | client | `GAP-PRD-GLOSSARY-GOVERNANCE` |
| 9.1/non_software | domain | `GAP-BACKLOG-ENABLERS` |
| 7.1/risks | domain | `GAP-PRD-DEPENDENCIES-ROADMAP` |

## 8. Supuestos

### 8.1 Lista de Supuestos

Sin supuestos registrados.

## 9. Cosas a Construir

### 9.1 Lista o Fases de Construcción

#### Lista o fases de construcción

- `C-01` Alcance: tablero de solo lectura de colas abiertas. [[sources § Registro de fuentes - [PROJECT_ID] # F-01 — sostiene: Lista o Fases de Construcción]] — depende de: ninguna

#### Trabajo que no es software

⏳ PENDIENTE DOMINIO (GAP-BACKLOG-ENABLERS)

#### Conclusión

Listo para construir: no. Bloquean 15 marcas pendientes (§7).

## A.glossary Glosario de Términos del Dominio

⏳ PENDIENTE (GAP-PRD-GLOSSARY-GOVERNANCE)

## A.provenance Procedencia y Datos de Referencia

| Fuente | Hechos citados |
|---|---|
| `F-01` | 7 |
| `F-02` | 1 |
| `F-03` | 1 |
| `F-04` | 1 |
| `F-05` | 1 |
| `F-06` | 1 |
| `F-07` | 1 |
