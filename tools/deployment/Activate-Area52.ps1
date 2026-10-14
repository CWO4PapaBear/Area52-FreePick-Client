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
$area52ProbeJob = $null
$area52ProbeDirectory = $null
$area52PreviousWslEnv = $env:WSLENV
$area52PreviousProbeFile = $env:AREA52_CLIENT_STATE_FILE
$area52PreviousProbeNonce = $env:AREA52_CLIENT_STATE_NONCE
try {
    if ($manifest.requires_client_closed) {
        $area52ProbeNonce = [Guid]::NewGuid().ToString('N')
        $area52ProbeDirectory = Join-Path ([IO.Path]::GetTempPath()) ('area52-client-' + $area52ProbeNonce)
        New-Item -ItemType Directory -Path $area52ProbeDirectory | Out-Null
        $area52ProbeFile = Join-Path $area52ProbeDirectory 'state.json'
        $area52ProbeJob = Start-Job -ArgumentList $area52ProbeFile, $area52ProbeNonce -ScriptBlock {
            param($statePath, $nonce)
            while ($true) {
                $state = @{ nonce = $nonce; checked_at_ms = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds();
                    closed = -not [bool](Get-Process Ascension -ErrorAction SilentlyContinue) }
                [IO.File]::WriteAllText($statePath + '.tmp', ($state | ConvertTo-Json -Compress))
                Move-Item -LiteralPath ($statePath + '.tmp') -Destination $statePath -Force
                Start-Sleep -Milliseconds 250
            }
        }
        $area52ProbeDeadline = [DateTime]::UtcNow.AddSeconds(15)
        while (-not (Test-Path -LiteralPath $area52ProbeFile)) {
            if ($area52ProbeJob.State -ne 'Running' -or [DateTime]::UtcNow -gt $area52ProbeDeadline) {
                throw 'Windows client-state probe did not start.'
            }
            Start-Sleep -Milliseconds 100
        }
        $area52LinuxProbe = & wsl.exe -d dml-arch -u root -- wslpath -a $area52ProbeFile.Replace('\', '/')
        if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the Windows client-state probe.' }
        $env:AREA52_CLIENT_STATE_FILE = $area52LinuxProbe.Trim()
        $env:AREA52_CLIENT_STATE_NONCE = $area52ProbeNonce
        $area52ProbeVariables = 'AREA52_CLIENT_STATE_FILE/u:AREA52_CLIENT_STATE_NONCE/u'
        $env:WSLENV = if ($area52PreviousWslEnv) { $area52PreviousWslEnv + ':' + $area52ProbeVariables } else { $area52ProbeVariables }
    }
    & wsl.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Activation did not complete. Read the status above before retrying.' }
} finally {
    if ($area52ProbeJob) { Stop-Job $area52ProbeJob; Remove-Job $area52ProbeJob }
    if ($area52ProbeDirectory) {
        Remove-Item -LiteralPath (Join-Path $area52ProbeDirectory 'state.json') -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $area52ProbeDirectory 'state.json.tmp') -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $area52ProbeDirectory -ErrorAction SilentlyContinue
    }
    $env:WSLENV = $area52PreviousWslEnv
    $env:AREA52_CLIENT_STATE_FILE = $area52PreviousProbeFile
    $env:AREA52_CLIENT_STATE_NONCE = $area52PreviousProbeNonce
}
