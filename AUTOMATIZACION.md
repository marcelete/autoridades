# Automatización de SIFCOP (costo cero)

El objetivo es que la búsqueda de autoridades corra sola **al iniciar sesión**, pero
sin gastar de más los créditos gratuitos de Tavily (~1.000/mes, y cada corrida usa ~92).
Por eso el diseño es: **disparar al login, pero correr de verdad una sola vez por mes.**

## Cómo funciona

- El disparador de Windows es "al iniciar sesión" → ejecuta `correr_sifcop.bat`.
- `buscar_autoridades.py` tiene un **candado mensual**: si ya existe una corrida de
  este mes en `output/`, sale enseguida sin buscar nada. Así, aunque prendas la PC
  todos los días, sólo hace el trabajo real una vez al mes.

## Instalación (una sola vez)

Clic derecho sobre `instalar_tarea_programada.ps1` → **Ejecutar con PowerShell**.

O desde una consola en esta carpeta:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar_tarea_programada.ps1
```

Eso registra la tarea `SIFCOP - Autoridades (mensual)`. Corre oculta, como tu usuario,
sin permisos de administrador.

## Comandos útiles

```powershell
# Probar la tarea ahora (respeta el candado mensual)
Start-ScheduledTask -TaskName 'SIFCOP - Autoridades (mensual)'

# Ver la tarea
Get-ScheduledTask -TaskName 'SIFCOP - Autoridades (mensual)'

# Quitar la automatización
Unregister-ScheduledTask -TaskName 'SIFCOP - Autoridades (mensual)' -Confirm:$false
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
