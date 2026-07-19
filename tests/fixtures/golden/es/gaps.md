# Gaps de Discovery - [PROJECT_ID]

Versión del documento: `1.0`
Proyecto: `[PROJECT_ID]`
Requerimiento padre: `REQ-001`
Audiencia: stakeholders del cliente, Producto, Tecnología, Diseño, Calidad y Delivery.
Propósito: recopilar información faltante o ambigua para madurar el requerimiento y poder generar project brief, PRD, specs, backlog, criterios de aceptación y tests.

## Cómo responder

Por favor responder directamente debajo de cada gap. Una respuesta breve sirve si es precisa. Si la respuesta corresponde a otro equipo, indicar el owner y cualquier información parcial disponible.

Formato sugerido de respuesta:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión: confirmado / pendiente / no aplica

## Secciones para respuesta del cliente

### GAP-BUSINESS-RULES - Reglas de negocio

- Lente: `business`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream.

Por qué importa (riesgo si queda abierto):
Las reglas y excepciones determinan validaciones, casos borde y criterios de aceptación.

Qué desbloquea esta respuesta:
Los FRs/ACs del PRD, las reglas de negocio de specs y los casos borde de Calidad.

Pregunta:
¿Qué reglas, excepciones, validaciones, fallbacks o exclusiones gobiernan el comportamiento?

Formato de respuesta esperado:
Reglas en formato EARS cuando describen comportamiento: Si <condición/regla>, entonces el sistema debe <respuesta>; incluir umbrales y excepciones.

Ejemplo de respuesta útil:
Una cola es de alto riesgo cuando más de 10 casos están a menos de 30 minutos de breach de SLA o cuando cualquier caso ya está vencido.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-PERSONA-DETAIL - Detalle de personas para PRD

- Lente: `business`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear.

Por qué importa (riesgo si queda abierto):
El PRD necesita personas con objetivos, dolores, frecuencia y habilidad para orientar experiencia, adopcion y soporte.

Qué desbloquea esta respuesta:
La sección de Personas del PRD.

Pregunta:
¿Qué información confirmada resuelve esta incertidumbre?

Formato de respuesta esperado:
Por persona: objetivo, dolores, frecuencia y habilidad.

Ejemplo de respuesta útil:
Persona primaria: operador central. Objetivo: resolver casos sin TI. Dolor: proceso manual riesgoso. Frecuencia: diaria. Habilidad: herramienta interna avanzada.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-METRIC-SOURCE - Fuente de métrica

- Lente: `business`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Aparece una métrica cuantitativa sin fuente o baseline explícito.

Evidencia que dispara la pregunta:
La métrica "30 por ciento" aparece sin fuente, baseline ni método de medición.

Por qué importa (riesgo si queda abierto):
Las métricas necesitan fuente o baseline para medir el éxito de manera consistente.

Qué desbloquea esta respuesta:
Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.

Pregunta:
¿Cuál es la fuente o baseline de la métrica cuantitativa?

Formato de respuesta esperado:
Nombre de la métrica + fuente/owner del baseline + valor objetivo + ventana de medición.

Ejemplo de respuesta útil:
El baseline sale del reporte semanal de operaciones, owner Support Ops; el target es detectar colas de alto riesgo antes de las 9:30 AM.

Opciones candidatas citadas (no seleccionadas):
- Opcion A: Confirmar que `30 por ciento` es la meta de exito y aportar fuente, baseline, owner y metodo de medicion. Cita local: `30 por ciento`.
- Opcion B: Tratar `30 por ciento` como objetivo direccional hasta confirmar fuente/baseline, indicando que evidencia falta. Cita local: `30 por ciento`.
Estas opciones no cierran el gap; el BA/owner debe confirmar una respuesta.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-METRIC-DEFINITION - Definición de métrica

- Lente: `business`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Se nombra una métrica, KPI o indicador sin su definición, fórmula, unidad, fuente ni umbral.

