---
description: Empieza o retoma una orden de trabajo de Clique (crea su rama y su carpeta de trabajo si hace falta)
argument-hint: OT-NNN
---

Vas a trabajar en la orden **$ARGUMENTS** de Clique. Sigue estos pasos en orden y no te saltes ninguno.

## 1. Trae lo más nuevo de GitHub

`git fetch origin`. El cerebro sube órdenes, correcciones y el tablero a `main` (por PR), así que **lee siempre desde `origin/main`**, no desde tu copia local:

- Orden: `git show origin/main:coordinacion/ordenes/<archivo>` (el archivo cuyo nombre empieza con `$ARGUMENTS`; búscalo con `git ls-tree --name-only origin/main coordinacion/ordenes/`). Si no existe, dilo y detente.
- Tablero: `git show origin/main:coordinacion/TABLERO.md`.

Después actualiza la raíz, que siempre está en `main`, para que comandos y roles estén al día: `git pull --ff-only` (si falla por un `.lock`, espera unos segundos y reintenta).

## 2. Lee el contexto

1. `CLAUDE.md` y `coordinacion/PROTOCOLO.md` completos.
2. La orden completa, incluida su sección **Correcciones** (si tiene, son lo primero que hay que resolver).
3. El agente que indica el campo **Agente** de la orden (código E# y rol; ver `coordinacion/AGENTES.md`): lee `.claude/agents/<rol>.md` completo y adopta ese rol y ese código durante toda la sesión.
4. Los ADR y contratos que la orden menciona.
5. Si ya existe tu bitácora `coordinacion/bitacoras/$ARGUMENTS.md` (en tu rama), léela completa: ahí está lo que hiciste antes.

## 3. Revisa dependencias

Lee el campo **Depende de** de la orden y las columnas "Para empezar" y "Para entregar" del tablero. Si algo que se necesita **para empezar** no está "Hecha", o la orden está "Bloqueada", explícale al dueño qué falta y detente. Lo que solo se necesita **para entregar** no te detiene: trabaja en todo lo demás y anótalo en la bitácora; `/entregar` lo vuelve a revisar.

## 4. Asegura tu lugar de trabajo

Todos los agentes comparten **una sola carpeta**: la carpeta principal del repositorio (la que el dueño abrió en VS Code; es la primera línea de `git worktree list`). La raíz de esa carpeta está siempre en `main` y **nadie edita ahí**. Cada orden tiene su subcarpeta `trabajo/$ARGUMENTS`, con su rama ya puesta; ahí vive todo tu trabajo, incluida tu bitácora. No es un clon: comparte el mismo repositorio y no se descarga nada. No se abren ventanas nuevas: sigues en este mismo chat.

1. Si `trabajo/$ARGUMENTS` ya existe, úsala.
2. Si no:
   - Si la rama no existe: `git worktree add trabajo/$ARGUMENTS -b <rama> origin/main`.
   - Si la rama ya existe (local o en GitHub): `git worktree add trabajo/$ARGUMENTS <rama>`.
   - Caso viejo: si `git worktree list` muestra la rama en `../Clique-trabajo/$ARGUMENTS` (protocolo anterior), esa orden sigue en su ventana aparte hasta cerrarse: díselo al dueño y detente.
3. Desde ahora **todo** ocurre dentro de `trabajo/$ARGUMENTS`: lee y edita archivos con rutas que empiecen ahí, y corre cada comando como `cd trabajo/$ARGUMENTS && <comando>` (git, pnpm, python). Nunca cambies de rama con `git switch` en la raíz ni dentro de la carpeta de otra orden.
4. Si tu carpeta ya existía y no tienes cambios sin guardar: `cd trabajo/$ARGUMENTS && git fetch origin && git rebase origin/main`.
5. Si git dice que otro proceso tiene un candado (un archivo `.lock`), es otro agente trabajando al mismo tiempo: espera unos segundos y reintenta. No borres el `.lock`.

## 5. Abre la sesión en la bitácora

- Si no existe `coordinacion/bitacoras/$ARGUMENTS.md`, créala desde `coordinacion/bitacoras/_plantilla.md` con el estado "En curso".
- Corre `/estado` (o haz lo mismo que describe) y anota los avisos dirigidos a tu rol, a `$ARGUMENTS` o a `@todos`.
- Agrega una entrada "Sesión N — fecha y hora" con el objetivo y tu plan en 3 a 7 pasos.
- Commit `docs(bitacora): inicio de sesión [$ARGUMENTS]` y `git push -u origin <rama>` (los dos dentro de `trabajo/$ARGUMENTS`).

## 6. Trabaja

- Muéstrale al dueño tu plan en pocas líneas y empieza; pregunta solo si la orden es ambigua o la decisión es irreversible (PROTOCOLO, "Cuándo parar y preguntar").
- Commits pequeños con el formato de `CLAUDE.md`. Sube la rama después de cada avance importante.
- Actualiza la bitácora con `/bitacora` en cada avance importante.
- Respeta la lista de archivos permitidos de la orden.

## 7. Al cerrar la sesión

Si no terminaste, deja en la bitácora qué falta y el siguiente paso exacto, haz commit y sube la rama. Si terminaste, usa `/entregar`.
