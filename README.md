# Clique

Apuestas sociales con dinero ficticio entre amigos: mercados sobre la vida del grupo, un casino premium de juegos originales, póker en vivo, ranking semanal por círculo y castigo votado para el último. En reconstrucción para uso comercial en México.

> Todo es dinero ficticio. Nada se cambia por dinero real ni por premios con valor real.

## Estructura

| Carpeta | Qué hay |
| --- | --- |
| `legacy/clique/` | La app actual en Python. Funciona y es la especificación de la nueva. No se modifica. |
| `coordinacion/` | Órdenes de trabajo, bitácoras, decisiones (ADR), contratos entre agentes y el tablero. |
| `.claude/` | Roles de agente y comandos (`/orden`, `/bitacora`, `/entregar`, `/estado`, `/cerrar`). |
| `docs/` | Plan maestro y documentación. |
| `apps/`, `packages/`, `supabase/`, `assets3d/` | La versión nueva (se crean con las órdenes de la Fase 0). |

## Empezar

- Dueño: lee [COMO-EMPEZAR.md](COMO-EMPEZAR.md).
- Agentes: lee [CLAUDE.md](CLAUDE.md) y [coordinacion/PROTOCOLO.md](coordinacion/PROTOCOLO.md).

## La app actual

```bash
cd legacy/clique
python server.py                                   # http://localhost:3000
python -m unittest discover -s tests -t .          # 1,142 pruebas
```

Más detalles en [legacy/clique/README.md](legacy/clique/README.md) (en inglés).
