param([int]$Port = 8765, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path -Parent $PSScriptRoot
$pythonRuntime = Get-Command python -ErrorAction SilentlyContinue
if ($pythonRuntime) { $pythonRuntime = $pythonRuntime.Source }
else { $pythonRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
$nodeRuntime = Get-Command node -ErrorAction SilentlyContinue
if ($nodeRuntime) { $nodeRuntime = $nodeRuntime.Source }
else { $nodeRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (!(Test-Path -LiteralPath $pythonRuntime)) { throw 'Install Python 3.11+ and put python on PATH.' }
if (!(Test-Path -LiteralPath $nodeRuntime)) { throw 'Install Node.js 24 and put node on PATH.' }
if (!(Test-Path -LiteralPath (Join-Path $demoRoot 'apps\bank-lab\node_modules\@electric-sql\pglite'))) {
    throw 'Install dependencies first: cd apps/bank-lab; pnpm install --frozen-lockfile --ignore-scripts'
}
if ($Port -lt 1024 -or $Port -gt 65535 -or $Port -eq 3000) { throw 'Use an unoccupied local port from 1024-65535 other than 3000.' }
if ($CheckOnly) { Write-Host 'Demo prerequisites found. The existing Docker bank will not be used.'; return }
Push-Location -LiteralPath $demoRoot
try { & $pythonRuntime -m core.cli demo --node $nodeRuntime --port $Port }
finally { Pop-Location }
