# Prompt de la sesión de refinamiento — 2026-07-17 20:00 ART

Sesión única (no recurrente) para el repo privado `github.com/marcelete/autoridades`.
Objetivo: probar y afinar el sistema de 2 agentes (Buscador + Verificador) hasta
que pase el autotest de 4 casos conocidos. **Esto es una prueba, no reemplaza
todavía la automatización de producción** — dejá todo documentado para que un
humano decida mañana si la reemplaza.

No uses flujos de trabajo dinámicos ni herramientas que orquesten subagentes en
paralelo (aprendido el 2026-07-17: ese tipo de flujo pide una confirmación humana
que nadie puede responder en una sesión desatendida). Hacé todo con llamadas
directas de WebSearch/Bash/Read/Write en el hilo principal.

## Fase 1 — Buscador

Seguí al pie de la letra `verificaciones/prompt_buscador.md` (leelo del repo).
Guardá el resultado en `verificaciones/2026-07-17_2000/buscador.json`.

## Fase 2 — Verificador

**Importante: al pasar a esta fase, no reutilices tu propio razonamiento de la
Fase 1.** Actuá como si fueras un agente distinto que sólo tiene acceso a
`verificaciones/2026-07-17_2000/buscador.json` (los datos y fuentes, no por qué
los elegiste) y a `maestro.json`. Seguí al pie de la letra
`verificaciones/prompt_verificador.md` (leelo del repo), incluyendo el autotest de
los 4 casos conocidos y el tope de 3 iteraciones.

Guardá `verificaciones/2026-07-17_2000/verificador.json` y
`verificaciones/2026-07-17_2000/reporte.md`.

## Fase 3 — Cierre

1. Agregá una fila a `verificaciones/historial.md` con los números de esta corrida
   (campos revisados/confirmados/corregidos/rechazados/dudosos, iteraciones,
   resultado del autotest).
2. Si hay campos "Corregido", abrí un Pull Request contra `main` con esos cambios
   puntuales en `maestro.json` (nada más). Si no hay ninguno, no abras PR.
3. Commiteá y pusheá `verificaciones/2026-07-17_2000/` y el `historial.md`
   actualizado directo a `main` (esto es sólo logging, no datos del maestro — no
   necesita PR).
4. Terminá con un resumen corto en el mensaje del último commit: cuántos campos
   revisaste, cuántos corrigió el Verificador, si el autotest pasó completo, y si
   abriste PR.
