# Verificaciones — sistema de 2 agentes (Buscador + Verificador)

Cada corrida del sistema de verificación semanal (Haiku 4.5, vía `/schedule`) deja
una carpeta acá con timestamp `AAAA-MM-DD_HHMM`, con tres archivos:

- **`buscador.json`** — salida cruda del agente Buscador: para cada campo de las
  29 entidades (5 fuerzas federales + 24 provincias/CABA), qué encontró con
  WebSearch y con qué fuente(s). No compara contra el maestro ni decide si es un
  cambio — sólo reporta hallazgos.

  ```json
  {
    "fecha_corrida": "2026-07-17T23:00:00Z",
    "hallazgos": [
      {
        "jurisdiccion": "...",
        "cargo": "...",
        "valor_encontrado": "...",
        "fuentes": [
          {"url": "...", "fecha_fuente": "...", "texto_citado": "..."}
        ],
        "confianza_propia": "alta|media|baja"
      }
    ]
  }
  ```

- **`verificador.json`** — segunda pasada, independiente: recibe sólo los
  hallazgos+fuentes del Buscador (no su razonamiento) más el `maestro.json`
  vigente, y por cada campo busca activamente evidencia de que la fuente del
  Buscador esté superada (¿sucesor? ¿remoción? ¿renuncia posterior?) antes de
  aceptar un cambio.

  ```json
  {
    "veredictos": [
      {
        "jurisdiccion": "...",
        "cargo": "...",
        "valor_maestro": "...",
        "valor_buscador": "...",
        "veredicto": "confirmado|corregido|rechazado|dudoso",
        "razon": "...",
        "fuentes_verificador": ["..."]
      }
    ],
    "autotest": {
      "spf_debe_rechazar_velarde": true,
      "salta_debe_confirmar_avellaneda": true,
      "catamarca_debe_confirmar_monguillot": true,
      "santiago_del_estero_debe_confirmar_herrera": true,
      "iteraciones_usadas": 1
    }
  }
  ```

- **`reporte.md`** — resumen legible agrupado por jurisdicción, sólo con los campos
  que no son "confirmado". Es lo que hay que leer antes de mergear el PR.

`historial.md` (en esta misma carpeta) es una tabla acumulativa, una fila por
corrida, para ver la evolución sin abrir cada carpeta.

**Por qué existe el Verificador como agente separado:** el 2026-07-17, la primera
versión de la rutina (un solo agente, ver `../rutina_verificacion_semanal.md`)
propuso 4 cambios; verificados a mano, 3 eran correctos y 1 no (SPF → "Velarde",
una persona removida del cargo en 2024, tomada de una noticia vieja de 2023 con URL
sin fecha). Las "reglas de calidad" escritas en el prompt de un solo agente no
alcanzaron para blindarlo — de ahí la idea de una segunda pasada, independiente,
cuyo trabajo específico es cazar ese tipo de error antes de que llegue al PR.
