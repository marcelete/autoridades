# Informe semanal SIFCOP

**Estado:** todavía no corrió ninguna verificación con este mecanismo.

Este archivo lo sobrescribe automáticamente la rutina en la nube
**"SIFCOP - Verificación semanal de autoridades"** (ver
[rutina_verificacion_semanal.md](../rutina_verificacion_semanal.md), paso 6) cada
vez que corre, con:

1. La fecha de la corrida.
2. Las novedades de esa semana (si algún campo dio "Cambió" o "Dudoso" contra
   `maestro.json`), o "Sin novedades" si todo coincidió.
3. Una tabla completa con el estado actual de las 29 entidades / ~110 campos.

Si estás viendo este texto, todavía no pasó la primera corrida desde que se agregó
este paso. Después del próximo lunes (o de la próxima vez que se dispare la
rutina), este archivo va a tener el informe real.
