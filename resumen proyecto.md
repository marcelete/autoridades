# Resumen del proyecto: SIFCOP Monitor de Autoridades

## Objetivo
Automatizar el monitoreo mensual de cambios en las autoridades de seguridad de Argentina: 5 fuerzas federales (jefe + subjefe) y 24 jurisdicciones (ministro + jefe + subjefe de policía) = 82 datos totales. Ejecución manual una vez por mes, sin servidores externos ni costos.

## Herramientas
- **Python** con la librería `google-genai`
- **Gemini API** (Google AI Studio, free tier): modelo final `gemini-2.5-flash-lite` (1000 RPD gratis)
- **Google Search Grounding**: permite al modelo buscar en internet en tiempo real
- **Tkinter / PyInstaller**: descartados por ahora, foco en el script
- **Archivos de salida**: JSON, CSV, TXT de diferencias, log de tokens

## Método
6 consultas pequeñas a Gemini con grounding activado, alternando entre 2 API keys del mismo proyecto para distribuir carga. Cada consulta pide un JSON estructurado con nombres, cargos y URL de fuente. El script compara los resultados contra un archivo de referencia y reporta diferencias.

## Problemas resueltos
| Problema | Solución |
|---|---|
| Modelo generaba 2 JSONs concatenados | `_extraer_primer_json()` por conteo de llaves |
| Caracteres de control rompían el parser | `re.sub` antes de parsear |
| URLs largas sin cerrar rompían el JSON | Regex trunca URLs > 300 chars |
| `response.text` devuelve `None` | Raise `ValueError` para trigger reintento |
| Límite 20 RPD de `gemini-2.5-flash` | Cambio a `gemini-2.5-flash-lite` (1000 RPD) |
| Falsos positivos por nombre completo vs apellido | Comparación por último apellido normalizado |
| Falsos positivos por tildes | `unicodedata.normalize NFD` |
| Modelo oscila entre valores distintos entre corridas | JSON maestro como referencia fija |

## Estado actual
- Script funcional: 6/6 consultas exitosas, ~21.000 tokens por corrida (muy por debajo de límites)
- JSON maestro (`maestro.json`) construido y verificado con 82 datos al 23/04/2026
- Lógica de comparación contra maestro implementada y testeada
- **Pendiente**: copiar `maestro.json` a la carpeta `SIFCOP_Gemini` para activar la comparación fija
- **Pendiente**: validar una corrida completa contra el maestro para confirmar que los falsos positivos desaparecen

## Datos verificados con errores en el listado original
Corrientes (Gaya→Vallejos), Jujuy (Corro→Gil Urquiola + nueva cúpula policial), Mendoza (Zárate→Mercedes Rus), Santa Fe subjefe (Filchel→Pagano), Córdoba (subjefe único→3 subjefes funcionales), Entre Ríos subjefe (Hormachea→Clausich), Catamarca (Rosales Matienzo→Venturini como Min. Seguridad), Río Negro subjefe (Fabi→Tapia), La Rioja (Castillo→Molina jefe, Sotomayor subjefe), San Juan (datos completamente distintos), Santiago del Estero ministro (Pato→Barbur), Tierra del Fuego ministro (confirmado por vos: Lucía Rossi).