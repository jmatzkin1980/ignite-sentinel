# Pedido: alta de proveedores con aprobación por monto

## Objetivo
El objetivo es que el alta de proveedores en el sistema de Compras deje de depender de planillas paralelas y de revisiones manuales. Resultado esperado: el analista de Compras da de alta un proveedor en una sola sesión y la jefatura aprueba por monto sin salir del sistema.

## Usuarios
- Analista de Compras: carga el alta del proveedor.
- Jefa de Compras: aprueba las altas de monto alto.
- Auditor interno: consulta el historial de aprobaciones.

## Situación actual y estado futuro
Proceso actual: el analista carga el alta, imprime el resumen y lo lleva a firmar. Estado futuro: la aprobación se registra en el sistema con usuario y fecha, y el analista ve el estado del alta en el listado.

## Proceso
1. El analista completa los datos fiscales, bancarios y de contacto del proveedor.
2. El sistema valida los datos y calcula el monto anual estimado de compras.
3. Si el monto anual estimado supera el umbral, el alta pasa a aprobación de la jefa de Compras.
4. La jefa aprueba o rechaza con un motivo; el analista recibe el resultado.
5. Un alta aprobada deja al proveedor habilitado para órdenes de compra.

## Reglas
- Regla 1: el CUIT del proveedor debe ser único; un CUIT duplicado se rechaza con un mensaje que nombra el proveedor existente.
- Regla 2: un alta con monto anual estimado mayor al umbral requiere aprobación de la jefa de Compras antes de habilitarse.
- Regla 3: un alta rechazada no se elimina; queda en estado Rechazada con su motivo.
- Regla 4: exclusión: los proveedores del exterior quedan fuera de este cambio.

## Criterios de aceptación
Criterios de aceptación del cambio, por cada regla:
- Dado un CUIT ya registrado, cuando el analista envía el alta, entonces el sistema la rechaza y nombra al proveedor existente.
- Dado un alta con monto superior al umbral, cuando el analista la envía, entonces queda en estado Pendiente de aprobación y no habilita órdenes de compra.
- Dado un alta pendiente, cuando la jefa la aprueba, entonces el proveedor queda habilitado y se registra usuario y fecha de la aprobación.
- Dado un alta rechazada, cuando el analista la consulta, entonces ve el motivo del rechazo.

## Se preserva
El alta de proveedores con monto bajo sigue habilitándose en el acto, como hoy. El sistema existente ya está en producción.
