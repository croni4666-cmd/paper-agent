# Probe common clash proxy ports
$ports = @(7890, 7891, 10809, 1080, 1087, 789, 8888, 8889, 1082, 1086, 2080, 2082)
Write-Host "Probing common proxy ports on 127.0.0.1..."
foreach ($p in $ports) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $ar = $c.BeginConnect('127.0.0.1', $p, $null, $null)
        $ok = $ar.AsyncWaitHandle.WaitOne(500, $false)
        if ($ok -and $c.Connected) {
            Write-Host "  port $p : OPEN"
            $c.Close()
        } else {
            Write-Host "  port $p : closed"
            $c.Close()
        }
    } catch {
        Write-Host "  port $p : error"
    }
}

# Also try env vars
Write-Host "`nEnv vars:"
foreach ($var in 'HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy') {
    $v = [Environment]::GetEnvironmentVariable($var)
    if ($v) { Write-Host "  $var = $v" }
}
