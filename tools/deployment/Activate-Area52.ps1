param(
    [Parameter(Mandatory = $true)][string]$Package,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$packagePath = (Resolve-Path -LiteralPath $Package).Path
$runnerPath = Join-Path $PSScriptRoot 'activate.py'
$manifest = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
if ($manifest.requires_client_closed -and (Get-Process Ascension -ErrorAction SilentlyContinue)) {
    throw 'Close Ascension before running this package.'
}
$linuxPackage = & wsl.exe -d dml-arch -u root -- wslpath -a $packagePath.Replace('\', '/')
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the package path in WSL.' }
$linuxRunner = & wsl.exe -d dml-arch -u root -- wslpath -a $runnerPath.Replace('\', '/')
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the activation script in WSL.' }
$arguments = @('-d', 'dml-arch', '-u', 'root', '--', 'python3', $linuxRunner.Trim(), $linuxPackage.Trim())
if ($CheckOnly) { $arguments += '--check-only' }
& wsl.exe @arguments
if ($LASTEXITCODE -ne 0) { throw 'Activation did not complete. Read the status above before retrying.' }
