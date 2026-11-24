# Cruce pedido ↔ diseño nuevo — CHG-001

- [RESPALDADO] La bandeja de la jefa de Compras está en el prototipo.
  - Pedido: F-PED "quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas"
  - Diseño: F-DIS "Bandeja de aprobaciones"
- [RESPALDADO] El rechazo con motivo tiene su campo en el detalle del alta.
  - Pedido: F-PED "La jefa aprueba o rechaza con un motivo"
  - Diseño: F-DIS "Motivo del rechazo"
- [SIN RESPALDO EN DISEÑO] El historial que consulta el auditor no tiene pantalla en el prototipo.
  - Pedido: F-PED "quiero consultar quién aprobó cada alta y cuándo"
- [SOLO EN DISEÑO] El prototipo permite delegar las aprobaciones y el pedido no lo menciona.
  - Diseño: F-DIS "Delegar aprobaciones"
- [DIVERGENCIA] El pedido fija el umbral en 5.000.000 y el prototipo muestra 1.000.000.
  - Pedido: F-PED "mayor a 5.000.000 requiere aprobación de la jefa de Compras"
  - Diseño: F-DIS "Umbral de aprobación: 1.000.000"
- [DIVERGENCIA] El pedido exige que apruebe la jefa de Compras y el prototipo permite delegar la aprobación.
  - Pedido: F-PED "Un alta con monto anual estimado mayor a 5.000.000"
  - Diseño: F-DIS "Delegar aprobaciones"
