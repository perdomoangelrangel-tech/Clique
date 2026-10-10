# Decisiones firmadas

*Las firma el dueño (Ángel). Mandan sobre todo lo demás: órdenes, contratos y bitácoras. Si una orden
contradice una decisión, se para y se anota en la bitácora; nunca se elige un lado.*

*Las escribe E0 (el cerebro) cuando el dueño decide. Cada una dice de dónde sale.*

| # | Decisión | Fecha | Detalle |
|---|---|---|---|
| **D1** | **Se mejora la app original en su lugar** y se deja sólida para crecer. No se reescribe en otro lenguaje. | 10-oct | ADR-006 (sustituye a ADR-001) |
| **D2** | **El dinero solo se mueve en un libro de doble partida.** Hoy, por `backend/ledger.py`; desde la etapa B, por funciones SQL en Postgres. Nunca desde el navegador ni sumando saldos a mano. | 09-oct | ADR-003 |
| **D3** | **Paquetes de fichas de hasta US$5**, en una cuenta aparte que no cuenta para el ranking semanal, no se transfiere ni se cambia por dinero. **La compra está apagada** (`PURCHASES_ENABLED=false`) hasta el dictamen legal. | 10-oct | ADR-004 |
| **D4** | **Estética: club privado de cartas** (papel sobre mesa de fieltro, latón y luz cálida). Los cuadros de `docs/arte/` son la referencia para toda la app. | 10-oct | ADR-005; aprobado al ver los renders |
| **D5** | **Español de México por defecto** en toda la interfaz, con un sistema de traducciones; inglés como segundo idioma. | 09-oct | Plan maestro, F1 |
| **D6** | **Supabase** (proyecto `Clique`, ref `rrmifvptjajfvxxdqqek`, plan Pro) es la base de datos de destino, y el candidato para cuentas y tiempo real. | 10-oct | ADR-006 |
| **D7** | **Forma de trabajo de Ches-Hex:** un encargo por agente (E1 a E7), cada uno en su rama fija y su árbol; órdenes en `equipo/ORDENES_E<n>.md`; una bitácora por rama que se junta; un dueño por archivo; ganchos que lo hacen cumplir. | 10-oct | `EQUIPO.md`, `COORDINACION.md` (sustituye a ADR-002) |
| **D8** | **El navegador nunca decide resultados** de juegos ni de mercados. Las animaciones solo muestran lo que el servidor ya decidió. | 09-oct | ADR-005 |
| **D9** | **Supabase de producción: leer sí, escribir nunca** desde una sesión de agente. Las migraciones las aplica E0 con el sí del dueño, en una ventana de migración. | 10-oct | `COORDINACION.md` |
| **D10** | **No se abre al público** sin verificación de edad (18+), aviso de privacidad y la revisión de un abogado. Antes de cobrar, dictamen legal. | 10-oct | Plan maestro, Fase 4 |

## Preguntas abiertas para el dueño

| Fecha | Pregunta | Quién la necesita |
|---|---|---|
| 10-oct | El repositorio está **público** en GitHub y el plan decía privado. ¿Lo pasamos a privado? (Configuración → Danger Zone → Change visibility) | Todos: mientras sea público, nada de datos reales ni de negocio sensible |
| 10-oct | Cuentas: ¿pasamos el registro a Supabase Auth (correo verificado, Google, Apple) en la ronda 2? | E2, E5 |
