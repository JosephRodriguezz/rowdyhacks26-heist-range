param([string]$Path = '.env.bank-disposable')

$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Path) {
    throw "Private environment file already exists: $Path"
}
function New-Secret {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}
$names = @(
    'BANK_DB_PASSWORD', 'BANK_APP_DB_PASSWORD', 'BANK_TRAINING_DB_PASSWORD',
    'BANK_CUSTOMER_PASSWORD', 'BANK_VAULT_PASSWORD',
    'BANK_AVAILABILITY_LOAD_TOKEN', 'BANK_AVAILABILITY_PROBE_TOKEN',
    'BANK_AVAILABILITY_EXECUTOR_TOKEN'
)
$lines = @('# Private credentials for the disposable Docker project only.', 'BANK_SCENARIO=baseline')
foreach ($name in $names) { $lines += "$name=$(New-Secret)" }
$absolutePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
[System.IO.File]::WriteAllText($absolutePath, ($lines -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Host "Created private disposable-bank environment at $absolutePath"
