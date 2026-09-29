# Abre los puertos de la profesora SOLO para redes privadas (la de la casa), igual que el Copiloto.
# 8770/TCP = conexión de la app   ·   8771/UDP = descubrimiento automático del PC
$ErrorActionPreference = "Stop"
Remove-NetFirewallRule -DisplayName "Profesora de Ingles*" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "Profesora de Ingles - Servidor" -Direction Inbound -Protocol TCP -LocalPort 8770 -Action Allow -Profile Private | Out-Null
New-NetFirewallRule -DisplayName "Profesora de Ingles - Descubrimiento" -Direction Inbound -Protocol UDP -LocalPort 8771 -Action Allow -Profile Private | Out-Null
Write-Host "Firewall listo (solo red privada)." -ForegroundColor Green

# Problema conocido del Copiloto: si Windows marca el wifi como "Público", el firewall bloquea todo.
$Publicas = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq "Public" }
foreach ($red in $Publicas) {
    $r = Read-Host "La red '$($red.Name)' esta marcada como Publica. ¿La cambio a Privada? (s/n)"
    if ($r -eq "s") {
        Set-NetConnectionProfile -InterfaceIndex $red.InterfaceIndex -NetworkCategory Private
        Write-Host "Red '$($red.Name)' ahora es Privada." -ForegroundColor Green
    }
}
Start-Sleep -Seconds 2
