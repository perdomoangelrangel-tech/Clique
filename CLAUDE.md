# Clique — instrucciones para todos los agentes

Clique es una app social de apuestas con dinero ficticio entre amigos: mercados de predicción sobre la vida del grupo, un casino premium de "originals", póker, ranking semanal por círculo y castigo votado para el último. La estamos reconstruyendo para uso comercial en México. **Todo debe sentirse premium**, como un casino privado de lujo.

Lee esto completo al iniciar cada sesión. Después lee `coordinacion/PROTOCOLO.md` y la orden que te toca.

## Dónde estamos

- **Fase actual:** 0 — Cimientos. Resumen del plan en `docs/plan-maestro.md`; el documento completo es "Clique — Diagnóstico y plan maestro" en el proyecto Clique de Claude.
- **Tablero:** `coordinacion/TABLERO.md`. Lo edita solo el cerebro.
- **Repositorio:** https://github.com/perdomoangelrangel-tech/Clique
- **Supabase:** proyecto `Clique` (ref `rrmifvptjajfvxxdqqek`, región us-east-1, plan Pro).

## Mapa del repositorio

```
CLAUDE.md                 este archivo
COMO-EMPEZAR.md           guía para el dueño (no para agentes)
coordinacion/             cómo nos organizamos (léelo)
  PROTOCOLO.md            reglas de trabajo entre cerebro, dueño y agentes
  TABLERO.md              estado de las órdenes (solo lo edita el cerebro)
  ordenes/                una orden de trabajo (OT) por archivo
  bitacoras/              una bitácora por orden + la del cerebro
  decisiones/             ADR: decisiones de arquitectura aprobadas
  contratos/              acuerdos entre agentes: esquema, API, tokens, reglas, arte 3D
coordinacion/AGENTES.md   quién es quién: E0 cerebro, E1 plataforma, E2 datos, E3 motor, E4 diseño, E5 frontend, E6 arte 3D, E7 QA
.claude/agents/           roles: plataforma, datos, motor, frontend, diseno, arte3d, qa
.claude/commands/         /orden, /bitacora, /entregar, /estado, /cerrar
docs/                     plan maestro y documentación del producto
  producto/               pantallas, rutas de la API, navegación y textos es-MX   ← OT-007
legacy/clique/            la app actual en Python: ES LA ESPECIFICACIÓN. No se modifica.
legacy/clique.sha256      huella de cada archivo del legacy (para comprobar que nadie lo cambió)
legacy-tools/             scripts que ejecutan el legacy para generar casos de referencia ← OT-005
apps/web/                 app nueva (React + TypeScript + Vite, PWA)        ← OT-002
packages/engine/          lógica pura de juegos y economía en TypeScript    ← OT-002 / OT-005
packages/tokens/          tokens de diseño (fuente única de colores, tipos)  ← OT-003
assets3d/                 archivos de Blender (.blend, con Git LFS)          ← OT-006
supabase/                 migraciones SQL, funciones, pruebas de base        ← OT-004
```

## Stack (ver `coordinacion/decisiones/ADR-001-stack.md`)

- TypeScript estricto en todo lo nuevo. Node 22 LTS. pnpm workspaces.
- Web: Vite + React + React Router + TanStack Query. i18n con `es-MX` por defecto. PWA.
- Estilos: variables CSS generadas desde `packages/tokens`. Nunca colores, tamaños o sombras sueltos.
- 3D y estética: Blender para modelar y renderizar; three.js / React Three Fiber para lo que se mueve en vivo (ADR-005).
- Backend: Supabase (Postgres + Auth + Realtime + Storage + Edge Functions + Cron).
- Pruebas: Vitest (unidades), Playwright (punta a punta), pgTAP (base de datos).

## Reglas de oro

