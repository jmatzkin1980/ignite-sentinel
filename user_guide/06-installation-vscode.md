# VS Code Portable Installation

Ignite Sentinel is designed to run from the cloned repository. This is the safest path for company laptops and client VDIs where admin rights, global installs, and marketplace access may be restricted.

## Recommended Setup

1. Clone or download the repository.

```powershell
git clone https://github.com/jmatzkin1980/ignite-sentinel.git
cd ignite-sentinel
```

If Git is unavailable, download the repository ZIP from GitHub and extract it to a writable folder.

2. Open the folder in VS Code.

```powershell
code .
```

3. Run the portable doctor.

```powershell
python -m sentinel /doctor
```

4. Start a workspace.

```powershell
python -m sentinel /init DEMO_PROJECT
```

## No-Install Mode

Use this mode first in securitized environments:

```powershell
python -m sentinel --help
python -m sentinel /doctor
```

No global package install is required.

## Optional Local Venv

Use only if your environment allows local virtual environments:

```powershell
.\installers\install.ps1 -CreateVenv
```

Or on Unix-like shells:

```sh
sh installers/install.sh --venv
```

## VS Code Extension Usage

Ignite works through repo-local files:

- Codex reads `.codex/skills/`.
- Kilo Code reads `.kilo/agents/`.
- The CLI works even without either extension.

## Daily Use

```powershell
python -m sentinel /ingest PROJECT_ID --source input\client-note.md
python -m sentinel /maturity PROJECT_ID
python -m sentinel /specs PROJECT_ID
python -m sentinel /backlog PROJECT_ID
python -m sentinel /quality PROJECT_ID
python -m sentinel /health PROJECT_ID
```

