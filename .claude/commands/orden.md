---
description: Empieza o retoma una orden de trabajo de Clique (crea su rama y su carpeta de trabajo si hace falta)
argument-hint: OT-NNN
---

Vas a trabajar en la orden **$ARGUMENTS** de Clique. Sigue estos pasos en orden y no te saltes ninguno.

## 1. Trae lo más nuevo de GitHub

`git fetch origin`. El cerebro sube órdenes, correcciones y el tablero a `main` (por PR), así que **lee siempre desde `origin/main`**, no desde tu copia local:

- Orden: `git show origin/main:coordinacion/ordenes/<archivo>` (el archivo cuyo nombre empieza con `$ARGUMENTS`; búscalo con `git ls-tree --name-only origin/main coordinacion/ordenes/`). Si no existe, dilo y detente.
- Tablero: `git show origin/main:coordinacion/TABLERO.md`.

## 2. Lee el contexto

1. `CLAUDE.md` y `coordinacion/PROTOCOLO.md` completos.
2. La orden completa, incluida su sección **Correcciones** (si tiene, son lo primero que hay que resolver).
3. El agente que indica el campo **Agente** de la orden (código E# y rol; ver `coordinacion/AGENTES.md`): lee `.claude/agents/<rol>.md` completo y adopta ese rol y ese código durante toda la sesión.
4. Los ADR y contratos que la orden menciona.
5. Si ya existe tu bitácora `coordinacion/bitacoras/$ARGUMENTS.md` (en tu rama), léela completa: ahí está lo que hiciste antes.

## 3. Revisa dependencias

Lee el campo **Depende de** de la orden y las columnas "Para empezar" y "Para entregar" del tablero. Si algo que se necesita **para empezar** no está "Hecha", o la orden está "Bloqueada", explícale al dueño qué falta y detente. Lo que solo se necesita **para entregar** no te detiene: trabaja en todo lo demás y anótalo en la bitácora; `/entregar` lo vuelve a revisar.

## 4. Asegura tu lugar de trabajo

- Mira la rama actual con `git branch --show-current`.
- **Si ya estás en la rama de la orden** (la del campo **Rama**): si no tienes cambios sin guardar, `git rebase origin/main` para traer lo nuevo. Sigue al paso 5.
- **Si no**, estás en la ventana principal. Prepara la carpeta de trabajo (las rutas `../Clique-trabajo/...` son relativas a la carpeta principal del repositorio, la primera línea de `git worktree list`):
  1. `git switch main` y `git pull --ff-only`.
  2. Si la rama no existe: `git worktree add ../Clique-trabajo/$ARGUMENTS -b <rama> origin/main`. Si ya existe en GitHub o local: `git worktree add ../Clique-trabajo/$ARGUMENTS <rama>`. Si la carpeta ya existe, úsala.
  3. Ábrela en una ventana nueva: `code ../Clique-trabajo/$ARGUMENTS`.
  4. Dile al dueño: "Se abrió una ventana nueva para $ARGUMENTS. Abre Claude ahí y escribe `/orden $ARGUMENTS`." y **detente**. No trabajes desde la ventana principal.

## 5. Abre la sesión en la bitácora

- Si no existe `coordinacion/bitacoras/$ARGUMENTS.md`, créala desde `coordinacion/bitacoras/_plantilla.md` con el estado "En curso".
- Corre `/estado` (o haz lo mismo que describe) y anota los avisos dirigidos a tu rol, a `$ARGUMENTS` o a `@todos`.
- Agrega una entrada "Sesión N — fecha y hora" con el objetivo y tu plan en 3 a 7 pasos.
- Commit `docs(bitacora): inicio de sesión [$ARGUMENTS]` y `git push -u origin <rama>`.

## 6. Trabaja

- Muéstrale al dueño tu plan en pocas líneas y empieza; pregunta solo si la orden es ambigua o la decisión es irreversible (PROTOCOLO, "Cuándo parar y preguntar").
- Commits pequeños con el formato de `CLAUDE.md`. Sube la rama después de cada avance importante.
- Actualiza la bitácora con `/bitacora` en cada avance importante.
- Respeta la lista de archivos permitidos de la orden.

## 7. Al cerrar la sesión

Si no terminaste, deja en la bitácora qué falta y el siguiente paso exacto, haz commit y sube la rama. Si terminaste, usa `/entregar`.
