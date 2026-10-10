---
description: Agrega una entrada a la bitácora de la orden actual
argument-hint: nota opcional
---

Actualiza la bitácora de la orden en la que estás trabajando.

1. Identifica la orden por la rama actual (`git branch --show-current`, formato `ot/NNN-nombre`) y abre `coordinacion/bitacoras/OT-NNN.md`. Si no estás en la rama de una orden, dilo y detente.
2. En la sesión abierta más reciente, completa o actualiza: **Hecho** (con hash de commit), **Decisiones y por qué**, **Bloqueos**, **Preguntas para el cerebro**, **Avisos para otros agentes** y **Siguiente paso**. Sé concreto: archivos, comandos, números.
3. Si el dueño agregó una nota, inclúyela: $ARGUMENTS
4. Si cambió el estado (por ejemplo a "Bloqueada"), actualiza la primera línea de la bitácora.
5. Haz commit: `docs(bitacora): <resumen corto> [OT-NNN]`.
6. Si agregaste una pregunta para el cerebro, dile al dueño en el chat cuál es, en una o dos líneas.
