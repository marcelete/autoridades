# CLAUDE.md

Este archivo guía a Claude Code (claude.ai/code) al trabajar con el código de este repositorio.

## Qué es esto

SIFCOP — una herramienta de **un solo script** que monitorea cambios en las autoridades de seguridad de Argentina: 5 fuerzas federales (jefe + subjefe) y 24 jurisdicciones provinciales/CABA (ministro de seguridad + jefe de policía + subjefe). Busca en la web, extrae datos estructurados con un LLM, e informa cualquier cambio de autoridades contra un archivo de referencia. Corre **una vez cada 7 días**: se puede ejecutar a mano, o dejar que la Tarea Programada lo verifique al iniciar sesión (una vez por día) y sólo busque si pasaron los 7 días.

El código, los prompts, los archivos de salida y los términos del dominio están todos en **español**. Mantené los nuevos strings visibles al usuario en español para que coincidan.

## Comandos

```bash
# Instalar dependencias del script activo
pip install groq tavily-python xlwings

# Correr la búsqueda (escribe todo bajo output/ + una hoja nueva en el Excel)
# Cadencia: si la última corrida fue hace < 7 días, sale sin gastar créditos.
python buscar_autoridades.py

# Modo tarea programada: verifica 1 vez por día y busca sólo si pasaron 7 días
python buscar_autoridades.py --auto

# Forzar la corrida ignorando la cadencia de 7 días (gasta créditos de Tavily)
python buscar_autoridades.py --force

# Regenerar una hoja de Excel desde maestro.json, sin búsquedas ni créditos
python buscar_autoridades.py --excel-desde-maestro
```

Las API keys viven en un archivo `.env` (gitignoreado; ver `.env.example`). El script lo
carga solo con `_cargar_env()`. Sin keys válidas, `main()` corta con un mensaje claro.

La automatización "al iniciar sesión" está en `correr_sifcop.bat` +
`instalar_tarea_programada.ps1` (ver [AUTOMATIZACION.md](AUTOMATIZACION.md)).

No hay build, ni linter, ni suite de tests. `prueba.py` es un chequeo de conexión descartable del camino **legacy** con Gemini (ver más abajo), no un test.

Una corrida completa tarda varios minutos a propósito: duerme `PAUSA_ENTRE_CONSULTAS = 35s` entre las 7 consultas para no pasarse del rate limit de Groq, además de pausas más cortas entre búsquedas de Tavily.

## Arquitectura

Todo el pipeline vive en [buscar_autoridades.py](buscar_autoridades.py). Procesa `CONSULTAS` — **7** grupos de consulta (consulta 1 = las 5 fuerzas federales; consultas 2–7 = provincias agrupadas ≤4 por grupo para mantener los prompts chicos). Para cada grupo:

1. **Búsqueda (Tavily)** — `buscar_entidad()` corre búsquedas web por entidad, y luego una búsqueda *extra* restringida a `include_domains=["gob.ar","gov.ar"]`. Los hosts de redes sociales de `DOMINIOS_EXCLUIDOS` se descartan.
2. **Ranking de fuentes** — `construir_contexto()` ordena primero los resultados oficiales `.gob/.gov/.gob.ar/.gov.ar` y los marca con `[FUENTE OFICIAL GOB/GOV]`; el prompt de sistema le indica al modelo que prefiera esos para `fuente_url`.
3. **Extracción (Groq)** — `llamar_groq()` envía el contexto de búsqueda a `llama-3.3-70b-versatile` con `temperature=0` y pide JSON estricto. Los grupos federal y provincial usan prompts/estructuras JSON distintas (`PROMPT_FEDERALES` vs `PROMPT_PROVINCIALES`).
4. **Comparación** — los resultados nuevos se comparan contra una referencia (ver abajo) y las diferencias se escriben en un reporte.

### La salida del LLM se trata como texto no confiable

`llamar_groq()` endurece deliberadamente el parseo de JSON porque el modelo se porta mal: `_extraer_primer_json()` cuenta llaves para tomar el primer objeto (el modelo a veces emite dos), un regex saca caracteres de control, y otro trunca URLs desbocadas. Si cambiás los prompts o el modelo, mantené este parseo defensivo.

### La comparación y el gotcha de `maestro.json`

`buscar_referencia()` elige la referencia por orden de prioridad:
1. **`output/maestro.json`** (maestro fijo, verificado a mano) si existe, si no
2. **`maestro.json` en la raíz del proyecto** (fallback), si no
3. el `output/autoridades_*.json` más reciente (última corrida).

El maestro [maestro.json](maestro.json) vive en la **raíz del proyecto**. Antes el código sólo lo leía desde `output/maestro.json` y las comparaciones caían a la corrida anterior; **ya está resuelto**: `buscar_referencia()` ahora también toma el maestro de la raíz (`MAESTRO_JSON_RAIZ`). Igual conviene, si algún día querés un maestro distinto para las corridas, dejarlo en `output/maestro.json` (tiene prioridad).

El esquema anidado del maestro difiere del esquema de salida por consulta, así que dos adaptadores los normalizan a un índice común `{jurisdiccion: {cargo: nombre}}`: `_indice_desde_maestro()` vs `_indice_desde_bloques()`. La comparación coteja **apellidos normalizados** (sin tildes, ignorando `NO ENCONTRADO`/vacío) — esto suprime específicamente los falsos positivos por nombre-completo-vs-apellido y por diferencias de tildes. Conservá eso al tocar `comparar_con_referencia()`. Limitación conocida: comparar sólo el último apellido puede **ocultar un cambio real** cuando el apellido coincide pero cambia la persona (p. ej. "Juan Pérez" → "Marcelo Pérez").

