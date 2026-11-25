### RN-01
- Tratamiento: requisito
- Líneas: 56-56
- Cita: "El CUIT del proveedor debe ser único"
- Enunciado: Cuando el analista envía un alta con un CUIT ya registrado, el sistema debe rechazarla nombrando al proveedor existente.
- Marca: contradiccion — el prototipo valida el CUIT sin consultar si ya existe

### RN-03
- Tratamiento: requisito
- Líneas: 58-58
- Cita: "Un alta con monto anual estimado mayor a 5.000.000 requiere doble aprobación."
- Enunciado: Cuando el analista envía un alta con monto anual estimado mayor a 5.000.000, el sistema debe pedir doble aprobación.
- Marca: contradiccion — el criterio CA-03 fija el umbral en 3.000.000

### RN-04
- Tratamiento: requisito
- Líneas: 59-59
- Cita: "La jefa de Compras no puede aprobar un alta que cargó ella misma."
- Enunciado: Si la jefa de Compras intenta aprobar un alta que cargó ella misma, el sistema debe impedirlo.
- Marca: contradiccion — el prototipo no distingue quién cargó el alta

### RN-05
- Tratamiento: descarte
- Líneas: 60-60
- Motivo: la notificación a la gerencia ya se decide aparte
- Cita: "se notifica a la gerencia de Compras"
