---
description: Lee tu orden vigente desde integracion y ponte al día (úsalo al empezar y cuando el dueño diga "sigue")
argument-hint: E<n>
---

Eres **$ARGUMENTS** de Clique. Ponte al día antes de tocar nada:

1. `git fetch origin`
2. Tu orden vigente: `git show origin/integracion:equipo/ORDENES_$ARGUMENTS.md`. Léela completa.
3. Tu rama y tu árbol salen de `equipo/EQUIPO.md` (tabla de encargos). Si el árbol `_ramas/<tu rama>` no existe, créalo desde la raíz: `git worktree add _ramas/<tu rama> <tu rama>`.
4. Dentro de tu árbol: `cd _ramas/<tu rama> && git rebase origin/integracion` (si no tienes cambios sin guardar).
5. Lee, y nada más: `equipo/DECISIONES.md`, `equipo/GLOSARIO.md`, lo que tu orden pide en "Lee antes", y las líneas nuevas de `origin/integracion:equipo/BITACORA_COMBINADA.md` que te nombran o que van a `@todos`.
6. Dile al dueño en cinco líneas qué vas a hacer, en qué orden y cómo vas a saber que terminaste. **Espera su visto bueno** la primera vez que recibes una orden nueva.

Todo tu trabajo pasa dentro de `_ramas/<tu rama>`: la raíz de la carpeta es `main` y no se edita (los ganchos lo impiden).
