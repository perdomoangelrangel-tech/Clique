# Agentes de Clique

Cada agente tiene un código (E + número), un rol fijo y un área de trabajo. El código no cambia aunque el agente pase de una orden a otra: E1 hace OT-001 y luego OT-002, cada una en su propia rama y su propia ventana. Lo edita solo el cerebro.

| Código | Rol | Área | Qué hace | Archivo de rol | Orden actual | Rama |
| --- | --- | --- | --- | --- | --- | --- |
| **E0** | Cerebro | Dirección | Escribe órdenes, revisa PR, mantiene tablero y decisiones. Ejecuta E6 mientras Blender solo esté conectado a la app de escritorio de Claude. | — | — | `cerebro/*` |
| **E1** | Plataforma | Servidores e infraestructura | Repositorio, monorepo, integración continua (GitHub Actions), ambientes, despliegues, monitoreo | `.claude/agents/plataforma.md` | OT-001, después OT-002 | `ot/001-verificacion`, `ot/002-monorepo-ci` |
| **E2** | Datos | Servidores de datos | Supabase: esquema Postgres, seguridad por fila, funciones SQL de dinero, tiempo real, cron, Storage | `.claude/agents/datos.md` | OT-004 | `ot/004-supabase-base` |
| **E3** | Motor | Lógica | Reglas de juegos y economía en TypeScript puro, market maker LMSR, azar verificable, paridad con el legacy | `.claude/agents/motor.md` | OT-005 | `ot/005-reglas-referencias` |
| **E4** | Diseño | Estética de interfaz | Tokens, componentes visuales, tipografía, movimiento, accesibilidad | `.claude/agents/diseno.md` | OT-003 | `ot/003-tokens-v2` |
| **E5** | Frontend | Pantallas y conexiones | App web (React, PWA), rutas, i18n, conexión con Supabase (Auth, datos, Realtime), notificaciones | `.claude/agents/frontend.md` | Fase 1 (sin orden aún) | — |
| **E6** | Arte 3D | Estética 3D | Blender: modelos, materiales, renders, exportación ligera para la web | `.claude/agents/arte3d.md` | OT-006 (la ejecuta E0) | `ot/006-direccion-de-arte` |
| **E7** | QA | Calidad | Revisa cada entrega contra la orden y las reglas. No se lanza aparte: `/entregar` lo llama solo. | `.claude/agents/qa.md` | Todas | — |

## Cómo se usan los códigos

- **Firma:** cada agente escribe su código en la primera línea de su bitácora (`**Agente:** E2 · Datos`) y al final de sus commits (`[OT-004 · E2]`).
- **Avisos:** en la bitácora se dirigen por código: `@E3: la tabla ledger_entries ya existe, firma en contratos/esquema.md`. También valen `@OT-NNN` y `@todos`.
- **Quién depende de quién:**
  - E1 (OT-002) prepara el terreno para E3, E4 y E5.
  - E2 publica el esquema que usan E3 y E5.
  - E3 publica las reglas que usan E2 y E5.
  - E4 y E6 publican la estética que usa E5.

## Mensaje para lanzar a un agente

El dueño pega este mensaje (con los datos de la tabla) en Claude, primero en la ventana principal y después en la ventana nueva que se abre:

```
Eres E<n> · <Rol> de Clique (<área>).
Tu orden: coordinacion/ordenes/<archivo de la orden>
Tu rama: <rama>  ·  tu carpeta de trabajo: ../Clique-trabajo/OT-<NNN>
Tu rol: .claude/agents/<rol>.md
Tu trabajo: <una línea>
Sigue .claude/commands/orden.md con OT-<NNN>. Firma tu bitácora y tus commits como E<n>.
```
