# ============================================================
#  SIFCOP - Registra una Tarea Programada que corre la busqueda
#  de autoridades AL INICIAR SESION en Windows.
#
#  El script buscar_autoridades.py tiene un candado interno:
#  solo corre de verdad UNA vez por mes, asi que aunque el
#  disparador sea "cada inicio de sesion", no se gastan creditos
#  de Tavily de mas.
#
#  USO:  clic derecho sobre este archivo -> "Ejecutar con PowerShell"
#        (o desde una consola:  powershell -ExecutionPolicy Bypass -File .\instalar_tarea_programada.ps1)
#
#  Para QUITARLA mas adelante:
#        Unregister-ScheduledTask -TaskName 'SIFCOP - Autoridades (mensual)' -Confirm:$false
# ============================================================

$ErrorActionPreference = "Stop"

$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bat = Join-Path $dir "correr_sifcop.bat"
$nombreTarea = "SIFCOP - Autoridades (mensual)"

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
    -Description "Busqueda mensual de autoridades SIFCOP al iniciar sesion (candado interno: 1 vez por mes)." | Out-Null

Write-Host ""
Write-Host "OK. Tarea '$nombreTarea' registrada." -ForegroundColor Green
Write-Host "Corre al iniciar sesion; el script salta si ya se corrio este mes."
Write-Host ""
Write-Host "Probar ahora mismo (respeta el candado mensual):"
Write-Host "    Start-ScheduledTask -TaskName '$nombreTarea'"
Write-Host "Quitarla:"
Write-Host "    Unregister-ScheduledTask -TaskName '$nombreTarea' -Confirm:`$false"
