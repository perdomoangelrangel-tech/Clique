# Poner Clique en línea

Objetivo: tus amigos abren un enlace en el teléfono y juegan en vivo a cualquier hora. Todo es con fichas ficticias; la compra
de fichas está apagada (`PURCHASES_ENABLED=false`, D3) y **no se abre al público** sin verificación de edad, aviso de privacidad
y la revisión de un abogado (D10). Esto es un **servidor de prueba** para el grupo.

## Qué necesita Clique de un servicio

Clique es un solo programa de Python que guarda sus datos en un archivo (`db.json`). Por eso el servicio tiene que:

1. **mantener el programa encendido** (no "despertarlo cuando alguien entra"),
2. darle un **disco que sobreviva a reinicios y despliegues**, porque ahí viven los saldos y las apuestas,
3. correr **una sola copia**.

Eso descarta los planes gratuitos (borran el disco o duermen el sitio, y el dinero de todos volvería a cero) y Vercel (no tiene
disco ni programas que se queden corriendo).

**Elegimos Render** (render.com): el repositorio trae `render.yaml`, así que el despliegue es un Blueprint que se crea desde su
página, sin instalar nada en tu computadora; revisa solo la salud del sitio en `/api/salud` y le dice a Clique qué commit corre.
Fly.io también serviría, pero pide instalar su programa de terminal y escribir comandos.

**Cuesta dinero y pide tarjeta.** El disco de Render solo existe en los planes de pago (Starter o más, más el disco por GB).
Revisa los precios de hoy en render.com/pricing antes de empezar: cambian. **Tú decides si se paga**; ningún agente crea la cuenta.

## Las variables

Las escribes en la página de Render (el servicio → **Environment**). Todas están en `.env.example`, con su explicación.

| Variable | ¿Hace falta? | Qué hace |
| --- | --- | --- |
| `ADMIN_PASSWORD` | **Sí** | Tu contraseña de fondos. 10 caracteres o más, tuya. En línea, el sitio no arranca sin ella. |
| `WEEK_TIMEZONE` | Ya viene | La zona horaria de las semanas. `render.yaml` pone `America/Mexico_City` (sigue el horario de verano donde lo hay). Sirve cualquier nombre como `UTC`. La antigua `WEEK_TZ_OFFSET_HOURS` (un número fijo como `-6`) sigue funcionando. |
| `PURCHASES_ENABLED` | Ya viene | `false`. La venta de fichas sigue apagada hasta el dictamen legal (D3). No la cambies. |
| `START_BALANCE` | Opcional | Lo que trae cada cuenta nueva. 1000 si no se pone. |
| `MIDWEEK_BONUS` | Opcional | Lo que recibe cada quien en su cuenta semanal los miércoles a las 12:00. 500 si no se pone; `0` lo apaga. |
| `FUNDS_VOTE_HOURS` | Opcional | Lo más que dura abierta la votación de fondos agregados con "Agregar fondos". 24 si no se pone. |
| `WEEKLY_ALLOCATION` | Opcional | A cuánto se pone la cuenta semanal cuando empieza la semana. 1000 si no se pone; `0` lo apaga (`WEEKLY_BONUS` es el nombre viejo). |
| `WEEKLY_REWARDS`, `PARTICIPATION_REWARD` | Opcional | Premios semanales por lugar, como `400,250,150,100,50`, y lo que recibe cualquier otro que jugó. |
| `WEEKLY_MIN_POLL_BETS`, `WEEKLY_MIN_CASINO_BETS` | Opcional | El mínimo semanal: apuestas en mercados y rondas de casino para seguir en el reto. 1 y 25 si no se ponen; quien no llega pierde la semana. `0` y `0` lo apagan. |
| `STORE_OVERRIDES` | Opcional | JSON para cambiar un precio de la Tienda o quitar un producto, por ejemplo `{"frame_gold": {"price": 900}}`. |
| `LOANS_ENABLED`, `GOALS_ENABLED`, `TRANSFERS_ENABLED` y sus límites | Opcional | Préstamos, rangos, retos, logros y transferencias. Los valores normales son las reglas publicadas (ECONOMY.md, secciones 7 a 11). |
| `ICE_SERVERS`, o `TURN_URL` + `TURN_SECRET` | Opcional | Solo si las llamadas de voz no conectan para algunos (ver "Salas de voz"). |
| `RESEND_API_KEY` o `BREVO_API_KEY` o `SMTP_HOST`, y `EMAIL_FROM` | Para recuperar contraseñas por correo | Ver "Correo". |
| `RANK_BY` | Opcional | `netWorth` (normal) o `cash`: quién cuenta como "el de menos" cada semana. |
| `SEASON_RESET` | Opcional | Cámbiala a una etiqueta nueva para empezar temporada (ver "El día a día"). |
| `CLIQUE_COMMIT` | No | El commit que corre, para `/api/salud`. Render ya da `RENDER_GIT_COMMIT` y Clique lo usa. |