Evidencia que dispara la pregunta:
El input menciona "metrica" pero no define la métrica: falta fórmula/unidad, fuente o umbral.

Por qué importa (riesgo si queda abierto):
Una métrica nombrada sin definición, fuente ni umbral no es medible ni comprometible y arrastra ambigüedad a KPIs y criterios de éxito.

Qué desbloquea esta respuesta:
Los KPIs del brief y la sección de NFRs/KPIs y medición del PRD.

Pregunta:
¿Cómo se define cada métrica/KPI (fórmula, unidad), de qué fuente sale y cuál es su baseline y umbral objetivo?

Formato de respuesta esperado:
Por métrica: definición/fórmula, unidad, fuente/owner del dato, baseline y umbral objetivo.

Ejemplo de respuesta útil:
La métrica 'tiempo de resolución' se define como promedio de horas entre apertura y cierre, fuente Case Management, baseline 8h, umbral objetivo 6h.

Opciones candidatas citadas (no seleccionadas):
- Opcion A: Confirmar que `metrica` esta dentro del alcance y responder el detalle faltante de `Definición de métrica`. Cita local: `metrica`.
- Opcion B: Confirmar que `metrica` es solo contexto, fuera de alcance o pendiente, y explicitar el limite. Cita local: `metrica`.
Estas opciones no cierran el gap; el BA/owner debe confirmar una respuesta.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRODUCT-ASIS-TOBE - Proceso actual y objetivo

- Lente: `product`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
El estado actual y el estado objetivo no están suficientemente claros para comparar impacto.

Por qué importa (riesgo si queda abierto):
El delta entre comportamiento actual y objetivo guía el análisis de impacto y el slicing de backlog.

Qué desbloquea esta respuesta:
La sección 3 del brief (as-is/to-be) y el slicing del backlog.

Pregunta:
¿Cuál es el proceso actual, el proceso objetivo y el delta exacto entre ambos?

Formato de respuesta esperado:
Comportamiento actual vs objetivo, expresado como delta.

Ejemplo de respuesta útil:
Hoy los analistas abren cada cola para inferir riesgo. To-be: la lista muestra riesgo directamente para priorizar antes de abrir detalle.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-BACKLOG-SLICING-READINESS - Preparacion de slicing de backlog

- Lente: `product`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No estan explicitas las senales necesarias para slicing de backlog: primer slice de valor, paths, variantes, reglas diferibles o limites de historia.

Por qué importa (riesgo si queda abierto):
El backlog necesita saber cual es el primer slice de valor, que variantes pueden diferirse y donde no conviene cortar por debajo del valor.

Qué desbloquea esta respuesta:
El primer slice de valor y los límites de slicing del backlog.

Pregunta:
¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor?

Formato de respuesta esperado:
El primer slice de valor más qué se difiere y dónde no conviene cortar.

Ejemplo de respuesta útil:
Primer slice: usuario autorizado ve un caso de alto riesgo con datos vigentes. Diferir exportacion, bulk actions y reglas avanzadas. No dividir en crear boton/endpoint/tabla porque ninguna parte sola valida valor.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-FR-AC - Requerimientos funcionales y criterios de aceptacion

- Lente: `product`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Functional requirements are not decomposed with source-backed acceptance criteria.

Por qué importa (riesgo si queda abierto):
El PRD debe listar requerimientos funcionales con criterios de aceptacion trazables para que backlog y QA no inventen alcance.

Qué desbloquea esta respuesta:
La sección de Requerimientos Funcionales del PRD (FRs con criterios de aceptación).

Pregunta:
¿Qué información confirmada resuelve esta incertidumbre?

Formato de respuesta esperado:
FR-NN con statement EARS trazable (Cuando/Si/Mientras/Donde/El sistema debe...) más criterio de aceptación y prioridad.

