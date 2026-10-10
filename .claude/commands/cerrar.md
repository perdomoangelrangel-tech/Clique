---
description: (Dueño) Después de fusionar el PR de una orden, actualiza main y borra su carpeta de trabajo
argument-hint: OT-NNN
---

El dueño fusionó el PR de **$ARGUMENTS** en GitHub. Ordena la computadora:

1. Debes estar en la carpeta principal del repositorio (la primera línea de `git worktree list`). Si no, dile al dueño que corra este comando en la ventana principal y detente.
2. `git switch main` y `git pull --ff-only`.
3. Comprueba que la rama de la orden ya está en `main`: `git branch --merged main` debe listarla (o el PR aparece como "Merged" en GitHub: `gh pr view <rama> --json state`). Si no está fusionada, dilo y detente.
4. Si hay una ventana de VS Code abierta en `../Clique-trabajo/$ARGUMENTS`, pide al dueño que la cierre.
5. `git worktree remove ../Clique-trabajo/$ARGUMENTS` y `git branch -d <rama>`. No uses `--force`: si git se niega, muestra el motivo y detente.
6. `git worktree prune`.
7. Dile al dueño en una línea: "$ARGUMENTS cerrada. Avísale al cerebro para que la marque como Hecha y diga cuál sigue."
