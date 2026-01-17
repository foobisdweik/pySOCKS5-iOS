# --- CONFIGURATION ---
$iPhoneIP = "172.20.10.1"
$ProxyPort = 9999
$CheckInterval = 3 

Clear-Host
Write-Host "--- iPhone SOCKS5 Proxy Dashboard ---" -ForegroundColor Cyan
Write-Host "Monitoring: $iPhoneIP on Port $ProxyPort"
Write-Host "---------------------------------------"

while($true) {
    $Timestamp = Get-Date -Format "HH:mm:ss"
    
    # 1. Ping the Hotspot Gateway
    $Ping = Test-Connection -ComputerName $iPhoneIP -Count 1 -Quiet
    $PhoneStatus = if($Ping) { "REACHABLE" } else { "UNREACHABLE" }
    
    # 2. Test the SOCKS5 Server Socket
    $Socket = New-Object Net.Sockets.TcpClient
    try {
        $Connect = $Socket.BeginConnect($iPhoneIP, $ProxyPort, $null, $null)
        $Wait = $Connect.AsyncWaitHandle.WaitOne(1000, $false)
        if($Wait -and $Socket.Connected) {
            $ProxyStatus = "ONLINE " # Space at end to clear old chars
            $Color = "Green"
        } else {
            $ProxyStatus = "OFFLINE"
            $Color = "Red"
        }
    } catch {
        $ProxyStatus = "ERROR  "
        $Color = "Red"
    } finally {
        $Socket.Close()
    }

    # --- THE IN-LINE UPDATE MAGIC ---
    # `r moves the cursor to the start of the line. 
    # -NoNewline prevents jumping to a new row.
    Write-Host "`r[$Timestamp] iPhone: $PhoneStatus | Proxy: $ProxyStatus" -ForegroundColor $Color -NoNewline

    Start-Sleep -Seconds $CheckInterval
}