### La fuente verificada es el JSON, no el Excel

El dato de referencia validado a mano es **[maestro.json](maestro.json)** (82 datos, corregidos según la lista de "Datos verificados con errores" de [resumen proyecto.md](resumen%20proyecto.md)). El Excel `Autoridades de Min. Seg y FFSS...xlsx` es el **listado original y está desactualizado**: todavía tiene valores viejos que el maestro ya corrigió (Corrientes: Gaya → Vallejos; Jujuy: Corro → Gil Urquiola; Catamarca: Natella/Córdoba/Sánchez → Venturini/Herrera/Seiler; Santiago del Estero: B. Herrera → Barbur; La Pampa subjefe: Calzada → Sosa; Salta ministro difiere; etc.). Al sincronizar o regenerar, **el JSON manda sobre el Excel**.

Estructura del Excel (1 hoja `Jurisdicciones Provinciales y C...`, 30 filas de datos): columnas `Jurisdicción | Ministro / Cargo | Fuente | Fuerza | Jefe | Subjefe | Fuente 2 | Fecha Actualización`. Filas 2–25 = provincias/CABA; filas 26–30 = las 5 fuerzas federales.

### Salidas

Todas bajo `output/` con timestamp: `autoridades_<ts>.json` / `.csv` (resultados principales), `fuentes_oficiales_<ts>.csv` / `.txt` (páginas oficiales detectadas), `diferencias_<ts>.txt` (reporte de cambios), `log_tokens.txt` y `log_ejecucion.txt` (se van agregando).

**Además**, cada corrida agrega una **hoja nueva al Excel** vía xlwings (`guardar_en_excel()`), llamada `autoridades_AAAAMMDD`, con el layout de 8 columnas y las celdas cambiadas resaltadas en amarillo. La salida a Excel está aislada en `try/except`: si Excel no está disponible o el libro está abierto, se avisa pero no se pierde el JSON/CSV. `_bloques_desde_maestro()` convierte el maestro al mismo formato de bloques para poder exportarlo (`--excel-desde-maestro`).

## Dos implementaciones — sabé cuál está viva

- **Activa:** `buscar_autoridades.py` (v6) — búsqueda web con **Tavily** + **Groq** (`llama-3.3-70b-versatile`).
- **Legacy:** `config.txt` y `prueba.py` son restos de un enfoque anterior con **Gemini** (`google-genai`, Google Search Grounding, dos API keys). `resumen proyecto.md` todavía describe ese diseño viejo con Gemini (y dice "6 consultas") — tratalo como contexto histórico, no como la especificación actual. El pipeline vivo es Tavily + Groq con 7 consultas.

## Configuración

Las API keys se leen **sólo** del entorno o de un archivo `.env` junto al script (`_cargar_env()` lo carga sin dependencias externas y sin pisar variables ya definidas). **Ya no hay keys hardcodeadas** en el código: `GROQ_API_KEY` / `TAVILY_API_KEY` tienen fallback vacío y `main()` corta si faltan. El `.env` real está en `.gitignore`; `.env.example` es la plantilla versionada. Los parámetros ajustables (modelo, tope de tokens, reintentos/backoff, duración de pausas, cantidad de resultados de Tavily, toggle de dominios oficiales) son las constantes en `MAYÚSCULAS` del bloque CONFIGURACION cerca del inicio del script.

## Restricciones y presupuesto

**Presupuesto cero — no se compran tokens.** Todo el pipeline depende de free tiers: Groq (LLM) y Tavily (búsqueda web, 1.000 créditos/mes). Cada corrida gasta ~46 búsquedas Tavily × 2 créditos (`search_depth="advanced"`) ≈ **~92 créditos**. Con la cadencia de **7 días** son ~4 corridas/mes ≈ **~400 créditos**, cómodo bajo el tope. Correrlo en cada arranque de la PC agotaría los créditos en días, por eso existe la doble protección: **chequeo diario** (`ya_se_chequeo_hoy` / `MARCADOR_CHEQUEO`) + **cadencia de N días** (`DIAS_ENTRE_CORRIDAS`, `dias_desde_ultima_corrida`). No bajar `DIAS_ENTRE_CORRIDAS` sin recalcular el presupuesto.

## Mejoras ya implementadas (antes eran roadmap)

- **Salida a Excel con xlwings:** implementada (`guardar_en_excel`, `--excel-desde-maestro`). Ver la sección de Salidas.
- **Automatización al iniciar sesión (costo cero):** `correr_sifcop.bat` (llama a `--auto`) + `instalar_tarea_programada.ps1` (tarea `SIFCOP - Autoridades (semanal)`). Doble protección: chequeo diario + cadencia de 7 días. Ver [AUTOMATIZACION.md](AUTOMATIZACION.md).
- **Fix del maestro:** `buscar_referencia()` ahora encuentra el maestro también en la raíz.
- **Fix `.lstrip("www.")`:** reemplazado por el helper `_dominio()`.
- **Seguridad:** las API keys salieron del código a un `.env` gitignoreado (`_cargar_env()`).

## Pendiente / ideas a futuro

- **Verificación asistida por Claude:** cuando una corrida marca diferencias, abrir una sesión de Claude Code y verificar cada cambio contra fuentes oficiales (WebSearch, incluido en el plan, sin API paga) antes de tocar el maestro.
- **Rotar las API keys** que estuvieron hardcodeadas (siguen siendo válidas; conviene regenerarlas por las dudas).
- **Limitación de la comparación por apellido:** puede ocultar cambios de persona con mismo apellido (ver sección de comparación).
