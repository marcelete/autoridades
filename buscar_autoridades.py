# =============================================================================
# SIFCOP - Busqueda mensual de autoridades de seguridad
# v6 — Tavily (busqueda web) + Groq Cloud (LLM llama-3.3-70b)
#
# Cambios v6:
#   - Nuevo objetivo: detectar paginas oficiales (.gob/.gov/.gob.ar/.gov.ar)
#     que anuncian cambios de autoridades (no diarios, no redes sociales)
#   - Busqueda adicional con include_domains=[gob.ar, gov.ar] por entidad
#   - Fuentes oficiales priorizadas en el contexto enviado a Groq
#   - Nuevo reporte: fuentes_oficiales_TIMESTAMP.csv y .txt
#   - Archivos de salida en subcarpeta "output" del proyecto
#
# Flujo por consulta:
#   1. Tavily busca en internet para cada entidad del grupo
#      (busqueda general + busqueda dirigida a dominios .gob.ar/.gov.ar)
#   2. Groq extrae y estructura los datos en JSON usando esos resultados
#   3. Se genera reporte separado de fuentes oficiales detectadas
#
# Consulta 1 — 5 fuerzas federales
# Consulta 2 — Buenos Aires, CABA, Cordoba, Santa Fe
# Consulta 3 — Mendoza, Tucuman, Salta, Jujuy
# Consulta 4 — Entre Rios, Corrientes, Misiones, Chaco
# Consulta 5 — Neuquen, Rio Negro, Chubut, Santa Cruz
# Consulta 6 — Tierra del Fuego, San Juan, San Luis, La Rioja
# Consulta 7 — Catamarca, La Pampa, Formosa, Santiago del Estero
#
# Requisitos:  pip install groq tavily-python
# Uso:         python buscar_autoridades.py
# =============================================================================

import os
import re
import json
import csv
import time
from datetime import datetime
from urllib.parse import urlparse
from groq import Groq
from tavily import TavilyClient

# =============================================================================
# CONFIGURACION
# =============================================================================