Ejemplo de respuesta útil:
FR-01: el sistema debe listar elementos pendientes. AC: Given existen pendientes, When el operador consulta, Then ve ID, estado, responsable y fecha con fuente trazable.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-ACCEPTANCE - Señal de aceptación

- Lente: `quality`
- Severidad: `critical`
- Estado: `CLOSED`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Faltan criterios de aceptación o condiciones de éxito.

Por qué importa (riesgo si queda abierto):
Calidad e implementación necesitan condiciones observables para saber cuándo el requerimiento está terminado.

Qué desbloquea esta respuesta:
Los criterios de aceptación del PRD, las ACs de specs y los test cases de Calidad.

Pregunta:
¿Qué condiciones observables demuestran que el requerimiento está terminado?

Formato de respuesta esperado:
Uno o más enunciados EARS o Dado/Cuando/Entonces con condiciones observables. Ejemplo EARS: Cuando ocurre <disparador>, el sistema debe <respuesta observable>.

Ejemplo de respuesta útil:
Dado que una cola tiene casos por encima del umbral de SLA, cuando carga el dashboard, entonces la cola se marca como alto riesgo y el analista puede identificarla sin abrir el detalle.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-QUALITY - Expectativas de calidad

- Lente: `quality`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Las expectativas de calidad o testeabilidad no están explícitas.

Por qué importa (riesgo si queda abierto):
Las expectativas de calidad orientan el análisis de riesgo, la profundidad de pruebas y la evidencia requerida.

Qué desbloquea esta respuesta:
Los NFRs del PRD y la estrategia de handoff/testing de Calidad.

Pregunta:
¿Qué expectativas de calidad, testeabilidad, riesgo o compliance aplican?

Formato de respuesta esperado:
Expectativas de calidad como bullets: áreas de riesgo, profundidad de pruebas y evidencia requerida.

Ejemplo de respuesta útil:
QA debe cubrir happy path, sin datos, datos desactualizados, falla de servicio externo y permisos insuficientes.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-QUALITY-HANDOFF - Handoff de calidad

- Lente: `quality`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
El handoff a Calidad no está suficientemente explícito: flujos críticos, casos borde, datos de prueba, riesgos de regresión o evidencia esperada.

Por qué importa (riesgo si queda abierto):
QA necesita flujos críticos, casos borde, datos y expectativas de evidencia para profundizar cobertura.

Qué desbloquea esta respuesta:
Los test cases y el coverage map de Calidad.

Pregunta:
¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura?

Formato de respuesta esperado:
Flujos críticos, casos borde, datos de prueba y expectativas de evidencia.

Ejemplo de respuesta útil:
Tests críticos: alto riesgo, riesgo normal, datos de fuente desactualizados, permisos faltantes, cola vacía y regresión de filtros existentes.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-NFR-KPI - NFRs, KPIs y medicion

- Lente: `quality`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance.

Por qué importa (riesgo si queda abierto):
NFRs y KPIs con targets, metodo de medicion y ventana temporal permiten validar valor y calidad objetivamente.

Qué desbloquea esta respuesta:
La sección de NFRs y KPIs del PRD.

Pregunta:
¿Qué información confirmada resuelve esta incertidumbre?

Formato de respuesta esperado:
NFR/KPI con target, método de medición y ventana temporal.

Ejemplo de respuesta útil:
NFR: auditoria disponible por 2 anios. KPI: 0 operaciones incorrectas, medido por incidentes post-release diarios durante el primer mes.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-TECH-DATA-SOURCE - Sistemas y ownership de datos

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
La fuente de datos, integración u ownership de sistema no está explícito en el input o contexto técnico.

Por qué importa (riesgo si queda abierto):
Tecnología necesita suficiente contexto de sistemas y ownership para analizar arquitectura sin inventar integraciones.

Qué desbloquea esta respuesta:
La sección 5 del brief (técnica) y los boundaries de sistema y ownership de datos de specs.

