@echo off
REM ============================================================
REM SIFCOP - Launcher de la verificacion de autoridades.
REM Lo usa la Tarea Programada AL INICIAR SESION. El modo --auto:
REM   - verifica una sola vez por dia (chequeos extra salen enseguida)
REM   - solo busca de verdad si pasaron 7 dias desde la ultima corrida
REM Asi corre ~1 vez por semana sin quemar los creditos de Tavily.
REM Para forzar una corrida ya:  python buscar_autoridades.py --force
REM ============================================================

setlocal
cd /d "%~dp0"
if not exist "output" mkdir "output"

REM Ruta de Python (con fallback al python del PATH)
set "PY=C:\Users\marcelo.bellizia\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

echo.>> "output\log_ejecucion.txt"
echo ==================== %date% %time% ====================>> "output\log_ejecucion.txt"
"%PY%" "buscar_autoridades.py" --auto >> "output\log_ejecucion.txt" 2>&1

endlocal
