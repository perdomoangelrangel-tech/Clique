# ADR-002 — Trabajo con agentes: una orden, una rama, una bitácora

- **Estado:** Aceptado
- **Fecha:** 2026-10-09

## Contexto

El dueño no programa. El trabajo lo hacen agentes de Claude en VS Code, varios a la vez, dirigidos por un "cerebro" que escribe órdenes y revisa. Sin reglas, varios agentes en la misma carpeta se pisan, olvidan lo que hicieron entre sesiones y cambian acuerdos sin avisar.

## Decisión

- Cada unidad de trabajo es una **orden** (`coordinacion/ordenes/OT-NNN-*.md`) con alcance, archivos permitidos y criterios de aceptación verificables.
- Cada orden vive en su **rama** `ot/NNN-nombre` y en su **carpeta de trabajo** `trabajo/OT-NNN`, una subcarpeta de la carpeta principal (`git worktree`, ignorada por git). Todos los agentes trabajan en la misma carpeta y la misma ventana de VS Code, cada uno en su chat. (Enmienda del 2026-10-10, a pedido del dueño: antes cada orden tenía carpeta y ventana aparte en `../Clique-trabajo/`.)
- Cada orden tiene su **bitácora** (`coordinacion/bitacoras/OT-NNN.md`): la memoria del agente entre sesiones y su canal hacia el cerebro y los demás agentes.
- Los acuerdos entre agentes son **contratos** (`coordinacion/contratos/`). Solo cambian con un ADR.
- El **tablero** lo edita solo el cerebro en `main`.
- `main` está protegida: solo entra código por PR aprobado y con CI en verde.

## Consecuencias

- Se puede trabajar en paralelo sin conflictos de archivos.
- Todo queda escrito: el dueño puede ver el estado con `/estado` sin preguntar a nadie.
- Hay un poco más de ceremonia por orden; por eso las órdenes deben ser de uno a tres días de trabajo.
