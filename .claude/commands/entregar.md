---
description: Deja listo un entregable: pruebas en verde, línea en la bitácora, commit con el porqué y push de tu rama
argument-hint: E<n> <número de entregable>
---

Vas a entregar el entregable indicado de tu orden ($ARGUMENTS). Todo dentro de tu árbol `_ramas/<tu rama>`. No declares nada como hecho sin comprobarlo.

1. **Ponte al día:** `cd _ramas/<tu rama> && git fetch origin && git rebase origin/integracion`. Si hay conflicto en un archivo que no es tuyo, detente y anótalo como BLOQUEADO.
2. **Corre la comprobación** que tu orden pone en la columna "Cómo se comprueba" de ese entregable, tal cual. Después, la suite completa: `python -m unittest discover -s tests -t .` (y `node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs` si tocaste algo de `herramientas/` o de `equipo/PROPIEDAD_DE_ARCHIVOS.md`). Todo en verde. Si algo ya estaba en rojo antes de ti, debe estar en `equipo/ROJOS_CONOCIDOS.json`; si no está, anótalo.
3. **Revisa el alcance:** `git diff --stat origin/integracion...HEAD`. Cada archivo debe ser tuyo según `equipo/PROPIEDAD_DE_ARCHIVOS.md`, o compartido.
4. **Revisión con ojos frescos:** pide al subagente `qa` que revise el diff contra tu orden y `equipo/DEFINICION_DE_TERMINADO.md`. Resuelve lo grave o anótalo con su motivo.
5. **Bitácora:** tu línea `[E<n>] … · HECHO: … · COMANDO: …` en `equipo/BITACORA.md` (ver `/bitacora`).
6. **Commit** con el porqué en el mensaje: `tipo(ámbito): qué y por qué [E<n>]`.
7. **Push de tu rama:** `git push origin <tu rama>` (si rebasaste algo ya subido: `git push --force-with-lease origin <tu rama>`). Nunca a `main` ni a `integracion`: E7 fusiona.
8. Dile al dueño en tres líneas qué quedó, el comando que lo demuestra y qué sigue.
