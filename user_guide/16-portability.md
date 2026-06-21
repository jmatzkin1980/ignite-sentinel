# Portabilidad Y Carta Para IT

Esta guia explica como usar Ignite Sentinel en laptops corporativas, VDIs de cliente y entornos donde no se permite instalar libremente. Tambien incluye el texto que un BA o PM puede reenviar a IT para pedir aprobacion.

## Principio

La estrategia de Sentinel no es pedir mas permisos. Es reducir la huella:

- usar Python 3.10+ ya aprobado cuando exista;
- no requerir paquetes obligatorios de terceros para el ciclo core;
- mantener el contenido de cliente local;
- operar con archivos auditables en texto plano;
- usar `sentinel.pyz` cuando conviene mover un unico archivo.

## Matriz De Portabilidad

| Situacion | Requisito minimo | Comando recomendado | Lectura esperada |
|---|---|---|---|
| Laptop libre o equipo propio | Python 3.10+ | `python -m sentinel /doctor` | `PASS`; LanceDB puede ser `WARN` si no se instalo el extra |
| Laptop corporativa con Python aprobado | Python 3.10+ y carpeta writable | `python -m sentinel /doctor` | `PASS`; sin paquetes obligatorios |
| VDI sin `pip` o sin permisos de admin | Python 3.10+ | `python -m sentinel /doctor` | `PASS` en modo `json-hybrid`; LanceDB queda como advertencia opcional |
| VDI con PowerShell restringido | Python 3.10+ | `python -m sentinel /doctor` | Usar CLI directa; el wrapper PowerShell no es necesario |
| Entorno donde se prefiere copiar un unico archivo | Python 3.10+ y `sentinel.pyz` generado previamente | `python sentinel.pyz /doctor --root .` | `PASS` usando recursos empaquetados |
| Superficie ya aprobada por la organizacion | VS Code, Codex, Kilo o Claude aprobados | `sentinel /doctor` o comando de chat equivalente | El agente enruta a CLI local; revisar politicas propias de la herramienta |
| Sin Python aprobado | Aprobacion de Python 3.10+ o runtime equivalente | No aplica hasta tener runtime | Pedir Python antes que un binario sin firmar suele ser mas aprobable |

## Pedido Breve Para IT

Copiar y adaptar:

```text
Necesito usar Ignite Sentinel vNext para madurar requerimientos de negocio en un proyecto local.

Requisitos tecnicos:
- Python 3.10 o superior aprobado por la organizacion.
- Una carpeta local con permisos de lectura/escritura.
- No requiere instalar paquetes Python obligatorios para el ciclo core.
- No requiere servicios cloud, MCP remoto, bases vectoriales externas ni servicios externos de embeddings para contenido de cliente.

Operacion:
- Los artefactos del proyecto quedan en archivos locales bajo workspaces/[PROJECT_ID]/.
- La memoria local es un indice reconstruible, no la fuente de verdad.
- Si LanceDB no esta instalado, el framework opera en modo deterministico json-hybrid; /doctor lo reporta como advertencia opcional y mantiene PASS.
- El codigo es auditable en texto plano dentro del repositorio.

Comando de validacion:
python -m sentinel /doctor
```

## Como Operar Sin Pip

Desde la raiz del repo:

```powershell
python -m sentinel /doctor
python -m sentinel /init PROJECT_ID
python -m sentinel /ingest PROJECT_ID --source input\client_requirement\request.md
```

Si `python` no esta en `PATH`, usar una ruta aprobada:

```powershell
$env:SENTINEL_PYTHON="C:\Ruta\Aprobada\python.exe"
.\installers\sentinel.ps1 /doctor
```

Si los scripts PowerShell estan bloqueados, evitar el wrapper y llamar al modulo directamente:

```powershell
C:\Ruta\Aprobada\python.exe -m sentinel /doctor
```

## Como Usar El `.pyz`

Construir en un entorno aprobado:

```powershell
python -m sentinel.build
```

Mover `dist\sentinel.pyz` por el canal permitido y correr:

```powershell
python sentinel.pyz /doctor --root .
```

El `.pyz` contiene el runtime y recursos declarativos de Sentinel. Sigue necesitando un interprete Python 3.10+, pero evita instalar el paquete en el entorno destino.

## Como Interpretar `/doctor`

Un resultado sano en entorno restringido puede verse asi:

- verdict global `PASS`;
- `memory dependency: lancedb (optional)` como `WARN`;
- `LanceDB local open/create` como `WARN`;
- `memory backend mode` como `WARN`;
- detalles que indican que LanceDB es opcional y que el backend activo es `json-hybrid`.

Eso significa que Sentinel esta listo para el ciclo core. La advertencia solo indica que no esta activa la capa vectorial local opcional.

## Que No Prometer

Para evitar malentendidos con Seguridad:

- No prometer que GitHub, VS Code, Codex, Claude o Kilo no usan red; esas superficies tienen su propia aprobacion.
- No prometer que el usuario nunca instalara extras; `lancedb` y embeddings semanticos son opcionales y deben instalarse solo si IT lo permite.
- No tratar `workspaces/` como repositorio publico: contiene material de proyecto y esta ignorado por git por defecto.

## Referencias Relacionadas

- [PORTABILITY.md](../PORTABILITY.md): carta corta para IT.
- [VS Code Portable Installation](06-installation-vscode.md): onboarding en laptop nueva.
- [Secure Environments Guide](09-secure-environments.md): operacion local-first y privacidad.
- [Command Reference](01-command-reference.md): detalle de `/doctor`.
