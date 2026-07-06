param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$SentinelArgs
)

$ErrorActionPreference = "Stop"

# Repo root is the parent of the installers directory that holds this script,
# resolved from the script location (not the caller's cwd) so the launcher works
# when invoked from anywhere. The CLI anchors workspaces/ to its cwd
# (sentinel/core/paths.py:repo_root), so we also run python from the repo root.
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

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
    if (Test-SentinelPython $env:SENTINEL_PYTHON) {
      return $env:SENTINEL_PYTHON
    }
  }

  # Prefer the repo-root .venv (resolved from the script location), then fall
  # back to a .venv under the caller's cwd for legacy invocations.
  foreach ($root in @($RepoRoot, (Get-Location).Path)) {
    $venv = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) {
      if (Test-SentinelPython $venv) {
        return $venv
      }
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

$python = Resolve-SentinelPython
if (-not $python) {
  Write-Error "Python 3.10+ was not found. Install Python, create .venv, or set SENTINEL_PYTHON to an approved python.exe."
}

if (-not $SentinelArgs -or $SentinelArgs.Count -eq 0) {
  $SentinelArgs = @("--help")
}

# $LASTEXITCODE reflects the last native command (the python call); Pop-Location
# is a cmdlet and does not touch it, so it survives the location restore.
Push-Location -LiteralPath $RepoRoot
try {
  & $python -m sentinel @SentinelArgs
} finally {
  Pop-Location
}

exit $LASTEXITCODE
