# Tablero

Lo edita solo el cerebro (E0), por PR desde ramas `cerebro/*`. Última actualización: 2026-10-10.

**Fase actual:** 0 — Cimientos. Compuerta para pasar a la Fase 1: CI en verde y primer PR de un agente revisado y fusionado.

**Listo:** repositorio en GitHub (`perdomoangelrangel-tech/Clique`), proyecto de Supabase `Clique` (ref `rrmifvptjajfvxxdqqek`, us-east-1, Pro), ADR-001 a ADR-005 aceptados.

| OT | Título | Agente (ver AGENTES.md) | Depende de | Rama | Estado |
| --- | --- | --- | --- | --- | --- |
| [OT-001](ordenes/OT-001-repositorio.md) | Clonar el repositorio y verificar la computadora | E1 · Plataforma | — | `ot/001-verificacion` | Lista |
| [OT-002](ordenes/OT-002-monorepo-ci.md) | Monorepo TypeScript e integración continua | E1 · Plataforma | OT-001 | `ot/002-monorepo-ci` | Lista |
| [OT-003](ordenes/OT-003-tokens-v2.md) | Tokens de diseño v2 | E4 · Diseño | OT-002 | `ot/003-tokens-v2` | Lista |
| [OT-004](ordenes/OT-004-supabase-base.md) | Supabase: esquema base y libro contable | E2 · Datos | OT-001 | `ot/004-supabase-base` | Lista |
| [OT-005](ordenes/OT-005-reglas-y-referencias.md) | Mapa de reglas y casos de referencia | E3 · Motor | OT-001 (entrega después de OT-002) | `ot/005-reglas-referencias` | Lista |
| [OT-006](ordenes/OT-006-direccion-de-arte.md) | Dirección de arte del casino premium en Blender | E6 · Arte 3D (la ejecuta E0) | — | `ot/006-direccion-de-arte` | En curso |

## Orden sugerido para lanzarlas

1. **Ola 1:** E1 con OT-001, sola: prueba el ciclo completo en la computadora del dueño.
2. **Ola 2**, en paralelo cuando OT-001 esté hecha: E1 con OT-002, E2 con OT-004 y E3 con OT-005 (la entrega de OT-005 espera a que OT-002 esté fusionada).
3. **Ola 3**, cuando OT-002 esté hecha: E4 con OT-003.
4. **E6 (OT-006)** la ejecuta el cerebro desde ya, porque Blender está conectado a la app de escritorio de Claude y no a VS Code.
5. **E5** espera a la Fase 1.

OT-002 y OT-005 escriben en `packages/engine/`, pero en carpetas distintas: OT-002 crea el paquete y su convención de pruebas; OT-005 solo agrega `fixtures/` y una prueba en `test/`.

## Decisiones del dueño

- [x] Rehacer la base sobre Supabase con TypeScript (ADR-001).
- [x] Proyecto de Supabase en Pro.
- [x] Repositorio privado en GitHub.
- [x] Modelo de ingresos: cosméticos, pase de temporada, suscripción y paquetes de fichas de hasta US$5 (ADR-004, apagado hasta dictamen legal).
- [x] Estética de casino premium hecha en Blender (ADR-005).
- [ ] Abogado de juegos y datos personales antes de abrir al público y antes de encender la venta de fichas.
- [ ] Registro de la marca "Clique" en el IMPI.
