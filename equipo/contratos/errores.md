**Estado:** Propuesto · **Dueño:** E3 · Motor · **Creado en:** ronda 1 (2026-10-10)

# Códigos de error de la API

Cada error que el servidor devuelve a la persona lleva un **código estable en inglés** (`insufficient_funds`,
`market_closed`…) además del mensaje en inglés de siempre. El código no cambia aunque cambie el texto: la interfaz traduce
por código, no por mensaje.

- **Dónde nace:** `bad(message, status=400, code=None)` en `backend/util.py` hace un `ApiError` con `.code`.
- **Cómo llega al navegador:** E1 agrega `code` a la respuesta de error en `server.py`, junto a `error` (el mensaje).
- **Quién traduce:** E5, con la columna "Texto en español" de abajo.
- **La regla:** todo `bad()` lleva un código de esta lista. Lo revisa `tests/test_errores_con_codigo.py`, que también
  rechaza un código que no esté aquí y un código de aquí que nadie use.
- **Para agregar uno:** primero la fila aquí, luego el `code="..."` en el `bad()`. Nunca se cambia el nombre de uno que
  ya existe; si su significado cambia, es otro código.

**Los números.** Muchos mensajes llevan una cantidad ("You need $12.50 more…"). El código no la trae aparte: el texto en
español de abajo se puede mostrar sin número, o E5 puede pedir a E3 que el número viaje en `data` para ese código.

## Los códigos

