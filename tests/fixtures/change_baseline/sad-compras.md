# SAD del backoffice de Compras (línea de base sintética)

## Atributos de calidad

El servicio de compras responde en menos de dos segundos al percentil 95 en horario pico, y la disponibilidad mensual objetivo es de 99,5 por ciento.

## Restricciones

Todo cambio sobre el backoffice debe respetar la política interna de retención: los datos de proveedores se conservan durante siete años y no se exponen fuera de la red corporativa.

## Despliegue y ambientes

El backoffice se despliega en tres ambientes: desarrollo, homologación y producción. Cada release pasa por homologación antes de llegar a producción, con un corte de ventana los jueves.

## Entradas técnicas

El modelo de datos vigente de proveedores y el contrato del endpoint de alta están documentados en el repositorio de compras y son la entrada técnica para cualquier cambio sobre el alta.