1. **Nunca trabajes en `main` ni subas a `main`.** Una orden = una rama `ot/NNN-nombre` = una bitácora. A `main` todo entra por PR que el dueño fusiona: el código de los agentes desde ramas `ot/*` y los cambios de coordinación del cerebro (tablero, órdenes, decisiones) desde ramas `cerebro/*`.
2. **El dinero solo se mueve dentro de Postgres**, con funciones SQL en una sola transacción que escriben en el libro contable. Nunca desde el navegador ni sumando saldos en TypeScript (ADR-003).
3. **El navegador nunca decide resultados** de juegos ni de mercados. Las animaciones 3D solo muestran un resultado que el servidor ya decidió.
4. **Las fichas compradas viven aparte** (ADR-004): no cuentan para el ranking semanal, no se transfieren, no se cambian por dinero y la compra está apagada hasta el dictamen legal.
5. **`legacy/clique/` es la especificación.** Antes de implementar una regla, búscala ahí y en sus pruebas. Si la nueva versión se comporta distinto, es un error salvo que un ADR diga lo contrario.
6. **No cambies un contrato** (`coordinacion/contratos/`) sin un ADR aprobado. Si lo necesitas, escríbelo como pregunta para el cerebro.
7. **Queda dentro del alcance de tu orden.** Archivos fuera de la lista permitida: pregunta primero.
8. **Todo texto visible va por i18n** (`es-MX`), nunca escrito directo en un componente.
9. **Sin secretos en git.** Claves en `.env.local` (ignorado). Ejemplos en `.env.example`. La clave `service_role` de Supabase nunca va al cliente ni al repo.
10. **Escribe en la bitácora** al iniciar, en cada avance importante y al terminar (`/bitacora`). Lo que no está escrito no existe para los demás.
11. **Ante una decisión irreversible o ambigua, pregunta.** Anótala como "Pregunta para el cerebro" y avísale al dueño en el chat.

## Idioma

- Documentación, bitácoras, commits, PR y textos de la interfaz: español de México.
- Código (variables, funciones, tablas, columnas): inglés.
- Commits: `tipo(ámbito): descripción en español [OT-NNN · E#]`. Tipos: feat, fix, refactor, test, docs, chore.
- Tu código de agente (E1 a E7) está en `coordinacion/AGENTES.md`. Úsalo en tu bitácora, tus commits y tus avisos.

## Definición de terminado

- [ ] Cada criterio de aceptación de la orden está cumplido y su evidencia está en la bitácora (comando y resultado, captura o enlace).
- [ ] Hay pruebas nuevas para lo nuevo y todas las pruebas del repo pasan.
- [ ] Las pruebas de `legacy/clique` siguen pasando y `legacy/clique.sha256` sigue cuadrando (nadie tocó el legacy).
- [ ] No hay textos sueltos fuera de i18n ni colores fuera de tokens.
- [ ] No hay cambios fuera del alcance, o están justificados en la bitácora.
- [ ] El subagente `qa` revisó la entrega y sus hallazgos están resueltos o anotados.
- [ ] La bitácora tiene la sección "Entrega" completa, la rama está subida y el PR abierto.

## Comandos

- `/orden OT-NNN` — empieza o retoma una orden (crea la rama y la carpeta de trabajo si hace falta).
- `/bitacora <nota>` — agrega una entrada a la bitácora de la orden actual.
- `/entregar` — verifica, pide revisión a `qa`, cierra la bitácora, sube la rama y abre el PR.
- `/estado` — resume todas las órdenes, bloqueos y preguntas abiertas.
- `/cerrar OT-NNN` — (dueño) después de fusionar un PR: actualiza `main` y borra la carpeta de trabajo.

## Cómo correr las cosas

- App actual (referencia): `cd legacy/clique && python server.py` → http://localhost:3000
- Pruebas de la app actual: `cd legacy/clique && python -m unittest discover -s tests -t .` (1,142 pruebas, de 5 a 9 minutos)
- Huella del legacy: `cd legacy/clique && sha256sum -c ../clique.sha256` (en Git Bash)
- Lo nuevo (cuando exista OT-002): `pnpm install`, `pnpm dev`, `pnpm test`, `pnpm lint`, `pnpm typecheck`.
