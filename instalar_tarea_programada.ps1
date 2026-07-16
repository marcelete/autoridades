# ============================================================
#  SIFCOP - Registra una Tarea Programada que corre la busqueda
#  de autoridades AL INICIAR SESION en Windows.
#
#  El script buscar_autoridades.py (modo --auto) verifica una vez
#  por dia y solo corre de verdad si pasaron 7 dias desde la ultima
#  corrida. Asi, aunque el disparador sea "cada inicio de sesion",
#  la busqueda se hace ~1 vez por semana y no gasta creditos de mas.
#
#  USO:  clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#        (o desde una consola:  powershell -ExecutionPolicy Bypass -File .\instalar_tarea_programada.ps1)
#
#  Para QUITARLA mas adelante:
#        Unregister-ScheduledTask -TaskName 'SIFCOP - Autoridades (semanal)' -Confirm:$false
# ============================================================

$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bat = Join-Path $dir "correr_sifcop.bat"
$nombreTarea = "SIFCOP - Autoridades (semanal)"

if (-not (Test-Path $bat)) {
    Write-Error "No se encontro el launcher: $bat"
    exit 1
}

# Idempotente: si ya existe la tarea, la borramos y la volvemos a crear.
$existente = Get-ScheduledTask -TaskName $nombreTarea -ErrorAction SilentlyContinue
if ($existente) {
    Unregister-ScheduledTask -TaskName $nombreTarea -Confirm:$false
    Write-Host "Tarea previa eliminada (se vuelve a crear)."
}

# Accion: corre el .bat de forma oculta via cmd.
$accion = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"$bat`"" `
    -WorkingDirectory $dir

# Disparador: al iniciar sesion este usuario.
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Ajustes: oculto, que arranque aunque se haya perdido el disparo, sin frenar por bateria.
$ajustes = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Corre como el usuario actual, sin privilegios elevados.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $nombreTarea `
    -Action $accion -Trigger $trigger -Settings $ajustes -Principal $principal `
    -Description "Verificacion de autoridades SIFCOP al iniciar sesion (1 chequeo por dia; busca cada 7 dias)." | Out-Null

Write-Host ""
Write-Host "OK. Tarea '$nombreTarea' registrada." -ForegroundColor Green
Write-Host "Verifica al iniciar sesion (1 vez por dia) y busca solo si pasaron 7 dias."
Write-Host ""
Write-Host "Probar ahora mismo (respeta la cadencia de 7 dias):"
Write-Host "    Start-ScheduledTask -TaskName '$nombreTarea'"
Write-Host "Quitarla:"
Write-Host "    Unregister-ScheduledTask -TaskName '$nombreTarea' -Confirm:`$false"
