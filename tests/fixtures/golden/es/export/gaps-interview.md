# Guion de entrevista - [PROJECT_ID]

Vista derivada READ-ONLY de los gaps abiertos, ordenada como guion de reunion (gaps bloqueantes primero, agrupados por lente). Las preguntas de profundizacion salen de las opciones candidatas citadas (IMP-113); nunca se inventan. Este guion NO reemplaza a `01_discovery/gaps.md` (la fuente de verdad) y no cierra ningun gap.


## Preguntas de seguimiento

### business

1. Reglas de negocio (`GAP-BUSINESS-RULES`, severidad `medium`, lente `business`)

- Preguntar: ¿Qué reglas, excepciones, validaciones, fallbacks o exclusiones gobiernan el comportamiento?

2. Definición de métrica (`GAP-METRIC-DEFINITION`, severidad `medium`, lente `business`)

- Contexto citado: El input menciona "metrica" pero no define la métrica: falta fórmula/unidad, fuente o umbral.
- Preguntar: ¿Cómo se define cada métrica/KPI (fórmula, unidad), de qué fuente sale y cuál es su baseline y umbral objetivo?
- Preguntas de profundizacion:
  - Confirmar que `metrica` esta dentro del alcance y responder el detalle faltante de `Definición de métrica`. Cita local: `metrica`.
  - Confirmar que `metrica` es solo contexto, fuera de alcance o pendiente, y explicitar el limite. Cita local: `metrica`.

3. Fuente de métrica (`GAP-METRIC-SOURCE`, severidad `medium`, lente `business`)

- Contexto citado: La métrica "30 por ciento" aparece sin fuente, baseline ni método de medición.
- Preguntar: ¿Cuál es la fuente o baseline de la métrica cuantitativa?
- Preguntas de profundizacion:
  - Confirmar que `30 por ciento` es la meta de exito y aportar fuente, baseline, owner y metodo de medicion. Cita local: `30 por ciento`.
  - Tratar `30 por ciento` como objetivo direccional hasta confirmar fuente/baseline, indicando que evidencia falta. Cita local: `30 por ciento`.

4. Detalle de personas para PRD (`GAP-PRD-PERSONA-DETAIL`, severidad `medium`, lente `business`)

- Preguntar: ¿Qué información confirmada resuelve esta incertidumbre?

### compliance

5. Restricciones de gobernanza (`GAP-GOVERNANCE-CONSTRAINTS`, severidad `medium`, lente `compliance`)

- Preguntar: ¿Qué restricciones de seguridad, privacidad, compliance, auditoría u operación deben respetarse?

6. Glosario y gobernanza (`GAP-PRD-GLOSSARY-GOVERNANCE`, severidad `medium`, lente `compliance`)

- Preguntar: ¿Qué información confirmada resuelve esta incertidumbre?

### delivery

7. Preparación de delivery (`GAP-DELIVERY-READINESS`, severidad `medium`, lente `delivery`)

- Preguntar: ¿Qué dependencias, ambientes, aprobaciones, owners, fechas o restricciones de rollout quedan pendientes?

8. Dependencias y roadmap (`GAP-PRD-DEPENDENCIES-ROADMAP`, severidad `medium`, lente `delivery`)

- Preguntar: ¿Qué información confirmada resuelve esta incertidumbre?

9. Rollout y ambientes (`GAP-PRD-ROLLOUT-ENVIRONMENTS`, severidad `medium`, lente `delivery`)

- Preguntar: ¿Qué ambientes, estrategia de rollout, restricciones de release y criterio de rollback deben quedar confirmados en el PRD?

### design

10. Journey y pantallas (`GAP-DESIGN-FLOW`, severidad `medium`, lente `design`)

- Preguntar: ¿Qué journey, pantallas, flujos, copy o cambios de interacción están dentro del alcance?

11. Foco del prototipo (`GAP-DESIGN-PROTOTYPE-INPUT`, severidad `medium`, lente `design`)

- Preguntar: ¿Qué debería prototipar o validar Diseño, y qué usuarios, momentos del journey, estados y referencias visuales deberían guiarlo?

12. Estados de UX (`GAP-DESIGN-STATES`, severidad `medium`, lente `design`)

- Preguntar: ¿Qué estados de loading, empty, error, recuperación y accesibilidad deben contemplarse?

### product

13. Preparacion de slicing de backlog (`GAP-BACKLOG-SLICING-READINESS`, severidad `medium`, lente `product`)

- Preguntar: ¿Cuál es el primer slice de valor observable, qué variantes o reglas pueden diferirse y dónde cortar más pequeño dejaría de aportar valor?

14. Requerimientos funcionales y criterios de aceptacion (`GAP-PRD-FR-AC`, severidad `medium`, lente `product`)

- Preguntar: ¿Qué información confirmada resuelve esta incertidumbre?

15. Proceso actual y objetivo (`GAP-PRODUCT-ASIS-TOBE`, severidad `medium`, lente `product`)

- Preguntar: ¿Cuál es el proceso actual, el proceso objetivo y el delta exacto entre ambos?

### quality

16. NFRs, KPIs y medicion (`GAP-PRD-NFR-KPI`, severidad `medium`, lente `quality`)

- Preguntar: ¿Qué información confirmada resuelve esta incertidumbre?

17. Expectativas de calidad (`GAP-QUALITY`, severidad `medium`, lente `quality`)

- Preguntar: ¿Qué expectativas de calidad, testeabilidad, riesgo o compliance aplican?

18. Handoff de calidad (`GAP-QUALITY-HANDOFF`, severidad `medium`, lente `quality`)

- Preguntar: ¿Qué flujos críticos, casos borde, datos de prueba, riesgos de regresión y evidencia esperada debería usar Calidad para profundizar cobertura?

### technical

19. Superficie backend (`GAP-BACKEND-SURFACE`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué capacidades backend, integraciones, reglas, persistencia/source of truth, contratos y comportamiento ante fallas se ven afectados?

20. Enablers transversales validos (`GAP-BACKLOG-ENABLERS`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué enablers transversales de implementación frontend/backend o arquitectura deben construirse antes para soportar esta funcionalidad, qué scope habilitan y cómo se distinguen de una precondición operacional genérica?

21. Superficie frontend (`GAP-FRONTEND-SURFACE`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué superficies frontend, roles, estados, validaciones, copy, analytics y bindings de API se ven afectados?

22. Sistemas y ownership de datos (`GAP-TECH-DATA-SOURCE`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué sistemas, endpoints, eventos, decisiones de crear/modificar/reutilizar, owners, fuente de verdad y campos críticos están involucrados?

23. Profundización técnica (`GAP-TECH-DEEP-DIVE-INPUT`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué repositorios/componentes, preguntas de arquitectura, inventario de endpoints/eventos, dependencias y riesgos debería inspeccionar Tecnología?

24. Restricciones operativas (`GAP-TECH-NFR`, severidad `medium`, lente `technical`)

- Preguntar: ¿Qué restricciones de seguridad, performance, observabilidad, disponibilidad u operación aplican?