| Código | HTTP | Texto en español | Dónde se usa |
|---|---|---|---|
| `already_claimed` | 409 | Ya cobraste esta recompensa. | retos, hitos |
| `already_friends` | 400 | Ya son amigos. | amigos |
| `already_owned` | 409 | Ya tienes este artículo. | tienda |
| `already_seated` | 400 | Ya estás sentado en una mesa. Levántate primero. | póker |
| `already_voted` | 400 | Ya votaste. | votación de fondos |
| `amount_not_positive` | 400 | Escribe una cantidad mayor que cero. | préstamos, transferencias, agregar fondos |
| `amount_too_small` | 400 | La cantidad es demasiado pequeña. | mercados, transferencias |
| `animated_picture` | 400 | No se permiten imágenes animadas. | fotos de perfil |
| `bet_below_minimum` | 400 | La apuesta es menor que la mínima. | casino, mercados |
| `cannot_friend_self` | 400 | No puedes agregarte a ti mismo. | amigos |
| `cannot_leave_chat` | 400 | Solo puedes salir de un chat de grupo. De un círculo se sale saliendo del círculo. | chats |
| `cannot_remove_self` | 400 | No puedes sacarte a ti mismo. | círculos |
| `cannot_send_to_self` | 400 | No puedes enviarte dinero a ti mismo. | transferencias |
| `cashout_too_early` | 400 | Todavía no hay nada que cobrar: avanza al menos un paso. | casino |
| `challenge_not_found` | 404 | Ese reto no existe. | retos |
| `chat_not_found` | 404 | No encontramos ese chat. | chats |
| `circle_not_found` | 404 | No encontramos ese círculo. | círculos |
| `close_time_too_far` | 400 | La fecha de cierre está demasiado lejos. | mercados |
| `close_time_too_soon` | 400 | La fecha de cierre está demasiado cerca. | mercados |
| `company_not_found` | 404 | No hay ninguna empresa con ese símbolo. | bolsa |
| `confirm_required` | 400 | Confirma para continuar. | póker, transferencias |
| `cross_site_blocked` | 403 | Bloqueamos una solicitud que venía de otro sitio. | servidor (E1) |
| `daily_limit_reached` | 403 | Superas tu límite diario de envíos desde esa cuenta. | transferencias |
| `deposit_too_large` | 400 | La cantidad pasa del máximo por depósito. | agregar fondos |
| `edit_date_is_material` | 400 | Cambiar la fecha no puede ser una aclaración: márcalo como cambio importante. | editar mercados |
| `edit_kind_required` | 400 | Indica si es una aclaración o un cambio importante. | editar mercados |
| `edit_material_limit` | 409 | Este mercado ya tuvo un cambio importante; solo se permiten aclaraciones. | editar mercados |
| `edit_reason_required` | 400 | Ya hay apuestas: explica por qué lo cambias. | editar mercados |
| `email_already_confirmed` | 400 | Ese ya es tu correo confirmado. | correo |
| `email_not_confirmed` | 403 | Necesitas un correo confirmado en tu cuenta. | transferencias |
| `email_required` | 400 | Escribe tu correo electrónico. | correo, registro |
| `email_taken` | 409 | Ese correo ya está confirmado en otra cuenta. | correo |
| `email_unavailable` | 503 | Este sitio todavía no puede enviar correos. | correo, transferencias |
| `exchange_closed` | 503 | La bolsa todavía no abre. | bolsa |
| `exit_window_closed` | 409 | Ya terminó el plazo para retirarte de este cambio. | editar mercados |
| `field_required` | 400 | Falta un dato obligatorio. | general |
| `friend_limit` | 400 | Se alcanzó el límite de amigos. | amigos |
| `game_in_progress` | 400 | El juego ya empezó. | póker |
| `goal_not_reached` | 400 | Todavía no completas esta meta. | retos, hitos |
| `group_full` | 400 | El grupo ya está lleno. | chats |
| `guess_not_offered` | 400 | Esa apuesta no puede perder, por eso no se ofrece. | casino (Hi-Lo) |
| `hand_in_progress` | 400 | Espera a que termine la mano. | póker |
| `insufficient_funds` | 400, 402 | No tienes fichas suficientes en esa cuenta. | casino, mercados, póker, préstamos, transferencias, tienda, bolsa, libro |
| `invalid_account` | 400 | Elige la cuenta semanal o la acumulada. | casino, transferencias, agregar fondos |
| `invalid_action` | 400 | Esa acción no existe. | casino, mercados, póker, bolsa |
| `invalid_bet` | 400 | Esa apuesta no es válida. | casino (ruleta) |
| `invalid_code` | 400, 403 | El código está mal o ya venció. Pide uno nuevo. | correo, transferencias |
| `invalid_date` | 400 | La fecha no es válida. | mercados |
| `invalid_email` | 400 | Eso no parece un correo electrónico. | correo |
| `invalid_game_option` | 400 | Esa opción del juego no es válida. | casino |
| `invalid_group` | 400 | Revisa quién está en el grupo. | chats |
| `invalid_json` | 400 | La solicitud no se pudo leer. | servidor (E1) |
| `invalid_move` | 400 | Esa jugada no está permitida ahora. | casino, póker |
| `invalid_option` | 400 | Esa opción no existe. | perfil |
| `invalid_outcome` | 400 | Elige un resultado válido. | mercados |
| `invalid_outcomes` | 400 | Un mercado necesita de 2 a 12 resultados, con nombres distintos. | mercados |
| `invalid_picture` | 400 | La imagen está dañada o no se puede leer. | fotos de perfil |
| `invalid_picture_size` | 400 | La imagen no tiene un tamaño permitido. | fotos de perfil |
| `invalid_request` | 400 | La solicitud no es válida. | general |
| `invalid_request_id` | 400 | Falta el identificador de la solicitud o no es válido. | mercados, tienda, bolsa, transferencias |
| `invalid_setting` | 400 | Ese ajuste no es válido. | chats, círculos, amigos |
| `invalid_shares` | 400 | Las acciones van en números enteros. | bolsa |
| `invalid_table_settings` | 400 | Revisa los ajustes de la mesa. | póker |
| `invalid_target` | 400 | El objetivo está fuera de rango. | casino |
| `invalid_username` | 400 | El usuario debe tener de 3 a 20 letras, números o guiones bajos. | cuentas |
| `invalid_vote` | 400 | Vota a favor o en contra. | votación de fondos, póker |
| `invite_code_required` | 403, 404 | Es privado: necesitas su código. | círculos, póker |
| `item_not_owned` | 403 | Todavía no tienes ese artículo. Consíguelo en la tienda. | perfil |
| `loan_not_allowed` | 403 | Ahora no puedes pedir un préstamo. | préstamos |
| `loan_too_large` | 403 | Pides más de lo que puedes pedir ahora. | préstamos |
| `loan_too_small` | 400 | El préstamo es menor que el mínimo. | préstamos |
| `login_required` | 401 | Inicia sesión. | servidor (E1) |
| `low_contrast` | 400 | Ese color no se lee bien sobre ese fondo. Elige otro. | perfil |
| `market_cancelled` | 409 | Este mercado se canceló. | editar mercados |
| `market_closed` | 400 | Ya cerraron las apuestas de este mercado. Falta el resultado. | mercados |
| `market_not_found` | 404 | No encontramos ese mercado. | mercados |
| `market_not_open` | 400, 409 | Este mercado ya no está abierto. | mercados |
| `market_settled` | 400, 409 | Este mercado ya se liquidó. | mercados |
| `message_not_found` | 404 | Ese mensaje ya no existe. | chats |
| `milestone_not_found` | 404 | Ese hito no existe. | hitos |
| `no_bets` | 400 | Pon al menos una ficha. | casino (ruleta) |
| `no_debt` | 409 | No debes nada. | préstamos |
| `no_game` | 400 | No hay ningún juego que terminar. | póker |
| `no_pending_email` | 400 | No hay ningún correo esperando confirmación. | correo |
| `no_picture` | 400 | Primero sube una imagen. | perfil |
| `no_round_in_progress` | 400 | No tienes una ronda en curso. | casino |
| `no_skips_left` | 400 | Ya no te quedan saltos en esta ronda. | casino (Hi-Lo) |
| `no_transfer_password` | 400, 403 | Primero elige una contraseña de transferencias. | transferencias |
| `not_a_group` | 400 | Eso solo funciona en un chat de grupo. | chats |
| `not_a_number` | 400 | Escribe un número. | general |
| `not_a_voter` | 403 | Esta votación no es para ti. | votación de fondos |
| `not_allowed` | 403 | No tienes permiso para hacer esto. | semana |
| `not_circle_member` | 400, 403 | Esa persona no está en el círculo. | círculos, voz |
| `not_circle_owner` | 403 | Solo el dueño del círculo puede hacer esto. | círculos |
| `not_enough_players` | 400 | Se necesitan al menos dos jugadores. | póker |
| `not_enough_shares` | 400 | No tienes tantas acciones. | mercados, bolsa |
| `not_friends` | 400, 403 | Solo con amigos que se agregaron mutuamente. | chats, amigos, transferencias |
| `not_group_owner` | 403 | Solo quien creó el grupo puede hacer esto. | chats |
| `not_in_room` | 409 | Esa persona no está en la sala. | voz |
| `not_market_manager` | 403 | Solo quien propuso el mercado (o el dueño del círculo) puede hacer esto. | mercados |
| `not_punishment_author` | 403 | Solo quien lo propuso o el dueño del círculo puede quitar este castigo. | semana |
| `not_seated` | 400, 404 | No estás sentado en esta mesa. | póker |
| `not_table_host` | 403 | Solo el anfitrión de la mesa puede hacer esto. | póker |
| `not_your_message` | 403 | Solo puedes borrar tus propios mensajes. | chats |
| `not_your_turn` | 400 | No es tu turno. | póker |
| `nothing_to_change` | 400 | No cambiaría nada. Edita la fecha o las reglas primero. | editar mercados |
| `nothing_to_withdraw` | 404 | No tienes una apuesta de antes del cambio que retirar. | editar mercados |
| `order_too_large` | 400 | Es más de lo que se puede operar de una vez. | bolsa |
| `owner_cannot_leave` | 400 | El dueño no puede salir de su propio círculo. | círculos |
| `password_same_as_login` | 400 | La contraseña de transferencias debe ser distinta de la de tu cuenta. | transferencias |
| `password_too_long` | 400 | La contraseña es demasiado larga. | cuentas, transferencias |
| `password_too_short` | 400 | La contraseña debe tener al menos 6 caracteres. | cuentas, transferencias |
| `picture_too_big` | 413 | La imagen pesa demasiado. | fotos de perfil |
| `poker_room_full` | 400 | La sala de póker está llena. Intenta más tarde. | póker |
| `price_moved` | 409 | El precio cambió mientras decidías. Revisa la nueva cotización. | mercados, bolsa |
| `product_free` | 400 | Ese es gratis: solo póntelo. | tienda |
| `product_not_found` | 404 | Ese producto no existe. | tienda |
| `product_unavailable` | 409 | Ese producto no está a la venta ahora. | tienda |
| `punishment_duplicate` | 400 | Alguien ya propuso ese castigo. Vota por él. | semana |
| `punishment_limit` | 400 | Ya propusiste todos los castigos que puedes esta semana. | semana |
| `punishment_not_found` | 404 | No encontramos ese castigo. | semana |
| `quote_expired` | 409 | La cotización venció. Aquí tienes una nueva. | bolsa |
| `quote_not_found` | 404 | No encontramos esa cotización. Pide una nueva. | bolsa |
| `quote_used` | 409 | Esa cotización ya se usó. | bolsa |
| `rate_limited` | 429 | Vas demasiado rápido. Espera un momento. | chats, correo, voz |
| `rebuy_not_allowed` | 400 | Ahora no puedes recomprar. | póker |
| `recipient_cap_reached` | 403 | Esa cuenta no puede recibir tanto. | transferencias |
| `recipient_required` | 400 | Elige a quién enviarle. | transferencias |
| `recipient_unavailable` | 403 | Esa cuenta no puede recibir dinero ahora. | transferencias |
| `repay_too_large` | 400 | Pagas más de lo que debes. | préstamos |
| `request_id_reused` | 409 | Ese identificador ya se usó para otra operación. | mercados, tienda, bolsa |
| `request_not_found` | 404 | No hay ninguna solicitud. | amigos |
| `request_pending` | 400 | Ya le enviaste una solicitud. Dale tiempo para responder. | amigos |
| `request_too_large` | 413 | La solicitud es demasiado grande. | voz, servidor (E1) |
| `requirement_not_met` | 403 | Todavía no cumples el requisito. | tienda |
| `room_full` | 409 | La sala está llena. | voz |
| `round_in_progress` | 400 | Ya tienes una ronda en curso de este juego. | casino |
| `settings_not_accepted` | 400 | Todos tienen que aceptar los ajustes primero. | póker |
| `shares_required` | 400 | Escribe cuántas acciones. | mercados, bolsa |
| `table_full` | 400 | La mesa está llena. | póker |
| `table_not_found` | 404 | No encontramos esa mesa. | póker |
| `text_required` | 400 | Escribe algo primero. | chats |
| `text_too_long` | 400 | El texto es demasiado largo. | general |
| `text_too_short` | 400 | El texto es demasiado corto. | general |
| `too_many_attempts` | 429 | Demasiados intentos. Espera unos minutos. | cuentas |
| `too_many_bets` | 400 | Demasiadas apuestas a la vez. | casino (ruleta) |
| `too_many_decimals` | 400 | Usa como máximo dos decimales. | préstamos, transferencias |
| `too_many_open_markets` | 400 | Ya tienes el máximo de mercados públicos abiertos. Liquida uno primero. | mercados |
| `too_many_requests` | 400 | Hay demasiadas solicitudes de amistad esperando. | amigos |
| `too_many_tables` | 400 | Ya tienes el máximo de mesas abiertas. | póker |
| `trading_halted` | 409 | Las órdenes de esta empresa están en pausa por un movimiento brusco. | bolsa |
| `transfer_password_required` | 400 | Escribe tu contraseña de transferencias actual, o usa el código del correo. | transferencias |
| `transfers_disabled` | 403 | Las transferencias están apagadas. | transferencias |
| `transfers_locked` | 429 | Demasiadas contraseñas equivocadas: las transferencias están bloqueadas un rato. | transferencias |
| `unsupported_picture` | 400, 415 | Sube una imagen PNG, JPEG o WebP. | fotos de perfil, servidor (E1) |
| `user_not_found` | 400, 404 | No encontramos a esa persona. | cuentas, chats, transferencias |
| `username_taken` | 409 | Ese nombre de usuario ya está ocupado. | cuentas |
| `vote_closed` | 400 | Esa votación ya terminó. | votación de fondos |
| `vote_not_found` | 404 | Esa votación no existe. | votación de fondos |
| `vote_pending` | 400 | Lo que agregaste antes sigue esperando la votación. | votación de fondos |
| `voucher_not_needed` | 400 | Todavía tienes fichas: el cupón es para cuando te quedas sin nada. | cupón |
| `voucher_round_in_play` | 400 | Termina la ronda que estás jugando y luego canjéalo. | cupón |
| `voucher_used` | 400 | Ya usaste el cupón de esta semana. | cupón |
| `week_not_settled` | 404 | Esa semana todavía no se cierra. | semana |
| `week_not_started` | 400 | Esa semana todavía no empieza. | retos |
| `week_over` | 400, 409 | Esa semana ya terminó. | retos, semana |
| `wrong_credentials` | 401 | Usuario o contraseña incorrectos. | cuentas |
| `wrong_funds_password` | 403 | La contraseña de fondos es incorrecta. | agregar fondos, cuentas |
| `wrong_password` | 403 | Escribe tu contraseña de la cuenta para confirmar. | correo, transferencias |
| `wrong_transfer_password` | 403 | La contraseña de transferencias es incorrecta. | transferencias |

