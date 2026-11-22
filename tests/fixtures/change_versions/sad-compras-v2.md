# SAD Compras v2 (versión de línea de base)

## Alta de proveedores

El backoffice de Compras expone el alta de proveedores como un formulario único que se envía completo.
El servicio valida los datos fiscales (CUIT) y bancarios (CBU) antes de crear el proveedor.
El envío responde en menos de dos segundos y registra el alta en la tabla de proveedores.

## Datos adjuntos

La documentación adjunta se guarda en el repositorio documental de Compras y se vincula al proveedor por su identificador.
