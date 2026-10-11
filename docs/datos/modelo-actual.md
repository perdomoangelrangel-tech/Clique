# El modelo real del archivo de datos

*Generado por `python -m backend.datos.inventario`. No se edita a mano: se cambia `backend/datos/catalogo.py` y se
vuelve a generar. `python -m backend.datos.inventario --verificar` falla si la app guarda un campo que aquí no está.*

Hoy toda la app vive en un archivo, `data/db.json` (`backend/store.py`), cargado en memoria y guardado completo
después de cada cambio. La bolsa de valores guarda sus precios aparte, en `data/market.json` (`backend/stockengine.py`),
y no está en este documento. Este es el inventario de lo que guarda `db.json`, de quién lo escribe y quién lo lee, y
de a dónde va en el esquema de Postgres v1 (`supabase/migrations/`).

**Cómo leerlo.** Rutas con punto: `{}` es la clave de un mapa (un id, una semana), `[]` un elemento de una lista. Un
campo *opaco* se guarda entero y no se describe por dentro. *Lo escriben* y *Lo leen* salen de leer el código
(`backend/datos/codigo.py`): es aproximado, sigue cadenas de claves, alias y nombres de variable; lo que no puede
seguir no lo cuenta. **El dinero** del archivo está en dólares con decimales (`balance`, `accum`, apuestas,
posiciones) salvo el libro (`ledger`), los préstamos y las transferencias, que ya van en centavos. En Postgres todo
va en centavos `bigint`.

## Lo que el esquema v1 todavía no guarda

Colecciones enteras que quedan para la ronda 2 (dentro de las demás, cada campo dice lo suyo en su fila):

- `feed`: Los premios grandes recientes de todos (el anuncio del casino). → se arma desde casino_rounds
- `poker`: Las mesas de póker vivas. → poker_tables, poker_seats; el dinero real de la mesa, en una cuenta del sistema por mesa
- `challenges`: Los retos de cada semana. → challenges
- `loans`: Los préstamos (§7). → loans y loan_payments
- `transfers`: Las transferencias entre amigos (§11). → transfers (el dinero ya está en el libro: transfer.out y transfer.in)
- `fundvotes`: Las votaciones para agregar fondos (§13e). → fund_votes
- `social`: Amistades, solicitudes y lo leído. → friendships
- `chats`: Los chats directos y de grupo. → chats, chat_members, chat_messages

Y lo que no se migra a propósito:

- `meta`: lo sustituyen las migraciones de Postgres
- `usernames`: índice único profiles_username_lower
- `sessions`: Supabase Auth (ronda 2)
- `idem`: en Postgres la idempotencia del dinero es ledger_transactions.idempotency_key; la de las respuestas, ronda 2

## Datos de la base

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `meta` | objeto | Datos de la base misma: versión y marcas de lo que ya corrió. | — | `server.main`, `weekly.pay_midweek`, `weekly.remind_short`, `weekly.requirements_start`, `weekly.tick` | no se migra: lo sustituyen las migraciones de Postgres |
| `meta.schema` | entero | Versión de los datos (backend/migrations.py). | — | — | no se migra: la versión es la de supabase/migrations |
| `meta.week` | semana (texto) | La última semana que vio el servidor; si cambia, se cierra la anterior. | `weekly.tick` | `weekly.tick` | ronda 2: tabla de estado del cierre semanal |
| `meta.midweek` | semana (texto) | La última semana en que se pagó el bono del miércoles. | `weekly.pay_midweek` | `weekly.pay_midweek` | ronda 2: estado del cierre semanal |
| `meta.reminded` | semana (texto) | La última semana en que se avisó a quien no llega al mínimo. | `weekly.remind_short` | `weekly.remind_short` | ronda 2: estado del cierre semanal |
| `meta.requirements_from` | semana (texto) | Desde qué semana cuenta el mínimo semanal. | `weekly.tick` | `weekly.requirements_start` | app_settings (requirements_from) |
| `meta.accounts_migration` | objeto · opaco | Constancia de cuando se partió el saldo en dos cuentas. | — | — | no se migra: historia del archivo |
| `meta.goals_migration` | objeto · opaco | Constancia de la migración de metas. | — | — | no se migra: historia del archivo |
| `meta.game_goals_migration` | objeto · opaco | Constancia de la migración de metas por juego. | — | — | no se migra: historia del archivo |
| `meta.horses_retired` | objeto · opaco | Constancia del retiro de las carreras de caballos (reembolsos). | — | — | no se migra: historia del archivo |