Todos los números de la economía están, con su valor normal, al final de **[ECONOMY.md](ECONOMY.md)**.

`CLIQUE_ENV=production`, `DATA_DIR=/data` y `HOST=0.0.0.0` ya vienen en el `Dockerfile`. `PORT` lo pone Render.

**Nunca escribas un valor real en un archivo del repositorio.** El repositorio es público mientras no lo cambies; los valores
van solo en la página de Render.

## Parte 1: crear la cuenta y el servicio en Render

Los nombres de los botones pueden cambiar un poco: Render cambia sus pantallas de vez en cuando.

1. Entra a <https://render.com> y **regístrate con GitHub** (el usuario dueño del repositorio `Clique`). Agrega la tarjeta
   cuando te la pida: el disco y el plan Starter son de pago.
2. Arriba: **New → Blueprint**. Si no aparece `perdomoangelrangel-tech/Clique`, da permiso a Render para ver ese repositorio.
3. Elige el repositorio y la rama **`integracion`** (la que E7 junta cada día; `render.yaml` ya la nombra). Render lee
   `render.yaml` y te muestra lo que va a crear: un servicio web `clique-prueba` (Docker, plan Starter, una copia) y un disco
   `clique-datos` de 1 GB montado en `/data`.
4. Te pide el valor de **`ADMIN_PASSWORD`**: pega tu contraseña de fondos (10 caracteres o más, que no esté en ningún archivo).
5. **Apply** (o **Deploy Blueprint**). Render construye la imagen con el `Dockerfile` y arranca el sitio. Tarda unos minutos.
6. Cuando el servicio diga **Live**, abre su enlace (algo como `https://clique-prueba.onrender.com`) y luego
   `https://clique-prueba.onrender.com/api/salud`. Debe decir `"ok": true` y `"database": {"read": true, "write": true}`.

`render.yaml` trae `autoDeploy: false`: cada despliegue nuevo se hace a mano con **Manual Deploy → Deploy latest commit**.
Si prefieres que se despliegue solo con cada cambio en `integracion`, cámbialo en **Settings → Auto-Deploy**.

## Parte 2: probar antes de avisarle a nadie

1. Abre el enlace, **crea una cuenta**, haz un círculo y una apuesta.
2. Abre **Logs** y revisa que **no** diga `WARNING: /data is not a mounted volume`. Si lo dice, el disco no está montado en `/data`.
3. En Render da **Manual Deploy → Deploy latest commit**. Cuando vuelva, entra otra vez: tu cuenta, tu círculo y tu apuesta
   tienen que seguir ahí. Si desaparecieron, el disco no está en `/data`: arréglalo antes de invitar a nadie.
4. Usa **Agregar fondos** con tu contraseña de fondos una vez, para ver que funciona. El dinero se agrega cuando los demás votan
   (les sale un aviso; si no hay nadie más en el sitio, se agrega en seguida).
5. Manda el enlace a tus amigos. Haz tus círculos **privados** y da el código de invitación solo a ellos. Cualquiera con el enlace
   puede crear una cuenta y ver y apostar en las apuestas **públicas**; los círculos privados y sus apuestas no los ve.

## Actualizar un sitio que ya corre

Cada arranque guarda antes una copia de `db.json` en `/data/backups` (las últimas 15) y corre, una sola vez, los pasos de datos
que falten. Hasta hoy son cuatro, y todos están en el registro como `Data migration ran: …`:

