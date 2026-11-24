### SEC-objetivo
- Tratamiento: seccion
- Líneas: 4-4
- Seccion: objetivo
- Texto: Que la jefatura apruebe las altas de monto alto dentro del sistema y el analista vea el estado sin preguntar.
- Cita: "la jefatura aprueba las altas de monto alto dentro del sistema"

### SEC-usuarios
- Tratamiento: seccion
- Líneas: 7-9
- Seccion: usuarios
- Texto: Analista de Compras, jefa de Compras y auditor interno.
- Cita: "Jefa de Compras: aprueba o rechaza las altas de monto alto."

### SEC-situacion-actual-y-estado-futuro
- Tratamiento: seccion
- Líneas: 12-12
- Seccion: proceso
- Texto: La aprobación queda registrada en el sistema con usuario y fecha.
- Cita: "la aprobación queda registrada en el sistema con usuario y fecha"

### SEC-proceso
- Tratamiento: seccion
- Líneas: 15-18
- Seccion: proceso
- Texto: El sistema calcula el monto anual estimado y, si supera el umbral, envía el alta a la jefa de Compras.
- Cita: "El sistema calcula el monto anual estimado de compras."

### SEC-fuera-de-alcance
- Tratamiento: seccion
- Líneas: 52-52
- Seccion: alcance
- Texto: Queda fuera la migración de las altas históricas en papel.
- Cita: "La migración de las altas históricas en papel."

### HU-01
- Tratamiento: requisito
- Líneas: 21-21
- Cita: "quiero enviar un alta a aprobación para no imprimir el resumen"
- Enunciado: Cuando el analista envía un alta con monto mayor al umbral, el sistema debe pasarla a la bandeja de aprobaciones.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### HU-02
- Tratamiento: requisito
- Líneas: 22-22
- Cita: "quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas"
- Enunciado: Mientras un alta está pendiente de aprobación, la bandeja de aprobaciones debe mostrarla a la jefa de Compras.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### HU-03
- Tratamiento: requisito
- Líneas: 24-25
- Cita: "quiero consultar quién aprobó cada alta y cuándo"
- Enunciado: Cuando el auditor consulta un alta aprobada, el sistema debe mostrar quién la aprobó y cuándo.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-01
- Tratamiento: requisito
- Líneas: 30-30
- Cita: "un CUIT duplicado se rechaza nombrando al proveedor existente"
- Enunciado: El sistema debe continuar rechazando un CUIT duplicado y nombrar al proveedor existente.
  - Delta: UNCHANGED
  - Superficie: Validación de CUIT

### RN-02
- Tratamiento: requisito
- Líneas: 31-31
- Cita: "requiere aprobación de la jefa de Compras"
- Enunciado: Cuando el analista envía un alta con monto anual estimado mayor al umbral, el sistema debe dejarla Pendiente de aprobación.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Enunciado: Mientras un alta está Pendiente de aprobación, el sistema debe impedir órdenes de compra a ese proveedor.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-03
- Tratamiento: requisito
- Líneas: 32-32
- Cita: "queda en estado Rechazada con su motivo"
- Enunciado: Si la jefa rechaza un alta, el sistema debe conservarla en estado Rechazada con su motivo.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-04
- Tratamiento: requisito
- Líneas: 33-33
- Cita: "La jefa de Compras no puede aprobar un alta que cargó ella misma."
- Enunciado: Si la jefa de Compras intenta aprobar un alta que cargó ella misma, el sistema debe impedirlo.
  - Delta: ADDED
  - Superficie: Aprobación por monto

### RN-05
- Tratamiento: requisito
- Líneas: 34-34
- Cita: "por más de 5 días hábiles se notifica a la gerencia de Compras"
- Enunciado: Si un alta sigue pendiente más de 5 días hábiles, el sistema debe notificar a la gerencia de Compras.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### RN-06
- Tratamiento: descarte
- Líneas: 35-35
- Motivo: es una exclusión de alcance y ya está en la respuesta de GAP-SCOPE
- Cita: "Los proveedores del exterior quedan fuera de este cambio."

### CA-01
- Tratamiento: seccion
- Líneas: 38-38
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces el sistema la rechaza y nombra al proveedor existente.
- Cita: "entonces el sistema la rechaza y nombra al proveedor existente"

### CA-02
- Tratamiento: seccion
- Líneas: 39-39
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces queda Pendiente de aprobación y no habilita órdenes de compra.
- Cita: "entonces queda Pendiente de aprobación y no habilita órdenes de compra"

### CA-03
- Tratamiento: seccion
- Líneas: 40-40
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces el proveedor queda habilitado y se registran usuario y fecha.
- Cita: "entonces el proveedor queda habilitado y se registran usuario y fecha"

### CA-04
- Tratamiento: seccion
- Líneas: 41-41
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces ve el motivo del rechazo.
- Cita: "entonces ve el motivo del rechazo"

### CA-05
- Tratamiento: seccion
- Líneas: 42-42
- Seccion: aceptacion
- Texto: Criterio de aceptación: el sistema no lo permite.
- Cita: "el sistema no lo permite"

### PD-01
- Tratamiento: seccion
- Líneas: 45-45
- Seccion: reglas
- Texto: El umbral de aprobación se configura por parámetro y arranca en 5.000.000.
- Cita: "El umbral de aprobación se configura por parámetro y arranca en 5.000.000."

### PD-02
- Tratamiento: descarte
- Líneas: 46-46
- Motivo: es una decisión de operación, no un requisito del cambio
- Cita: "La notificación a la gerencia se envía por correo interno"

### SEC-se-preserva
- Tratamiento: requisito
- Líneas: 49-49
- Cita: "El alta de proveedores con monto menor o igual al umbral sigue habilitándose en el acto"
- Enunciado: Cuando el analista envía un alta con monto menor o igual al umbral, el sistema debe continuar habilitándola en el acto.
  - Delta: UNCHANGED
  - Superficie: Alta de monto bajo

### SEC-proceso-to-be-detallado.p1
- Tratamiento: seccion
- Líneas: 55-57
- Seccion: proceso
- Cita: "El alta nace en estado Borrador cuando el analista guarda los datos por primera vez"

### SEC-proceso-to-be-detallado.p2
- Tratamiento: seccion
- Líneas: 59-68
- Seccion: proceso
- Cita: "El analista abre el alta en Borrador y completa los datos fiscales"

### SEC-proceso-to-be-detallado.p3
- Tratamiento: seccion
- Líneas: 80-83
- Lectura: parcial
- Seccion: proceso
- Cita: "Las transiciones posibles entre estados son las de la tabla siguiente"

### SEC-proceso-to-be-detallado.p4
- Tratamiento: seccion
- Líneas: 85-98
- Seccion: proceso
- Cita: "Enviar con monto menor o igual al umbral"
