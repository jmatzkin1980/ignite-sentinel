### HU-01
- Tratamiento: requisito
- Cita: "quiero enviar un alta a aprobación para no imprimir el resumen"
- Enunciado: Cuando el analista envía un alta con monto mayor al umbral, el sistema debe pasarla a la bandeja de aprobaciones.
  - Delta: ADDED
  - Superficie: Bandeja de aprobaciones

### RN-02
- Tratamiento: requisito
- Cita: "requiere aprobación de la jefa de Compras"
- Enunciado: Cuando el analista envía un alta con monto anual estimado mayor al umbral, el sistema debe dejarla Pendiente de aprobación.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Enunciado: Mientras un alta está Pendiente de aprobación, el sistema debe impedir órdenes de compra a ese proveedor.
  - Delta: ADDED
  - Superficie: Tabla de proveedores

### RN-04
- Tratamiento: requisito
- Cita: "La jefa de Compras no puede aprobar un alta que cargó ella misma."
- Enunciado: Si la jefa de Compras intenta aprobar un alta que cargó ella misma, el sistema debe impedirlo.
  - Delta: ADDED
  - Superficie: Aprobación por monto
- Marca: contradiccion — el SAD permite que una jefatura apruebe sus propias altas

### SEC-objetivo
- Tratamiento: seccion
- Seccion: objetivo
- Texto: Que la jefatura apruebe las altas de monto alto dentro del sistema y el analista vea el estado sin preguntar.
- Cita: "la jefatura aprueba las altas de monto alto dentro del sistema"

### RN-06
- Tratamiento: descarte
- Motivo: es una exclusión de alcance y ya está en la respuesta de GAP-SCOPE
- Cita: "Los proveedores del exterior quedan fuera de este cambio."
