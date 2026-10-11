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
| **D11** | **Los juegos se ven como los dibujos 2D, pero en 3D** ("me gusta más la estética de la versión 2D; el chiste sería hacer la versión 2D pero en 3D"). Las 14 imágenes de juego y los juegos en vivo usan el estilo del dibujo: formas redondeadas, colores planos de la paleta en dos tonos y contorno de tinta. Ahí lima y bermellón son colores de los objetos. La ruleta en vivo es funcional: lleva sus números y se simplifica si hace falta. El club privado de cartas (D4) sigue para el armazón, los fondos y los íconos de la app. | 11-oct | `equipo/contratos/arte3d.md` §13; para los juegos sustituye la receta de luz de mesa |
| **D12** | **La monetización no está decidida y se conservan sus piezas:** la compra de fichas (apagada, D3) y el pase de temporada siguen en el plan. El modelo lo decide el dueño después del dictamen legal (D10). Guía: el documento del dueño "Clique: un casino que no es casino" (las fichas no valen dinero; se cobra por estilo y acceso, nunca por probabilidades; los premios son de estatus). | 11-oct | Conversación con E0 |
| **D13** | **El repositorio pasa a privado.** Lo cambia el dueño en GitHub (Settings → General → Danger Zone → Change visibility → Private): el proxy de los agentes no lo permite. Mientras siga público, nada de secretos ni datos reales. Con el repositorio privado, los minutos de GitHub Actions cuentan (E1). | 11-oct | Conversación con E0 |
| **D14** | **La app es para escritorio y para celular.** El celular de referencia es el iPhone del dueño: Safari dibuja a 60 cuadros por segundo como máximo, y la meta es 60 sin caídas. Un modelo en vivo no pasa de 8 mil triángulos (la ruleta quedó en 7,206). | 11-oct | `equipo/contratos/arte3d.md` §6 |
| **D15** | **Textos de casino, sí, mientras no prometan dinero real.** Se aprueban las propuestas de E5: "fichas" o un ícono de ficha en vez del signo $, "Plantarte" por "Cash out", "Agregar fichas", "Préstamos de fichas" y "Enviar fichas". Clique habla como casino, pero nunca de dinero que se cobra o se retira. | 11-oct | `equipo/contratos/textos.md` §5 (E5) |
| **D16** | **Cada juego tiene su sala y entras a ella.** Los juegos se ven como un casino de verdad: la forma y los colores del dibujo con acabado real (laca, esmalte, latón, fieltro) y luz cálida, dentro de un salón (alfombra, nogal, terciopelo, candiles, otras mesas). Al abrir un juego la cámara entra al salón y baja a la mesa. La sala de ruleta es la muestra; las demás siguen cuando el dueño la apruebe. Afina D11: la idea del dibujo se queda, el acabado plano no. El panorama de cada sala puede medir hasta 4096 × 2048 y 600 KB: es la excepción al tope de 1024 px de las texturas (ADR-005). | 11-oct | `equipo/contratos/arte3d.md` §14 |

## Preguntas abiertas para el dueño

| Fecha | Pregunta | Quién la necesita |
|---|---|---|
| 10-oct | Cuentas: ¿pasamos el registro a Supabase Auth (correo verificado, Google, Apple) en la ronda 2? | E2, E5 |
| 11-oct | La sala de ruleta (D16) es la muestra de cómo se ven todos los juegos: ¿la apruebas para hacer las otras? | E6, E5 |
