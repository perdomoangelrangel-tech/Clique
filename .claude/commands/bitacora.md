---
description: Agrega tu línea a la bitácora de tu rama (HECHO / PENDIENTE / BLOQUEADO POR / COMANDO)
argument-hint: E<n> <qué pasó>
---

Agrega una línea al final de la sección `## Registro` de `equipo/BITACORA.md` **en tu árbol** (`_ramas/<tu rama>/equipo/BITACORA.md`), con este formato exacto y la fecha de hoy:

```
- `[E<n>] <dd-mmm> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
```

- `HECHO`: lo que quedó terminado, con la prueba en verde.
- `PENDIENTE`: lo que falta del entregable.
- `BLOQUEADO POR`: quién o qué te detiene (otro encargo, el dueño), o "nada".
- `COMANDO`: el comando que demuestra lo hecho, tal cual se corre.

Si necesitas un archivo de otro encargo, además agrega una fila en `## Peticiones`: fecha, de, para, qué necesitas (archivo y línea) y "abierta".

No edites líneas anteriores: solo se agrega al final. Nota: $ARGUMENTS