Pregunta:
¿Qué sistemas, endpoints, eventos, decisiones de crear/modificar/reutilizar, owners, fuente de verdad y campos críticos están involucrados?

Formato de respuesta esperado:
Sistemas/endpoints involucrados, source of truth y equipo owner.

Ejemplo de respuesta útil:
Reutilizar `GET /queues`; modificarlo para incluir `slaRisk`. La fuente de verdad de riesgo es Case Management, owner Operations Platform.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-TECH-NFR - Restricciones operativas

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No están explícitas restricciones de performance, seguridad, observabilidad u operación.

Por qué importa (riesgo si queda abierto):
Las restricciones operativas afectan arquitectura, implementación, monitoreo y readiness de salida.

Qué desbloquea esta respuesta:
Los NFRs del PRD y la sección de restricciones operativas de specs.

Pregunta:
¿Qué restricciones de seguridad, performance, observabilidad, disponibilidad u operación aplican?

Formato de respuesta esperado:
NFRs nombrados con umbrales concretos (latencia, retención, disponibilidad) y cómo se observan.

Ejemplo de respuesta útil:
La respuesta del dashboard debe mantenerse debajo de 2 segundos p95. Loguear fallas de cálculo y exponer métricas de datos faltantes/desactualizados.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-BACKLOG-ENABLERS - Enablers transversales validos

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No estan claros los enablers transversales validos: trabajo de implementacion frontend/backend o arquitectura que debe construirse antes para soportar funcionalidades confirmadas dentro del boundary del proyecto.

Por qué importa (riesgo si queda abierto):
Los enablers transversales solo son validos si son implementacion previa/cross que soporta funcionalidad confirmada dentro del boundary del proyecto.

Qué desbloquea esta respuesta:
Los enablers transversales del backlog.

Pregunta:
¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica?

Formato de respuesta esperado:
Cada enabler con el boundary de capacidad que soporta y la evidencia objetiva de completitud.

Ejemplo de respuesta útil:
Enabler valido: soporte backend compartido para consultas de riesgo y permisos por rol del flujo, con validacion objetiva. No enabler: 'asegurar que una herramienta interna sea accesible'; eso es precondicion operacional.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-FRONTEND-SURFACE - Superficie frontend

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
La superficie de implementación frontend no está suficientemente explícita: pantallas, estados, validaciones, copy, roles o bindings de API.

Por qué importa (riesgo si queda abierto):
Frontend necesita superficies, estados, copy y bindings afectados antes de estimar o implementar responsablemente.

Qué desbloquea esta respuesta:
La superficie frontend de specs y el context pack Frontend / historias del backlog.

Pregunta:
¿Qué superficies frontend, roles, estados, validaciones, copy, analytics y bindings de API se ven afectados?

Formato de respuesta esperado:
Superficie(s) afectada(s), estados, validaciones, copy y eventos de analytics.

Ejemplo de respuesta útil:
Superficie afectada: dashboard diario de Operaciones. Agregar badge de riesgo, preservar filtros existentes, bindear `slaRisk` y trackear `risk_badge_clicked`.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-BACKEND-SURFACE - Superficie backend

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
La superficie de implementación backend no está suficientemente explícita: capacidades, integraciones, reglas, persistencia, contratos o comportamiento ante fallas.

Por qué importa (riesgo si queda abierto):
Backend necesita contexto de capacidades, integraciones, persistencia y comportamiento ante fallas antes de diseñar servicios.

Qué desbloquea esta respuesta:
La superficie backend de specs y el context pack Backend / historias del backlog.

Pregunta:
¿Qué capacidades backend, integraciones, reglas, persistencia/source of truth, contratos y comportamiento ante fallas se ven afectados?

Formato de respuesta esperado:
Capacidades, contratos, persistencia/source of truth y comportamiento ante fallas.

