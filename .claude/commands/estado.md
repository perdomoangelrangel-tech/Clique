---
description: Resume el estado de todas las órdenes, bloqueos, preguntas abiertas y avisos entre agentes
---

Haz un resumen del estado del proyecto Clique. Solo lee; no modifiques nada.

1. Lee `coordinacion/TABLERO.md`.
2. Reúne la bitácora de cada orden, de la fuente más reciente que exista:
   - la carpeta de trabajo de esa orden, si existe: `trabajo/OT-NNN/coordinacion/bitacoras/OT-NNN.md` (las rutas exactas salen en `git worktree list`);
   - si no, la rama remota: `git fetch origin` y `git show origin/<rama>:coordinacion/bitacoras/OT-NNN.md`;
   - si no, la copia en la carpeta actual.
   Usa `git worktree list` y `git branch -a` para encontrar las ramas `ot/*`.
3. Muestra:
   - Una tabla: orden, agente, estado según el tablero, estado según su bitácora, fecha de la última sesión, siguiente paso. Marca cuando el tablero y la bitácora no coincidan.
   - **Preguntas para el cerebro** sin resolver, con su orden.
   - **Bloqueos** activos.
   - **Avisos entre agentes**: quién le avisó qué a quién. Si estás trabajando en una orden, resalta los avisos dirigidos a tu rol o a tu orden.
   - Órdenes listas para lanzar (dependencias hechas y estado "Lista").
4. Termina con una línea: qué conviene hacer ahora.
