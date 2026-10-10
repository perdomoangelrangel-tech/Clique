# Contratos

Un contrato es un acuerdo escrito entre agentes que les permite trabajar en paralelo: uno lo publica, los demás lo usan tal cual. Cambiar un contrato existente requiere un ADR aprobado por el cerebro, porque puede romper el trabajo de otra rama.

| Contrato | Dueño | Lo crea | Para qué sirve |
| --- | --- | --- | --- |
| `comandos.md` | plataforma | OT-002 | Comandos estándar del repo (instalar, probar, construir) |
| `tokens.md` | diseno | OT-003 | Nombres de tokens de diseño y reglas de uso |
| `esquema.md` | datos | OT-004 | Tablas, RLS y firmas de funciones SQL |
| `reglas-economia.md` | motor | OT-005 | Cada regla y número de la economía y los juegos, con referencia al legacy |
| `arte3d.md` | arte3d | OT-006 | Escala, nombres, materiales, presupuestos y exportación de todo el 3D |
| `api.md` | datos + frontend | Fase 1 | Llamadas que hace la app a Supabase y sus respuestas |

Un contrato nuevo empieza como "Propuesto" en su primera línea y pasa a "Aprobado" cuando el cerebro lo revisa.
