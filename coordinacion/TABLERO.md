# Tablero

Lo edita solo el cerebro (E0), por PR desde ramas `cerebro/*`. Última actualización: 2026-10-10.

**Fase actual:** 0 — Cimientos. Compuerta para pasar a la Fase 1: CI en verde y primer PR de un agente revisado y fusionado.

**Listo:** repositorio en GitHub (`perdomoangelrangel-tech/Clique`) clonado en `Downloads\Clique\Clique-1`, proyecto de Supabase `Clique` (ref `rrmifvptjajfvxxdqqek`, us-east-1, Pro), ADR-001 a ADR-005 aceptados.

| OT | Título | Agente (ver AGENTES.md) | Para empezar | Para entregar | Rama | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| [OT-001](ordenes/OT-001-repositorio.md) | Verificar la computadora y el clon | E1 · Plataforma | — | — | `ot/001-verificacion` | Lista |
| [OT-002](ordenes/OT-002-monorepo-ci.md) | Monorepo TypeScript e integración continua | E1 · Plataforma | — | — | `ot/002-monorepo-ci` | Lista |
| [OT-003](ordenes/OT-003-tokens-v2.md) | Tokens de diseño v2 | E4 · Diseño | — (parte A) | OT-002 fusionada (parte B) | `ot/003-tokens-v2` | Lista |
| [OT-004](ordenes/OT-004-supabase-base.md) | Supabase: esquema base y libro contable | E2 · Datos | — | OT-002 fusionada | `ot/004-supabase-base` | Lista |
| [OT-005](ordenes/OT-005-reglas-y-referencias.md) | Mapa de reglas y casos de referencia | E3 · Motor | — | OT-002 fusionada | `ot/005-reglas-referencias` | Lista |
| [OT-006](ordenes/OT-006-direccion-de-arte.md) | Dirección de arte del casino premium en Blender | E6 · Arte 3D (la ejecuta E0) | — | — | `ot/006-direccion-de-arte` | En curso |
| [OT-007](ordenes/OT-007-mapa-pantallas-textos.md) | Mapa de pantallas, navegación y textos en español | E5 · Frontend | — | — | `ot/007-mapa-pantallas` | Lista |

## Cómo se lanzan

**Todos a la vez, desde ya, en una sola carpeta y una sola ventana.** El dueño abre `Downloads\Clique\Clique-1` en VS Code y, por cada agente, abre un chat nuevo de Claude y pega su mensaje de `AGENTES.md`. Cada agente trabaja en su subcarpeta `trabajo/OT-NNN` (su rama y su bitácora viven ahí):

1. E1 con OT-001 (ya va en curso, con el protocolo anterior) y, en otro chat, E1 con OT-002.
2. E2 con OT-004.
3. E3 con OT-005.
4. E4 con OT-003 (parte A).
5. E5 con OT-007.
6. E6 (OT-006) la ejecuta el cerebro con Blender. E7 no se lanza: `/entregar` lo llama solo.

OT-002 es la pieza de la que dependen las entregas de E2, E3 y E4: es la primera que el cerebro revisa y que el dueño fusiona. Mientras tanto, esos agentes avanzan en todo lo que no necesita el monorepo (cada orden dice qué en su sección "Correcciones") y, cuando se fusione, hacen `git rebase origin/main` y entregan.

Quién escribe dónde, para no chocar: OT-002 crea la raíz, `apps/web` y `packages/engine` (salvo `fixtures/`); OT-003 crea `packages/tokens`; OT-004 crea `supabase/`; OT-005 crea `legacy-tools/`, `packages/engine/fixtures/` y una prueba en `packages/engine/test/`; OT-007 escribe solo en `docs/producto/`; OT-006 en `assets3d/`, `docs/arte/` y `apps/web/public/3d/`.

## Decisiones del dueño

- [x] Rehacer la base sobre Supabase con TypeScript (ADR-001).
- [x] Proyecto de Supabase en Pro.
- [x] Repositorio privado en GitHub.
- [x] Modelo de ingresos: cosméticos, pase de temporada, suscripción y paquetes de fichas de hasta US$5 (ADR-004, apagado hasta dictamen legal).
- [x] Estética de casino premium hecha en Blender (ADR-005).
- [ ] Abogado de juegos y datos personales antes de abrir al público y antes de encender la venta de fichas.
- [ ] Registro de la marca "Clique" en el IMPI.