## Personas y sesiones

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `users` | mapa id → persona | Las cuentas de la app. | — | `challenges.settle_week`, `chats._friends_only`, `chats._name`, `chats.open_dm`, `fundvotes._eligible`, `fundvotes._user` y 22 más | profiles |
| `users.{}` | objeto | Una persona. | `txn.Txn.__exit__`, `users.register` | `chats._name`, `fundvotes._user`, `markets.edit_apply`, `server.Hub.publish`, `social._person`, `transfers._check` y 9 más | profiles (una fila) |
| `users.{}.id` | texto (12 hex) | Su id. | `users.register` | `challenges._pay`, `challenges.backfill_week`, `chats._group_owned`, `chats.add_members`, `chats.chat_for`, `chats.create_group` y 124 más | profiles.legacy_id (y profiles.id = uuid5 del id) |
| `users.{}.username` | texto | Su nombre de usuario, 3 a 20 letras, números o _. | `users.register` | `chats._name`, `fundvotes.propose`, `games._record`, `games.accum_account`, `games.demo_account`, `poker._new_seat` y 17 más | profiles.username |
| `users.{}.salt` | texto | Sal de la contraseña. | `users.register`, `users.set_password` | `users.login`, `users.password_ok`, `users.set_password` | no se migra: las contraseñas las guarda Supabase Auth (ronda 2) |
| `users.{}.hash` | texto | Contraseña con sal (pbkdf2). | `users.register`, `users.set_password` | `users.login`, `users.password_ok` | no se migra: Supabase Auth (ronda 2) |
| `users.{}.balance` | dólares (float) | Saldo de la cuenta semanal. | `migrations.split_accounts`, `seed.new_season`, `users.credit`, `users.debit`, `users.register` | `games._bet`, `games._bj_json`, `games._chicken_json`, `games._hilo_json`, `games._mines_json`, `games._moles_json` y 23 más | accounts (kind weekly).balance, en centavos; debe ser la suma del libro |
| `users.{}.accum` | dólares (float) | Saldo de la cuenta acumulada. | `migrations.split_accounts`, `users.register` | `server.api_user`, `server.me_json` | accounts (kind accumulated).balance, en centavos |
| `users.{}.createdAt` | ms (entero) | Cuándo se creó la cuenta. | `users.register` | `cosmetics.requirement_met`, `cosmetics.requirement_progress`, `loans.limits`, `ranking.board`, `server.api_user`, `weekly.pay_midweek` y 3 más | profiles.created_at |
| `users.{}.suspended` | bool | Cuenta suspendida (la pone el dueño a mano; la app solo la lee). | — | `fundvotes._eligible`, `ranking.board`, `transfers.eligible`, `weekly.pay_midweek` | profiles.suspended |
| `users.{}.deleted` | bool | Cuenta borrada (a mano; la app solo la lee). | — | `fundvotes._eligible`, `ranking.board`, `transfers.eligible`, `weekly.pay_midweek` | profiles.deleted_at |
| `users.{}.wk` | objeto | La línea de salida de su semana. | `ledger.post`, `migrations.split_accounts`, `users.register`, `weekly.refill_weekly` | `loans.collect_from_allocation`, `weekly.perf_inputs`, `weekly.refill_weekly` | ronda 2: week_starts (persona, semana, inicio, externo) |
| `users.{}.wk.week` | semana (texto) | De qué semana es la línea de salida. | `migrations.split_accounts`, `users.register`, `weekly.refill_weekly` | `weekly.perf_inputs` | ronda 2 |
| `users.{}.wk.start_c` | centavos (entero) | Lo que tenía al empezar la semana. | `migrations.split_accounts`, `users.register`, `weekly.refill_weekly` | `weekly.perf_inputs` | ronda 2 |
| `users.{}.wk.ext_c` | centavos (entero) | Lo que le dieron de fuera esta semana (no cuenta como ganancia). | `ledger.post`, `migrations.split_accounts`, `users.register`, `weekly.refill_weekly` | `ledger.post`, `weekly.perf_inputs` | ronda 2: se puede sacar del libro (meta.external) |
| `users.{}.stats` | mapa semana → contadores · opaco | Contadores por semana (apuestas, rondas, mejores premios). | `seed.new_season`, `users._week`, `users.add_deposit_stat`, `users.register` | `games.profit_summary`, `migrations.add_goals`, `migrations.split_accounts`, `milestones.backfill`, `server.api_user`, `users._week` y 4 más | ronda 2: se recalcula desde casino_rounds y market_trades |
| `users.{}.activity` | lista | Su actividad reciente (para el perfil). | `seed.new_season`, `users.log`, `users.register` | `markets.portfolio`, `users.log` | ronda 2: se arma desde el libro y las rondas |
| `users.{}.activity[]` | objeto · opaco | Un renglón de actividad: t, kind, amount, text, ref. | `seed.new_season`, `users.log` | — | ronda 2 |
| `users.{}.history` | lista | Sus rondas de casino terminadas con la cuenta semanal (las más nuevas). | `games._record`, `poker._cash_out`, `seed.new_season`, `users.register` | `challenges.backfill_week`, `games._record`, `games.profit_summary`, `milestones.backfill`, `milestones.backfill_games`, `poker._cash_out` y 1 más | casino_rounds (account weekly, status finished) |
| `users.{}.history[]` | objeto | Una ronda terminada. | — | — | casino_rounds |
| `users.{}.history[].id` | texto | Id de la ronda. | `games._record`, `poker._cash_out` | — | casino_rounds.legacy_id |
| `users.{}.history[].t` | ms (entero) | Cuándo terminó. | `games._record`, `poker._cash_out` | `challenges.backfill_week` | casino_rounds.created_at y finished_at |
| `users.{}.history[].game` | texto | El juego (dice, mines, poker...). | `games._record`, `poker._cash_out` | `challenges.backfill_week`, `milestones.backfill_games` | casino_rounds.game |
| `users.{}.history[].bet` | dólares (float) | Lo apostado. | `games._record`, `poker._cash_out` | `challenges.backfill_week`, `milestones.backfill_games` | casino_rounds.bet, en centavos |
| `users.{}.history[].payout` | dólares (float) | Lo pagado. | `games._record`, `poker._cash_out` | `challenges.backfill_week`, `milestones.backfill_games` | casino_rounds.payout, en centavos |
| `users.{}.history[].profit` | dólares (float) | payout - bet. | `games._record`, `poker._cash_out` | — | no se migra: se calcula |
| `users.{}.history[].mult` | decimal o null | El multiplicador. | `games._record`, `poker._cash_out` | `challenges.backfill_week`, `milestones.backfill_games` | casino_rounds.multiplier |
| `users.{}.history[].detail` | texto | Cómo fue ("number 26"). | `games._record`, `poker._cash_out` | — | casino_rounds.detail |
| `users.{}.accGame` | objeto | El casino jugado con la cuenta acumulada (13c). | `games.accum_account` | — | casino_rounds (account accumulated) |
| `users.{}.accGame.history` | lista | Sus rondas terminadas con la cuenta acumulada. | — | `games.accum_account` | casino_rounds (account accumulated) |
| `users.{}.accGame.history[]` | objeto · opaco | Una ronda: los mismos campos que users.{}.history[]. | — | — | casino_rounds |
| `users.{}.accGame.activity` | lista · opaco | Actividad del casino con la cuenta acumulada. | — | `games.accum_account` | ronda 2 |
| `users.{}.accGame.stats` | mapa · opaco | Contadores del casino con la cuenta acumulada. | — | `games.accum_account` | ronda 2 |
| `users.{}.demo` | objeto · opaco | La cartera de práctica: saldo, historia y contadores de mentira. | `games.demo_account` | `migrations.retire_horses` | no se migra: no es dinero (ECONOMY.md §1) |
| `users.{}.goals` | objeto · opaco | Rango, XP, retos y metas (progress.py, milestones.py). | `progress.state` | `progress.close_week`, `progress.state`, `progress.xp_of` | ronda 2: progress, milestones |
| `users.{}.inbox` | lista | Sus avisos. | `inbox.push` | `inbox.mark_seen`, `inbox.unseen`, `inbox.view` | ronda 2: notifications |
| `users.{}.inbox[]` | objeto · opaco | Un aviso: id, t, kind, title, text, data, seen. | `inbox.mark_seen`, `inbox.push` | `inbox.mark_seen` | ronda 2 |
| `users.{}.inv` | mapa artículo → compra · opaco | Lo que compró en la tienda. | `cosmetics.inventory` | — | ronda 2: inventory |
| `users.{}.profile` | objeto · opaco | Lo que se ve de su perfil: avatar, marco, insignia, título, fondo, color, letra y bio. | `cosmetics.profile` | `cosmetics.profile`, `cosmetics.public_style`, `cosmetics.uploaded_file`, `users.look_field` | profiles.look (sin bio) y profiles.bio |
| `users.{}.pos` | mapa símbolo → posición · opaco | Sus acciones en la bolsa: sh, cost_c, real_c. | `exchange._positions`, `exchange.trade` | `exchange.listing`, `exchange.trade` | ronda 2: stock_positions |
| `users.{}.trades` | lista | Sus operaciones en la bolsa. | `exchange.trade` | `challenges.backfill_week`, `exchange.detail`, `exchange.portfolio`, `milestones.backfill` | ronda 2: stock_trades |
| `users.{}.trades[]` | objeto · opaco | Una operación: id, t, sym, side, sh, px, total, mid. | `exchange.trade` | `challenges.backfill_week` | ronda 2 |
| `users.{}.loanId` | texto o null | El préstamo abierto. | `loans._apply_payment`, `loans.borrow` | `loans.active` | ronda 2: loans |
| `users.{}.loans` | lista | Los ids de sus préstamos. | `loans.borrow` | `loans._count_this_week`, `loans.view` | ronda 2: loans |
| `users.{}.loans[]` | texto | Un id de préstamo. | — | — | ronda 2 |
| `users.{}.mail` | objeto | Su correo para recuperar la cuenta. | `recovery.attach` | `recovery._owner`, `recovery.attach`, `recovery.confirm`, `recovery.request_reset`, `recovery.resend`, `recovery.reset_with_code` y 4 más | no se migra: Supabase Auth (ronda 2) |
| `users.{}.mail.addr` | texto | La dirección. | `recovery.attach` | `server.api_reset_by_email` | no se migra: Supabase Auth |
| `users.{}.mail.verified` | bool | Si ya la confirmó. | `recovery.attach` | — | no se migra: Supabase Auth |
| `users.{}.mail.codes` | objeto · opaco | Códigos de confirmación y de recuperación, con sal. | — | `recovery.reset_with_code` | no se migra: Supabase Auth |
| `users.{}.midweek` | objeto | El bono del miércoles que ya recibió. | `weekly.pay_midweek` | `weekly.pay_midweek` | ronda 2: se saca del libro (txid midweek-<semana>) |
| `users.{}.midweek.week` | semana (texto) | De qué semana. | `weekly.pay_midweek` | — | ronda 2 |
| `users.{}.midweek.amount` | dólares (float) | Cuánto. | `weekly.pay_midweek` | — | ronda 2 |
| `users.{}.passGo` | objeto | El último relleno semanal (para el aviso). | `weekly.refill_weekly` | `server.me_json` | ronda 2 |
| `users.{}.passGo.week` | semana (texto) | De qué semana. | `weekly.refill_weekly` | — | ronda 2 |
| `users.{}.passGo.amount` | dólares (float) | Cuánto. | `weekly.refill_weekly` | — | ronda 2 |
| `users.{}.voucher` | objeto · opaco | El vale de bienvenida usado. | `users.redeem_voucher` | `users.voucher_info` | ronda 2 |
| `users.{}.xfer` | objeto | Sus transferencias a amigos: contraseña, límites y registro. | `transfers.state` | `transfers.has_password` | ronda 2: transfers |
| `users.{}.xfer.fails` | entero | Intentos fallidos de la contraseña de transferencias. | `transfers.state` | — | ronda 2 |
| `users.{}.xfer.lockUntil` | ms (entero) | Hasta cuándo está bloqueada. | `transfers.state` | — | ronda 2 |
| `users.{}.xfer.pw` | objeto · opaco | La contraseña de transferencias (hash, sal, fecha). | — | — | ronda 2 |
| `users.{}.xfer.sent` | mapa día → centavos · opaco | Lo enviado por día, cuenta acumulada. | `transfers.state` | — | ronda 2 |
| `users.{}.xfer.sent_weekly` | mapa día → centavos · opaco | Lo enviado por día, cuenta semanal. | — | — | ronda 2 |
| `users.{}.xfer.log` | lista | Sus transferencias recientes. | `transfers.state` | — | ronda 2: transfers |
| `users.{}.xfer.log[]` | objeto · opaco | Una transferencia vista desde la persona: dir, peer, c, acct, note, status. | — | — | ronda 2 |
| `usernames` | mapa nombre → id | Índice de nombres en minúsculas. | — | `social.search`, `users.by_username`, `users.login`, `users.register`, `users.reset_password` | no se migra: índice único profiles_username_lower |
| `usernames.{}` | texto | El id de la persona con ese nombre. | `users.register` | `users.by_username`, `users.login`, `users.reset_password` | no se migra |
| `sessions` | mapa sha256(token) → sesión | Las sesiones abiertas. | — | `users.drop_session`, `users.make_session`, `users.set_password`, `users.user_for_token` | no se migra: Supabase Auth (ronda 2) |
| `sessions.{}` | objeto | Una sesión. | `users.drop_session`, `users.make_session`, `users.set_password`, `users.user_for_token` | `users.user_for_token` | no se migra |
| `sessions.{}.userId` | texto | De quién es. | `users.make_session` | `users.user_for_token` | no se migra |
| `sessions.{}.expires` | ms (entero) | Cuándo vence. | `users.make_session` | `users.user_for_token` | no se migra |