- **split_accounts**: parte cada saldo en dos (hasta $1,000 se queda en la cuenta semanal y lo demás pasa a la acumulada). No se
  crea ni se pierde un centavo, y queda su asiento en el libro.
- **retire_horses**: retira el juego de caballos y devuelve completa cualquier apuesta en una carrera sin resolver.
- **add_goals**: solo agrega: lugares vacíos para préstamos, retos y transferencias, y el avance que los registros viejos ya
  muestran. Lo que se desbloquee no se paga hasta que la persona lo reclame; la experiencia empieza en 0 para todos.
- **add_game_goals**: llena los números de cada juego (rondas, victorias, mejor multiplicador) desde el historial.

Para ver el resultado antes, con una copia del `db.json` real en tu computadora:
`python scripts/preview_migration.py ruta/a/db.json` (imprime los saldos antes y después, revisa que el total sea idéntico y no
cambia nada). Para deshacer: detén el sitio, pon el archivo más nuevo de `/data/backups` como `/data/db.json` y despliega la
versión anterior del código.

En el mismo disco viven `db.json` (cuentas y libro), `market.json` (precios e historia de la bolsa) y `uploads/` (fotos de perfil).
Si se pierde el disco, se pierde todo junto.

## Correo: contraseñas olvidadas

Cada persona tiene que dar un correo y confirmarlo con un código de 6 dígitos; desde entonces, **"¿Olvidaste tu contraseña?"
manda un código a ese correo**.

**El sitio no manda correo solo: necesita un servicio de correo.** Mientras no haya uno, el sitio sigue pidiendo el correo pero
nadie puede confirmarlo, y "¿Olvidaste tu contraseña?" dice que el correo no está encendido (la recuperación con la contraseña de
fondos sigue funcionando). Elige UNO, agrega sus variables en **Environment** y deja que se reinicie:

| Servicio | Variables | Bueno saber |
| --- | --- | --- |
| **Resend** (resend.com) | `RESEND_API_KEY`, `EMAIL_FROM` | Manda por la web, así que funciona aunque el servicio bloquee los puertos de correo. Hasta que verifiques un dominio tuyo, solo manda **a la dirección con la que te registraste**: tus amigos no recibirían sus códigos. Con dominio verificado, `EMAIL_FROM` queda como `Clique <noreply@tudominio.com>`. |
| **Brevo** (brevo.com) | `BREVO_API_KEY`, `EMAIL_FROM` | También por la web, con un cupo gratis. Verificas una sola dirección de remitente (cualquier correo tuyo) y la usas como `EMAIL_FROM`; no necesitas dominio. |
| **Cualquier servidor SMTP** (Gmail con contraseña de aplicación, uno propio) | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SECURITY` (`starttls`, `ssl` o `none`), `EMAIL_FROM` | Algunos servicios bloquean los puertos de correo; si los códigos no llegan y el registro dice que el servidor "could not be reached", usa Resend o Brevo. |

Estos servicios cambian sus reglas y planes; lee lo que dicen hoy al registrarte. **No se probó con un servicio real**: las
peticiones siguen la documentación de cada uno y se prueban contra un servidor de mentira. La primera prueba real es crear una
cuenta con tu correo y ver si llega el código; si no, **Logs** dice `Email to a***@gmail.com was not sent: …` y por qué.

Cómo se cuida: un correo cuenta solo cuando se confirma; los códigos duran de 15 a 30 minutos, sirven una vez, mueren tras cinco
intentos fallidos y se guardan revueltos; pedir un código da la misma respuesta exista o no la cuenta; un correo se confirma en una
sola cuenta; cambiar un correo confirmado pide la contraseña; al restablecer la contraseña se cierran todas las sesiones de esa
cuenta y se avisa por correo. En tu computadora (`python server.py`) no hace falta servicio: cada correo se imprime en la terminal.

## Salas de voz

Cada círculo tiene una sala de voz. El audio va directo entre los navegadores (WebRTC); el servidor solo los presenta.

- **Necesita `https`** (los navegadores solo dan el micrófono en páginas seguras). El enlace de Render ya es `https`.
- **Casi todas las conexiones de casa funcionan con los servidores STUN gratuitos. Algunas no** (ciertas oficinas, algunas
  compañías de celular): esas personas entran pero no oyen a nadie. Se arregla con un **relevo TURN** (rentado, o `coturn`
  propio): pon `TURN_URL` (como `turn:turn.ejemplo.com:3478`) y `TURN_SECRET`, o los servidores en `ICE_SERVERS` como JSON.
  Sin TURN, Clique funciona igual; solo esas personas se quedan fuera. **No se probó con un TURN real.**
- Los teléfonos cortan la llamada al bloquear la pantalla o cambiar de app: es el teléfono, no Clique. Se retoma al volver.

## El día a día

- **Cambiar el sitio:** los cambios llegan a `integracion` por E7; luego **Manual Deploy → Deploy latest commit** en Render (o
  solo, si encendiste Auto-Deploy). El sitio se cae unos segundos.
- **Cambiar la contraseña de fondos:** edita `ADMIN_PASSWORD` en **Environment**. Render reinicia el sitio.
- **Temporada nueva** (todos vuelven al saldo inicial; cuentas y círculos se quedan; mercados e historial se borran): pon en
  `SEASON_RESET` una etiqueta nueva como `2026-s42`. Se hace una vez, recuerda la etiqueta y la ignora en los siguientes
  despliegues. Usa otra la próxima vez. Antes guarda una copia de los datos.
- **En tu computadora** lo mismo es `python scripts/seed.py new-season` (con el servidor detenido). `wipe` borra también las cuentas.
- **Respaldos:** cada arranque guarda una copia de `db.json` en `/data/backups` (las últimas 15). Está en el mismo disco: protege de
  errores, no de perder el disco. Render hace instantáneas diarias de los discos; revisa en la página del disco cómo restaurar una.
- **Salud:** `https://<tu enlace>/api/salud` dice el commit, cuánto lleva encendido y si la base se puede leer y escribir. Render
  la consulta solo y reinicia el sitio si deja de responder.
