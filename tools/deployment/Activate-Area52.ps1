param(
    [Parameter(Mandatory = $true)][string]$Package,
    [switch]$CheckOnly,
    [switch]$ResumePublish
)
$ErrorActionPreference = 'Stop'
$packagePath = (Resolve-Path -LiteralPath $Package).Path
$runnerPath = Join-Path $PSScriptRoot 'activate.py'
$manifest = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
if ($manifest.requires_windows_administrator -and -not $CheckOnly) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'This package requires Administrator PowerShell for Windows scheduled-task maintenance. Reopen PowerShell using Run as administrator and approve Windows UAC, then rerun this command. No countdown or deployment has started.'
    }
}
if (@($manifest.artifacts | Where-Object { $_.path -ieq 'hooks/Task.ps1' -and (Test-Path -LiteralPath (Join-Path (Split-Path $packagePath) 'hooks/task-before.xml')) }).Count -gt 0) {
    . (Join-Path $PSScriptRoot 'realm_keepalive.ps1')
    Assert-Area52Keepalive
}
if (-not $ResumePublish -and $manifest.requires_client_closed -and (Get-Process Ascension -ErrorAction SilentlyContinue)) {
    throw 'Close Ascension before running this package.'
}
if ($manifest.target -eq 'combined') {
    if ($ResumePublish) { throw 'Combined server activation does not resume publication.' }
    $combinedPython = 'C:\Users\danie\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $combinedArguments = @((Join-Path $PSScriptRoot 'combined_activation.py'), $packagePath)
    if ($CheckOnly) { $combinedArguments += '--check-only' }
    & $combinedPython @combinedArguments
    if ($LASTEXITCODE -ne 0) { throw 'Combined package stopped. Review the per-realm receipts before retrying; do not reactivate a completed realm.' }
    return
}
if ($manifest.target -eq 'cloud') {
    if ($ResumePublish) { throw 'Cloud server activation is separate from client publication recovery.' }
    $cloudPython = 'C:\Users\danie\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $cloudArguments = @((Join-Path $PSScriptRoot 'cloud_transport.py'), $packagePath)
    if ($CheckOnly) { $cloudArguments += '--check-only' }
    if ($manifest.service -eq 'featured_catalog') {
        . (Join-Path $PSScriptRoot 'realm_keepalive.ps1')
        Assert-Area52Keepalive
        $catalogTask = Get-ScheduledTask -TaskName 'Area52 Featured Catalog' -ErrorAction Stop
        if (-not $CheckOnly) {
            & $cloudPython @cloudArguments --check-only
            if ($LASTEXITCODE -ne 0) { throw 'Cloud catalog preflight failed before retiring the Windows worker.' }
            Disable-ScheduledTask -TaskName 'Area52 Featured Catalog' | Out-Null
            if ($catalogTask.State -eq 'Running') { Stop-ScheduledTask -TaskName 'Area52 Featured Catalog' }
            if ((Get-ScheduledTask -TaskName 'Area52 Featured Catalog').Settings.Enabled) {
                throw 'Legacy catalog worker remains enabled; Cloud activation stopped.'
            }
        }
    }
    & $cloudPython @cloudArguments
    if ($LASTEXITCODE -ne 0) { throw 'Cloud activation or preflight did not complete. Review its retained transaction before retrying.' }
    return
}
$linuxPackage = & wsl.exe -d dml-arch -u root -- wslpath -a $packagePath.Replace('\', '/')
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the package path in WSL.' }
$linuxRunner = & wsl.exe -d dml-arch -u root -- wslpath -a $runnerPath.Replace('\', '/')
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the activation script in WSL.' }
$arguments = @('-d', 'dml-arch', '-u', 'root', '--', 'python3', $linuxRunner.Trim(), $linuxPackage.Trim())
if ($CheckOnly) { $arguments += '--check-only' }
if ($ResumePublish) { $arguments += '--resume-publish' }
$area52ProbeJob = $null
$area52ProbeDirectory = $null
$area52PreviousWslEnv = $env:WSLENV
$area52PreviousProbeFile = $env:AREA52_CLIENT_STATE_FILE
$area52PreviousProbeNonce = $env:AREA52_CLIENT_STATE_NONCE
$area52PreviousCertificateFile = $env:SSL_CERT_FILE
$area52TrustDirectory = $null
try {
    if (@($manifest.publish).Count -gt 0 -and $manifest.publish) {
        . (Join-Path $PSScriptRoot 'publication_tls.ps1')
        $area52TrustDirectory = Join-Path ([IO.Path]::GetTempPath()) ('area52-tls-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $area52TrustDirectory | Out-Null
        $env:SSL_CERT_FILE = New-Area52PublicationTrust -Directory $area52TrustDirectory
        $area52ForwardedVariables = @($env:WSLENV -split ':' | Where-Object { $_ -and ($_ -split '/')[0] -ne 'SSL_CERT_FILE' })
        $env:WSLENV = (@($area52ForwardedVariables) + 'SSL_CERT_FILE') -join ':'
    }
    if (-not $ResumePublish -and $manifest.requires_client_closed) {
        $area52ProbeNonce = [Guid]::NewGuid().ToString('N')
        $area52ProbeDirectory = Join-Path ([IO.Path]::GetTempPath()) ('area52-client-' + $area52ProbeNonce)
        New-Item -ItemType Directory -Path $area52ProbeDirectory | Out-Null
        $area52ProbeFile = Join-Path $area52ProbeDirectory 'state.json'
        $area52ProbeJob = Start-Job -ArgumentList $area52ProbeFile, $area52ProbeNonce -ScriptBlock {
            param($statePath, $nonce)
            $ErrorActionPreference = 'Stop'
            while ($true) {
                $state = @{ nonce = $nonce; checked_at_ms = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds();
                    closed = -not [bool](Get-Process Ascension -ErrorAction SilentlyContinue) }
                [IO.File]::WriteAllText($statePath + '.tmp', ($state | ConvertTo-Json -Compress))
                if ([IO.File]::Exists($statePath)) {
                    [IO.File]::Replace($statePath + '.tmp', $statePath, [NullString]::Value)
                } else {
                    [IO.File]::Move($statePath + '.tmp', $statePath)
                }
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
        $env:WSLENV = if ($env:WSLENV) { $env:WSLENV + ':' + $area52ProbeVariables } else { $area52ProbeVariables }
    }
    & wsl.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Activation did not complete. Read the status above before retrying.' }
    if ($CheckOnly -and $manifest.requires_windows_administrator) {
        Write-Output 'Read-only preflight passed. Running this package requires Administrator PowerShell.'
    }
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
    $env:SSL_CERT_FILE = $area52PreviousCertificateFile
    if ($area52TrustDirectory) {
        Remove-Item -LiteralPath (Join-Path $area52TrustDirectory 'publication-ca.pem') -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $area52TrustDirectory -ErrorAction SilentlyContinue
    }
}
