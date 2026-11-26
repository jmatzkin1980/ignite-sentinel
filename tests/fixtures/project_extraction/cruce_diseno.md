# Cruce pedido ↔ diseño nuevo

- [RESPALDADO] El historial que consulta el auditor está en el prototipo.
  - Pedido: F-PED "quiero consultar quién aprobó cada alta y cuándo"
  - Diseño: F-DIS "Historial del alta"
- [SIN RESPALDO EN DISEÑO] La bandeja de la jefa de Compras no tiene pantalla en el prototipo.
  - Pedido: F-PED "quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas"
- [DIVERGENCIA] El pedido fija el umbral en 5.000.000 (PD-01 pidió a Diseño ajustarlo) y el prototipo muestra 3.000.000.
  - Pedido: F-PED "Un alta con monto anual estimado mayor a 5.000.000 requiere doble aprobación."
  - Diseño: F-DIS "Umbral de doble aprobación: 3.000.000"
- [SOLO EN DISEÑO] El prototipo trae un botón para validar el CUIT que el pedido no menciona.
  - Diseño: F-DIS "Validar CUIT"
