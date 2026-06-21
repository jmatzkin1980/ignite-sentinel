# Portabilidad en Entornos Restringidos

Este documento es una carta breve para equipos de IT, Seguridad o Arquitectura que deben aprobar el uso de Ignite Sentinel en una laptop corporativa o VDI de cliente.

## Resumen Para IT

Ignite Sentinel vNext es un framework local-first para madurar requerimientos de negocio y producto. Se ejecuta desde un repositorio local y guarda la fuente de verdad en archivos versionables bajo `workspaces/[PROJECT_ID]/`.

Para el ciclo core no requiere servicios externos, bases vectoriales remotas, MCP remoto, APIs de embeddings ni paquetes obligatorios de terceros. El runtime esta protegido por un guard de pureza stdlib: `/doctor` falla si se introduce una dependencia Python dura no opcional en la ruta caliente.

## Requisitos

Requisito minimo:

- Python 3.10 o superior aprobado por la organizacion.
- Una carpeta local con permisos de lectura y escritura para el repositorio y los workspaces.

No se requiere:

- instalacion global de paquetes Python para el ciclo core;
- permisos de administrador para operar el framework si Python ya esta disponible;
- servicios cloud, bases vectoriales remotas o embeddings externos para contenido de cliente;
- conexion de red durante el uso normal, una vez que el repositorio o el `.pyz` ya fue copiado al entorno.

## Modos De Ejecucion

| Entorno | Que pedir | Como correr |
|---|---|---|
| Laptop con Python aprobado | Python 3.10+ en `PATH` o ruta conocida | `python -m sentinel /doctor` |
| VDI con Python pero sin `pip` | Solo Python 3.10+ y carpeta writable | `python -m sentinel /doctor` |
| VDI con scripts restringidos | Python 3.10+; evitar wrappers PowerShell si estan bloqueados | `python -m sentinel /doctor` |
| Entorno con un solo archivo permitido | Python 3.10+ y `sentinel.pyz` generado en un entorno aprobado | `python sentinel.pyz /doctor --root .` |
| Superficie con runtime aprobado | Usar Codex/Kilo/Claude/VS Code si ya estan aprobados por la organizacion | Ejecutar los comandos Sentinel desde chat o terminal local |

## Modo Sin Instalacion De Paquetes

El ciclo core funciona sin instalar paquetes:

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\request.md
```

Si `lancedb` no esta instalado, Sentinel usa memoria deterministica `json-hybrid`. Ese estado es sano para entornos restringidos: `/doctor` mantiene verdict global `PASS` y muestra los checks de memoria opcional como `WARN`, no como fallas.

La capa vectorial local es opcional. Si la organizacion la permite, puede habilitarse despues con:

```powershell
python -m pip install -e .[memory]
python -m sentinel /reindex PROJECT_ID
```

## Single-File Zipapp

Cuando conviene mover un unico archivo, el equipo puede construir un zipapp local:

```powershell
python -m sentinel.build
python dist\sentinel.pyz /doctor --root .
```

Ese archivo se genera con `zipapp`, una herramienta de la biblioteca estandar de Python. Incluye los recursos runtime de Sentinel, como schemas, manifest de comandos, lentes, planes de retrieval y modelo de slicing. El artefacto `*.pyz` es local, reconstruible e ignorado por git.

## Manejo De Datos

Por diseno:

- los contenidos de cliente permanecen en archivos locales;
- `workspaces/` esta ignorado por git por defecto;
- la memoria local es un indice reconstruible, no la fuente de verdad;
- no se usa MCP remoto, vector DB externa ni servicio externo de embeddings para contenido de cliente salvo aprobacion explicita fuera del framework.

Si se opera desde una herramienta de agente aprobada por la organizacion, las politicas de esa herramienta aplican por separado. Ignite Sentinel no cambia ese canal: solo organiza y valida los artefactos locales del proyecto.

## Comando De Verificacion

El primer comando recomendado para IT o para el usuario final es:

```powershell
python -m sentinel /doctor
```

`/doctor` verifica Python, estructura del repo, permisos de escritura, paridad de comandos, pureza stdlib, launchers portables y memoria local opcional. Un resultado `PASS` con advertencias opcionales de LanceDB es valido para operar en modo local restringido.

Mas detalle: [user_guide/16-portability.md](user_guide/16-portability.md).
