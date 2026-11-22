### GAP-OBJECTIVE
- Respuesta: Que el analista de Compras pueda guardar lo cargado en el alta de proveedores aunque esté incompleta, y retomarla después para terminar el registro sin perder datos.
- Owner / fuente: Jefa de Compras
- Evidencia o referencia: taller de Compras, 2026-11-18
- Estado de decisión: confirmado

### GAP-USERS
- Respuesta: Los analistas de Compras que cargan altas de proveedores en el backoffice; la Jefa de Compras revisa las altas pendientes de su equipo.
- Owner / fuente: Jefa de Compras
- Evidencia o referencia: taller de Compras, 2026-11-18
- Estado de decisión: confirmado

### GAP-ACCEPTANCE
- Respuesta: Cuando el analista guarda un alta incompleta, el sistema debe conservar los datos cargados. Cuando el analista abre la lista de altas incompletas, el sistema debe listar sus altas guardadas.
- Owner / fuente: Jefa de Compras
- Evidencia o referencia: taller de Compras, 2026-11-18
- Delta: ADDED
- Superficie: Botón "Guardar borrador" en el alta de proveedores; Listado "Mis borradores"
- Estado de decisión: confirmado

### GAP-BUSINESS-RULES
- Respuesta: Si un borrador tiene más de 30 días, el sistema debe eliminarlo.
- Owner / fuente: Jefa de Compras
- Evidencia o referencia: taller de Compras, 2026-11-18
- Delta: ADDED
- Superficie: Tabla de proveedores
- Estado de decisión: confirmado

### GAP-PRODUCT-ASIS-TOBE
- Respuesta: Cuando el usuario envía un alta completa, el sistema debe continuar validando todos los campos obligatorios.
- Owner / fuente: Jefa de Compras
- Evidencia o referencia: taller de Compras, 2026-11-18
- Delta: UNCHANGED
- Superficie: Envío actual del alta de proveedores
- Estado de decisión: confirmado