def _cargar_env():
    """Carga variables de un archivo .env junto al script (si existe), sin
    dependencias externas. No pisa variables ya definidas en el entorno."""
    ruta_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(ruta_env):
        return
    try:
        with open(ruta_env, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, _, valor = linea.partition("=")
                clave = clave.strip()
                valor = valor.strip().strip('"').strip("'")
                if clave and clave not in os.environ:
                    os.environ[clave] = valor
    except OSError:
        pass


_cargar_env()

# Las API keys se leen SOLO del entorno o del .env — nunca hardcodeadas.
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY",   "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

MODELO                = "llama-3.3-70b-versatile"
MAX_TOKENS            = 6000
MAX_REINTENTOS        = 3
PAUSA_ENTRE_CONSULTAS = 35   # segundos entre consultas (margen para rate limit Groq)
PAUSA_ENTRE_BUSQUEDAS = 2    # segundos entre entidades en Tavily
TAVILY_MAX_RESULTS    = 7
TAVILY_CHARS_POR_RESULTADO = 1200  # truncar contenido de cada resultado

# Busqueda adicional dirigida a dominios oficiales .gob.ar / .gov.ar
BUSCAR_EN_DOMINIOS_OFICIALES = True
DOMINIOS_OFICIALES_TAVILY    = ["gob.ar", "gov.ar"]
TAVILY_MAX_RESULTS_OFICIAL   = 5

# Archivos de salida en subcarpeta "output" del proyecto
CARPETA_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
MAESTRO_JSON   = os.path.join(CARPETA_SALIDA, "maestro.json")

DOMINIOS_EXCLUIDOS = frozenset({
    "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "facebook.com", "pinterest.com",
})

# =============================================================================
# PROMPTS
# {fecha}, {lista} y {contexto} se reemplazan en tiempo de ejecucion.
# =============================================================================

PROMPT_SISTEMA = (
    "Eres un asistente experto en extraer informacion estructurada sobre "
    "autoridades de seguridad de Argentina a partir de resultados de busqueda web. "
    "Analiza los resultados proporcionados y extrae los datos solicitados en JSON estricto. "
    "Usa SOLO la informacion que aparece explicitamente en los resultados. "
    "PRIORIZA las fuentes marcadas como [FUENTE OFICIAL GOB/GOV] para el campo fuente_url. "
    "Si hay una fuente oficial disponible, usa su URL en fuente_url en lugar de fuentes periodisticas. "
    "Si un nombre contiene errores de tipeo evidentes, numeros sueltos o parece corrupto, pon 'NO ENCONTRADO'. "
    "Si un dato no aparece con claridad suficiente, pon 'NO ENCONTRADO'."
)

PROMPT_FEDERALES = """La fecha de hoy es {fecha}.

A continuacion encontraras resultados de busqueda web sobre las autoridades actuales
de las siguientes fuerzas de seguridad federales de Argentina:

{lista}

=== RESULTADOS DE BUSQUEDA ===
{contexto}
=== FIN DE RESULTADOS ===

Basandote UNICAMENTE en los resultados anteriores, extrae el jefe y subjefe de cada fuerza.
Para cada fuerza necesito:
- Cargo exacto del jefe (puede variar: Jefe, Director Nacional, Prefecto, Comandante, etc.)
- Nombre completo del jefe
- Cargo exacto del subjefe
- Nombre completo del subjefe
- URL de la fuente donde aparece el dato (preferir fuentes [FUENTE OFICIAL GOB/GOV])

Responde UNICAMENTE con un JSON valido con esta estructura, sin texto adicional:
{{
  "fecha_busqueda": "{fecha}",
  "seccion": "fuerzas_federales",
  "registros": [
    {{
      "jurisdiccion": "nombre de la fuerza",
      "cargo_autoridad_1": "titulo exacto del jefe",
      "nombre_autoridad_1": "nombre completo",
      "cargo_autoridad_2": "titulo exacto del subjefe",
      "nombre_autoridad_2": "nombre completo",
      "fuente_url": "https://url-de-la-fuente",
      "notas": ""
    }}
  ]
}}

Si no encuentras algun dato en los resultados, pon "NO ENCONTRADO" en ese campo."""

PROMPT_PROVINCIALES = """La fecha de hoy es {fecha}.

A continuacion encontraras resultados de busqueda web sobre las autoridades actuales
de seguridad de las siguientes provincias de Argentina:

{lista}

=== RESULTADOS DE BUSQUEDA ===
{contexto}
=== FIN DE RESULTADOS ===

Basandote UNICAMENTE en los resultados anteriores, extrae para cada provincia:
1. El Ministro o Secretario de Seguridad (cargo politico equivalente)
2. El Jefe de la Policia provincial (Jefe, Comisario General, Director General, etc.)
3. El Subjefe de la Policia provincial

Responde UNICAMENTE con un JSON valido con esta estructura, sin texto adicional:
{{
  "fecha_busqueda": "{fecha}",
  "seccion": "policias_provinciales",
  "registros": [
    {{
      "jurisdiccion": "nombre de la provincia",
      "ministro_cargo": "titulo exacto del cargo politico",
      "ministro_nombre": "nombre completo",
      "jefe_policia_cargo": "titulo exacto",
      "jefe_policia_nombre": "nombre completo",
      "subjefe_policia_cargo": "titulo exacto",
      "subjefe_policia_nombre": "nombre completo",
      "fuente_url": "https://url-de-la-fuente",
      "notas": ""
    }}
  ]
}}

Si no encuentras algun dato en los resultados, pon "NO ENCONTRADO" en ese campo."""

# =============================================================================
# DEFINICION DE LAS 7 CONSULTAS (max 4 entidades por grupo provincial)
# =============================================================================
CONSULTAS = [
    {
        "id": 1, "seccion": "fuerzas_federales",
        "titulo": "Fuerzas federales",
        "entidades": [
            "Policia Federal Argentina (PFA)",
            "Gendarmeria Nacional Argentina (GNA)",
            "Prefectura Naval Argentina (PNA)",
            "Policia de Seguridad Aeroportuaria (PSA)",
            "Servicio Penitenciario Federal (SPF)",
        ],
    },
    {
        "id": 2, "seccion": "policias_provinciales",
        "titulo": "Provincias: Buenos Aires, CABA, Cordoba, Santa Fe",
        "entidades": [
            "Buenos Aires",
            "CABA (Ciudad Autonoma de Buenos Aires)",
            "Cordoba",
            "Santa Fe",
        ],
    },
    {
        "id": 3, "seccion": "policias_provinciales",
        "titulo": "Provincias: Mendoza, Tucuman, Salta, Jujuy",
        "entidades": [
            "Mendoza",
            "Tucuman",
            "Salta",
            "Jujuy",
        ],
    },
    {
        "id": 4, "seccion": "policias_provinciales",
        "titulo": "Provincias: Entre Rios, Corrientes, Misiones, Chaco",
        "entidades": [
            "Entre Rios",
            "Corrientes",
            "Misiones",
            "Chaco",
        ],
    },
    {
        "id": 5, "seccion": "policias_provinciales",
        "titulo": "Provincias: Neuquen, Rio Negro, Chubut, Santa Cruz",
        "entidades": [
            "Neuquen",
            "Rio Negro",
            "Chubut",
            "Santa Cruz",
        ],
    },
    {
        "id": 6, "seccion": "policias_provinciales",
        "titulo": "Provincias: Tierra del Fuego, San Juan, San Luis, La Rioja",
        "entidades": [
            "Tierra del Fuego",
            "San Juan",
            "San Luis",
            "La Rioja",
        ],
    },
    {
        "id": 7, "seccion": "policias_provinciales",
        "titulo": "Provincias: Catamarca, La Pampa, Formosa, Santiago del Estero",
        "entidades": [
            "Catamarca",
            "La Pampa",
            "Formosa",
            "Santiago del Estero",
        ],
    },
]

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _uso_vacio():
    class _V:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
    return _V()


def _extraer_primer_json(texto):
    """Extrae el primer objeto JSON completo del texto."""
    inicio = texto.find('{')
    if inicio == -1:
        return texto
    profundidad = 0
    en_string = False
    escape = False
    for i, c in enumerate(texto[inicio:], start=inicio):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            en_string = not en_string
        if not en_string:
            if c == '{':
                profundidad += 1
            elif c == '}':
                profundidad -= 1
                if profundidad == 0:
                    return texto[inicio:i+1]
    return texto[inicio:]


def _normalizar(texto):
    """Elimina tildes y pasa a minusculas para comparacion robusta."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )


def _apellidos(nombre):
    """Extrae el ultimo apellido normalizado para comparacion."""
    partes = [p for p in nombre.strip().split() if p not in ("NO", "ENCONTRADO")]
    return _normalizar(partes[-1]) if partes else _normalizar(nombre)


def _clave_registro(reg, seccion):
    return reg.get("jurisdiccion", "").strip().lower()


def _campos_nombre(reg, seccion):
    if seccion == "fuerzas_federales":
        return {
            "Jefe":    reg.get("nombre_autoridad_1", ""),
            "Subjefe": reg.get("nombre_autoridad_2", ""),
        }
    else:
        return {
            "Ministro": reg.get("ministro_nombre", ""),
            "Jefe":     reg.get("jefe_policia_nombre", ""),
            "Subjefe":  reg.get("subjefe_policia_nombre", ""),
        }


# =============================================================================
# DETECCION DE FUENTES OFICIALES (.gob / .gov / .gob.ar / .gov.ar)
# =============================================================================

def _es_fuente_oficial(url):
    """Devuelve True si la URL pertenece a un dominio oficial .gob/.gov/.gob.ar/.gov.ar."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        host = host.split(":")[0]
        return (
            host.endswith(".gob.ar") or host.endswith(".gov.ar") or
            host.endswith(".gob")    or host.endswith(".gov")    or
            host in ("gob.ar", "gov.ar")
        )
    except Exception:
        return False


def extraer_fuentes_oficiales(resultados_por_entidad):
    """Devuelve {entidad: [{"url": ..., "titulo": ..., "dominio": ...}]} con solo fuentes oficiales."""
    fuentes = {}
    for entidad, resultados in resultados_por_entidad.items():
        oficiales = []
        for r in resultados:
            url = r.get("url", "")
            if _es_fuente_oficial(url):
                try:
                    dominio = urlparse(url).netloc.lower().lstrip("www.")
                except Exception:
                    dominio = url
                oficiales.append({
                    "url":     url,
                    "titulo":  r.get("title", ""),
                    "dominio": dominio,
                })
        if oficiales:
            fuentes[entidad] = oficiales
    return fuentes


# =============================================================================
# BUSQUEDA CON TAVILY
# =============================================================================

def _es_fuente_valida(url):
    """Descarta fuentes de redes sociales con poca informacion estructurada."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return not any(host == d or host.endswith("." + d) for d in DOMINIOS_EXCLUIDOS)
    except Exception:
        return True


def _queries_para_entidad(entidad, seccion):
    anio = datetime.now().year
    if seccion == "fuerzas_federales":
        return [f'jefe subjefe "{entidad}" Argentina {anio} autoridades designado']
    else:
        return [
            f'ministro secretario seguridad "{entidad}" provincia Argentina {anio} autoridades',
            f'jefe policia comisario general "{entidad}" provincia Argentina {anio} asumio cargo',
        ]


def buscar_entidad(entidad, seccion, tavily_client):
    """Busca informacion de una entidad con Tavily. Devuelve lista de resultados."""
    queries = _queries_para_entidad(entidad, seccion)
    todos = []
    urls_vistas = set()

    # Busquedas generales
    for j, query in enumerate(queries):
        try:
            response = tavily_client.search(
                query=query,
                max_results=TAVILY_MAX_RESULTS,
                search_depth="advanced",
            )
            for r in response.get("results", []):
                url = r.get("url", "")
                if url not in urls_vistas and _es_fuente_valida(url):
                    urls_vistas.add(url)
                    todos.append(r)
        except Exception as e:
            print(f"      Error Tavily [{entidad}] q{j+1}: {type(e).__name__}: {e}")
        if j < len(queries) - 1:
            time.sleep(1)

    # Busqueda adicional dirigida a dominios oficiales
    if BUSCAR_EN_DOMINIOS_OFICIALES:
        try:
            response = tavily_client.search(
                query=queries[0],
                max_results=TAVILY_MAX_RESULTS_OFICIAL,
                search_depth="advanced",
                include_domains=DOMINIOS_OFICIALES_TAVILY,
            )
            nuevos = 0
            for r in response.get("results", []):
                url = r.get("url", "")
                if url not in urls_vistas:
                    urls_vistas.add(url)
                    todos.append(r)
                    nuevos += 1
        except Exception as e:
            print(f"      Error Tavily oficial [{entidad}]: {type(e).__name__}: {e}")
        time.sleep(1)

    n_oficial = sum(1 for r in todos if _es_fuente_oficial(r.get("url", "")))
    print(f"      [{entidad}]: {len(todos)} resultado(s)  |  {n_oficial} oficial(es)")
    return todos


def construir_contexto(resultados_por_entidad):
    """Convierte el dict {entidad: [resultados]} en texto para el prompt de Groq.
    Las fuentes oficiales aparecen primero y marcadas con [FUENTE OFICIAL GOB/GOV]."""
    contexto = ""
    for entidad, resultados in resultados_por_entidad.items():
        if not resultados:
            continue
        contexto += f"\n--- {entidad} ---\n"
        oficiales   = [r for r in resultados if     _es_fuente_oficial(r.get("url", ""))]
        no_oficiales = [r for r in resultados if not _es_fuente_oficial(r.get("url", ""))]
        for r in oficiales + no_oficiales:
            es_of     = _es_fuente_oficial(r.get("url", ""))
            titulo    = r.get("title", "")
            url       = r.get("url", "")
            contenido = r.get("content", "")[:TAVILY_CHARS_POR_RESULTADO]
            try:
                dominio = urlparse(url).netloc.lower().lstrip("www.")
            except Exception:
                dominio = ""
            tag = " [FUENTE OFICIAL GOB/GOV]" if es_of else ""
            contexto += (
                f"Fuente: {dominio}{tag}\n"
                f"Titulo: {titulo}\n"
                f"URL: {url}\n"
                f"Contenido: {contenido}\n\n"
            )
    return contexto.strip()


# =============================================================================
# EXTRACCION CON GROQ
# =============================================================================

def llamar_groq(consulta, contexto, fecha_hoy):
    """Llama a Groq con el contexto de busqueda y extrae el JSON estructurado."""
    groq_client = Groq(api_key=GROQ_API_KEY)
    lista = "\n".join(f"- {e}" for e in consulta["entidades"])

    if consulta["seccion"] == "fuerzas_federales":
        prompt_usuario = PROMPT_FEDERALES.format(
            lista=lista, fecha=fecha_hoy, contexto=contexto
        )
    else:
        prompt_usuario = PROMPT_PROVINCIALES.format(
            lista=lista, fecha=fecha_hoy, contexto=contexto
        )

    espera = 20
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            completion = groq_client.chat.completions.create(
                model=MODELO,
                messages=[
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "user",   "content": prompt_usuario},
                ],
                temperature=0,
                max_tokens=MAX_TOKENS,
            )

            uso   = completion.usage
            texto = completion.choices[0].message.content.strip()
            print(f"    Tokens: entrada {uso.prompt_tokens:,} | "
                  f"salida {uso.completion_tokens:,} | "
                  f"total {uso.total_tokens:,}")

            # Limpiar bloque ```json ... ```
            if texto.startswith("```"):
                texto = "\n".join(texto.split("\n")[1:-1]).strip()
            # Eliminar caracteres de control
            texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', texto)
            # Truncar URLs rotas
            texto = re.sub(r'"https?://[^"]{300,}"', '"URL_TRUNCADA"', texto)

            primer_json = _extraer_primer_json(texto)
            try:
                datos = json.loads(primer_json)
            except json.JSONDecodeError as e:
                print(f"    ERROR JSON: {e}")
                print(f"    Respuesta:\n{texto[:600]}")
                return None, uso

            n = len(datos.get("registros", []))
            print(f"    OK — {n} registro(s)")
            return datos, uso

        except Exception as e:
            nombre_error = type(e).__name__
            print(f"    Error (intento {intento}): {nombre_error}: {e}")
            if "RateLimit" in nombre_error or "rate_limit" in str(e).lower():
                espera = max(espera, 60)
            if intento < MAX_REINTENTOS:
                print(f"    Reintentando en {espera}s...")
                time.sleep(espera)
                espera *= 2
            else:
                return None, _uso_vacio()


def procesar_consulta(consulta, fecha_hoy, tavily_client):
    """Busca con Tavily y extrae con Groq. Devuelve (datos, uso, fuentes_oficiales)."""
    print(f"    Buscando con Tavily ({len(consulta['entidades'])} entidades)...")
    resultados_por_entidad = {}
    for i, entidad in enumerate(consulta["entidades"]):
        resultados_por_entidad[entidad] = buscar_entidad(entidad, consulta["seccion"], tavily_client)
        if i < len(consulta["entidades"]) - 1:
            time.sleep(PAUSA_ENTRE_BUSQUEDAS)

    fuentes_oficiales = extraer_fuentes_oficiales(resultados_por_entidad)

    contexto = construir_contexto(resultados_por_entidad)
    if not contexto:
        print("    Sin resultados de busqueda — omitiendo extraccion.")
        return None, _uso_vacio(), fuentes_oficiales

    print(f"    Extrayendo con Groq ({MODELO})...")
    datos, uso = llamar_groq(consulta, contexto, fecha_hoy)
    return datos, uso, fuentes_oficiales


# =============================================================================
# MOSTRAR RESULTADOS EN PANTALLA
# =============================================================================

def mostrar_resultados(datos):
    seccion = datos.get("seccion", "")
    for reg in datos.get("registros", []):
        print(f"      {reg.get('jurisdiccion','')}")
        if seccion == "fuerzas_federales":
            print(f"        Jefe   : [{reg.get('cargo_autoridad_1','')}] "
                  f"{reg.get('nombre_autoridad_1','')}")
            n2 = reg.get("nombre_autoridad_2", "")
            if n2 and n2 != "NO ENCONTRADO":
                print(f"        Subjefe: [{reg.get('cargo_autoridad_2','')}] {n2}")
        else:
            print(f"        Ministro: [{reg.get('ministro_cargo','')}] "
                  f"{reg.get('ministro_nombre','')}")
            print(f"        Jefe    : [{reg.get('jefe_policia_cargo','')}] "
                  f"{reg.get('jefe_policia_nombre','')}")
            sub = reg.get("subjefe_policia_nombre", "")
            if sub and sub != "NO ENCONTRADO":
                print(f"        Subjefe : [{reg.get('subjefe_policia_cargo','')}] {sub}")
        fuente = reg.get("fuente_url", "")
        if fuente and fuente != "NO ENCONTRADO":
            print(f"        Fuente  : {fuente}")
        if reg.get("notas"):
            print(f"        Nota    : {reg['notas']}")


# =============================================================================
# COMPARACION CON CORRIDA ANTERIOR
# =============================================================================

def buscar_referencia():
    """Devuelve (ruta, tipo) del archivo de referencia para comparar."""
    if os.path.exists(MAESTRO_JSON):
        return MAESTRO_JSON, "maestro"
    if not os.path.exists(CARPETA_SALIDA):
        return None, None
    archivos = sorted([
        f for f in os.listdir(CARPETA_SALIDA)
        if f.startswith("autoridades_") and f.endswith(".json")
    ])
    if archivos:
        return os.path.join(CARPETA_SALIDA, archivos[-1]), "anterior"
    return None, None


def _indice_desde_maestro(maestro):
    indice = {}
    ff = maestro.get("fuerzas_federales", {})
    mapeo_ff = {
        "policia federal argentina (pfa)":          ff.get("policia_federal_argentina", {}),
        "gendarmeria nacional argentina (gna)":     ff.get("gendarmeria_nacional_argentina", {}),
        "prefectura naval argentina (pna)":         ff.get("prefectura_naval_argentina", {}),
        "policia de seguridad aeroportuaria (psa)": ff.get("policia_seguridad_aeroportuaria", {}),
        "servicio penitenciario federal (spf)":     ff.get("servicio_penitenciario_federal", {}),
    }
    for clave, datos in mapeo_ff.items():
        valores = list(datos.values())
        nombres = {}
        if len(valores) >= 1:
            nombres["Jefe"] = valores[0]
        if len(valores) >= 2:
            nombres["Subjefe"] = valores[1]
        indice[clave] = nombres

    for jur in maestro.get("jurisdicciones_provinciales_y_caba", []):
        nombre_jur = jur.get("jurisdiccion", "").strip().lower()
        titular = jur.get("ministerio_seguridad", {}).get("titular", "")
        policia  = jur.get("policia", {})
        indice[nombre_jur] = {
            "Ministro": titular,
            "Jefe":     policia.get("jefe", ""),
            "Subjefe":  policia.get("subjefe", ""),
        }
    return indice


def _indice_desde_bloques(datos_ant_lista):
    indice = {}
    for bloque in datos_ant_lista:
        seccion = bloque.get("seccion", "")
        for reg in bloque.get("registros", []):
            clave = _clave_registro(reg, seccion)
            indice[clave] = _campos_nombre(reg, seccion)
    return indice


def comparar_con_referencia(datos_nuevos, ruta_ref, tipo_ref):
    if not ruta_ref or not os.path.exists(ruta_ref):
        return []
    try:
        with open(ruta_ref, "r", encoding="utf-8") as f:
            datos_ref = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    indice_ref = (_indice_desde_maestro(datos_ref)
                  if tipo_ref == "maestro"
                  else _indice_desde_bloques(datos_ref))

    diferencias = []
    for bloque in datos_nuevos:
        seccion = bloque.get("seccion", "")
        for reg in bloque.get("registros", []):
            clave = _clave_registro(reg, seccion)
            nombres_nuevos = _campos_nombre(reg, seccion)
            if clave not in indice_ref:
                continue
            nombres_ref = indice_ref[clave]
            for cargo, nombre_nuevo in nombres_nuevos.items():
                nombre_ref = nombres_ref.get(cargo, "")
                if nombre_nuevo in ("NO ENCONTRADO", "") and nombre_ref in ("NO ENCONTRADO", ""):
                    continue
                if (_apellidos(nombre_nuevo) != _apellidos(nombre_ref) and
                        _normalizar(nombre_nuevo) != _normalizar(nombre_ref)):
                    diferencias.append({
                        "jurisdiccion": reg.get("jurisdiccion", clave),
                        "cargo":        cargo,
                        "anterior":     nombre_ref or "NO ENCONTRADO",
                        "nuevo":        nombre_nuevo or "NO ENCONTRADO",
                    })
    return diferencias


def guardar_diferencias(diferencias, timestamp):
    ruta = os.path.join(CARPETA_SALIDA, f"diferencias_{timestamp}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("SIFCOP - REPORTE DE DIFERENCIAS\n")
        f.write(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        if not diferencias:
            f.write("Sin diferencias respecto a la corrida anterior.\n")
            f.write("Todos los nombres de autoridades coinciden.\n")
        else:
            f.write(f"Se detectaron {len(diferencias)} diferencia(s).\n")
            f.write("ATENCION: Verificar manualmente antes de actualizar registros.\n\n")
            for d in diferencias:
                f.write(f"Jurisdiccion : {d['jurisdiccion']}\n")
                f.write(f"Cargo        : {d['cargo']}\n")
                f.write(f"Anterior     : {d['anterior']}\n")
                f.write(f"Nuevo        : {d['nuevo']}\n")
                f.write("-" * 40 + "\n")
    return ruta


# =============================================================================
# GUARDAR FUENTES OFICIALES
# =============================================================================

def guardar_fuentes_oficiales(todas_fuentes, timestamp):
    """Genera CSV y TXT con las paginas oficiales .gob/.gov encontradas."""
    total = sum(len(v) for v in todas_fuentes.values())

    # CSV
    ruta_csv = os.path.join(CARPETA_SALIDA, f"fuentes_oficiales_{timestamp}.csv")
    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Entidad", "Dominio Oficial", "Titulo", "URL"])
        for entidad, fuentes in todas_fuentes.items():
            for fu in fuentes:
                writer.writerow([entidad, fu["dominio"], fu["titulo"], fu["url"]])

    # TXT
    ruta_txt = os.path.join(CARPETA_SALIDA, f"fuentes_oficiales_{timestamp}.txt")
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("SIFCOP - FUENTES OFICIALES DETECTADAS\n")
        f.write(f"Generado : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("Dominios : .gob | .gov | .gob.ar | .gov.ar\n")
        f.write("=" * 60 + "\n\n")
        if not todas_fuentes:
            f.write("No se encontraron fuentes oficiales en esta corrida.\n")
        else:
            f.write(f"Total: {total} fuente(s) oficial(es) en {len(todas_fuentes)} entidad(es)\n")
            for entidad, fuentes in todas_fuentes.items():
                f.write(f"\n{'─' * 40}\n")
                f.write(f"  {entidad}  ({len(fuentes)} fuente(s))\n")
                f.write(f"{'─' * 40}\n")
                for fu in fuentes:
                    f.write(f"  [{fu['dominio']}]\n")
                    if fu["titulo"]:
                        f.write(f"  {fu['titulo']}\n")
                    f.write(f"  {fu['url']}\n\n")

    return ruta_csv, ruta_txt


# =============================================================================
# GUARDAR RESULTADOS PRINCIPALES
# =============================================================================

def guardar_resultados(todos_los_datos, timestamp, tokens_totales):
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    # JSON
    ruta_json = os.path.join(CARPETA_SALIDA, f"autoridades_{timestamp}.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(todos_los_datos, f, ensure_ascii=False, indent=2)
    print(f"  JSON : {ruta_json}")

    # CSV
    ruta_csv = os.path.join(CARPETA_SALIDA, f"autoridades_{timestamp}.csv")
    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Seccion", "Jurisdiccion",
            "Responsable Politico Cargo", "Responsable Politico Nombre",
            "Jefe Cargo", "Jefe Nombre",
            "Subjefe Cargo", "Subjefe Nombre",
            "Fuente URL", "Fecha Busqueda", "Notas",
        ])
        for bloque in todos_los_datos:
            seccion = bloque.get("seccion", "")
            fecha   = bloque.get("fecha_busqueda", datetime.now().strftime("%d/%m/%Y"))
            if seccion == "fuerzas_federales":
                for reg in bloque.get("registros", []):
                    writer.writerow([
                        "Fuerzas Federales",
                        reg.get("jurisdiccion", ""),
                        "", "",
                        reg.get("cargo_autoridad_1", ""),
                        reg.get("nombre_autoridad_1", ""),
                        reg.get("cargo_autoridad_2", ""),
                        reg.get("nombre_autoridad_2", ""),
                        reg.get("fuente_url", ""),
                        fecha, reg.get("notas", ""),
                    ])
            elif seccion == "policias_provinciales":
                for reg in bloque.get("registros", []):
                    writer.writerow([
                        "Policias Provinciales",
                        reg.get("jurisdiccion", ""),
                        reg.get("ministro_cargo", ""),
                        reg.get("ministro_nombre", ""),
                        reg.get("jefe_policia_cargo", ""),
                        reg.get("jefe_policia_nombre", ""),
                        reg.get("subjefe_policia_cargo", ""),
                        reg.get("subjefe_policia_nombre", ""),
                        reg.get("fuente_url", ""),
                        fecha, reg.get("notas", ""),
                    ])
    print(f"  CSV  : {ruta_csv}")

    # Log de tokens
    ruta_log = os.path.join(CARPETA_SALIDA, "log_tokens.txt")
    with open(ruta_log, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | "
            f"ejecucion={timestamp} | "
            f"tokens_entrada={tokens_totales['entrada']} | "
            f"tokens_salida={tokens_totales['salida']} | "
            f"total={tokens_totales['total']}\n"
        )
    print(f"  Log  : {ruta_log}")

    return ruta_json


# =============================================================================
# MAIN
# =============================================================================

def main():
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    if not GROQ_API_KEY or not TAVILY_API_KEY:
        print("ERROR: Faltan API keys.")
        print("Definí GROQ_API_KEY y TAVILY_API_KEY en un archivo .env junto al")
        print("script (ver .env.example) o como variables de entorno del sistema.")
        return

    print("=" * 60)
    print("SIFCOP - Busqueda mensual de autoridades de seguridad  v6")
    print(f"Fecha : {fecha_hoy}  {datetime.now().strftime('%H:%M:%S')}")
    print(f"Modelo: {MODELO}  |  Consultas: {len(CONSULTAS)}")
    print(f"Salida: {CARPETA_SALIDA}")
    if BUSCAR_EN_DOMINIOS_OFICIALES:
        print(f"Fuentes oficiales: activado ({', '.join(DOMINIOS_OFICIALES_TAVILY)})")
    print("=" * 60)

    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

    # Buscar referencia ANTES de generar el nuevo
    ruta_ref, tipo_ref = buscar_referencia()
    if tipo_ref == "maestro":
        print(f"\nReferencia: maestro.json (fijo)")
    elif tipo_ref == "anterior":
        print(f"\nReferencia: {os.path.basename(ruta_ref)} (ultima corrida)")
    else:
        print("\nPrimera ejecucion — sin referencia para comparar.")

    timestamp            = datetime.now().strftime("%Y%m%d_%H%M%S")
    todos_los_datos      = []
    todas_fuentes        = {}   # {entidad: [{url, titulo, dominio}]}
    tokens_totales       = {"entrada": 0, "salida": 0, "total": 0}
    fallidas             = []
    busquedas_tavily     = 0

    for consulta in CONSULTAS:
        print(f"\n[{consulta['id']}/{len(CONSULTAS)}] {consulta['titulo']}")
        print(f"    {len(consulta['entidades'])} entidades")

        datos, uso, fuentes_consulta = procesar_consulta(consulta, fecha_hoy, tavily_client)

        # Acumular fuentes oficiales
        todas_fuentes.update(fuentes_consulta)

        # Conteo de busquedas Tavily
        busquedas_tavily += sum(
            len(_queries_para_entidad(e, consulta["seccion"]))
            for e in consulta["entidades"]
        )
        if BUSCAR_EN_DOMINIOS_OFICIALES:
            busquedas_tavily += len(consulta["entidades"])  # busqueda oficial extra

        tokens_totales["entrada"] += uso.prompt_tokens
        tokens_totales["salida"]  += uso.completion_tokens
        tokens_totales["total"]   += uso.total_tokens

        if datos:
            todos_los_datos.append(datos)
            mostrar_resultados(datos)
        else:
            fallidas.append(consulta["titulo"])

        n_of = sum(len(v) for v in fuentes_consulta.values())
        if n_of:
            print(f"    Fuentes oficiales en esta consulta: {n_of}")

        if consulta["id"] < len(CONSULTAS):
            print(f"\n    Esperando {PAUSA_ENTRE_CONSULTAS}s (rate limit Groq)...")
            time.sleep(PAUSA_ENTRE_CONSULTAS)

    # Resumen
    creditos_tavily = busquedas_tavily * 2   # advanced = 2 creditos por busqueda
    total_fuentes   = sum(len(v) for v in todas_fuentes.values())
    print(f"\n{'=' * 60}")
    print("  RESUMEN")
    print(f"{'=' * 60}")
    print(f"  Consultas exitosas : {len(CONSULTAS) - len(fallidas)}/{len(CONSULTAS)}")
    if fallidas:
        print(f"  Fallidas           : {', '.join(fallidas)}")
    print(f"  Tokens Groq entrada: {tokens_totales['entrada']:,}")
    print(f"  Tokens Groq salida : {tokens_totales['salida']:,}")
    print(f"  Tokens Groq total  : {tokens_totales['total']:,}")
    print(f"  Busquedas Tavily   : {busquedas_tavily}  (~{creditos_tavily} creditos de 1.000/mes)")
    print(f"  Fuentes oficiales  : {total_fuentes} en {len(todas_fuentes)} entidades")

    if not todos_los_datos:
        print("\n  Sin datos para guardar.")
        return

    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    # Guardar archivos principales
    print(f"\n{'=' * 60}")
    print("  GUARDANDO ARCHIVOS")
    print(f"{'=' * 60}")
    guardar_resultados(todos_los_datos, timestamp, tokens_totales)

    # Guardar reporte de fuentes oficiales
    ruta_of_csv, ruta_of_txt = guardar_fuentes_oficiales(todas_fuentes, timestamp)
    print(f"  Fuentes oficiales CSV : {ruta_of_csv}")
    print(f"  Fuentes oficiales TXT : {ruta_of_txt}")

    # Comparar con corrida anterior
    print(f"\n{'=' * 60}")
    print("  COMPARACION CON CORRIDA ANTERIOR")
    print(f"{'=' * 60}")
    diferencias = comparar_con_referencia(todos_los_datos, ruta_ref, tipo_ref)

    etiqueta = "maestro.json" if tipo_ref == "maestro" else "corrida anterior"
    if not ruta_ref:
        print("  (primera ejecucion, sin comparacion)")
    elif not diferencias:
        print(f"  Sin diferencias detectadas respecto al {etiqueta}.")
    else:
        print(f"  ATENCION: {len(diferencias)} diferencia(s) vs {etiqueta}:")
        for d in diferencias:
            print(f"    {d['jurisdiccion']} / {d['cargo']}")
            print(f"      Antes: {d['anterior']}")
            print(f"      Ahora: {d['nuevo']}")

    ruta_dif = guardar_diferencias(diferencias, timestamp)
    print(f"  Reporte diferencias: {ruta_dif}")

    print(f"\n{'=' * 60}")
    print(f"  Listo. Archivos en: {CARPETA_SALIDA}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