Ejemplo de respuesta útil:
Backend enriquece summaries de cola con SLA risk, maneja indisponibilidad de Case Management como `riskUnknown` y no persiste riesgo localmente.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-TECH-DEEP-DIVE-INPUT - Profundización técnica

- Lente: `technical`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Tecnología no cuenta con suficiente input para análisis de repositorios, arquitectura, endpoints/eventos, source of truth o riesgos.

Por qué importa (riesgo si queda abierto):
Los agentes técnicos necesitan dirección suficiente para inspeccionar repositorios, componentes, endpoints y riesgos eficientemente.

Qué desbloquea esta respuesta:
El context pack de Tecnología y la arquitectura de solución (SAD).

Pregunta:
¿Qué repositorios/componentes, preguntas de arquitectura, inventario de endpoints/eventos, dependencias y riesgos debería inspeccionar Tecnología?

Formato de respuesta esperado:
Repositorios/componentes, endpoints y source of truth a inspeccionar.

Ejemplo de respuesta útil:
Tecnología debe revisar `ops-dashboard-web`, `queue-summary-api` y documentación de integración de Case Management antes de proponer arquitectura.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-GOVERNANCE-CONSTRAINTS - Restricciones de gobernanza

- Lente: `compliance`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No están explícitas restricciones de gobernanza, seguridad, privacidad, compliance u operación.

Por qué importa (riesgo si queda abierto):
Seguridad, privacidad, compliance y auditoría pueden cambiar diseño, implementación y testing.

Qué desbloquea esta respuesta:
La sección 6 del brief (gobernanza) y la sección de gobernanza del PRD.

Pregunta:
¿Qué restricciones de seguridad, privacidad, compliance, auditoría u operación deben respetarse?

Formato de respuesta esperado:
Restricciones nombradas de seguridad/privacidad/compliance/auditoría que aplican.

Ejemplo de respuesta útil:
No agregar PII en la lista del dashboard. Logs de auditoría no deben incluir nombres de clientes ni números de documento.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-GLOSSARY-GOVERNANCE - Glosario y gobernanza

- Lente: `compliance`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD.

Por qué importa (riesgo si queda abierto):
Glosario, restricciones mandatorias, pending inputs y audit trail preservan entendimiento compartido y trazabilidad.

Qué desbloquea esta respuesta:
La sección de Gobernanza del PRD (glosario, restricciones, audit trail).

Pregunta:
¿Qué información confirmada resuelve esta incertidumbre?

Formato de respuesta esperado:
Términos de glosario, restricciones mandatorias y pending inputs con owner.

Ejemplo de respuesta útil:
Glosario: 'estado grisado' significa no operable. Restriccion: no exponer datos sensibles en logs. Pending input: owner de metrica.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-DELIVERY-READINESS - Preparación de delivery

- Lente: `delivery`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No están explícitas dependencias, ambientes, ownership, fechas o restricciones de rollout.

Por qué importa (riesgo si queda abierto):
Dependencias, owners, ambientes y fechas determinan secuencia y factibilidad de salida.

Qué desbloquea esta respuesta:
El plan de ejecución del PRD y la secuencia/rollout del backlog.

Pregunta:
¿Qué dependencias, ambientes, aprobaciones, owners, fechas o restricciones de rollout quedan pendientes?

Formato de respuesta esperado:
Dependencias con owners, ambientes, fechas y enfoque de rollout.

Ejemplo de respuesta útil:
Dependencia: Case Management debe exponer umbral de SLA antes del 15 de junio. Rollout con feature flag primero para supervisores de Operaciones.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-DEPENDENCIES-ROADMAP - Dependencias y roadmap

- Lente: `delivery`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning.

Por qué importa (riesgo si queda abierto):
Dependencias, owners, MVP y roadmap sostienen la planificacion y evitan historias bloqueadas por supuestos.

Qué desbloquea esta respuesta:
El plan de ejecución del PRD (dependencias, MVP, roadmap).

