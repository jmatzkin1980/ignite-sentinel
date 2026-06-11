param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$SentinelArgs
)

$ErrorActionPreference = "Stop"

function Resolve-SentinelPython {
  if ($env:SENTINEL_PYTHON -and (Test-Path -LiteralPath $env:SENTINEL_PYTHON)) {
    if (Test-SentinelPython $env:SENTINEL_PYTHON) {
      return $env:SENTINEL_PYTHON
    }
  }

  $repoVenv = Join-Path (Get-Location) ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $repoVenv) {
    if (Test-SentinelPython $repoVenv) {
      return $repoVenv
    }
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python -and (Test-SentinelPython $python.Source)) {
    return $python.Source
  }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py -and (Test-SentinelPython $py.Source)) {
    return $py.Source
  }

  $codexRuntime = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if ((Test-Path -LiteralPath $codexRuntime) -and (Test-SentinelPython $codexRuntime)) {
    return $codexRuntime
  }

  return $null
}

function Test-SentinelPython {
  param([string]$Candidate)

  try {
    & $Candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

$python = Resolve-SentinelPython
if (-not $python) {
  Write-Error "Python 3.10+ was not found. Install Python, create .venv, or set SENTINEL_PYTHON to an approved python.exe."
}

if (-not $SentinelArgs -or $SentinelArgs.Count -eq 0) {
  $SentinelArgs = @("--help")
}

& $python -m sentinel @SentinelArgs
