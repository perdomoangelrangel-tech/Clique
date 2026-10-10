# Agentes de Clique

Cada agente tiene un código (E + número), un rol fijo y un área de trabajo. El código no cambia aunque el agente pase de una orden a otra: E1 hace OT-001 y luego OT-002, cada una en su propia rama, su subcarpeta `trabajo/OT-NNN` y su propio chat. Lo edita solo el cerebro.

| Código | Rol | Área | Qué hace | Archivo de rol | Orden actual | Rama |
| --- | --- | --- | --- | --- | --- | --- |
| **E0** | Cerebro | Dirección | Escribe órdenes, revisa PR, mantiene tablero y decisiones. Ejecuta E6 mientras Blender solo esté conectado a la app de escritorio de Claude. | — | — | `cerebro/*` |
| **E1** | Plataforma | Servidores e infraestructura | Repositorio, monorepo, integración continua (GitHub Actions), ambientes, despliegues, monitoreo | `.claude/agents/plataforma.md` | OT-001 y OT-002 (dos chats) | `ot/001-verificacion`, `ot/002-monorepo-ci` |
| **E2** | Datos | Servidores de datos | Supabase: esquema Postgres, seguridad por fila, funciones SQL de dinero, tiempo real, cron, Storage | `.claude/agents/datos.md` | OT-004 | `ot/004-supabase-base` |
| **E3** | Motor | Lógica | Reglas de juegos y economía en TypeScript puro, market maker LMSR, azar verificable, paridad con el legacy | `.claude/agents/motor.md` | OT-005 | `ot/005-reglas-referencias` |
| **E4** | Diseño | Estética de interfaz | Tokens, componentes visuales, tipografía, movimiento, accesibilidad | `.claude/agents/diseno.md` | OT-003 | `ot/003-tokens-v2` |
| **E5** | Frontend | Pantallas y conexiones | App web (React, PWA), rutas, i18n, conexión con Supabase (Auth, datos, Realtime), notificaciones | `.claude/agents/frontend.md` | OT-007 | `ot/007-mapa-pantallas` |
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

## Una sola carpeta, una sola ventana

- **Carpeta principal:** `C:\Users\legma\Downloads\Clique\Clique-1` (el clon). Es lo único que el dueño abre en VS Code. Su raíz siempre está en `main` y nadie la edita.
- **Subcarpetas de trabajo:** `Clique-1\trabajo\OT-NNN`, una por orden, cada una con su rama. Ahí trabaja cada agente y ahí vive su bitácora (`trabajo\OT-NNN\coordinacion\bitacoras\OT-NNN.md`). Las crea `/orden`; no son clones (comparten el mismo repositorio) y git las ignora.
- **Un chat de Claude por agente**, todos en la misma ventana. El dueño pega el mensaje del agente **una vez**.
- Por qué cada orden tiene subcarpeta: una carpeta de git solo puede tener una rama a la vez; si dos agentes compartieran exactamente la misma, al cambiar de rama uno le borraría el trabajo al otro.
- Lo demás de `Downloads\Clique` (`clique/`, `_viejo/`, `_ot006/`) no se toca. `Clique-trabajo\OT-001` es del protocolo anterior y desaparece al cerrar OT-001.

## Mensaje para lanzar a un agente

```
Eres E<n> · <Rol> de Clique (<área>).
Tu orden: coordinacion/ordenes/<archivo de la orden>
Tu rama: <rama>  ·  tu carpeta de trabajo: trabajo/OT-<NNN> (dentro de esta misma carpeta)
Tu rol: .claude/agents/<rol>.md
Tu trabajo: <una línea>
Sigue .claude/commands/orden.md con OT-<NNN>. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E<n>.
```

## Mensajes listos (lanzamiento del 2026-10-10)

OT-001 ya está en curso con el protocolo anterior: no hace falta volver a lanzarla.

**E1 · OT-001**
```
Eres E1 · Plataforma de Clique (servidores e infraestructura).
Tu orden: coordinacion/ordenes/OT-001-repositorio.md
Tu rama: ot/001-verificacion  ·  tu carpeta de trabajo: trabajo/OT-001 (dentro de esta misma carpeta)
Tu rol: .claude/agents/plataforma.md
Tu trabajo: verificar las herramientas de esta computadora, que el legacy está intacto y pasa sus pruebas, y abrir el primer PR.
Sigue .claude/commands/orden.md con OT-001. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E1.
```

**E1 · OT-002**
```
Eres E1 · Plataforma de Clique (servidores e infraestructura).
Tu orden: coordinacion/ordenes/OT-002-monorepo-ci.md
Tu rama: ot/002-monorepo-ci  ·  tu carpeta de trabajo: trabajo/OT-002 (dentro de esta misma carpeta)
Tu rol: .claude/agents/plataforma.md
Tu trabajo: el monorepo TypeScript (pnpm, apps/web, packages/engine) y la integración continua en GitHub Actions. Las entregas de E2, E3 y E4 esperan tu PR.
Sigue .claude/commands/orden.md con OT-002. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E1.
```

**E2 · OT-004**
```
Eres E2 · Datos de Clique (servidores de datos).
Tu orden: coordinacion/ordenes/OT-004-supabase-base.md
Tu rama: ot/004-supabase-base  ·  tu carpeta de trabajo: trabajo/OT-004 (dentro de esta misma carpeta)
Tu rol: .claude/agents/datos.md
Tu trabajo: el esquema base en Supabase (perfiles, círculos, cuentas, libro contable de doble partida), la función que mueve dinero de forma atómica, seguridad por fila y pruebas pgTAP.
Sigue .claude/commands/orden.md con OT-004. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E2.
```

**E3 · OT-005**
```
Eres E3 · Motor de Clique (lógica).
Tu orden: coordinacion/ordenes/OT-005-reglas-y-referencias.md
Tu rama: ot/005-reglas-referencias  ·  tu carpeta de trabajo: trabajo/OT-005 (dentro de esta misma carpeta)
Tu rol: .claude/agents/motor.md
Tu trabajo: el mapa de todas las reglas de economía y juegos de la app actual y los casos de referencia generados ejecutando el legacy.
Sigue .claude/commands/orden.md con OT-005. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E3.
```

**E4 · OT-003**
```
Eres E4 · Diseño de Clique (estética de interfaz).
Tu orden: coordinacion/ordenes/OT-003-tokens-v2.md
Tu rama: ot/003-tokens-v2  ·  tu carpeta de trabajo: trabajo/OT-003 (dentro de esta misma carpeta)
Tu rol: .claude/agents/diseno.md
Tu trabajo: los tokens de diseño v2 (paleta, tipografías, sombras, espacios) como fuente única, con su prueba de contraste; la página /diseno cuando OT-002 esté fusionada.
Sigue .claude/commands/orden.md con OT-003. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E4.
```

**E5 · OT-007**
```
Eres E5 · Frontend de Clique (pantallas y conexiones).
Tu orden: coordinacion/ordenes/OT-007-mapa-pantallas-textos.md
Tu rama: ot/007-mapa-pantallas  ·  tu carpeta de trabajo: trabajo/OT-007 (dentro de esta misma carpeta)
Tu rol: .claude/agents/frontend.md
Tu trabajo: el inventario de pantallas y rutas de la app actual, la navegación de la app nueva y todos los textos traducidos al español de México.
Sigue .claude/commands/orden.md con OT-007. Lee primero la sección "Correcciones" de tu orden. Trabaja solo dentro de tu carpeta de trabajo. Firma tu bitácora y tus commits como E5.
```

E6 (OT-006) la ejecuta el cerebro con Blender. E7 no se lanza: `/entregar` lo llama solo.