## Círculos y cierre semanal

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `circles` | mapa id → círculo | Los grupos de amigos. | — | `chats.chat_for`, `chats.delete_message`, `chats.list_for`, `chats.recipients`, `chats.summary`, `chats.title` y 17 más | circles |
| `circles.{}` | objeto | Un círculo. | `circles.create` | `chats.chat_for`, `chats.delete_message`, `chats.recipients`, `chats.summary`, `chats.title`, `circles.get` y 2 más | circles (una fila) |
| `circles.{}.id` | texto | Su id. | `circles.create` | `chats.summary`, `circles.join_by_code`, `circles.summary`, `markets.create`, `markets.detail`, `markets.distribution.circle_key` y 9 más | circles.legacy_id |
| `circles.{}.name` | texto | Nombre, 2 a 40 caracteres. | `circles.create`, `circles.update` | `chats.title`, `circles.summary`, `markets.distribution.circle_key`, `markets.summary`, `server.api_user`, `social.circle_mates` y 4 más | circles.name |
| `circles.{}.description` | texto | Descripción, hasta 200. | `circles.create`, `circles.update` | `circles.summary` | circles.description |
| `circles.{}.emoji` | texto | Su emoji. | `circles.create`, `circles.update` | `chats.summary`, `circles.summary`, `markets.distribution.circle_key`, `markets.summary`, `server.api_user` | circles.emoji |
| `circles.{}.visibility` | texto | private o public. | `circles.create`, `circles.update` | `circles.can_view`, `circles.join`, `circles.summary`, `markets.summary` | circles.visibility |
| `circles.{}.inviteCode` | texto | El código para entrar. | `circles.create`, `circles.regen_code` | `circles._code`, `circles.join`, `circles.join_by_code`, `circles.summary` | circles.invite_code |
| `circles.{}.ownerId` | texto | Quién lo creó. | `circles.create` | `chats.delete_message`, `circles.leave`, `circles.owner_or_403`, `circles.summary`, `markets._manager_or_403`, `markets.can_edit` y 5 más | circles.owner_id |
| `circles.{}.createdAt` | ms (entero) | Cuándo se creó. | `circles.create` | `circles.summary`, `weekly.finalize_week`, `weekly.plan_rewards` | circles.created_at |
| `circles.{}.members` | mapa id → ms | Los miembros y cuándo entraron. | `circles.create` | `chats.chat_for`, `chats.recipients`, `chats.summary`, `circles.is_member`, `circles.join`, `circles.join_by_code` y 14 más | circle_members |
| `circles.{}.members.{}` | ms (entero) | Cuándo entró ese miembro. | `circles.join`, `circles.join_by_code`, `circles.kick`, `circles.leave` | `server.api_circle_get` | circle_members.joined_at |
| `circles.{}.punishments` | mapa semana → castigos | Los castigos propuestos para cada semana. | `circles.create`, `seed.new_season` | `weekly._poll`, `weekly._poll_json`, `weekly._winning_punishment` | ronda 2: punishments y punishment_votes |
| `circles.{}.punishments.{}` | lista | Los castigos de una semana. | `weekly._poll` | `weekly._poll_json`, `weekly._winning_punishment` | ronda 2 |
| `circles.{}.punishments.{}[]` | objeto · opaco | Un castigo: id, authorId, text, t, votes. | — | `weekly._poll_json` | ronda 2 |
| `circles.{}.recaps` | mapa semana → cierre | La tabla final de cada semana cerrada, guardada para siempre. | `circles.create`, `seed.new_season` | `cosmetics.rewards_earned`, `weekly.finalize_week`, `weekly.mark_served`, `weekly.reward_history`, `weekly.rewards_pending`, `weekly.trophies` y 1 más | week_closes |
| `circles.{}.recaps.{}` | objeto | El cierre de una semana. | `weekly.finalize_week` | `weekly.mark_served`, `weekly.view` | week_closes (una fila) |
| `circles.{}.recaps.{}.week` | semana (texto) | La semana. | `weekly.finalize_week` | — | week_closes.week |
| `circles.{}.recaps.{}.finalizedAt` | ms (entero) | Cuándo se cerró. | `weekly.finalize_week` | `weekly.view` | week_closes.finalized_at |
| `circles.{}.recaps.{}.reason` | texto | last (el peor) o minimum (no llegó al mínimo). | `weekly.finalize_week` | `weekly.view` | week_closes.reason |
| `circles.{}.recaps.{}.loserIds` | lista | Quién perdió la semana. | `weekly.finalize_week` | `weekly.mark_served`, `weekly.view` | week_closes.loser_ids |
| `circles.{}.recaps.{}.loserIds[]` | texto | Un id. | — | — | week_closes.loser_ids |
| `circles.{}.recaps.{}.punishment` | objeto o null · opaco | El castigo ganador, con su autor. | `weekly.finalize_week` | `weekly.view` | week_closes.punishment |
| `circles.{}.recaps.{}.note` | texto | La nota del cierre. | `weekly.finalize_week` | `weekly.view` | week_closes.note |
| `circles.{}.recaps.{}.awards` | lista · opaco | Los premios simbólicos de la semana. | `weekly.finalize_week` | `weekly.trophies`, `weekly.view` | week_closes.awards |
| `circles.{}.recaps.{}.rules` | objeto · opaco | Las reglas que aplicaron esa semana. | `weekly.finalize_week` | `weekly.view` | week_closes.rules |
| `circles.{}.recaps.{}.active` | entero | Cuántos miembros jugaron. | `weekly.finalize_week` | `weekly.view` | week_closes.active |
| `circles.{}.recaps.{}.scale` | decimal | La escala de premios por círculo chico. | `weekly.finalize_week` | `weekly.view` | week_closes.scale |
| `circles.{}.recaps.{}.served` | bool | Si el castigo ya se cumplió. | `weekly.finalize_week`, `weekly.mark_served` | `weekly.mark_served`, `weekly.view` | week_closes.served |
| `circles.{}.recaps.{}.standings` | lista | La tabla final, en orden. | `weekly.finalize_week` | `weekly.view` | week_standings |
| `circles.{}.recaps.{}.standings[]` | objeto | Un renglón de la tabla. | — | — | week_standings (una fila) |
| `circles.{}.recaps.{}.standings[].userId` | texto | Quién. | `weekly.finalize_week` | — | week_standings.user_id |
| `circles.{}.recaps.{}.standings[].position` | entero | Su lugar. | `weekly.finalize_week` | — | week_standings.position |
| `circles.{}.recaps.{}.standings[].value` | dólares (float) | Lo que tenía al cerrar. | `weekly.finalize_week` | — | week_standings.value, en centavos |
| `circles.{}.recaps.{}.standings[].start` | dólares (float) | Lo que tenía al empezar. | `weekly.finalize_week` | — | week_standings.start_value, en centavos |
| `circles.{}.recaps.{}.standings[].delta` | dólares (float) | Su desempeño de la semana. | `weekly.finalize_week` | — | week_standings.delta, en centavos |
| `circles.{}.recaps.{}.standings[].moves` | entero | Cuántas jugadas hizo. | `weekly.finalize_week` | — | week_standings.moves |
| `circles.{}.recaps.{}.standings[].active` | bool | Si jugó. | `weekly.finalize_week` | — | week_standings.active |
| `circles.{}.recaps.{}.standings[].out` | bool | Si perdió por no llegar al mínimo. | `weekly.finalize_week` | — | week_standings.out_by_minimum |
| `circles.{}.recaps.{}.standings[].rewardNote` | texto | Por qué cobró o no. | `weekly.finalize_week` | — | week_standings.reward_note |
| `circles.{}.recaps.{}.standings[].req` | objeto · opaco | Cómo iba con el mínimo semanal. | `weekly.finalize_week` | — | week_standings.requirements |
| `circles.{}.recaps.{}.rewards` | mapa id → premio | Los premios en dinero de esa semana. | `weekly.finalize_week` | `cosmetics.rewards_earned`, `weekly.reward_history`, `weekly.rewards_pending`, `weekly.view` | week_rewards |
| `circles.{}.recaps.{}.rewards.{}` | objeto | El premio de una persona. | — | — | week_rewards (una fila) |
| `circles.{}.recaps.{}.rewards.{}.amount` | centavos (entero) | Cuánto. | — | — | week_rewards.amount |
| `circles.{}.recaps.{}.rewards.{}.position` | entero | Por qué lugar. | — | — | week_rewards.position |
| `circles.{}.recaps.{}.rewards.{}.paid` | bool | Si ya se pagó. | — | — | week_rewards.paid |
| `circles.{}.recaps.{}.rewards.{}.txid` | texto | La clave del pago en el libro. | — | — | week_rewards.transaction_id |
| `circles.{}.recaps.{}.rewards.{}.paidAt` | ms (entero) | Cuándo se pagó. | — | — | ledger_transactions.created_at del pago |
| `snapshots` | mapa semana → valores | Lo que tenía cada persona al cerrar cada semana. | — | `weekly.finalize_week`, `weekly.start_value` | week_snapshots |
| `snapshots.{}` | mapa persona → dólares | Los de una semana. | `weekly.finalize_week` | `weekly.start_value` | week_snapshots |
| `snapshots.{}.{}` | dólares (float) | Lo que tenía esa persona, neto de deudas. | — | `weekly.start_value` | week_snapshots.holding, en centavos |
| `challenges` | mapa semana → retos | Los retos de cada semana. | `challenges.assign` | `challenges.claim`, `challenges.settle_pending`, `challenges.settle_week`, `challenges.view`, `weekly.tick` | ronda 2: challenges |
| `challenges.{}` | objeto | Los retos de una semana. | `challenges.assign` | `challenges.assign`, `challenges.claim`, `challenges.settle_week`, `challenges.view` | ronda 2 |
| `challenges.{}.week` | semana (texto) | La semana. | `challenges.assign` | — | ronda 2 |
| `challenges.{}.start` | ms (entero) | Empieza. | `challenges.assign` | — | ronda 2 |
| `challenges.{}.end` | ms (entero) | Termina. | `challenges.assign` | — | ronda 2 |
| `challenges.{}.assignedAt` | ms (entero) | Cuándo se repartieron. | `challenges.assign` | — | ronda 2 |
| `challenges.{}.settled` | bool | Si ya se pagaron los no reclamados. | `challenges.assign`, `challenges.settle_week` | `challenges.settle_week`, `challenges.view` | ronda 2 |
| `challenges.{}.settledAt` | ms (entero) | Cuándo. | `challenges.settle_week` | — | ronda 2 |
| `challenges.{}.items` | lista | Los retos. | `challenges.assign` | `challenges.claim`, `challenges.settle_week`, `challenges.view` | ronda 2 |
| `challenges.{}.items[]` | objeto · opaco | Un reto: id, kind, metric, target, reward_c, account, xp y sus textos. | — | `challenges._pay`, `challenges._value`, `challenges.cid_of`, `challenges.claim`, `challenges.evaluate`, `challenges.item_row` y 2 más | ronda 2 |

## Mercados

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `markets` | mapa id → mercado | Los mercados de predicción. | — | `markets.create`, `markets.distribution`, `markets.get`, `markets.list_markets`, `markets.open_positions_value`, `markets.portfolio` | markets |
| `markets.{}` | objeto | Un mercado. | `markets.create` | `markets.distribution.circle_key`, `markets.get` | markets (una fila) |
| `markets.{}.id` | texto | Su id. | `markets.create` | `challenges.backfill_week`, `markets._position_row`, `markets._request_key`, `markets.cancel`, `markets.create`, `markets.edit_apply` y 9 más | markets.legacy_id |
| `markets.{}.circleId` | texto o null | Su círculo (null: de todo el sitio). | `markets.create` | `markets.circle_of`, `markets.list_markets`, `server.api_market_cancel`, `server.api_market_comment`, `server.api_market_create`, `server.api_market_edit` y 3 más | markets.circle_id |
| `markets.{}.creatorId` | texto | Quién lo propuso. | `markets.create` | `challenges.backfill_week`, `markets._manager_or_403`, `markets.can_edit`, `markets.history`, `markets.summary`, `milestones.backfill` | markets.creator_id |
| `markets.{}.question` | texto | La pregunta, 5 a 160 caracteres. | `markets.create` | `markets._position_row`, `markets.cancel`, `markets.edit_apply`, `markets.list_markets`, `markets.resolve`, `markets.summary` y 5 más | markets.question |
| `markets.{}.description` | texto | Detalles. | `markets.create`, `markets.edit_apply` | `markets.detail`, `markets.edit_plan`, `markets.list_markets`, `markets.summary` | markets.description |
| `markets.{}.category` | texto | La categoría. | `markets.create` | `challenges.backfill_week`, `markets._position_row`, `markets.list_markets`, `markets.summary`, `markets.trade` | markets.category |
| `markets.{}.emoji` | texto | Su emoji. | `markets.create` | `markets._position_row`, `markets.summary` | markets.emoji |
| `markets.{}.outcomes` | lista | Los resultados posibles, 2 a 12. | `markets.create` | `markets._outcome_rows`, `markets._position_row`, `markets.list_markets`, `markets.resolve`, `markets.summary`, `markets.token_label` y 1 más | markets.outcomes |
| `markets.{}.outcomes[]` | texto | Un resultado. | — | — | markets.outcomes |
| `markets.{}.b` | decimal | La liquidez b del LMSR (no es dinero). | `markets.create` | `markets._outcome_rows`, `markets._plan`, `markets._position_row`, `markets.open_positions_value`, `markets.trade`, `markets.withdraw` | markets.liquidity_b |
| `markets.{}.q` | lista | Acciones vendidas por resultado (no es dinero). | `markets.create`, `markets.trade`, `markets.withdraw` | `markets._outcome_rows`, `markets._plan`, `markets._position_row`, `markets.open_positions_value`, `markets.trade`, `markets.withdraw` | markets.shares_q |
| `markets.{}.q[]` | decimal | Las de un resultado. | — | — | markets.shares_q |
| `markets.{}.status` | texto | open, closed, resolved o void. | `markets.cancel`, `markets.create`, `markets.resolve` | `markets._manager_or_403`, `markets._position_row`, `markets.edit_plan`, `markets.open_positions_value`, `markets.state_of`, `markets.summary` y 1 más | markets.status |
| `markets.{}.winner` | entero o null | El resultado ganador. | `markets.create`, `markets.resolve` | `markets.summary` | markets.winner |
| `markets.{}.volume` | dólares (float) | Lo apostado en total. | `markets.create`, `markets.trade` | `markets.list_markets`, `markets.summary` | markets.volume, en centavos |
| `markets.{}.closesAt` | ms o null | Cuándo cierra. | `markets.create`, `markets.edit_apply` | `markets._position_row`, `markets.edit_plan`, `markets.list_markets`, `markets.state_of`, `markets.summary` | markets.closes_at |
| `markets.{}.createdAt` | ms (entero) | Cuándo se creó. | `markets.create` | `challenges.backfill_week`, `markets.history`, `markets.list_markets`, `markets.summary` | markets.created_at |
| `markets.{}.resolvedAt` | ms o null | Cuándo se decidió. | `markets.cancel`, `markets.create`, `markets.resolve` | `markets.list_markets`, `markets.summary` | markets.resolved_at |
| `markets.{}.version` | entero | Cuántas veces se editó la pregunta en algo de fondo (§6). | `markets.edit_apply` | `markets._position_row`, `markets.edit_apply`, `markets.edit_preview`, `markets.history`, `markets.summary`, `markets.trade` | ronda 2: market_edits |
| `markets.{}.edits` | lista · opaco | Las ediciones de la pregunta. | `markets.edit_apply` | `markets.detail`, `markets.edit_plan`, `markets.history`, `markets.summary` | ronda 2: market_edits |
| `markets.{}.exit` | objeto · opaco | La ventana para salir sin costo tras una edición de fondo. | `markets.edit_apply` | `markets.exit_info`, `markets.exit_open` | ronda 2: market_edits |
| `markets.{}.positions` | mapa id → fichas | Las posiciones de cada persona. | `markets.create` | `markets._plan`, `markets.cancel`, `markets.detail`, `markets.edit_apply`, `markets.edit_plan`, `markets.exit_info` y 7 más | market_positions |
| `markets.{}.positions.{}` | mapa ficha → posición | Las de una persona, por ficha (y0 = sí al 0, n1 = no al 1). | `markets.trade`, `markets.withdraw` | `markets._plan`, `markets.detail`, `markets.exit_info`, `markets.open_positions_value`, `markets.portfolio`, `markets.trade` y 1 más | market_positions |
| `markets.{}.positions.{}.{}` | objeto | Una posición. | `images._jpeg`, `markets.trade`, `markets.withdraw` | `markets._plan`, `markets.withdraw` | market_positions (una fila) |
| `markets.{}.positions.{}.{}.shares` | decimal | Acciones que tiene. | `markets.trade`, `markets.withdraw` | `markets._plan`, `markets._position_row`, `markets.detail`, `markets.edit_apply`, `markets.edit_plan`, `markets.open_positions_value` y 3 más | market_positions.shares |
| `markets.{}.positions.{}.{}.invested` | dólares (float) | Lo que metió. | `markets.trade`, `markets.withdraw` | `markets._plan`, `markets._position_row`, `markets.cancel`, `markets.resolve`, `markets.trade`, `markets.withdraw` | market_positions.invested, en centavos |
| `markets.{}.positions.{}.{}.settled` | bool | Si ya se liquidó. | `markets.cancel`, `markets.resolve` | `markets._position_row`, `markets.portfolio` | market_positions.settled |
| `markets.{}.positions.{}.{}.payout` | dólares (float) | Lo que cobró al liquidar. | `markets.cancel`, `markets.resolve` | `markets._position_row` | market_positions.payout, en centavos |
| `markets.{}.positions.{}.{}.refunded` | dólares (float) | Lo que se le devolvió (mercado anulado o retiro). | `markets.cancel` | `markets._position_row` | ronda 2: market_positions.refunded |
| `markets.{}.positions.{}.{}.v` | entero | La versión de la pregunta con que compró. | — | `markets._position_row` | ronda 2: market_edits |
| `markets.{}.positions.{}.{}.pre` | objeto · opaco | Lo que tenía antes de la última edición de fondo. | `markets.edit_apply`, `markets.withdraw` | `markets._position_row`, `markets.withdraw` | ronda 2: market_edits |
| `markets.{}.trades` | lista | Las operaciones, en orden. | `markets.create`, `markets.trade`, `markets.withdraw` | `challenges.backfill_week`, `markets.detail`, `markets.participants`, `markets.recent_volume`, `markets.trade`, `markets.withdraw` | market_trades |
| `markets.{}.trades[]` | objeto | Una operación. | — | — | market_trades (una fila) |
| `markets.{}.trades[].u` | texto | Quién. | `markets.trade`, `markets.withdraw` | `challenges.backfill_week`, `markets.detail`, `markets.participants` | market_trades.user_id |
| `markets.{}.trades[].k` | texto | buy, sell... | `markets.trade`, `markets.withdraw` | `challenges.backfill_week`, `markets.detail` | market_trades.kind |
| `markets.{}.trades[].token` | texto | La ficha. | `markets.trade`, `markets.withdraw` | `markets.detail` | market_trades.token |
| `markets.{}.trades[].shares` | decimal | Acciones. | `markets.trade`, `markets.withdraw` | `markets.detail` | market_trades.shares |
| `markets.{}.trades[].amount` | dólares (float) | Dinero. | `markets.trade`, `markets.withdraw` | `challenges.backfill_week`, `markets.detail`, `markets.recent_volume` | market_trades.amount, en centavos |
| `markets.{}.trades[].price` | decimal | Precio promedio (0 a 1). | `markets.trade`, `markets.withdraw` | `markets.detail` | market_trades.price |
| `markets.{}.trades[].t` | ms (entero) | Cuándo. | `markets.trade`, `markets.withdraw` | `challenges.backfill_week`, `markets.detail`, `markets.recent_volume` | market_trades.created_at |
| `markets.{}.history` | lista | Las probabilidades a lo largo del tiempo (la gráfica). | `markets.create`, `markets.trade`, `markets.withdraw` | `markets.detail`, `markets.trade`, `markets.withdraw` | ronda 2: market_prices |
| `markets.{}.history[]` | objeto | Un punto. | — | — | ronda 2 |
| `markets.{}.history[].t` | ms (entero) | Cuándo. | `markets.trade`, `markets.withdraw` | — | ronda 2 |
| `markets.{}.history[].p` | lista | La probabilidad de cada resultado. | `markets.trade`, `markets.withdraw` | — | ronda 2 |
| `markets.{}.history[].p[]` | decimal | Una probabilidad. | — | — | ronda 2 |
| `markets.{}.comments` | lista | Los comentarios. | `markets.add_comment`, `markets.create` | `markets.add_comment`, `markets.detail`, `markets.summary` | ronda 2: market_comments |
| `markets.{}.comments[]` | objeto | Un comentario. | — | — | ronda 2 |
| `markets.{}.comments[].id` | texto | Su id. | `markets.add_comment` | — | ronda 2 |
| `markets.{}.comments[].u` | texto | Quién. | `markets.add_comment` | — | ronda 2 |
| `markets.{}.comments[].text` | texto | El texto. | `markets.add_comment` | — | ronda 2 |
| `markets.{}.comments[].t` | ms (entero) | Cuándo. | `markets.add_comment` | — | ronda 2 |

## Casino y póker

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `games` | mapa persona → juegos | Las rondas de casino en curso. La clave es el id de la persona, o id:acc para la cuenta acumulada. | — | `games._games`, `games.demo_reset`, `games.escrow`, `users.voucher_info` | casino_rounds (status active) |
| `games.{}` | mapa juego → estado · opaco | Una ronda en curso por juego (la baraja, dónde están las minas...). | `games._games`, `games.demo_reset` | `games.escrow`, `users.voucher_info` | casino_rounds.state (el navegador no la lee) |
| `feed` | lista | Los premios grandes recientes de todos (el anuncio del casino). | `games._record` | `games._record`, `server.api_games_feed` | ronda 2: se arma desde casino_rounds |
| `feed[]` | objeto | Un premio grande. | — | — | ronda 2 |
| `feed[].user` | texto | Quién. | `games._record` | — | ronda 2 |
| `feed[].game` | texto | El juego. | `games._record` | — | ronda 2 |
| `feed[].mult` | decimal | El multiplicador. | `games._record` | — | ronda 2 |
| `feed[].profit` | dólares (float) | La ganancia. | `games._record` | — | ronda 2 |
| `feed[].t` | ms (entero) | Cuándo. | `games._record` | — | ronda 2 |
| `poker` | mapa id → mesa | Las mesas de póker vivas. | `poker.tables` | — | ronda 2: poker_tables, poker_seats; el dinero real de la mesa, en una cuenta del sistema por mesa |
| `poker.{}` | objeto · opaco | Una mesa: ajustes, asientos con sus fichas, la mano en juego (baraja incluida) y su registro. | `poker._buy_in`, `poker._cash_out`, `poker._deal_street`, `poker._end_by_fold`, `poker._finish_game`, `poker._fold` y 22 más | `poker._advance_once`, `poker._after_action`, `poker._buy_in`, `poker._cash_out`, `poker._close_idle`, `poker._code` y 45 más | ronda 2 |

## El libro del archivo

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `ledger` | mapa persona → renglones | El libro de cada persona: los renglones más nuevos, completos. | `ledger._rows` | `txn.Txn.__enter__` | ledger_transactions y ledger_entries (un renglón = una transacción de dos líneas) |
| `ledger.{}` | lista | Los renglones de una persona, en orden. | `ledger._rows` | `txn.Txn.__enter__` | ledger_entries |
| `ledger.{}[]` | objeto | Un movimiento de una cuenta. | — | — | ledger_transactions + 2 ledger_entries |
| `ledger.{}[].id` | texto | Id del renglón. | `ledger.opening`, `ledger.post` | `ledger.entries` | ledger_transactions.idempotency_key (import:<persona>:<id>) y meta.legacy_id |
| `ledger.{}[].t` | ms (entero) | Cuándo. | `ledger.opening`, `ledger.post` | `ledger._compact`, `ledger.entries`, `ledger.weekly_flow` | ledger_transactions.created_at |
| `ledger.{}[].a` | texto | La cuenta: weekly o accumulated. | `ledger.opening`, `ledger.post` | `ledger._compact`, `ledger.audit`, `ledger.entries`, `ledger.weekly_flow` | ledger_entries.account_id (la cuenta de la persona) |
| `ledger.{}[].c` | centavos (entero) | El monto (+ entra, - sale). | `ledger.opening`, `ledger.post` | `ledger._compact`, `ledger.audit`, `ledger.entries`, `ledger.weekly_flow` | ledger_entries.amount (y su contrapartida en una cuenta del sistema) |
| `ledger.{}[].b` | centavos (entero) | El saldo después. | `ledger.opening`, `ledger.post` | `ledger.entries` | ledger_entries.balance_after |
| `ledger.{}[].r` | texto | La razón (casino.dice, market.buy, weekly.reward...). | `ledger.opening`, `ledger.post` | `ledger._compact`, `ledger.entries`, `ledger.weekly_flow` | ledger_transactions.reason |
| `ledger.{}[].x` | texto | Una referencia (mercado, semana...). | `ledger.post` | `ledger.entries` | ledger_transactions.meta.ref |
| `ledger.{}[].n` | texto | Una nota. | `ledger.opening`, `ledger.post` | `ledger.entries` | ledger_transactions.meta.note |
| `ledger.{}[].i` | texto | La clave de idempotencia del que lo pidió. | `ledger.post` | `ledger.find` | ledger_transactions.meta.txid |
| `ledger.{}[].e` | 1 | Dinero que llegó de fuera del juego (no cuenta como ganancia). | `ledger.opening`, `ledger.post` | `ledger.entries` | ledger_transactions.meta.external |
| `ledger_sum` | mapa persona → semanas | Los renglones viejos, sumados por semana, cuenta y razón. | `ledger._compact` | `ledger.audit`, `ledger.summaries`, `txn.Txn.__enter__` | una transacción import.carried por cuenta |
| `ledger_sum.{}` | mapa semana → cuentas | Los de una persona. | `ledger._compact` | `ledger.audit`, `ledger.summaries`, `txn.Txn.__enter__` | import.carried |
| `ledger_sum.{}.{}` | mapa cuenta → razones | Los de una semana. | `ledger._compact` | — | import.carried |
| `ledger_sum.{}.{}.{}` | mapa razón → suma | Los de una cuenta. | `ledger._compact` | — | import.carried |
| `ledger_sum.{}.{}.{}.{}` | objeto | La suma de una razón. | `ledger._compact` | — | import.carried |
| `ledger_sum.{}.{}.{}.{}.n` | entero | Cuántos renglones. | `ledger._compact` | — | ledger_transactions.meta.rows |
| `ledger_sum.{}.{}.{}.{}.c` | centavos (entero) | Cuánto suman. | `ledger._compact` | — | ledger_entries.amount de import.carried |
| `idem` | mapa clave → resultado | Peticiones ya atendidas, para que un reintento no se haga dos veces (backend/idem.py). | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `idem.seen`, `loans.borrow`, `loans.repay` y 5 más | — | no se migra: en Postgres la idempotencia del dinero es ledger_transactions.idempotency_key; la de las respuestas, ronda 2 |
| `idem.{}` | objeto | Una petición atendida. | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `markets._remember`, `markets.edit_apply`, `markets.withdraw` | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `idem.seen`, `markets._remember`, `markets.edit_apply` y 2 más | no se migra |
| `idem.{}.t` | ms (entero) | Cuándo. | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `markets._remember`, `markets.edit_apply`, `markets.withdraw` | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `markets._remember` | no se migra |
| `idem.{}.fp` | texto | La huella de lo que pedía. | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `markets._remember`, `markets.edit_apply`, `markets.withdraw` | `exchange.trade`, `idem.seen`, `markets.trade` | no se migra |
| `idem.{}.result` | objeto · opaco | La respuesta que se dio. | `cosmetics.buy`, `exchange.trade`, `idem.remember`, `markets._remember`, `markets.edit_apply`, `markets.withdraw` | `exchange.trade`, `idem.seen`, `markets.edit_apply`, `markets.trade`, `markets.withdraw` | no se migra |

## Préstamos, transferencias y votos de fondos

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `loans` | mapa id → préstamo | Los préstamos (§7). | `loans._loans` | — | ronda 2: loans y loan_payments |
| `loans.{}` | objeto | Un préstamo. | — | — | ronda 2 |
| `loans.{}.id` | texto | Su id. | `loans.borrow` | `loans._apply_payment`, `loans.collect_at_close`, `loans.collect_from_allocation`, `loans.loan_json`, `loans.repay` | ronda 2 |
| `loans.{}.uid` | texto | Quién lo pidió. | `loans.borrow` | `loans.collect_at_close`, `loans.collect_from_allocation` | ronda 2 |
| `loans.{}.week` | semana (texto) | La semana en que lo pidió. | `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.principal_c` | centavos (entero) | Lo prestado. | `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.fee_c` | centavos (entero) | El cargo. | `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.total_c` | centavos (entero) | Lo que debe en total. | `loans.borrow` | `loans._apply_payment`, `loans.loan_json` | ronda 2 |
| `loans.{}.repaid_c` | centavos (entero) | Lo que ya pagó. | `loans._apply_payment`, `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.owed_c` | centavos (entero) | Lo que falta. | `loans._apply_payment`, `loans.borrow` | `loans._apply_payment`, `loans.borrow`, `loans.collect_at_close`, `loans.collect_from_allocation`, `loans.loan_json`, `loans.owed_c` y 1 más | ronda 2 |
| `loans.{}.status` | texto | open, overdue, paid... | `loans._apply_payment`, `loans.borrow` | `loans.active`, `loans.collect_at_close`, `loans.collect_from_allocation`, `loans.loan_json`, `loans.repay` | ronda 2 |
| `loans.{}.overdue` | bool | Si está vencido. | `loans.borrow`, `loans.collect_at_close` | `loans.limits`, `loans.loan_json` | ronda 2 |
| `loans.{}.createdAt` | ms (entero) | Cuándo. | `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.dueAt` | ms (entero) | Cuándo vence. | `loans.borrow` | `loans.limits`, `loans.loan_json` | ronda 2 |
| `loans.{}.closedAt` | ms (entero) | Cuándo se cerró. | `loans._apply_payment`, `loans.borrow` | `loans.loan_json` | ronda 2 |
| `loans.{}.payments` | lista | Los pagos. | `loans._apply_payment`, `loans.borrow` | `loans._apply_payment`, `loans.loan_json` | ronda 2: loan_payments |
| `loans.{}.payments[]` | objeto | Un pago. | — | — | ronda 2 |
| `loans.{}.payments[].id` | texto | Su id. | `loans._apply_payment` | — | ronda 2 |
| `loans.{}.payments[].t` | ms (entero) | Cuándo. | `loans._apply_payment` | — | ronda 2 |
| `loans.{}.payments[].c` | centavos (entero) | Cuánto. | `loans._apply_payment` | — | ronda 2 |
| `loans.{}.payments[].kind` | texto | repay, collect... | `loans._apply_payment` | — | ronda 2 |
| `loans.{}.payments[].tx` | texto | El renglón del libro. | `loans._apply_payment` | — | ronda 2 |
| `transfers` | mapa id → transferencia | Las transferencias entre amigos (§11). | `transfers.send` | — | ronda 2: transfers (el dinero ya está en el libro: transfer.out y transfer.in) |
| `transfers.{}` | objeto | Una transferencia. | `transfers.send` | — | ronda 2 |
| `transfers.{}.id` | texto | Su id. | `transfers.send` | — | ronda 2 |
| `transfers.{}.from` | texto | Quién manda. | `transfers.send` | — | ronda 2 |
| `transfers.{}.to` | texto | Quién recibe. | `transfers.send` | — | ronda 2 |
| `transfers.{}.c` | centavos (entero) | Cuánto. | `transfers.send` | — | ronda 2 |
| `transfers.{}.account` | texto | weekly o accumulated. | `transfers.send` | — | ronda 2 |
| `transfers.{}.note` | texto | La nota. | `transfers.send` | — | ronda 2 |
| `transfers.{}.status` | texto | completed... | `transfers.send` | — | ronda 2 |
| `transfers.{}.day` | fecha (texto) | El día, para el límite diario. | `transfers.send` | — | ronda 2 |
| `transfers.{}.t` | ms (entero) | Cuándo. | `transfers.send` | — | ronda 2 |
| `fundvotes` | mapa id → votación | Las votaciones para agregar fondos (§13e). | `fundvotes._all` | — | ronda 2: fund_votes |
| `fundvotes.{}` | objeto | Una votación. | — | — | ronda 2 |
| `fundvotes.{}.id` | texto | Su id. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json`, `fundvotes.propose` | ronda 2 |
| `fundvotes.{}.userId` | texto | Quién pide los fondos. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json`, `fundvotes.hold`, `fundvotes.mine`, `fundvotes.open_for` | ronda 2 |
| `fundvotes.{}.username` | texto | Su nombre. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json` | ronda 2 |
| `fundvotes.{}.amount` | dólares (float) | Cuánto pide. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json`, `fundvotes.hold` | ronda 2, en centavos |
| `fundvotes.{}.account` | texto | A qué cuenta. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json`, `fundvotes.hold` | ronda 2 |
| `fundvotes.{}.status` | texto | open, approved, rejected... | `fundvotes._close`, `fundvotes.propose` | `fundvotes._json`, `fundvotes.cast`, `fundvotes.hold`, `fundvotes.mine`, `fundvotes.open_for`, `fundvotes.owed` y 1 más | ronda 2 |
| `fundvotes.{}.createdAt` | ms (entero) | Cuándo se abrió. | `fundvotes.propose` | `fundvotes._json`, `fundvotes.mine`, `fundvotes.owed` | ronda 2 |
| `fundvotes.{}.closesAt` | ms (entero) | Cuándo cierra. | `fundvotes.propose` | `fundvotes._json`, `fundvotes.settle` | ronda 2 |
| `fundvotes.{}.closedAt` | ms (entero) | Cuándo cerró. | `fundvotes._close` | — | ronda 2 |
| `fundvotes.{}.voters` | lista | Quién puede votar. | `fundvotes.propose` | `fundvotes._close`, `fundvotes._json`, `fundvotes.cast`, `fundvotes.owed`, `fundvotes.tally` | ronda 2 |
| `fundvotes.{}.voters[]` | texto | Un id. | — | — | ronda 2 |
| `fundvotes.{}.votes` | mapa id → bool | Los votos. | `fundvotes.propose` | `fundvotes._json`, `fundvotes.cast`, `fundvotes.owed`, `fundvotes.tally` | ronda 2 |
| `fundvotes.{}.votes.{}` | bool | A favor o en contra. | `fundvotes.cast` | — | ronda 2 |
| `fundvotes.{}.result` | objeto | El conteo al cerrar. | `fundvotes._close` | `fundvotes._json` | ronda 2 |
| `fundvotes.{}.result.inFavor` | entero | A favor. | `fundvotes._close` | — | ronda 2 |
| `fundvotes.{}.result.against` | entero | En contra. | `fundvotes._close` | — | ronda 2 |
| `fundvotes.{}.result.didNotVote` | entero | No votaron. | `fundvotes._close` | — | ronda 2 |

## Amigos y chats

| Campo | Tipo | Qué es | Lo escriben | Lo leen | En Postgres |
|---|---|---|---|---|---|
| `social` | mapa persona → amigos | Amistades, solicitudes y lo leído. | `social.rec` | — | ronda 2: friendships |
| `social.{}` | objeto | Lo de una persona. | `social.rec` | — | ronda 2 |
| `social.{}.friends` | lista | Sus amigos. | `social.rec`, `social.remove` | `social.accept`, `social.remove`, `social.request`, `social.search`, `social.view` | ronda 2 |
| `social.{}.friends[]` | texto | Un id. | — | — | ronda 2 |
| `social.{}.incoming` | lista | Solicitudes recibidas. | `social.accept`, `social.cancel`, `social.decline`, `social.rec`, `social.request` | `social.accept`, `social.cancel`, `social.decline`, `social.request`, `social.search`, `social.view` | ronda 2 |
| `social.{}.incoming[]` | texto | Un id. | — | — | ronda 2 |
| `social.{}.outgoing` | lista | Solicitudes enviadas. | `social.accept`, `social.cancel`, `social.decline`, `social.rec`, `social.request` | `social.accept`, `social.cancel`, `social.decline`, `social.request`, `social.search`, `social.view` | ronda 2 |
| `social.{}.outgoing[]` | texto | Un id. | — | — | ronda 2 |
| `social.{}.hide` | bool | Si se esconde de la lista de conectados. | `social.rec` | `social.view` | ronda 2 |
| `social.{}.receipts` | bool | Si manda avisos de leído. | `social.rec` | — | ronda 2 |
| `social.{}.seen` | ms (entero) | Última vez que se le vio. | `social.rec` | — | ronda 2 |
| `social.{}.reads` | mapa chat → número · opaco | Hasta qué mensaje leyó cada chat. | `social.rec` | — | ronda 2 |
| `social.{}.seenIn` | mapa · opaco | Dónde se le vio. | `social.rec` | — | ronda 2 |
| `chats` | mapa id → chat | Los chats directos y de grupo. | `chats._chats` | — | ronda 2: chats, chat_members, chat_messages |
| `chats.{}` | objeto | Un chat. | `chats.create_group` | — | ronda 2 |
| `chats.{}.id` | texto | Su id (dm_a_b, group_x o circle_x). | `chats._ensure` | `chats._pointer`, `chats._see`, `chats.delete_message`, `chats.leave`, `chats.list_for`, `chats.mark_read` y 6 más | ronda 2 |
| `chats.{}.kind` | texto | dm, group o circle (el chat de un círculo). | `chats._ensure` | `chats._append`, `chats._group_owned`, `chats._pointer`, `chats.delete_message`, `chats.detail`, `chats.leave` y 8 más | ronda 2 |
| `chats.{}.name` | texto | El nombre del grupo. | `chats._ensure`, `chats.create_group`, `chats.rename` | `chats.rename`, `chats.title`, `server.chat_notify` | ronda 2 |
| `chats.{}.owner` | texto o null | Quién creó el grupo. | `chats._ensure`, `chats.create_group`, `chats.leave` | `chats._group_owned`, `chats.detail`, `chats.leave` | ronda 2 |
| `chats.{}.members` | lista | Quién está. | `chats._ensure`, `chats.add_members`, `chats.create_group`, `chats.leave`, `chats.open_dm`, `chats.remove_member` | `chats._other`, `chats.add_members`, `chats.chat_for`, `chats.detail`, `chats.leave`, `chats.list_for` y 8 más | ronda 2 |
| `chats.{}.members[]` | texto | Un id. | — | `chats.leave` | ronda 2 |
| `chats.{}.seq` | entero | El número del último mensaje. | `chats._append`, `chats._ensure` | `chats._append`, `chats._pointer`, `chats._see`, `chats.mark_read`, `chats.send` | ronda 2 |
| `chats.{}.created` | ms (entero) | Cuándo se creó. | `chats._ensure` | `chats.summary` | ronda 2 |
| `chats.{}.last` | ms (entero) | El último mensaje. | `chats._append`, `chats._ensure` | `chats.summary` | ronda 2 |
| `chats.{}.msgs` | lista | Los mensajes recientes. | `chats._append`, `chats._ensure`, `chats.delete_message` | `chats._append`, `chats.delete_message`, `chats.history`, `chats.list_for`, `chats.summary`, `chats.unread` | ronda 2: chat_messages |
| `chats.{}.msgs[]` | objeto | Un mensaje. | — | `chats.history` | ronda 2 |
| `chats.{}.msgs[].n` | entero | Su número. | `chats._append` | `chats.delete_message`, `chats.fmt`, `chats.history`, `chats.unread` | ronda 2 |
| `chats.{}.msgs[].u` | texto o null | Quién (null: aviso del sistema). | `chats._append` | `chats.delete_message`, `chats.fmt`, `chats.unread` | ronda 2 |
| `chats.{}.msgs[].x` | texto | El texto. | `chats._append` | `chats.fmt` | ronda 2 |
| `chats.{}.msgs[].t` | ms (entero) | Cuándo. | `chats._append` | `chats._append`, `chats.fmt` | ronda 2 |
| `chats.{}.msgs[].sys` | bool | Si es aviso del sistema. | `chats._append` | `chats.delete_message`, `chats.fmt`, `chats.unread` | ronda 2 |

