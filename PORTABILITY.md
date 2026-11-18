# Portabilidad en Entornos Restringidos

Este documento es una carta breve para equipos de IT, Seguridad o Arquitectura que deben aprobar el uso de Ignite Sentinel en una laptop corporativa o VDI de cliente.

## Resumen Para IT

Ignite Sentinel vNext es un framework local-first para madurar requerimientos de negocio y producto. Guarda la fuente de verdad en archivos de texto bajo `workspaces/[PROJECT_ID]/`, en la carpeta donde se ejecuta.

Para el ciclo core no requiere servicios externos, bases vectoriales remotas, MCP remoto, APIs de embeddings ni paquetes obligatorios de terceros: usa solo la biblioteca estandar de Python. No tiene codigo de red; `/doctor` falla si aparece una importacion de red o una dependencia dura no opcional en el runtime.

## Requisitos

- Python 3.10 o superior aprobado por la organizacion.
- Una carpeta local con permisos de lectura y escritura.

No se requiere instalar paquetes Python para el ciclo core, permisos de administrador si Python ya esta disponible, servicios cloud ni conexion de red durante el uso normal.

## Formas De Instalarlo

| Entorno | Que pedir | Como |
|---|---|---|
| Claude Code aprobado | Python 3.10+ y Claude Code | Plugin desde GitHub: `/plugin marketplace add jmatzkin1980/ignite-sentinel#stable` y `/plugin install ignite-sentinel@ignite-sentinel` |
| Claude Code aprobado, git bloqueado | Python 3.10+ y Claude Code 2.1.224+ | Archivo `.zip` del plugin de un release de GitHub, instalado por HTTPS con su `SHA256SUMS` |
| Clon o ZIP del repositorio, sin `pip` | Python 3.10+ y carpeta writable | `python -m sentinel /doctor` |
| Instalacion revisable, solo la linea de comandos | Python 3.10+ y `pip` | Wheel de un release: `python -m pip install .\ignite_sentinel-X.Y.Z-py3-none-any.whl`, verificable con `gh attestation verify` |
| Un solo archivo permitido | Python 3.10+ y un `sentinel.pyz` construido en un entorno aprobado | `python sentinel.pyz /doctor` |

Si PowerShell esta restringido, se llama a Python directamente; el launcher no hace falta.

El `.pyz` se construye desde un clon con `python -m sentinel.build`. No forma parte de un release de GitHub ni tiene atestacion, y no incluye la libreria de diagramas: `/view` muestra cada diagrama como codigo. Si alcanza con la linea de comandos, el wheel es la mejor opcion de un solo archivo porque esta atestado.

## Extras Opcionales

Sin extras, Sentinel usa memoria deterministica `json-hybrid`. Es un estado sano: `/doctor` mantiene el veredicto `PASS` y muestra la memoria opcional como `WARN`.

Si la organizacion lo permite, cada extra tiene un archivo de bloqueo con versiones y hashes en `constraints/` (`memory.txt`, `memory-semantic.txt`, `mcp.txt`). En un clon:

```powershell
python -m pip install --require-hashes -r constraints/memory.txt
python -m pip install --no-deps -e .
python -m sentinel /reindex PROJECT_ID
```

Sentinel nunca descarga un modelo de embeddings: los modelos locales se preparan en una maquina aprobada y se copian.

## Manejo De Datos

- Los contenidos de cliente permanecen en archivos locales.
- `workspaces/` esta ignorado por git en el repositorio del framework.
- La memoria local es un indice reconstruible, no la fuente de verdad.
- Los secretos detectados en las fuentes se reemplazan por `<SECRETO:tipo>` y se registran sin su valor.

Si se opera desde una herramienta de agente aprobada (Claude Code, Codex, Kilo Code, VS Code), las politicas de esa herramienta aplican por separado. Sentinel no cambia ese canal.

## Comando De Verificacion

```powershell
python -m sentinel /doctor
```

Un resultado `PASS` con advertencias opcionales de LanceDB es valido para operar en modo restringido. Fuera de un clon (plugin, wheel o `.pyz`), `/doctor` corre en modo runtime y revisa solo el interprete, la paridad de comandos, la carpeta y los extras.

## Para Revisar Mas

- [Modo de portabilidad y nota para IT](user_guide/16-portability.md)
- [Instalacion](user_guide/06-installation-vscode.md) y [entornos seguros](user_guide/09-secure-environments.md)
- [Modelo de amenazas](user_guide/19-threat-model.md), [guia de administracion](user_guide/20-admin-guide.md) y [SECURITY.md](SECURITY.md)
