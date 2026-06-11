<#
.SYNOPSIS
  Corre la verificacion obligatoria de Ignite Sentinel resolviendo el interprete
  Python de forma robusta (evita el alias stub de Microsoft Store).

.DESCRIPTION
  Mismo resolver que installers\sentinel.ps1: prueba SENTINEL_PYTHON, luego
  .venv\Scripts\python.exe, luego `python` del PATH, luego el launcher `py`, y
  por ultimo el runtime de Codex. Con el interprete resuelto corre, en orden:
    1. unittest discover -s tests
    2. python -m sentinel /doctor
    3. tests/evals/run_discovery_evals.py   (omitible con -SkipEvals)
  Se detiene en el primer paso que falle.

.EXAMPLE
  .\verify.ps1
  .\verify.ps1 -SkipEvals
#>
param(
  [switch]$SkipEvals
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

function Test-SentinelPython {
  param([string]$Candidate)
  try {
    & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Resolve-SentinelPython {
  if ($env:SENTINEL_PYTHON -and (Test-Path -LiteralPath $env:SENTINEL_PYTHON)) {
    if (Test-SentinelPython $env:SENTINEL_PYTHON) { return $env:SENTINEL_PYTHON }
  }

  $repoVenv = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $repoVenv) {
    if (Test-SentinelPython $repoVenv) { return $repoVenv }
  }

  # `python` del PATH: el alias stub de Microsoft Store NO pasa Test-SentinelPython,
  # asi que aunque resuelva al stub, lo descartamos y seguimos.
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python -and (Test-SentinelPython $python.Source)) { return $python.Source }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py -and (Test-SentinelPython $py.Source)) { return $py.Source }

  $codexRuntime = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if ((Test-Path -LiteralPath $codexRuntime) -and (Test-SentinelPython $codexRuntime)) { return $codexRuntime }

  return $null
}

$python = Resolve-SentinelPython
if (-not $python) {
  Write-Error @"
No se encontro Python 3.10+.
Opciones:
  - Instalar Python desde python.org marcando 'Add python.exe to PATH'.
  - Apagar el alias de Microsoft Store: Configuracion > Aplicaciones > Alias de
    ejecucion de aplicaciones > apagar python.exe y python3.exe.
  - Crear un venv:  py -m venv .venv  ;  .\.venv\Scripts\python -m pip install -e .
  - O exportar SENTINEL_PYTHON apuntando a un python.exe valido.
"@
}

Write-Host "==> Interprete: $python" -ForegroundColor Cyan
Push-Location $repoRoot
try {
  Write-Host "`n==> [1/3] unittest discover -s tests" -ForegroundColor Cyan
  & $python -m unittest discover -s tests
  if ($LASTEXITCODE -ne 0) { Write-Error "unittest fallo (exit $LASTEXITCODE)" }

  Write-Host "`n==> [2/3] sentinel /doctor" -ForegroundColor Cyan
  & $python -m sentinel /doctor
  if ($LASTEXITCODE -ne 0) { Write-Error "/doctor fallo (exit $LASTEXITCODE)" }

  if ($SkipEvals) {
    Write-Host "`n==> [3/3] evals OMITIDOS (-SkipEvals)" -ForegroundColor Yellow
  } else {
    Write-Host "`n==> [3/3] discovery evals" -ForegroundColor Cyan
    & $python tests/evals/run_discovery_evals.py
    if ($LASTEXITCODE -ne 0) { Write-Error "evals fallaron (exit $LASTEXITCODE)" }
  }

  Write-Host "`n==> Verificacion OK" -ForegroundColor Green
}
finally {
  Pop-Location
}