## Para E1 y E2

Los `bad()` de sus archivos los ponen ellos, con estos códigos (las líneas son de hoy):

| Archivo | Línea | Mensaje | Código |
|---|---|---|---|
| `server.py` | 152 | Enter your email address… | `email_required` |
| `server.py` | 256 | Unknown account | `invalid_account` |
| `server.py` | 261 | Invalid paging | `invalid_request` |
| `server.py` | 293 | Confirm the loan to borrow it | `confirm_required` |
| `server.py` | 344 | Invalid notifications | `invalid_request` |
| `server.py` | 797 | Pick a grid size and a number of mines | `invalid_game_option` |
| `server.py` | 876 | That table is gone | `table_not_found` |
| `server.py` | 1270 | Cross-site request blocked | `cross_site_blocked` |
| `server.py` | 1275 | That picture is too big… | `picture_too_big` |
| `server.py` | 1277 | Send a PNG, JPEG or WebP picture | `unsupported_picture` |
| `server.py` | 1282 | Request too large | `request_too_large` |
| `server.py` | 1285 | Expected JSON | `invalid_json` |
| `server.py` | 1291, 1293 | Invalid JSON | `invalid_json` |
| `server.py` | 1299 | Please log in | `login_required` |
| `backend/idem.py` | 19 | Invalid request id | `invalid_request_id` |
| `backend/idem.py` | 39 | That request id was already used for something different | `request_id_reused` |

Cuando los pongan, bajan su número en `PENDIENTES` de `tests/test_errores_con_codigo.py` (avisando a E3 en la bitácora).
