---
description: (Dueño) Después de fusionar el PR de una orden, actualiza main y borra su carpeta de trabajo
argument-hint: OT-NNN
---

El dueño fusionó el PR de **$ARGUMENTS** en GitHub. Ordena la computadora:

1. Trabaja desde la carpeta principal del repositorio (la primera línea de `git worktree list`), nunca desde `trabajo/`.
2. `git switch main` y `git pull --ff-only`.
3. Comprueba que la rama de la orden ya está en `main`: `git branch --merged main` debe listarla (o el PR aparece como "Merged" en GitHub: `gh pr view <rama> --json state`). Si no está fusionada, dilo y detente.
4. Si el chat del agente de esa orden sigue abierto, pide al dueño que lo cierre.
5. `git worktree remove trabajo/$ARGUMENTS` (o `../Clique-trabajo/$ARGUMENTS` si la orden usó el protocolo anterior) y `git branch -d <rama>`. No uses `--force`: si git se niega, muestra el motivo y detente.
6. `git worktree prune`.
7. Dile al dueño en una línea: "$ARGUMENTS cerrada. Avísale al cerebro para que la marque como Hecha y diga cuál sigue."
