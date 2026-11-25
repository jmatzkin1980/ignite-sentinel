# Alta de proveedores con aprobación por monto

## Objetivo
Que el alta de proveedores de Compras se haga y se apruebe dentro del sistema, sin firmas en papel, y que el analista vea el estado del trámite sin preguntar.

## Usuarios
- Analista de Compras: carga el alta del proveedor.
- Jefa de Compras: aprueba, rechaza u observa las altas de monto alto.
- Auditor interno: consulta el historial de cada alta.

## Proceso
El alta nace en estado Borrador cuando el analista guarda los datos por primera vez y no tiene número de trámite.
El número de trámite se asigna al enviarla y no cambia aunque el alta vuelva observada varias veces.
Cada transición queda en el historial con usuario, fecha y hora, y el historial no se puede editar.

1. El analista abre el alta en Borrador y completa los datos fiscales; el CUIT se valida contra el padrón al salir del campo.
2. El analista adjunta la constancia de inscripción; se aceptan PDF o imagen de hasta 5 MB.
3. El analista carga los datos bancarios; la cuenta se valida con el dígito verificador antes de guardar.
4. El analista carga el contacto comercial; el correo es obligatorio y el teléfono opcional.
5. El sistema calcula el monto anual estimado con las compras previstas; el cálculo se repite si cambia una cantidad.
6. Al enviar, el sistema asigna el número de trámite; el formato es año, guion y seis dígitos.
7. Si el monto no supera el umbral, el alta pasa directo a Habilitada; no interviene la jefa.
8. Si el monto supera el umbral, el alta pasa a Pendiente de aprobación; aparece en la bandeja de la jefa de Compras.
9. La jefa abre el alta desde la bandeja; el sistema muestra primero los datos que cambiaron desde el último envío.
10. La jefa aprueba el alta; el proveedor queda Habilitado y se registran usuario, fecha y hora.
11. La jefa rechaza el alta; el motivo es obligatorio y tiene al menos 20 caracteres.
12. La jefa observa el alta; el alta vuelve al analista en estado Observada con el comentario visible.
13. El analista corrige un alta Observada; tiene 3 días hábiles para reenviarla.
14. Si vence el plazo de corrección, el alta pasa a Vencida; el analista debe iniciar un alta nueva.
15. Un alta Pendiente más de 5 días hábiles se notifica a la gerencia; la notificación se repite cada 2 días hábiles.
16. Un alta Rechazada no se borra; queda consultable con su motivo durante 5 años.
17. Un alta Habilitada no vuelve a Pendiente; un cambio bancario posterior abre un trámite de modificación.
18. El auditor consulta el historial de un alta; ve cada transición con usuario, fecha y hora.
19. El auditor exporta el historial; el archivo sale en CSV con separador punto y coma.
20. Ninguna transición se puede deshacer; un error se corrige con una transición nueva y su motivo.

Las transiciones posibles entre estados son las de la tabla siguiente.
Una transición que no figura en la tabla se rechaza con el mensaje "Transición no permitida".
Los nombres de estado se muestran tal cual en la bandeja y en el historial.
La tabla rige también para las altas creadas antes que sigan abiertas y quedan en estado Observada.

| Estado de origen | Acción | Estado de destino | Quién |
| --- | --- | --- | --- |
| Borrador | Enviar con monto menor o igual al umbral | Habilitada | Analista |
| Borrador | Enviar con monto mayor al umbral | Pendiente de aprobación | Analista |
| Pendiente de aprobación | Aprobar | Habilitada | Jefa de Compras |
| Pendiente de aprobación | Rechazar con motivo | Rechazada | Jefa de Compras |
| Pendiente de aprobación | Observar con comentario | Observada | Jefa de Compras |
| Observada | Reenviar corregida | Pendiente de aprobación | Analista |
| Observada | Vencer el plazo de corrección | Vencida | Sistema |
| Rechazada | Cumplir 5 años | Archivada | Sistema |

## Reglas de negocio
| ID | Regla |
| --- | --- |
| RN-01 | El CUIT del proveedor debe ser único; un CUIT duplicado se rechaza nombrando al proveedor existente. |
| RN-02 | Un alta rechazada no se elimina: queda en estado Rechazada con su motivo. |
| RN-03 | Un alta con monto anual estimado mayor a 5.000.000 requiere doble aprobación. |
| RN-04 | La jefa de Compras no puede aprobar un alta que cargó ella misma. |
| RN-05 | Un alta pendiente de aprobación por más de 5 días hábiles se notifica a la gerencia de Compras. |

## Criterios de aceptación
- CA-01: Dado un CUIT ya registrado, cuando el analista envía el alta, entonces el sistema la rechaza y nombra al proveedor existente.
- CA-02: Dado un alta rechazada, cuando el analista la consulta, entonces ve el motivo del rechazo.
- CA-03: Dado un alta con monto mayor a 3.000.000, cuando el analista la envía, entonces queda Pendiente de doble aprobación.
- CA-04: Dado un alta cargada por la jefa, cuando ella intenta aprobarla, entonces el sistema no lo permite.

## Historias
- HU-01: Como analista de Compras quiero enviar un alta a aprobación para no imprimir el resumen.
- HU-02: Como jefa de Compras quiero ver las altas pendientes en una bandeja para aprobarlas o rechazarlas.

### HU-03 Consultar el historial
Como auditor interno quiero consultar quién aprobó cada alta y cuándo, para revisar los controles.

## Decisiones
- PD-01: El prototipo muestra 3.000.000; rige el pedido: 5.000.000 (RN-03).
