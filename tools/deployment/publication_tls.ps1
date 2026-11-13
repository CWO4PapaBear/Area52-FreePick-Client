function Get-Area52PublicationAuthorities {
    param([Parameter(Mandatory = $true)][string]$HostName)
    $tcp = [Net.Sockets.TcpClient]::new()
    $tls = $null
    $chain = $null
    try {
        $connect = $tcp.BeginConnect($HostName, 443, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(15000)) { throw "TLS connection timed out: $HostName" }
        $tcp.EndConnect($connect)
        $tls = [Net.Security.SslStream]::new($tcp.GetStream(), $false)
        $authenticate = $tls.BeginAuthenticateAsClient($HostName, $null, $null)
        if (-not $authenticate.AsyncWaitHandle.WaitOne(15000)) { throw "TLS authentication timed out: $HostName" }
        $tls.EndAuthenticateAsClient($authenticate)
        $leaf = [Security.Cryptography.X509Certificates.X509Certificate2]::new($tls.RemoteCertificate)
        $chain = [Security.Cryptography.X509Certificates.X509Chain]::new()
        [void]$chain.ChainPolicy.ApplicationPolicy.Add([Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.1'))
        $chain.ChainPolicy.UrlRetrievalTimeout = [TimeSpan]::FromSeconds(15)
        if (-not $chain.Build($leaf) -or $chain.ChainElements.Count -lt 2) {
            throw "Windows rejected publication certificate chain: $HostName"
        }
        foreach ($element in ($chain.ChainElements | Select-Object -Skip 1)) {
            [Convert]::ToBase64String($element.Certificate.RawData)
        }
    } finally {
        if ($chain) { $chain.Dispose() }
        if ($tls) { $tls.Dispose() }
        $tcp.Dispose()
    }
}

function New-Area52PublicationTrust {
    param([Parameter(Mandatory = $true)][string]$Directory)
    $authorities = @{}
    foreach ($hostName in @('github.com', 'api.github.com', 'uploads.github.com', 'raw.githubusercontent.com', 'release-assets.githubusercontent.com')) {
        $hostAuthorities = @(Get-Area52PublicationAuthorities -HostName $hostName)
        if (-not $hostAuthorities.Count) { throw "Missing publication certificate chain: $hostName" }
        foreach ($encoded in $hostAuthorities) {
            if (-not $encoded) { throw 'Empty publication certificate chain' }
            $authorities[$encoded] = $true
        }
    }
    if (-not $authorities.Count) { throw 'No validated publication certificate authorities' }
    $pem = ($authorities.Keys | Sort-Object | ForEach-Object {
        "-----BEGIN CERTIFICATE-----`n" + $_ + "`n-----END CERTIFICATE-----"
    }) -join "`n"
    $bundle = Join-Path $Directory 'publication-ca.pem'
    [IO.File]::WriteAllText($bundle, $pem, [Text.Encoding]::ASCII)
    return $bundle
}
