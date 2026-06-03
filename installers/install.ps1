param(
  [switch]$CreateVenv
)

$ErrorActionPreference = "Stop"

Write-Host "Ignite Sentinel portable setup"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
  Write-Error "Python 3.10+ was not found. Install or expose Python in PATH, then rerun."
}

if ($CreateVenv) {
  & $python.Source -m venv .venv
  $venvPython = Join-Path ".venv" "Scripts\python.exe"
  & $venvPython -m pip install -e .
  & $venvpython -m sentinel /doctor
} else {
  & $python.Source -m sentinel doctor
}

Write-Host "Ignite Sentinel is ready for repo-local VS Code usage."
