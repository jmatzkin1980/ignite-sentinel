# Pedido: aprobación de altas de proveedores por monto

## Objetivo
Que el alta de proveedores de Compras deje de depender de firmas en papel: la jefatura aprueba las altas de monto alto dentro del sistema y el analista ve el estado sin preguntar.

## Usuarios
- Analista de Compras: carga el alta del proveedor.
- Jefa de Compras: aprueba o rechaza las altas de monto alto.
- Auditor interno: consulta el historial de aprobaciones.

## Situación actual y estado futuro
Proceso actual: el analista imprime el resumen del alta y lo lleva a firmar. Estado futuro: la aprobación queda registrada en el sistema con usuario y fecha.

## Proceso
1. El analista completa los datos fiscales, bancarios y de contacto del proveedor.
2. El sistema calcula el monto anual estimado de compras.
3. Si el monto supera el umbral, el alta pasa a la bandeja de la jefa de Compras.
4. La jefa aprueba o rechaza con un motivo y el analista ve el resultado en el listado.

## Historias
- HU-01: Como analista de Compras quiero enviar un alta a aprobación para no imprimir el resumen.
- HU-02: Como jefa de Compras quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas.

### HU-03 Consultar el historial
Como auditor interno quiero consultar quién aprobó cada alta y cuándo, para revisar los controles.

## Reglas de negocio
| ID | Regla |
| --- | --- |
| RN-01 | El CUIT del proveedor debe ser único; un CUIT duplicado se rechaza nombrando al proveedor existente. |
| RN-02 | Un alta con monto anual estimado mayor a 5.000.000 requiere aprobación de la jefa de Compras. |
| RN-03 | Un alta rechazada no se elimina: queda en estado Rechazada con su motivo. |
| RN-04 | La jefa de Compras no puede aprobar un alta que cargó ella misma. |
| RN-05 | Un alta pendiente de aprobación por más de 5 días hábiles se notifica a la gerencia de Compras. |
| RN-06 | Los proveedores del exterior quedan fuera de este cambio. |

## Criterios de aceptación
- CA-01: Dado un CUIT ya registrado, cuando el analista envía el alta, entonces el sistema la rechaza y nombra al proveedor existente.
- CA-02: Dado un alta con monto superior al umbral, cuando el analista la envía, entonces queda Pendiente de aprobación y no habilita órdenes de compra.
- CA-03: Dado un alta pendiente, cuando la jefa la aprueba, entonces el proveedor queda habilitado y se registran usuario y fecha.
- CA-04: Dado un alta rechazada, cuando el analista la consulta, entonces ve el motivo del rechazo.
- CA-05: Dado un alta cargada por la jefa, cuando ella intenta aprobarla, entonces el sistema no lo permite.

## Decisiones
- PD-01: El umbral de aprobación se configura por parámetro y arranca en 5.000.000.
- PD-02: La notificación a la gerencia se envía por correo interno, no por el sistema de mensajería.

## Se preserva
El alta de proveedores con monto menor o igual al umbral sigue habilitándose en el acto, como hoy. La validación de CUIT existente no cambia.

## Fuera de alcance
La migración de las altas históricas en papel.