Pregunta:
¿Qué información confirmada resuelve esta incertidumbre?

Formato de respuesta esperado:
MVP, dependencias con owner y fases del roadmap.

Ejemplo de respuesta útil:
MVP: consulta, regla principal y auditoria. Dependencias: servicio X owner Equipo A, copy owner Diseno, credenciales owner Seguridad. Fase 2: reportes.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-PRD-ROLLOUT-ENVIRONMENTS - Rollout y ambientes

- Lente: `delivery`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning.

Por qué importa (riesgo si queda abierto):
Rollout, ambientes y restricciones de release evitan que specs y backlog inventen secuencia o condiciones de salida.

Qué desbloquea esta respuesta:
El plan de ejecución del PRD (rollout, ambientes y restricciones de release).

Pregunta:
¿Qué ambientes, estrategia de rollout, restricciones de release y criterio de rollback deben quedar confirmados en el PRD?

Formato de respuesta esperado:
Ambientes objetivo, estrategia de rollout, restricciones de release y criterio de rollback.

Ejemplo de respuesta útil:
Rollout: feature flag primero en ambiente staging, luego piloto con supervisores. Produccion requiere ventana aprobada y plan de rollback.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-DESIGN-FLOW - Journey y pantallas

- Lente: `design`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
El journey de usuario, flujo de pantallas o modelo de interacción no está explícito en el input o contexto de diseño.

Por qué importa (riesgo si queda abierto):
Diseño necesita journeys y pantallas afectadas para crear flujos o prototipos significativos.

Qué desbloquea esta respuesta:
La sección 4 del brief (diseño), los flujos UX de specs y el context pack de Diseño.

Pregunta:
¿Qué journey, pantallas, flujos, copy o cambios de interacción están dentro del alcance?

Formato de respuesta esperado:
Punto de entrada y journey paso a paso hasta la(s) pantalla(s) afectada(s).

Ejemplo de respuesta útil:
El indicador aparece en la lista del dashboard diario. Los usuarios entran por Home > Operaciones > Colas diarias y deciden qué cola revisar primero.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-DESIGN-STATES - Estados de UX

- Lente: `design`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No están explícitos los estados requeridos de UI: loading, empty, error y recuperación.

Por qué importa (riesgo si queda abierto):
Los estados UX faltantes suelen convertirse en ambigüedad de implementación o casos borde sin testear.

Qué desbloquea esta respuesta:
Los estados UX de specs y la cobertura de casos borde de Calidad.

Pregunta:
¿Qué estados de loading, empty, error, recuperación y accesibilidad deben contemplarse?

Formato de respuesta esperado:
Los estados de carga, vacío, error y recuperación de la superficie.

Ejemplo de respuesta útil:
Mostrar skeleton durante carga, estado neutral sin colas, warning para datos desactualizados y error genérico existente ante fallas de servicio.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


### GAP-DESIGN-PROTOTYPE-INPUT - Foco del prototipo

- Lente: `design`
- Severidad: `medium`
- Estado: `OPEN`
- Requerimiento relacionado: `REQ-001`

Descripción breve:
No queda claro qué debe prototipar o validar Diseño en los flujos de usuario.

Por qué importa (riesgo si queda abierto):
Un prototipo solo es útil si Diseño sabe qué decisión, flujo o interacción debe validar.

Qué desbloquea esta respuesta:
El context pack de Diseño y el alcance del prototipo.

Pregunta:
¿Qué debería prototipar o validar Diseño, y qué usuarios, momentos del journey, estados y referencias visuales deberían guiarlo?

Formato de respuesta esperado:
La decisión/flujo/interacción que el prototipo debe validar.

Ejemplo de respuesta útil:
Prototipar la lista del dashboard con estados normal, alto riesgo, datos desactualizados y vacío para validar escaneabilidad con analistas.


Respuesta del cliente / dominio:

- Respuesta:
- Owner / fuente:
- Evidencia o referencia:
- Estado de decisión:


