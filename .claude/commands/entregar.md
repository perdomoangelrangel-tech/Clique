---
description: Verifica, pide revisión a qa, cierra la bitácora, sube la rama y abre el PR de la orden actual
---

Vas a entregar la orden de la rama actual. No declares nada como hecho sin haberlo comprobado.

1. **Identifica la orden** por la rama (`ot/NNN-nombre`). Lee su versión más nueva con `git fetch origin` y `git show origin/main:coordinacion/ordenes/<archivo>`, y lee tu bitácora.
   Revisa lo que la orden necesita **para entregar** (campo "Depende de" y columna "Para entregar" del tablero en `origin/main`). Si falta algo, por ejemplo que OT-002 esté fusionada, no entregues: anota en la bitácora "Esperando OT-NNN para entregar", sube la rama y díselo al dueño.
2. **Actualiza con `main`:** `git rebase origin/main`. Si hay conflictos en archivos de otra orden, detente y pregunta.
3. **Corre las verificaciones:**
   - Cada comando de "Cómo verificar" de la orden.
   - `pnpm lint`, `pnpm typecheck` y `pnpm test` si ya existen.
   - `pnpm test:legacy` (o `cd legacy/clique && python -m unittest discover -s tests -t .`) si la orden toca algo relacionado con el legacy o con reglas de economía.
   - En Git Bash: `cd legacy/clique && sha256sum -c --quiet ../clique.sha256` (el legacy no debe cambiar).
   Si algo falla, arréglalo antes de seguir.
4. **Pide revisión:** usa el subagente `qa` con el número de orden. Resuelve cada hallazgo grave o anótalo con su motivo.
5. **Revisa el alcance:** `git diff --stat origin/main...HEAD`. Cualquier archivo fuera de la lista permitida debe estar justificado en la bitácora.
6. **Cierra la bitácora:** completa la sección "Entrega" de la plantilla, con cada criterio de aceptación marcado y su evidencia, y cambia el estado a "En revisión". Commit: `docs(bitacora): entrega [OT-NNN]`.
7. **Sube la rama:** `git push -u origin <rama>`. Si ya estaba subida y rebasaste, `git push --force-with-lease origin <rama>`.
8. **Abre el PR** con `gh pr create --base main --head <rama> --title "OT-NNN: <título de la orden>" --body-file <archivo temporal con la sección Entrega>`. Si ya existe, actualízalo. Si no hay `gh`, dale al dueño el enlace `https://github.com/perdomoangelrangel-tech/Clique/compare/main...<rama>` para que lo abra.
9. **Mensaje para el dueño:** muéstrale la sección "Entrega" completa y el enlace del PR, y dile: "Avísale al cerebro que OT-NNN está lista para revisión."
