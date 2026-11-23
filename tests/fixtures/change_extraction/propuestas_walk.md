### SEC-objetivo
- Tratamiento: seccion
- Seccion: objetivo
- Texto: Que la jefatura apruebe las altas de monto alto dentro del sistema y el analista vea el estado sin preguntar.
- Cita: "la jefatura aprueba las altas de monto alto dentro del sistema"

### SEC-usuarios
- Tratamiento: seccion
- Seccion: usuarios
- Texto: Analista de Compras, jefa de Compras y auditor interno.
- Cita: "Jefa de Compras: aprueba o rechaza las altas de monto alto."

### SEC-situacion-actual-y-estado-futuro
- Tratamiento: seccion
- Seccion: proceso
- Texto: La aprobación queda registrada en el sistema con usuario y fecha.
- Cita: "la aprobación queda registrada en el sistema con usuario y fecha"

### SEC-proceso
- Tratamiento: seccion
- Seccion: proceso
- Texto: El sistema calcula el monto anual estimado y, si supera el umbral, envía el alta a la jefa de Compras.
- Cita: "El sistema calcula el monto anual estimado de compras."

### SEC-fuera-de-alcance
- Tratamiento: seccion
- Seccion: alcance
- Texto: Queda fuera la migración de las altas históricas en papel.
- Cita: "La migración de las altas históricas en papel."

### HU-01
- Tratamiento: requisito
- Cita: "quiero enviar un alta a aprobación para no imprimir el resumen"
- Enunciado: Cuando el analista envía un alta con monto mayor al umbral, el sistema debe pasarla a la bandeja de aprobaciones.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### HU-02
- Tratamiento: requisito
- Cita: "quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas"
- Enunciado: Mientras un alta está pendiente de aprobación, la bandeja de aprobaciones debe mostrarla a la jefa de Compras.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### HU-03
- Tratamiento: requisito
- Cita: "quiero consultar quién aprobó cada alta y cuándo"
- Enunciado: Cuando el auditor consulta un alta aprobada, el sistema debe mostrar quién la aprobó y cuándo.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-02
- Tratamiento: requisito
- Cita: "requiere aprobación de la jefa de Compras"
- Enunciado: Cuando el analista envía un alta con monto anual estimado mayor al umbral, el sistema debe dejarla Pendiente de aprobación.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Enunciado: Mientras un alta está Pendiente de aprobación, el sistema debe impedir órdenes de compra a ese proveedor.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-03
- Tratamiento: requisito
- Cita: "queda en estado Rechazada con su motivo"
- Enunciado: Si la jefa rechaza un alta, el sistema debe conservarla en estado Rechazada con su motivo.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-04
- Tratamiento: requisito
- Cita: "La jefa de Compras no puede aprobar un alta que cargó ella misma."
- Enunciado: Si la jefa de Compras intenta aprobar un alta que cargó ella misma, el sistema debe impedirlo.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Marca: contradiccion — el SAD permite que una jefatura apruebe sus propias altas

### RN-05
- Tratamiento: requisito
- Cita: "por más de 5 días hábiles se notifica a la gerencia de Compras"
- Enunciado: Si un alta sigue pendiente más de 5 días hábiles, el sistema debe notificar a la gerencia de Compras.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### RN-06
- Tratamiento: descarte
- Motivo: es una exclusión de alcance y ya está en la respuesta de GAP-SCOPE
- Cita: "Los proveedores del exterior quedan fuera de este cambio."

### CA-01
- Tratamiento: seccion
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces el sistema la rechaza y nombra al proveedor existente.
- Cita: "entonces el sistema la rechaza y nombra al proveedor existente"

### CA-02
- Tratamiento: seccion
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces queda Pendiente de aprobación y no habilita órdenes de compra.
- Cita: "entonces queda Pendiente de aprobación y no habilita órdenes de compra"

### CA-03
- Tratamiento: seccion
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces el proveedor queda habilitado y se registran usuario y fecha.
- Cita: "entonces el proveedor queda habilitado y se registran usuario y fecha"

### CA-04
- Tratamiento: seccion
- Seccion: aceptacion
- Texto: Criterio de aceptación: entonces ve el motivo del rechazo.
- Cita: "entonces ve el motivo del rechazo"

### CA-05
- Tratamiento: seccion
- Seccion: aceptacion
- Texto: Criterio de aceptación: el sistema lo rechaza.
- Cita: "el sistema lo rechaza"

### PD-01
- Tratamiento: seccion
- Seccion: reglas
- Texto: El umbral de aprobación se configura por parámetro y arranca en 5.000.000.
- Cita: "El umbral de aprobación se configura por parámetro y arranca en 5.000.000."

### PD-02
- Tratamiento: descarte
- Motivo: es una decisión de operación, no un requisito del cambio
- Cita: "La notificación a la gerencia se envía por correo interno"

### SEC-se-preserva
- Tratamiento: requisito
- Cita: "El alta de proveedores con monto menor o igual al umbral sigue habilitándose en el acto"
- Enunciado: Cuando el analista envía un alta con monto menor o igual al umbral, el sistema debe continuar habilitándola en el acto.
  - Delta: UNCHANGED
  - Superficie: Alta de monto bajo
