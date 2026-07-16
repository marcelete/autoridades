# Automatización de SIFCOP (costo cero)

El objetivo es que la búsqueda de autoridades corra sola **al iniciar sesión**, pero
sin gastar de más los créditos gratuitos de Tavily (~1.000/mes, y cada corrida usa ~92).
Por eso el diseño es: **verificar al login una vez por día, pero buscar de verdad sólo
una vez cada 7 días** (~4 corridas/mes ≈ ~400 créditos, muy por debajo del tope).

## Cómo funciona

- El disparador de Windows es "al iniciar sesión" → ejecuta `correr_sifcop.bat`, que
  llama a `buscar_autoridades.py --auto`.
- **Chequeo diario:** en modo `--auto`, la primera vez del día registra la fecha en
  `output\ultimo_chequeo.txt`; si volvés a iniciar sesión el mismo día, sale enseguida.
- **Cadencia de 7 días:** aunque sea el chequeo del día, sólo busca de verdad si pasaron
  **7 días** desde la última corrida (mira los `autoridades_*.json` de `output/`). Si no,
  informa cuántos días faltan y sale sin gastar nada.
- **Al día 7:** el primer inicio de sesión de ese día dispara la búsqueda "lo antes
  posible", y el contador de 7 días se reinicia desde esa corrida.
- El número de días se ajusta con `DIAS_ENTRE_CORRIDAS` en el script.

## Instalación (una sola vez)

Clic derecho sobre `instalar_tarea_programada.ps1` → **Ejecutar con PowerShell**.

O desde una consola en esta carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar_tarea_programada.ps1
```

Eso registra la tarea `SIFCOP - Autoridades (semanal)`. Corre oculta, como tu usuario,
sin permisos de administrador.

## Comandos útiles

```powershell
# Probar la tarea ahora (respeta el chequeo diario y la cadencia de 7 días)
Start-ScheduledTask -TaskName 'SIFCOP - Autoridades (semanal)'

# Ver la tarea
Get-ScheduledTask -TaskName 'SIFCOP - Autoridades (semanal)'

# Quitar la automatización
Unregister-ScheduledTask -TaskName 'SIFCOP - Autoridades (semanal)' -Confirm:$false
```

```bash
# Correr a mano, ignorando el candado (gasta créditos)
python buscar_autoridades.py --force

# Regenerar una hoja de Excel desde el maestro verificado (NO gasta créditos)
python buscar_autoridades.py --excel-desde-maestro
```

## Dónde queda el registro

- Consola de cada corrida automática: `output\log_ejecucion.txt`
- Resultados: `output\autoridades_<timestamp>.json` / `.csv`
- Cambios detectados: `output\diferencias_<timestamp>.txt`
- Hoja nueva por corrida en el Excel, con las celdas cambiadas resaltadas en amarillo.

## Verificación asistida (recomendado)

Cuando `diferencias_<timestamp>.txt` marque un cambio, **verificalo antes de tocar el
maestro**. Podés abrir una sesión de Claude Code y pedirle que confirme ese cambio
puntual contra la fuente oficial (búsqueda web incluida en el plan, sin API paga).
Recién ahí actualizás `maestro.json`.
