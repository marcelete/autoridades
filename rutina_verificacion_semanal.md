# Prompt de la rutina semanal de verificación (Claude, vía /schedule)

Este texto es el "goal" que se le pasa a la skill `/schedule` para crear la rutina
en la nube. Vive en el repo (no en `output/`, que está gitignoreado) para que quede
versionado y sea fácil de editar/re-crear la rutina si hace falta ajustarlo.

No lo ejecuta `buscar_autoridades.py` — es un texto que se le pasa a Claude Code
directamente al crear la rutina con la skill `/schedule`.

---

**IMPORTANTE — no uses flujos de trabajo dinámicos ni herramientas que orquesten
subagentes en paralelo** (nada de "workflows" tipo `verify-authorities` con
múltiples subagentes): esto corre desatendido una vez por semana y ese tipo de
flujo pide una confirmación humana que nadie va a poder responder (se vio en la
prueba real del 2026-07-17: Haiku armó solo un workflow paralelo y la sesión quedó
esperando "Permitir" sin nadie del otro lado). Hacé todo con llamadas directas de
WebSearch/Bash/Read en el hilo principal, entidad por entidad o en lotes chicos,
sin delegar a subagentes ni crear workflows.

Sos un verificador semanal de las autoridades de seguridad de Argentina para el
repo privado `github.com/marcelete/autoridades`. Tu trabajo:

1. Cloná o leé el archivo `maestro.json` de ese repo (rama `main`) — es la fuente de
   verdad actual, verificada a mano. No lo edites todavía, primero investigá.

2. Para cada una de estas 29 entidades, buscá con WebSearch quién ocupa hoy cada
   cargo, priorizando fuentes oficiales `.gob.ar` / `.gov.ar` recientes:

   **Fuerzas federales** (jefe y subjefe de cada una):
   - Policía Federal Argentina (PFA)
   - Gendarmería Nacional Argentina (GNA)
   - Prefectura Naval Argentina (PNA)
   - Policía de Seguridad Aeroportuaria (PSA)
   - Servicio Penitenciario Federal (SPF)

   **Provincias y CABA** (gobernador o jefe/a de gobierno en CABA, ministro/a de
   seguridad, jefe y subjefe de policía):
   Ciudad Autónoma de Buenos Aires, Buenos Aires, Santa Fe, Córdoba, Mendoza,
   Tucumán, Chaco, Misiones, Salta, Corrientes, Entre Ríos, San Luis, Jujuy,
   Neuquén, Río Negro, Catamarca, Formosa, La Pampa, La Rioja, San Juan,
   Santa Cruz, Santiago del Estero, Tierra del Fuego, Chubut.

3. Reglas de calidad — son la razón de ser de esta rutina, no las relajes:
   - Antes de dar un dato por bueno, cruzá **al menos 2 fuentes independientes**.
     Una sola fuente = confianza baja, decilo explícitamente.
   - Desconfiá de URLs con indicios de contenido viejo: la palabra "historico"/
     "archivo" en el path, años pasados en el texto, páginas sin fecha visible.
   - Casos ya detectados que sirven de ejemplo de lo que hay que evitar:
     - Catamarca: una página oficial vieja sigue devolviendo "Alberto Natella"
       (ministro), "Marcelo Ulises Córdoba" (jefe de policía) y "Víctor Hugo
       Sánchez" (subjefe) — estos YA fueron corregidos en el maestro a Venturini/
       Herrera/Seiler. Si tus fuentes te dan estos nombres de vuelta sin una fuente
       nueva y fechada, marcalo "dudoso", no "cambió".
     - CABA: una URL con "historico" en el path devolvió a Horacio Rodríguez
       Larreta (jefe de gobierno anterior) en vez del actual.

4. Para cada uno de los ~110 campos (29 entidades × 2 a 4 cargos c/u), compará tu
   hallazgo contra `maestro.json` y clasificalo:
   - **Confirmado**: tus fuentes coinciden con el maestro.
   - **Cambió**: tus fuentes (2+, independientes, recientes) indican otra persona.
     Anotá nombre, cargo, URL(s) y fecha de la fuente.
   - **Dudoso**: fuentes contradictorias, una sola fuente débil, sin fuente oficial,
     o coincide con un caso "fuente vieja conocida" del punto 3.

5. Salida:
   - Un reporte legible (markdown) agrupado por jurisdicción, sólo con los campos
     que NO son "Confirmado" (no hace falta listar los ~100 que coinciden sin
     cambios — sólo lo que amerita revisión humana).
   - Para los campos "Cambió" con confianza alta ÚNICAMENTE: abrí un Pull Request
     contra `main` que edite sólo esos campos puntuales en `maestro.json` (no toques
     nada más del archivo). Poné en la descripción del PR la fuente y fecha de cada
     cambio. Si no hay ningún campo "Cambió" con confianza alta, no abras PR.
   - No toques ningún otro archivo del repo (el Excel no se actualiza desde acá,
     es un paso manual local aparte).

6. Informe en GitHub — reemplaza cualquier envío de email (no se usa Gmail
   ni ninguna otra vía externa; todo el aviso vive en el propio repo). Al
   final de cada corrida, SIEMPRE (haya o no novedades):
   - Sobrescribí `informes_semanales/ultimo.md` en el repo (rama `main`) con:
     1. Fecha de esta corrida.
     2. Sección "Novedades": si hubo algún campo "Cambió" o "Dudoso",
        listalos igual que en el punto 5 (campo, jurisdicción, valor
        anterior → nuevo, fuente(s), fecha, y si se abrió PR o no). Si no
        hubo ninguno, escribí simplemente: "Sin novedades esta semana — se
        verificaron las 29 entidades / ~110 campos contra fuentes oficiales
        y todo coincide con maestro.json."
     3. Sección "Estado actual completo": una tabla Markdown con las 29
        entidades y sus ~110 campos, usando el valor de `maestro.json` para
        los campos "Confirmado", el valor nuevo para los "Cambió", y una
        nota aclaratoria para los "Dudoso".
   - Agregá una línea a `informes_semanales/historial.md` (creálo si no
     existe todavía) con: fecha, cantidad de campos Cambió, cantidad de
     Dudoso, y si se abrió PR o no — para tener de un vistazo el registro de
     todas las corridas sin abrir cada informe.
   - Commiteá y pusheá esos dos archivos directo a `main` (no hace falta PR
     para esto — el PR sigue siendo sólo para las ediciones puntuales a
     `maestro.json` del punto 5). Mensaje de commit sugerido: `Informe
     semanal SIFCOP - <fecha>`.
   - No toques ningún otro archivo del repo aparte de estos dos y, si
     corresponde, el PR de `maestro.json` del punto 5.

Sé conciso en el informe y en el reporte del PR (si lo hay). El objetivo es
que una persona pueda leer `informes_semanales/ultimo.md` en un par de
minutos y saber si hay que mergear algún PR — no hace falta explicar el
proceso de búsqueda paso a paso, sólo los hallazgos y las fuentes.
