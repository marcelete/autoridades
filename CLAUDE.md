# CLAUDE.md

Este archivo guía a Claude Code (claude.ai/code) al trabajar con el código de este repositorio.

## Qué es esto

SIFCOP — una herramienta de **un solo script** que se corre una vez por mes (a mano) para monitorear cambios en las autoridades de seguridad de Argentina: 5 fuerzas federales (jefe + subjefe) y 24 jurisdicciones provinciales/CABA (ministro de seguridad + jefe de policía + subjefe). Busca en la web, extrae datos estructurados con un LLM, e informa cualquier cambio de autoridades contra un archivo de referencia. Sin servidor, sin scheduler — se ejecuta manualmente.

El código, los prompts, los archivos de salida y los términos del dominio están todos en **español**. Mantené los nuevos strings visibles al usuario en español para que coincidan.

## Comandos

```bash
# Instalar dependencias del script activo
pip install groq tavily-python

# Correr la búsqueda mensual (escribe todo bajo output/)
python buscar_autoridades.py
```

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
1. **`output/maestro.json`** (un maestro fijo, verificado a mano) si existe, si no
2. el `output/autoridades_*.json` más reciente (última corrida).

**Importante:** el maestro [maestro.json](maestro.json) hoy vive en la **raíz del proyecto**, pero el código sólo lo lee desde `output/maestro.json` (`MAESTRO_JSON = CARPETA_SALIDA/"maestro.json"`). Hasta que se copie dentro de `output/`, las comparaciones caen a la corrida anterior en vez del maestro fijo. Este paso de copiado es una tarea pendiente conocida. Peor aún: **hoy `output/` ni siquiera existe** (el script nunca se corrió en esta máquina), así que toda corrida arranca como "primera ejecución — sin referencia" y no compara contra nada hasta que se resuelva esto.

El esquema anidado del maestro difiere del esquema de salida por consulta, así que dos adaptadores los normalizan a un índice común `{jurisdiccion: {cargo: nombre}}`: `_indice_desde_maestro()` vs `_indice_desde_bloques()`. La comparación coteja **apellidos normalizados** (sin tildes, ignorando `NO ENCONTRADO`/vacío) — esto suprime específicamente los falsos positivos por nombre-completo-vs-apellido y por diferencias de tildes. Conservá eso al tocar `comparar_con_referencia()`. Limitación conocida: comparar sólo el último apellido puede **ocultar un cambio real** cuando el apellido coincide pero cambia la persona (p. ej. "Juan Pérez" → "Marcelo Pérez").

### La fuente verificada es el JSON, no el Excel

El dato de referencia validado a mano es **[maestro.json](maestro.json)** (82 datos, corregidos según la lista de "Datos verificados con errores" de [resumen proyecto.md](resumen%20proyecto.md)). El Excel `Autoridades de Min. Seg y FFSS...xlsx` es el **listado original y está desactualizado**: todavía tiene valores viejos que el maestro ya corrigió (Corrientes: Gaya → Vallejos; Jujuy: Corro → Gil Urquiola; Catamarca: Natella/Córdoba/Sánchez → Venturini/Herrera/Seiler; Santiago del Estero: B. Herrera → Barbur; La Pampa subjefe: Calzada → Sosa; Salta ministro difiere; etc.). Al sincronizar o regenerar, **el JSON manda sobre el Excel**.

Estructura del Excel (1 hoja `Jurisdicciones Provinciales y C...`, 30 filas de datos): columnas `Jurisdicción | Ministro / Cargo | Fuente | Fuerza | Jefe | Subjefe | Fuente 2 | Fecha Actualización`. Filas 2–25 = provincias/CABA; filas 26–30 = las 5 fuerzas federales.

### Salidas (todas bajo `output/`, con timestamp)

`autoridades_<ts>.json` / `.csv` (resultados principales), `fuentes_oficiales_<ts>.csv` / `.txt` (páginas oficiales detectadas), `diferencias_<ts>.txt` (reporte de cambios), y un `log_tokens.txt` que se va agregando.

## Dos implementaciones — sabé cuál está viva

- **Activa:** `buscar_autoridades.py` (v6) — búsqueda web con **Tavily** + **Groq** (`llama-3.3-70b-versatile`).
- **Legacy:** `config.txt` y `prueba.py` son restos de un enfoque anterior con **Gemini** (`google-genai`, Google Search Grounding, dos API keys). `resumen proyecto.md` todavía describe ese diseño viejo con Gemini (y dice "6 consultas") — tratalo como contexto histórico, no como la especificación actual. El pipeline vivo es Tavily + Groq con 7 consultas.

## Configuración

Las API keys se leen de variables de entorno con fallbacks hardcodeados en el código fuente (`GROQ_API_KEY`, `TAVILY_API_KEY` en `buscar_autoridades.py`; las keys de Gemini en `config.txt`). Definí las variables de entorno para sobrescribirlas. Los parámetros ajustables (modelo, tope de tokens, reintentos/backoff, duración de pausas, cantidad de resultados de Tavily, toggle de dominios oficiales) son las constantes en `MAYÚSCULAS` del bloque CONFIGURACION cerca del inicio del script.

## Restricciones y presupuesto

**Presupuesto cero — no se compran tokens.** Todo el pipeline depende de free tiers: Groq (LLM) y Tavily (búsqueda web, 1.000 créditos/mes). Cada corrida gasta ~46 búsquedas Tavily × 2 créditos (`search_depth="advanced"`) ≈ **~92 créditos**, o sea un tope práctico de ~10 corridas/mes. Por eso el diseño es **una corrida por mes**, no por evento: correrlo en cada arranque de la PC agotaría los créditos en días. Cualquier automatización debe throttlear a una corrida mensual.

## Roadmap (pedido por el usuario, aún NO implementado)

- **Salida a Excel con xlwings:** cada corrida debe agregar una **hoja nueva** (`autoridades_AAAAMMDD`) al workbook existente, respetando su layout de 8 columnas, en vez de sólo JSON/CSV. Hoy el script no toca el Excel.
- **Automatización al iniciar sesión (costo cero):** Task Scheduler de Windows con trigger "al iniciar sesión" corriendo `buscar_autoridades.py`, pero con un guard que **salta si ya se corrió este mes** (chequear fecha de la última salida en `output/`).
- **Verificación asistida por Claude:** cuando la corrida mensual marca diferencias, abrir una sesión de Claude Code y verificar cada cambio contra fuentes oficiales (WebSearch, incluido en el plan, sin API paga) antes de tocar el maestro.

## Bugs conocidos menores

- `.lstrip("www.")` (en `extraer_fuentes_oficiales` y `construir_contexto`) no saca el prefijo `www.` sino cualquier char del conjunto `{w, ., }` al inicio → `web.policiadesalta.gob.ar` queda como `eb.policiadesalta.gob.ar`. Sólo afecta el nombre de dominio mostrado. Corregir con `if host.startswith("www."): host = host[4:]`.
- API keys reales hardcodeadas en `buscar_autoridades.py`, `config.txt` y `prueba.py`. Si el repo se comparte, se filtran. Convendría moverlas a variables de entorno / `.env` y rotarlas.
