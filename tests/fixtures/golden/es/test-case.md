# Test Case Set - US-001

- Project: `[PROJECT_ID]`
- Source story: `US-001`
- Status: `draft`

## Coverage Matrix

| Test Step | Acceptance Criterion |
| --- | --- |
| TC step AC-001-01 [fail-to-pass] | AC-001-01 [fail-to-pass]: Given `SPEC-U-001` esta confirmado y sus fuentes estan disponibles, When Cuando haya metricas de cola disponibles, el sistema debe mostrar las colas de riesgo abiertas., Then el sistema produce el resultado observable indicado por la unidad y conserva la traza hacia la evidencia. |
| TC step AC-001-02 [fail-to-pass] | AC-001-02 [fail-to-pass]: Given una precondicion, dato o regla requerida por `SPEC-U-001` no se cumple, When el usuario o sistema intenta completar el slice, Then el avance riesgoso se bloquea o queda recuperable sin registrar exito falso. |
| TC step AC-001-03 [fail-to-pass] | AC-001-03 [fail-to-pass]: Given una dependencia, dato, permiso o estado externo citado por la unidad no esta disponible, When el sistema intenta completar el slice, Then la falla queda visible, no se oculta informacion parcial como definitiva y se preserva la auditabilidad. |
| TC step AC-001-04 [pass-to-pass] | AC-001-04 [pass-to-pass]: Given existen comportamientos vigentes, contratos o pruebas relacionadas antes de implementar esta historia, When se valida el incremento junto con la regresion definida por Quality o el repositorio, Then las capacidades existentes siguen pasando sin cambios colaterales fuera del blast radius declarado. |
| TC step AC-001-05 [evidence] | AC-001-05 [evidence]: Given Quality revisa la historia para aceptacion o automatizacion, When consulta criterios, alcance, dependencias y trazas, Then encuentra SPEC-U-001, REQ-EARS-001, REQ-001, PRD-001, SPEC-001 y los criterios en formato verificable. |

## Automation Notes

- Prepare valid input data for the happy path.
- Prepare missing and invalid input data for validation paths.
- Separate fail-to-pass checks, pass-to-pass regression checks, and evidence checks when classifications are present.
- Assert trace IDs remain visible in the artifact chain.