- **Registro:** la pestaña **Logs** del servicio. Ahí salen los errores.

## Si algo sale mal

| Lo que ves | Por qué |
| --- | --- |
| Se cae con `Refusing to start: set the ADMIN_PASSWORD` | Falta la variable, o tiene menos de 10 caracteres. |
| Todo se borra después de un despliegue | El disco no está montado en `/data`. |
| `/api/salud` responde 503 | La carpeta de la base no se puede escribir: revisa el disco en la página del servicio. |
| Ven la página pero lo en vivo va lento o se traba | Revisa que haya una sola copia, y usa el enlace `https`. |
| El castigo semanal pasa a la hora equivocada | Corrige `WEEK_TIMEZONE`. |
| El sitio se detiene con `Unknown WEEK_TIMEZONE` | El nombre no es una zona horaria real. Usa una como `America/Mexico_City` o `UTC`. |
| Voz: algunos entran pero no oyen nada | Están en una red estricta y necesitan un TURN (ver "Salas de voz"). |
| Los precios de la bolsa se ven congelados al reiniciar | La bolsa repasa el tiempo que estuvo apagada (hasta 3 días) en unos segundos; espera un momento. |

## Probarlo en tu computadora con Docker

Si tienes Docker instalado: `docker build -t clique .` y luego
`docker run -p 3000:3000 -e ADMIN_PASSWORD=prueba-local-123 clique`, y abre <http://localhost:3000/api/salud>.
El CI hace exactamente esto en cada cambio (el trabajo `contenedor`).

## Límites honestos

- **Las salas de voz son para grupos chicos** (8 personas por omisión): cada quien se conecta con cada quien.
- **La bolsa es un juego, no un mercado:** una simulación compartida, sin impacto de tus órdenes en el precio. Ver ECONOMY.md.
- **Una sola copia.** Toda la base está en la memoria del programa y en un archivo. Para un grupo de amigos sobra; guardar tras
  cada acción tarda unos 25 ms incluso con una base inflada a propósito. El paso a Postgres (ADR-006, etapa B) quitará este límite.
- **El registro está abierto** a quien tenga el enlace, y las apuestas públicas se ven desde cualquier cuenta. Solo quien propone
  una apuesta pública puede resolverla: apuesta en las públicas solo de gente de confianza.
- **Otros servicios:** Railway o Fly.io sirven con el mismo `Dockerfile` y las mismas variables, siempre con un disco montado en
  `/data` y una sola copia.
