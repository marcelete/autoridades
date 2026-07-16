@echo off
REM ============================================================
REM SIFCOP - Launcher de la corrida mensual de autoridades.
REM Lo usa la Tarea Programada (al iniciar sesion) y tambien
REM se puede ejecutar a mano. El script tiene un candado interno:
REM solo corre de verdad UNA vez por mes (protege los creditos
REM de Tavily). Para forzar, usar:  python buscar_autoridades.py --force
REM ============================================================

setlocal
cd /d "%~dp0"
if not exist "output" mkdir "output"

REM Ruta de Python (con fallback al python del PATH)
set "PY=C:\Users\marcelo.bellizia\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

echo.>> "output\log_ejecucion.txt"
echo ==================== %date% %time% ====================>> "output\log_ejecucion.txt"
"%PY%" "buscar_autoridades.py" >> "output\log_ejecucion.txt" 2>&1

endlocal
