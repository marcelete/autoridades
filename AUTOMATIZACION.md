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

## Alerta visual de cambios

Si la corrida detecta diferencias contra el maestro, al terminar se abre una
**ventana emergente** (con `tkinter`, ya viene con Python) que lista jurisdicción,
cargo, valor anterior y nuevo. Queda al frente aunque la tarea corra oculta, así el
cambio no pasa desapercibido. Se cierra sola a los 30 minutos si nadie la ve, o antes
con el botón "Cerrar". Para desactivarla (el reporte en texto se guarda igual):

```bash
python buscar_autoridades.py --sin-alerta
```

## Dónde queda el registro

- Consola de cada corrida automática: `output\log_ejecucion.txt`
- Resultados: `output\autoridades_<timestamp>.json` / `.csv`
- Cambios detectados: `output\diferencias_<timestamp>.txt` + ventana emergente si hay cambios
- Hoja nueva por corrida en el Excel, con las celdas cambiadas resaltadas en amarillo.

## Verificación asistida (recomendado)

Cuando `diferencias_<timestamp>.txt` marque un cambio, **verificalo antes de tocar el
maestro**. Podés abrir una sesión de Claude Code y pedirle que confirme ese cambio
puntual contra la fuente oficial (búsqueda web incluida en el plan, sin API paga).
Recién ahí actualizás `maestro.json`.

## Rutina semanal de verificación en la nube (2026-07-17)

Además de la verificación manual de arriba, hay una **rutina automática** creada con
la skill `/schedule` de Claude Code que hace ese mismo trabajo sola, una vez por
semana, sin gastar créditos de Tavily/Groq (usa el plan de Claude del usuario, no una
API separada). El prompt completo que usa está en
[rutina_verificacion_semanal.md](rutina_verificacion_semanal.md).

**Qué hace:** lee `maestro.json` del repo `github.com/marcelete/autoridades` (privado),
verifica con WebSearch las 29 entidades/~110 campos, y para cada uno reporta
Confirmado / Cambió / Dudoso. Para los campos "Cambió" con confianza alta (2+ fuentes
independientes y recientes) abre un **Pull Request** con la edición puntual — nunca
escribe directo a `main`. El Excel **no** se actualiza desde la nube (no hay Excel en
un sandbox en la nube); después de mergear un PR hay que correr localmente:

```bash
python buscar_autoridades.py --excel-desde-maestro
```

**Modelo:** arranca con Haiku 4.5 (para minimizar consumo de tokens en una tarea
semanal recurrente). Si el reporte muestra la misma falla que tuvo Groq/llama-3.3-70b
(poco recall, no distingue fuentes desactualizadas), reconfigurar la rutina a
Sonnet 5 con effort alto — se puede editar sin recrearla desde cero, vía la propia
skill `/schedule`.

**Dónde ver los resultados:** en el historial de la rutina en Claude.ai (`/schedule`
también permite listarlas y ver corridas pasadas). Este mecanismo es independiente de
la Tarea Programada de Windows — sigue corriendo aunque la PC esté apagada.

**Posible evolución futura** (no implementada todavía, ver `CLAUDE.md`): si esta
rutina demuestra ser consistentemente mejor que Tavily+Groq, evaluar reemplazar todo
el pipeline de recolección semanal por un agente Claude — probablemente corriendo
localmente (Task Scheduler + `claude` en modo headless) para no perder el acceso al
Excel, que la nube no puede tocar.

## Sistema de 2 agentes (Buscador + Verificador) — en prueba (2026-07-17)

Motivado por un hallazgo real: la rutina de un solo agente de arriba propuso 4
cambios el 2026-07-17; verificados a mano, 3 eran correctos y 1 no (Servicio
Penitenciario Federal → "Velarde", una persona removida del cargo en 2024, tomada
de una fuente de 2023 sin fecha visible en la URL). Las reglas de calidad
escritas en un solo prompt no bastaron para evitarlo.

**Diseño**: dos roles separados, documentados en `verificaciones/`:
- **Buscador** (`verificaciones/prompt_buscador.md`): busca con WebSearch y reporta
  hallazgos + fuentes para las 29 entidades, sin juzgar si es "un cambio".
- **Verificador** (`verificaciones/prompt_verificador.md`): segunda pasada
  independiente (no ve el razonamiento del Buscador) que busca activamente
  evidencia de que una fuente esté superada antes de aceptar un cambio, y se
  autoevalúa contra 4 casos ya conocidos (autotest) antes de terminar.

Todo queda registrado en `verificaciones/AAAA-MM-DD_HHMM/` (`buscador.json`,
`verificador.json`, `reporte.md`) + una fila en `verificaciones/historial.md` — ver
el esquema completo en `verificaciones/README.md`.

**Estado actual**: sesión de refinamiento única programada para el 2026-07-17 20:00
ART (`trig_01KHrB4aFLoTPiANpdwbazEm`, `run_once_at`, no recurrente). Es una prueba —
**no reemplaza** todavía la rutina semanal de producción
(`trig_01FYEWGSbaSUxCrCBQZZPGDq`) ni la Tarea Programada local de Tavily+Groq, que
siguen activas como respaldo. La decisión de reemplazar la producción se toma
revisando el resultado (`verificaciones/2026-07-17_2000/reporte.md` y el autotest),
no automáticamente.
