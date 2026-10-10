# ADR-001 — Rehacer la base en TypeScript sobre Supabase

- **Estado:** Aceptado por el dueño el 2026-10-10
- **Fecha:** 2026-10-09
- **Decide:** cerebro, con aprobación del dueño

## Contexto

La app actual (`legacy/clique`) es un servidor de Python de la librería estándar con todo el estado en memoria y en un archivo JSON (`backend/store.py`). En cada cambio serializa la base completa mientras sostiene un candado global, y solo puede correr una copia. Estimación: con 1,000 jugadores, ~48 MB por escritura y ~0.45 s de sitio congelado por apuesta. Mover a Postgres obliga a reescribir el acceso a datos de casi todos los módulos (106 llamadas a `db()` que mutan diccionarios en memoria).

Su lógica, en cambio, es muy buena y está cubierta por 1,142 pruebas.

## Decisión

Construir la versión comercial como un monorepo TypeScript sobre Supabase, usando `legacy/clique` y sus pruebas como especificación:

| Capa | Elección | Por qué |
| --- | --- | --- |
| Web | Vite + React + TypeScript estricto + React Router + TanStack Query, PWA | App autenticada sin necesidad de SEO; un solo lenguaje en todo el repo |
| Idioma | i18next, `es-MX` por defecto | El mercado es México; permite inglés después |
| Estilos | Variables CSS generadas desde `packages/tokens` | Una sola fuente de verdad para web y app |
| Componentes accesibles | Primitivas sin estilo (por ejemplo Radix) | Diálogos, menús y pestañas accesibles sin pelear con la identidad |
| Datos | Supabase Postgres con RLS | Transacciones reales, respaldos, réplicas |
| Dinero | Funciones SQL atómicas y libro de doble partida (ADR-003) | La base garantiza lo que hoy garantiza `txn.py` |
| Cuentas | Supabase Auth (correo, Google, Apple) | Recuperación, verificación y proveedores sin código propio |
| Tiempo real | Supabase Realtime | Precios, chat y presencia |
| Lógica de juegos | `packages/engine`, TypeScript puro y determinista, ejecutado en Edge Functions | Mismo código en servidor, pruebas y servidor de juego |
| 3D y estética | Blender para modelar y renderizar; three.js / React Three Fiber en vivo (ADR-005) | Casino premium sin perder rendimiento en celular |
| Juego en vivo (Fase 3) | Servidor Node + TS aparte para póker y Crash | Necesitan un reloj que corra solo |
| Voz (Fase 3) | LiveKit | La malla actual no pasa de 8 personas |
| Tareas programadas | Supabase Cron | Cierre semanal y bono del miércoles |
| Pruebas | Vitest, Playwright, pgTAP | Unidades, punta a punta y base de datos |
| Errores y analítica | Sentry y PostHog | Saber qué falla y medir retención |
| Paquetes | pnpm workspaces, Node 22 LTS | Rápido y estándar |

## Consecuencias

- Se reescribe todo, pero por módulos y comprobando paridad contra los casos de referencia de OT-005.
- La app actual sigue corriendo sin cambios hasta que la nueva tenga paridad; luego se migran saldos.
- Un solo lenguaje permite que cualquier agente lea cualquier parte.
- Supabase Pro (desde US$25 al mes) da ramas de base de datos por agente, respaldos diarios y evita pausas por inactividad.

## Alternativa descartada

Mantener Python (por ejemplo FastAPI) y cambiar solo el almacenamiento. Conserva más código, pero deja dos lenguajes, no aprovecha Edge Functions ni tipos compartidos con la web, y el cambio de almacenamiento ya toca casi todos los módulos.
