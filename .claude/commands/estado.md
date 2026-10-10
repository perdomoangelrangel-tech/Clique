---
description: Resume el estado del equipo: qué hizo cada encargo, qué está bloqueado y qué peticiones siguen abiertas
---

Solo lees; no modificas nada.

1. `git fetch origin`
2. Lee `origin/integracion:equipo/BITACORA_COMBINADA.md`. Si está vieja o no existe, lee la bitácora de cada rama: `git show origin/<rama>:equipo/BITACORA.md` para `e1-plataforma`, `e2-datos`, `e3-motor`, `e4-diseno`, `e5-frontend`, `e6-arte3d` e `integracion`.
3. Para cada rama: `git log --oneline -3 origin/<rama>` y si ya está en integracion (`git merge-base --is-ancestor origin/<rama> origin/integracion`).
4. Muestra:
   - una tabla: encargo, último HECHO, PENDIENTE, BLOQUEADO POR, último commit y si ya está fusionado;
   - las **peticiones abiertas** (de quién, para quién, qué archivo): una fila de «Peticiones» sigue abierta mientras ninguna línea del registro diga que se atendió;
   - las **preguntas para el dueño** de `equipo/DECISIONES.md` que siguen abiertas;
   - la última etiqueta `cimiento-*`.
5. Termina con una línea: qué conviene hacer ahora.
