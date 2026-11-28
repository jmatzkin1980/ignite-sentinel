# Contexto técnico: alta de proveedores

Execution commands: run pytest for the ProveedorAltaService suite and the backoffice lint.

Critical surfaces: ProveedorAltaService, the approvals queue AprobacionesQueue and the tax id validator ValidadorCuit.

Engineering practices: keep the supplier tax id masked in logs and validate every approval transition.

Quality evidence: fail-to-pass and pass-to-pass tests cover the approval threshold of the Jefa de Compras.