## Notas adicionales

Agregar cualquier nuevo requerimiento, restricción, decisión, screenshot, diagrama o ejemplo que no haya quedado cubierto arriba.

## Tabla de trazabilidad del framework

Esta tabla se mantiene para trazabilidad y procesamiento automático de Sentinel.

| Gap ID | Lente | Severidad | Estado | Padre | Descripción | Pregunta para cliente/dominio | Fuente consultada | Disparador detectado | Origen | Nota de resolución | Unidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-BUSINESS-RULES | business | medium | OPEN | `REQ-001` | Las reglas de negocio, exclusiones o reglas de decisión no están suficientemente explícitas para slicing downstream. | ¿Qué reglas, excepciones, validaciones, fallbacks o exclusiones gobiernan el comportamiento? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-PERSONA-DETAIL | business | medium | OPEN | `REQ-001` | Persona attributes are not complete enough for a PRD: goals, pain points, proficiency, and usage frequency are unclear. | ¿Qué información confirmada resuelve esta incertidumbre? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-METRIC-SOURCE | business | medium | OPEN | `REQ-001` | Aparece una métrica cuantitativa sin fuente o baseline explícito. | ¿Cuál es la fuente o baseline de la métrica cuantitativa? | Carpetas de contexto e input fuente. | 30 por ciento | checklist | N/A | RU-003 |
| GAP-METRIC-DEFINITION | business | medium | OPEN | `REQ-001` | Se nombra una métrica, KPI o indicador sin su definición, fórmula, unidad, fuente ni umbral. | ¿Cómo se define cada métrica/KPI (fórmula, unidad), de qué fuente sale y cuál es su baseline y umbral objetivo? | Carpetas de contexto e input fuente. | metrica | checklist | N/A | RU-003 |
| GAP-PRODUCT-ASIS-TOBE | product | medium | OPEN | `REQ-001` | El estado actual y el estado objetivo no están suficientemente claros para comparar impacto. | ¿Cuál es el proceso actual, el proceso objetivo y el delta exacto entre ambos? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-BACKLOG-SLICING-READINESS | product | medium | OPEN | `REQ-001` | No estan explicitas las senales necesarias para slicing de backlog: primer slice de valor, paths, variantes, reglas diferibles o limites de historia. | ¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-FR-AC | product | medium | OPEN | `REQ-001` | Functional requirements are not decomposed with source-backed acceptance criteria. | ¿Qué información confirmada resuelve esta incertidumbre? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-ACCEPTANCE | quality | critical | CLOSED | `REQ-001` | Faltan criterios de aceptación o condiciones de éxito. | ¿Qué condiciones observables demuestran que el requerimiento está terminado? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-QUALITY | quality | medium | OPEN | `REQ-001` | Las expectativas de calidad o testeabilidad no están explícitas. | ¿Qué expectativas de calidad, testeabilidad, riesgo o compliance aplican? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-QUALITY-HANDOFF | quality | medium | OPEN | `REQ-001` | El handoff a Calidad no está suficientemente explícito: flujos críticos, casos borde, datos de prueba, riesgos de regresión o evidencia esperada. | ¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-NFR-KPI | quality | medium | OPEN | `REQ-001` | NFRs, KPIs, targets, measurement method, or timeframe are not explicit enough for PRD governance. | ¿Qué información confirmada resuelve esta incertidumbre? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-TECH-DATA-SOURCE | technical | medium | OPEN | `REQ-001` | La fuente de datos, integración u ownership de sistema no está explícito en el input o contexto técnico. | ¿Qué sistemas, endpoints, eventos, decisiones de crear/modificar/reutilizar, owners, fuente de verdad y campos críticos están involucrados? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-TECH-NFR | technical | medium | OPEN | `REQ-001` | No están explícitas restricciones de performance, seguridad, observabilidad u operación. | ¿Qué restricciones de seguridad, performance, observabilidad, disponibilidad u operación aplican? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-BACKLOG-ENABLERS | technical | medium | OPEN | `REQ-001` | No estan claros los enablers transversales validos: trabajo de implementacion frontend/backend o arquitectura que debe construirse antes para soportar funcionalidades confirmadas dentro del boundary del proyecto. | ¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-FRONTEND-SURFACE | technical | medium | OPEN | `REQ-001` | La superficie de implementación frontend no está suficientemente explícita: pantallas, estados, validaciones, copy, roles o bindings de API. | ¿Qué superficies frontend, roles, estados, validaciones, copy, analytics y bindings de API se ven afectados? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-BACKEND-SURFACE | technical | medium | OPEN | `REQ-001` | La superficie de implementación backend no está suficientemente explícita: capacidades, integraciones, reglas, persistencia, contratos o comportamiento ante fallas. | ¿Qué capacidades backend, integraciones, reglas, persistencia/source of truth, contratos y comportamiento ante fallas se ven afectados? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-TECH-DEEP-DIVE-INPUT | technical | medium | OPEN | `REQ-001` | Tecnología no cuenta con suficiente input para análisis de repositorios, arquitectura, endpoints/eventos, source of truth o riesgos. | ¿Qué repositorios/componentes, preguntas de arquitectura, inventario de endpoints/eventos, dependencias y riesgos debería inspeccionar Tecnología? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-GOVERNANCE-CONSTRAINTS | compliance | medium | OPEN | `REQ-001` | No están explícitas restricciones de gobernanza, seguridad, privacidad, compliance u operación. | ¿Qué restricciones de seguridad, privacidad, compliance, auditoría u operación deben respetarse? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-GLOSSARY-GOVERNANCE | compliance | medium | OPEN | `REQ-001` | Glossary, mandatory constraints, pending inputs, or governance/audit notes are not explicit enough for a complete PRD. | ¿Qué información confirmada resuelve esta incertidumbre? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-DELIVERY-READINESS | delivery | medium | OPEN | `REQ-001` | No están explícitas dependencias, ambientes, ownership, fechas o restricciones de rollout. | ¿Qué dependencias, ambientes, aprobaciones, owners, fechas o restricciones de rollout quedan pendientes? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-DEPENDENCIES-ROADMAP | delivery | medium | OPEN | `REQ-001` | Dependencies, owners, MVP scope, nice-to-haves, or roadmap are not explicit enough for PRD execution planning. | ¿Qué información confirmada resuelve esta incertidumbre? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-PRD-ROLLOUT-ENVIRONMENTS | delivery | medium | OPEN | `REQ-001` | Rollout approach, target environments, or release constraints are not explicit enough for PRD execution planning. | ¿Qué ambientes, estrategia de rollout, restricciones de release y criterio de rollback deben quedar confirmados en el PRD? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-DESIGN-FLOW | design | medium | OPEN | `REQ-001` | El journey de usuario, flujo de pantallas o modelo de interacción no está explícito en el input o contexto de diseño. | ¿Qué journey, pantallas, flujos, copy o cambios de interacción están dentro del alcance? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-DESIGN-STATES | design | medium | OPEN | `REQ-001` | No están explícitos los estados requeridos de UI: loading, empty, error y recuperación. | ¿Qué estados de loading, empty, error, recuperación y accesibilidad deben contemplarse? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |
| GAP-DESIGN-PROTOTYPE-INPUT | design | medium | OPEN | `REQ-001` | No queda claro qué debe prototipar o validar Diseño en los flujos de usuario. | ¿Qué debería prototipar o validar Diseño, y qué usuarios, momentos del journey, estados y referencias visuales deberían guiarlo? | Carpetas de contexto e input fuente. | N/A | checklist | N/A | N/A |

## Trazabilidad de resolución

| Gap ID | Fuente de resolución | Seed promovida | Artefactos impactados |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |
