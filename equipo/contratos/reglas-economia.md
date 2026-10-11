**Estado:** Propuesto · **Dueño:** E3 · Motor · **Creado en:** ronda 1 (2026-10-10)

# Reglas de la economía y de los juegos

Cada regla y cada número de la economía de Clique, tal como **los hace el código hoy**, con su `archivo:línea` y la prueba
que la cubre. Todo es dinero ficticio (fichas). Si una regla de aquí y el código no coinciden, manda el código y este
contrato está mal: avisa a E3. Lo que `ECONOMY.md` dice y el código no hace (o al revés) está en **Diferencias**, al final.

Lo leen E0 (para decidir), E2 (para llevar el libro a SQL: sección **Dónde se mueve el dinero**), E5 (para mostrar
números que se puedan rastrear) y E7 (para verificar).

**Cómo se lee.**
- Las líneas son de la rama `e3-motor` el 10-oct-2026. Las pruebas se citan como `archivo::Clase.prueba`
  (todas en `tests/`). "Sin prueba" quiere decir que ninguna prueba la fija.
- El dinero se guarda en dólares de punto flotante en el usuario (`user["balance"]`, `user["accum"]`), pero el libro
  trabaja en **centavos enteros** (`backend/ledger.py:33`, `to_cents`: redondea a la mitad hacia arriba).
- Dos redondeos distintos en el código: `backend/util.py:59` `round2` (a la mitad hacia arriba) y
  `backend/lmsr.py:93` `floor_cents` (hacia abajo, "nunca a favor del jugador").

| Sección de `ECONOMY.md` | Aquí |
|---|---|
| 1. Two accounts (y "The ledger") | §1, §2 |
| 2. The weekly cycle (rendimiento, orden, recompensas, mínimo, cierre, sobrantes) | §3, §4, §5 |
| 3. Migration from the single balance | §1.5 |
| 4. The Store | §10 |
| 5. The Stock Exchange | §11 |
| 6. Editing a published poll | §13.6 |
| 7. Loans | §6 |
| 8. Ranks and XP | §8 |
| 9. Weekly challenges | §9.1 |
| 10. Milestones | §9.2 |
| 11. Friend-to-friend transfers | §7 |
| 12. The weekly close, in order | §5 |
| 13. Voice rooms | fuera de la economía: no mueve dinero |
| 13c. Casino rounds on either account | §12.1 |
| 13d. The Wednesday bonus | §2.4 |
| 13e. A vote on added funds | §2.3 |
| 14. What was verified | la columna "Prueba" de cada tabla |
| 15. Every setting | §15 |
| (no está en `ECONOMY.md`) | §2.1 bienvenida, §2.2 cupón, §12 ventaja de cada juego, §13 LMSR, §14 póker, §4.3 premios y castigo, §16 ranking global |

---

## 1. Las cuentas y el libro

| Regla | Dónde | Prueba |
|---|---|---|
| Dos cuentas por persona: **semanal** (`user["balance"]`) y **acumulada** (`user["accum"]`). No hay otra. | `backend/ledger.py:26-27` | `test_ledger.py::TwoAccounts.test_a_new_member_gets_the_welcome_money_in_the_weekly_account_only` |
| **No hay ninguna operación que pase dinero de una cuenta propia a la otra.** | `backend/economy.py:35-39` (lo declara); ninguna función lo hace | `test_ledger.py::TwoAccounts.test_there_is_no_way_to_move_money_between_the_accounts` |
| Todo cambio de saldo pasa por `ledger.post(user, cuenta, monto, razón)`. Trabaja en centavos enteros. | `backend/ledger.py:87-121` | `test_ledger.py::TwoAccounts.test_cents_never_drift`, `test_random_activity_always_adds_up`; arnés `test_dinero_solo_en_libro.py` |
| Un cargo que dejaría la cuenta bajo cero se rechaza ("Not enough funds" en la semanal, "Not enough in your accumulated account" en la acumulada). | `backend/ledger.py:101-102` | `test_ledger.py::TwoAccounts.test_weekly_money_cannot_pay_from_the_accumulated_account_or_the_other_way_round` |
| Tope de saldo: `MAX_BALANCE` = 1e18. Un abono que lo pasaría se recorta al tope (el renglón registra lo que de verdad entró). | `backend/config.py:62`, `backend/ledger.py:103-105` | `test_transfers.py::WhatCanBeSent.test_an_account_that_would_overflow_cannot_receive` |
| Cada renglón guarda: id, hora, cuenta, centavos, saldo después, razón, y opcionalmente referencia, nota, `txid` y la marca `external`. | `backend/ledger.py:107-119` | `test_ledger.py::TwoAccounts.test_a_row_says_what_where_when_and_how_much` |
| **Idempotencia:** un `txid` que ya está en el libro de esa persona devuelve el renglón anterior y no mueve nada. | `backend/ledger.py:94-97` | `test_ledger.py::TwoAccounts.test_a_transaction_id_makes_a_retry_harmless` |
| La razón, si no se da, la pone la ruta HTTP (`casino.<juego>`, `poker`, `market`, `voucher`, `store`, `stocks`, si no `other`). | `server.py:124-135`, `server.py:1303`, `backend/ledger.py:41-53` | `test_ledger.py::EveryMovementIsRecorded.test_casino_rounds_and_market_trades_leave_rows_with_a_reason_and_the_statement_matches` |
| **`external`**: dinero que llega de fuera del juego. En la semanal se suma a `wk.ext_c`, que se resta del rendimiento de la semana. | `backend/ledger.py:114-118` | `test_ledger.py::TwoAccounts.test_external_money_is_marked_and_kept_out_of_this_weeks_performance` |
| Se guardan completos los últimos `LEDGER_KEEP` = 400 renglones por persona (se compacta al pasar de 450); los viejos se suman por semana, cuenta y razón. | `backend/economy.py:111`, `backend/ledger.py:75-84` | `test_ledger.py::TwoAccounts.test_old_rows_are_folded_into_weekly_totals_and_the_books_still_balance` |
| **Auditoría:** renglones + resúmenes = saldo, en las dos cuentas (diferencia 0). | `backend/ledger.py:131-139` | `test_ledger.py::TwoAccounts.test_random_activity_always_adds_up` y casi todas las pruebas de dinero |
| La **cartera de práctica** (demo, $1,000) no es una cuenta: no tiene libro, no cuenta para nada. | `backend/games.py:21-31`, `backend/users.py:202-204`, `backend/users.py:215-219` | `test_ledger.py::TwoAccounts.test_the_practice_wallet_never_touches_the_ledger`, `test_perks.py::Demo.*` |

### 1.5 La migración a dos cuentas (archivo de E2)

| Regla | Dónde | Prueba |
|---|---|---|
| Al pasar del saldo único: hasta `WEEKLY_ALLOCATION` ($1,000) se queda en la semanal; lo que sobra va a la acumulada. Se registra un renglón `opening` por cuenta. Corre una vez (`meta.schema`). | `backend/migrations.py:12-44` | `test_migration.py::SplitAccounts.*` |
| Al quitar Horses (esquema 3): cada apuesta de una carrera sin terminar se devuelve completa a la semanal, con `txid` `horse:retired:<carrera>:<clave>`. | `backend/migrations.py:47-76` | `test_retire_horses.py::Retire.*` |

## 2. Dinero que entra de fuera

### 2.1 Bienvenida

| Regla | Dónde | Prueba |
|---|---|---|
| Cuenta nueva: `START_BALANCE` = $1,000 en la **semanal**, externo, razón `welcome`. La línea de salida de su primera semana es ese saldo. | `backend/config.py:26-37`, `backend/users.py:59-60` | `test_ledger.py::TwoAccounts.test_a_new_member_gets_the_welcome_money_in_the_weekly_account_only`, `test_deploy.py::ProductionSettings.test_start_balance_setting` |

### 2.2 El cupón semanal

| Regla | Dónde | Prueba |
|---|---|---|
| $250 (`VOUCHER_AMOUNT`) a la semanal, externo, razón `voucher`, si el efectivo semanal es menor a $0.50 (`VOUCHER_BELOW`). | `backend/config.py:52-53`, `backend/users.py:289-301` | `test_perks.py::Voucher.test_only_under_fifty_cents`, `test_redeeming_pays_250_once_a_week` |
| Uno por semana; no mientras haya una ronda de casino en curso o dinero real en una mesa de póker. | `backend/users.py:270-280`, `backend/users.py:291-296` | `test_perks.py::Voucher.test_not_while_a_round_is_on_the_table`, `test_poker_tables.py::RealMoney.test_money_at_the_table_blocks_the_voucher` |
| No cuenta como ganancia. | `backend/users.py:298-299` | `test_perks.py::Voucher.test_the_voucher_helps_but_never_counts_as_winnings`, `test_ledger.py::TwoAccounts.test_the_voucher_is_external_money_in_the_weekly_account` |

### 2.3 Agregar fondos y su votación

| Regla | Dónde | Prueba |
|---|---|---|
| La caja "Add funds" pide la contraseña de fondos (`ADMIN_PASSWORD`); máximo `MAX_DEPOSIT` = 1e15 por petición; 5 intentos por persona y 20 entre todos cada 10 minutos. | `backend/users.py:228-248`, `backend/config.py:15`, `backend/config.py:61` | `test_backend.py::Accounts.test_deposit_password`, `test_deposit_is_rate_limited`, `test_deploy.py::BruteForceLimits.test_funds_password_guesses_are_limited_across_accounts` |
| El monto queda **en espera** (en ninguna cuenta) y lo votan todos los demás con cuenta (no suspendidos ni borrados). Una petición abierta por persona. | `backend/fundvotes.py:63-79` | `test_midweek_and_fundvotes.py::StartingAVote.*` |
| Termina cuando el resultado ya no puede cambiar, cuando todos votaron o a las `FUNDS_VOTE_HOURS` = 24 h. Pasa solo con **más a favor que en contra**; empate o nadie votando no agrega nada. Sin nadie a quien preguntar, se agrega de inmediato. | `backend/economy.py:58`, `backend/fundvotes.py:47-57`, `backend/fundvotes.py:98-131` | `test_midweek_and_fundvotes.py::HowItEnds.*`, `StartingAVote.test_with_nobody_to_ask_the_money_is_added_at_once` |
| Aprobado: a la cuenta elegida, externo, razón `deposit`, `txid` `fundvote-<id>`. En la semanal también suma a la estadística `deposits`. | `backend/fundvotes.py:116`, `backend/users.py:251-257` | `test_midweek_and_fundvotes.py::WhereTheMoneyGoes.*` |
| `users.deposit()` (abono inmediato, sin votación) sigue existiendo para pruebas y el anfitrión; la web no lo usa. | `backend/users.py:260-265` | `test_midweek_and_fundvotes.py::WhereTheMoneyGoes.test_the_old_direct_credit_is_still_there_for_the_code_that_needs_it` |

### 2.4 El bono del miércoles

| Regla | Dónde | Prueba |
|---|---|---|
| Desde el **miércoles 12:00** (zona de la semana), `MIDWEEK_BONUS` = $500 a la **semanal**, externo, razón `weekly.midweek`, `txid` `midweek-<semana>`. 0 lo apaga. | `backend/economy.py:53`, `backend/weekly.py:624-655` | `test_midweek_and_fundvotes.py::Midweek.test_it_is_due_on_wednesday_at_noon_in_the_sites_time_zone`, `test_the_amount_that_ships_is_500_and_the_environment_can_change_or_remove_it` |
| A quien tenía cuenta antes de las 12:00 y no está suspendido ni borrado. Una vez por semana, aunque el reloj corra muchas veces o el servidor se reinicie; si el servidor estaba apagado a mediodía, paga al volver **en la misma semana**. | `backend/weekly.py:640-654`, `backend/weekly.py:690` | `test_midweek_and_fundvotes.py::Midweek.test_once_a_week_however_often_it_runs_and_also_after_a_restart`, `test_a_server_that_was_off_at_noon_pays_when_it_is_back_in_the_same_week`, `test_only_people_who_had_an_account_by_noon_and_are_in_good_standing` |
| Un préstamo no le quita nada al bono. | `backend/weekly.py:646-653` (no llama a `loans`) | Sin prueba |

## 3. La semana y el rendimiento

| Regla | Dónde | Prueba |
|---|---|---|
| Una semana va del **lunes 00:00 al lunes siguiente 00:00**, hora de `WEEK_TIMEZONE` (por omisión `America/Mexico_City`; sin base de zonas, UTC−6 fijo). Las fronteras se cuentan por calendario, no sumando horas. Una zona desconocida detiene el arranque. | `backend/config.py:64-71`, `backend/util.py:12-35`, `backend/util.py:107-162` | `test_timezone.py::WeekBoundaries.*`, `ChoosingTheZone.*` |
| **Lo que tienes** = efectivo semanal + valor de venta de las apuestas abiertas + apuestas en rondas de casino sin terminar + dinero real en una mesa de póker − **lo que debes de un préstamo**. | `backend/markets.py:542-562`, `backend/games.py:222-230`, `backend/poker.py:216-231` | `test_weekly_rewards.py::Leaderboard.test_open_bets_and_unfinished_rounds_count_as_money_you_hold`, `test_loans.py::Disbursement.test_borrowing_does_not_change_what_you_hold_or_how_the_week_went` |
| **Rendimiento** = lo que tienes ahora − lo que tenías al empezar la semana − lo que te dieron de fuera (`external`). La acumulada, la tienda y la bolsa no cuentan. | `backend/weekly.py:73-78`, `backend/weekly.py:139` | `test_weekly_rewards.py::Leaderboard.test_performance_is_what_you_hold_minus_where_you_started_minus_handouts`, `test_the_accumulated_account_and_what_you_spend_there_do_not_count` |
| Orden de la tabla del círculo: (0) quien no cumplió el mínimo al cierre va al final; 1. mayor rendimiento; 2. más tenencia; 3. cuenta más antigua; 4. id. | `backend/weekly.py:142` | `test_weekly_rewards.py::Leaderboard.test_order_and_tie_breakers_are_fixed`, `test_a_tie_on_performance_goes_to_whoever_holds_more_then_the_older_account` |
| **Activo** en la semana: al menos `REWARD_MIN_MOVES` = 1 apuesta en mercado o ronda de casino con la cuenta semanal (las rondas con la acumulada no cuentan). | `backend/economy.py:75`, `backend/weekly.py:81-83`, `backend/weekly.py:140` | `test_weekly_rewards.py::Rewards.test_a_week_of_doing_nothing_earns_no_place_and_no_reward` |

## 4. Las recompensas, el mínimo semanal y el castigo

### 4.1 Recompensas por posición

| Regla | Dónde | Prueba |
|---|---|---|
| Se pagan a la **acumulada** al cerrar la semana: 1.º $400, 2.º $250, 3.º $150, 4.º $100, 5.º $50; activo debajo del 5.º, `PARTICIPATION_REWARD` = $25. | `backend/economy.py:63-72`, `backend/economy.py:91-97` | `test_weekly_rewards.py::Rewards.test_each_position_earns_its_configured_amount`, `test_rewards_go_to_the_accumulated_account_never_the_weekly_one` |
| Solo los activos que cumplieron el mínimo ocupan lugares; se numeran entre ellos. | `backend/weekly.py:176-185` | `test_weekly_minimum.py::AtTheEndOfTheWeek.test_somebody_who_missed_it_is_out_placed_last_and_paid_nothing_even_with_the_best_week` |
| Círculos chicos: la tabla se multiplica por `min(1, (n−1)/(REWARD_FULL_AT−1))`, con *n* activos (incluye a quien no cumplió el mínimo): 2 → 25 %, 3 → 50 %, 4 → 75 %, 5+ → 100 %. Con menos de `REWARD_MIN_ACTIVE` = 2 activos no se paga nada. Se redondea con `round(…, 2)`. | `backend/economy.py:77-97`, `backend/weekly.py:178` | `test_weekly_rewards.py::Rewards.test_small_circles_are_paid_on_a_sliding_scale_and_a_lone_player_gets_nothing`, `test_weekly_minimum.py::AtTheEndOfTheWeek.test_the_circle_still_pays_on_the_full_scale_when_one_member_is_out` |
| Quien está en varios círculos cobra solo su **mejor** resultado (`REWARD_MAX_PER_USER_PER_WEEK` = 1). Empate de monto: el círculo más antiguo. | `backend/economy.py:82`, `backend/weekly.py:195-202` | `test_weekly_rewards.py::Rewards.test_somebody_in_several_circles_is_paid_for_their_best_finish_only` |
| Pago exactamente una vez: `txid` `reward:<semana>:<círculo>:<persona>` y la marca `paid` en el resumen de la semana; se reintenta en cada arranque y en cada tic. | `backend/weekly.py:248-261`, `backend/weekly.py:694-696`, `server.py:1508-1509` | `test_weekly_rewards.py::ExactlyOnce.*` |
| Un círculo creado después de la semana o con menos de 2 miembros esa semana no tiene cierre. | `backend/weekly.py:570-575` | `test_weekly_rewards.py::Rewards.test_circles_with_one_member_have_no_week_to_settle` |

### 4.2 El mínimo semanal

| Regla | Dónde | Prueba |
|---|---|---|
| Para seguir en la competencia: **≥ 1 apuesta en un mercado** (`WEEKLY_MIN_POLL_BETS`) y **≥ 25 rondas de casino** (`WEEKLY_MIN_CASINO_BETS`) en la semana, con dinero real de la cuenta semanal. Una sesión de póker con dinero real cuenta como una ronda. Ambos en 0 apagan la regla. | `backend/economy.py:106-107`, `backend/weekly.py:101-114`, `backend/poker.py:414-416` | `test_weekly_minimum.py::Counting.test_the_defaults_are_one_poll_and_twenty_five_casino_bets`, `test_both_have_to_be_met_and_the_edge_is_exactly_the_minimum` |
| Vender no suma otra apuesta; la práctica no cuenta; la ronda cuenta cuando termina. | `backend/markets.py:441` (solo al comprar), `backend/games.py:78-83` | `test_weekly_minimum.py::Counting.test_a_real_poll_purchase_counts_and_selling_it_does_not_add_another`, `test_practice_rounds_do_not_count` |
| Cuenta creada durante la semana: exenta esa primera semana. | `backend/weekly.py:109` | `test_weekly_minimum.py::Counting.test_an_account_made_this_week_is_exempt_for_its_first_week` |
| Empieza con la semana siguiente a la primera en que corrió este código (`meta.requirements_from`). | `backend/weekly.py:97-110`, `backend/weekly.py:664-666` | `test_weekly_minimum.py::Counting.test_the_first_tick_starts_it_with_next_week_so_there_is_a_weeks_notice` |
| Al cierre, quien no cumplió **pierde la semana**: va al final, no cobra, recibe el castigo (todos los que no cumplieron) y el premio "Hot Seat" con el texto "Missed the weekly minimum". Si todos cumplieron, decide la peor semana. | `backend/weekly.py:129-160`, `backend/weekly.py:374-377`, `backend/weekly.py:580-584` | `test_weekly_minimum.py::AtTheEndOfTheWeek.*` |
| Mientras corre la semana solo se muestra como progreso: no cambia el orden ni las recompensas estimadas. | `backend/weekly.py:129-131`, `backend/weekly.py:478-489` | `test_weekly_minimum.py::AtTheEndOfTheWeek.test_live_the_minimum_is_only_progress_it_changes_neither_order_nor_rewards` |
| Aviso una vez por semana `WEEKLY_REMIND_H` = 24 h antes del cierre, solo a quien le falta. | `backend/economy.py:108`, `backend/weekly.py:700-725` | `test_weekly_minimum.py::Reminders.*` |

### 4.3 Premios de la semana y castigo (no está en `ECONOMY.md`)

| Regla | Dónde | Prueba |
|---|---|---|
| 20 premios sin dinero (Top Dog, Hot Seat, Rocket Man…), calculados de las estadísticas de la semana. | `backend/weekly.py:12-33`, `backend/weekly.py:343-450` | `test_backend.py::Weekly.test_rollover_punishes_poorest_and_gives_awards` |
| Castigo: cada miembro propone hasta 2 por semana; proponer cuenta como tu voto; gana el más votado, y en empate el más antiguo; sin votos, el primero. Si todo el círculo empató, no hay castigo. | `backend/weekly.py:10`, `backend/weekly.py:275-338`, `backend/weekly.py:154-160` | `test_backend.py::Weekly.test_poll_voting_rules`, `test_everyone_tied_means_no_punishment` |

## 5. El cierre de la semana, en orden

`backend/weekly.py:658-697` (`tick`), cada paso seguro de repetir:

| Paso | Qué hace | Dónde | Prueba |
|---|---|---|---|
| 1 | Foto de lo que tiene cada quien (neto de deuda), tablas finales y castigo | `backend/weekly.py:561-596` | `test_close_order.py::TheWholeClose.test_the_steps_happen_in_the_published_order` |
| 2 | Recompensas a la acumulada | `backend/weekly.py:597` | `test_close_order.py::TheWholeClose.test_the_final_table_and_the_leaderboard_reward_are_what_they_always_were` |
| 3 | Retos terminados y no cobrados se abonan (semanales a la semanal **antes** del reinicio) | `backend/challenges.py:217-250` | `test_challenges.py::ClosingTheWeek.test_a_weekly_account_reward_is_credited_before_the_reset_and_never_lands_in_the_new_weeks_allocation` |
| 4 | Se cobra a cada préstamo lo que haya en la semanal; lo que falte queda vencido | `backend/loans.py:208-231` | `test_loans.py::TheWeeklyClose.test_the_funds_you_have_pay_the_debt_before_the_reset` |
| 5 | XP de semana constante | `backend/progress.py:92-100` | `test_progress.py::WeeklyThings.test_a_steady_week_pays_a_bonus_once_at_the_close` |
| 6 | **Reinicio** de la semanal: modo `reset` (por omisión) la deja en exactamente `WEEKLY_ALLOCATION` = $1,000 (lo que sobra sale como `weekly.expired`, lo que falta entra como `weekly.allocation`, ambos externos); modo `topup` suma $1,000 a lo que quede. Nueva línea de salida = lo que tiene. No toca a quien se registró después del lunes. | `backend/economy.py:41-48`, `backend/weekly.py:600-621` | `test_perks.py::PassGo.*`, `test_weekly_rewards.py::PendingAtTheEndOfAWeek.test_leftover_weekly_cash_above_the_allocation_expires_and_is_written_down_as_such` |
| 7 | Una deuda que sigue toma `LOAN_ALLOC_REPAY_PCT` = 50 % de la nueva asignación | `backend/loans.py:234-254` | `test_loans.py::TheWeeklyClose.test_a_big_debt_takes_its_share_of_each_new_allocation` |
| 8 | Retos de la semana nueva | `backend/challenges.py:65` | `test_challenges.py::ClosingTheWeek.test_the_new_weeks_challenges_are_made_at_the_rollover_exactly_once` |

Apuestas abiertas, rondas en curso y fichas de póker cruzan el cierre sin tocarse; el reinicio solo mueve el efectivo de la
semanal (`backend/weekly.py:611-616`; `test_weekly_rewards.py::PendingAtTheEndOfAWeek.*`).

## 6. Préstamos

| Regla | Dónde | Prueba |
|---|---|---|
| Entran a la **semanal** y se pagan solo desde la semanal. Nunca de la acumulada. | `backend/loans.py:153`, `backend/loans.py:165` | `test_loans.py::Disbursement.test_the_money_lands_in_the_weekly_account_only_and_is_written_down`, `Repayment.test_only_the_weekly_account_is_ever_charged` |
| Uno a la vez. | `backend/loans.py:94-95` | `test_loans.py::Eligibility.test_only_one_loan_at_a_time` |
| Tamaño: máximo `LOAN_MAX_PCT_OF_ALLOCATION` = 50 % de la asignación ($500), mínimo `LOAN_MIN` = $10, y nunca más de lo que falta para que lo que tienes llegue a la asignación. | `backend/economy.py:154-155`, `backend/loans.py:84-88`, `backend/loans.py:105-111` | `test_loans.py::Eligibility.test_a_normal_account_can_borrow_up_to_the_cap`, `test_a_loan_can_only_top_you_back_up_to_the_weekly_allocation` |
| Sin interés; `LOAN_FEE` (0 por omisión) es un cargo fijo que se debe desde el principio. | `backend/economy.py:156`, `backend/loans.py:128-135` | `test_loans.py::Disbursement.test_a_fee_is_a_fixed_disclosed_cost` |
| No en las últimas `LOAN_CUTOFF_H` = 24 h de la semana; no en las primeras `LOAN_MIN_ACCOUNT_AGE_H` = 24 h de la cuenta; máximo `LOAN_MAX_PER_WEEK` = 2 préstamos iniciados por semana. | `backend/economy.py:157-159`, `backend/loans.py:96-104` | `test_loans.py::Eligibility.test_nobody_can_borrow_in_the_last_hours_of_the_week`, `test_a_brand_new_account_cannot_borrow_yet`, `test_at_most_two_loans_started_in_a_week` |
| Montos con máximo dos decimales. | `backend/loans.py:65-72` | `test_loans.py::Eligibility.test_amounts_are_checked` |
| **No es ingreso:** la deuda se resta de lo que tienes, así que pedir prestado no cambia el rendimiento. Los renglones `loan.*` no son externos. Ni pedir ni pagar da XP, retos ni hitos. | `backend/markets.py:559-562`, `backend/loans.py:153` | `test_loans.py::Disbursement.test_borrowing_does_not_change_what_you_hold_or_how_the_week_went`, `NothingToFarm.*` |
| Pago parcial o total (`"all"`); un pago no puede pasar de lo que se debe ni de lo que hay en la semanal. | `backend/loans.py:177-205` | `test_loans.py::Repayment.test_partial_then_full`, `test_you_cannot_repay_more_than_you_owe_or_with_nothing` |
| Al cierre se cobra lo que haya en la semanal (paso 4); lo que quede sigue debiéndose a través de reinicios y reinicios del servidor; luego el 50 % de cada nueva asignación (paso 7). | `backend/loans.py:208-254` | `test_loans.py::TheWeeklyClose.*` |
| Todo es todo o nada (`Txn`) y con `requestId` que repite la respuesta guardada. | `backend/loans.py:138-160`, `backend/loans.py:177-205` | `test_loans.py::Disbursement.test_the_same_request_never_lends_twice_and_a_different_one_is_refused`, `test_a_failure_halfway_leaves_nothing_behind` |
| Interruptor: `LOANS_ENABLED`. | `backend/economy.py:153` | `test_loans.py::Eligibility.test_switching_loans_off_stops_borrowing` |

## 7. Transferencias entre amigos

| Regla | Dónde | Prueba |
|---|---|---|
| Semanal → semanal o acumulada → acumulada, nunca cruzado. Sin decir cuenta, sale de la acumulada. `TRANSFER_ACCOUNTS` apaga una u otra. | `backend/economy.py:177-183`, `backend/transfers.py:195-202` | `test_transfers_accounts.py::ChoosingTheAccount.*` |
| Solo entre amigos mutuos (solicitud aceptada); se vuelve a revisar al mover el dinero. Ni a uno mismo ni a cuentas suspendidas o borradas. | `backend/transfers.py:175-183`, `backend/transfers.py:273-283` | `test_transfers.py::WhoCanReceive.*` |
| Límite diario por remitente: `TRANSFER_DAILY_LIMIT` = $250 desde la acumulada y `TRANSFER_WEEKLY_DAILY_LIMIT` = $500 desde la semanal, por separado, por día de calendario de la zona de la semana. Recibir no devuelve cupo; un rechazo no lo gasta. | `backend/economy.py:184-185`, `backend/transfers.py:205-219`, `backend/transfers.py:293-295` | `test_transfers.py::TheDailyLimit.*`, `test_transfers_accounts.py::WhatChipsCanBeSent.test_daily_limits_belong_to_each_account_separately` |
| Mínimo `TRANSFER_MIN` = $1; dos decimales; nota hasta 80 caracteres; sin comisión. | `backend/economy.py:189-190`, `backend/transfers.py:244-262`, `backend/transfers.py:284-287` | `test_transfers.py::WhatCanBeSent.test_amounts_are_checked_on_the_server`, `test_no_fee_and_the_review_says_so` |
| Solo efectivo. Semanal: lo que se debe de un préstamo no se puede enviar. | `backend/transfers.py:222-225` | `test_transfers_accounts.py::WhatChipsCanBeSent.test_borrowed_money_is_never_passed_on_what_you_owe_stays_with_you` |
| Semanal: al que recibe solo se le puede completar hasta `TRANSFER_WEEKLY_RECEIVER_PCT` = 100 % de la asignación (contando lo que tiene en juego). 0 lo apaga. | `backend/economy.py:188`, `backend/transfers.py:228-234` | `test_transfers_accounts.py::WhoCanReceiveChips.*` |
| Las dos piernas son **externas**: nadie gana ni pierde rendimiento por enviar o recibir. No es progreso. | `backend/transfers.py:339-340` | `test_transfers_accounts.py::WeeklyChipsAndTheLeaderboard.*`, `test_transfers.py::EarnsNothing.*` |
| Contraseña de transferencias aparte, pedida cada vez; 5 errores (`TRANSFER_PW_MAX_FAILS`) bloquean 15 min (`TRANSFER_PW_LOCK_MIN`); el conteo sobrevive reinicios. | `backend/economy.py:191-193`, `backend/transfers.py:73-91` | `test_transfers.py::ThePassword.*` |
| Una transferencia = un cargo y un abono bajo un id, todo o nada, con `requestId` obligatorio. | `backend/transfers.py:318-361` | `test_transfers.py::SafeAndWhole.*` |
| Interruptor: `TRANSFERS_ENABLED`. | `backend/economy.py:177`, `backend/transfers.py:267-268` | `test_transfers.py::WhatCanBeSent.test_it_can_be_switched_off` |

## 8. Rangos y XP

| Regla | Dónde | Prueba |
|---|---|---|
| 16 escalones: Bronce, Plata, Oro, Platino y Diamante (III, II, I) y Maestro. XP: 0, 100, 250 · 450, 700, 1000 · 1400, 1900, 2500 · 3200, 4000, 5000 · 6200, 7600, 9200 · 11000. `RANK_XP_SCALE` los multiplica. | `backend/rules.py:19-42`, `backend/economy.py:171` | `test_progress.py::TheLadder.*` |
| El XP nunca baja; cada premio de XP tiene id y se da una vez. | `backend/progress.py:69-89` | `test_progress.py::Promotions.test_no_demotion_xp_only_goes_up`, `test_the_same_award_twice_gives_xp_once` |
| XP por acción (y tope diario por tipo): mercado 5 (4), ronda de casino 2 (10), operación en bolsa 3 (2), mano de póker 1 (6), proponer mercado 4 (2). Tope total `XP_DAILY_CAP` = 60 al día. `XP_SCALE` los multiplica. | `backend/rules.py:68-75`, `backend/rules.py:87-88`, `backend/activity.py:105-111` | `test_progress.py::WhatEarnsXp.test_each_kind_of_action_is_worth_a_little`, `test_each_kind_stops_paying_after_its_daily_cap`, `test_the_most_a_day_can_pay_is_the_sum_of_the_caps_and_never_more_than_the_ceiling` |
| Un mercado cuenta una vez al día. Apuesta mínima para contar: `QUALIFY_MIN_STAKE` = $1; apostar más no da más XP. | `backend/economy.py:168`, `backend/activity.py:35-36`, `backend/activity.py:47-49` | `test_progress.py::WhatEarnsXp.test_betting_again_in_the_same_poll_the_same_day_is_not_a_second_bet_for_xp`, `test_how_much_you_stake_does_not_change_the_xp`, `test_stakes_below_the_minimum_do_not_count` |
| Semana constante: activo 3 días distintos → 30 XP al cierre. | `backend/rules.py:76-77`, `backend/progress.py:92-100` | `test_progress.py::WeeklyThings.test_a_steady_week_pays_a_bonus_once_at_the_close` |
| Nunca dan XP: práctica, solicitudes rechazadas, préstamos, transferencias, compras en tienda, mirar páginas. | `backend/activity.py:9-10`, `backend/activity.py:33-36` | `test_progress.py::WhatEarnsXp.test_practice_rounds_never_count`, `test_looking_around_and_buying_cosmetics_earn_nothing` |
| Interruptor: `GOALS_ENABLED`. | `backend/economy.py:165`, `backend/activity.py:33` | Sin prueba |

## 9. Retos e hitos

### 9.1 Retos semanales

| Regla | Dónde | Prueba |
|---|---|---|
| Ocho por semana: por cada cuenta, 2 de las familias generales y 2 sobre un juego. Se eligen con un hash de la semana y se congelan al asignarse. | `backend/rules.py:133-134`, `backend/rules.py:183`, `backend/challenges.py:65-100` | `test_challenges.py::Assignment.test_four_for_each_account_two_general_and_two_about_a_particular_game`, `test_it_is_made_once_and_never_changes_even_if_the_settings_do` |
| Familias generales (meta: recompensa · XP): semanal: Game Sampler 3/4/5 juegos: $35/$50/$70 · 20; Many Opinions 2/3/4 mercados: $30/$40/$55 · 20; Regular 3/4/5 días: $40/$55/$70 · 25; Poll Maker 1 mercado propuesto: $35 · 20. Acumulada: Market Watcher 2/3 empresas: $15/$25 · 15; Cross-Training 3/4 partes: $20/$30 · 15; Show Up 4/5/6 días: $20/$30/$40 · 15; Well Read 2/3 categorías: $15/$25 · 15. | `backend/rules.py:99-123` | `test_challenges.py::Assignment.test_every_challenge_carries_what_the_page_needs` |
| Familias de un juego: semanal "Regular" 8/12/16 rondas: $30/$40/$50 y "High Flyer" (multiplicador por juego): $30/$40/$60; acumulada (paga la mitad, `ACCOUNT_FACTOR`) "Winner" 3/5/8 victorias: $15/$20/$30 y "Earner" $20/$35/$50 de ganancia: $15/$20/$30. 15 XP cada uno. | `backend/rules.py:168-184`, `backend/rules.py:154-158` | `test_game_goals.py::AsWeeklyChallenges.*` |
| Una ronda gana para "Earner" como máximo `GAME_WIN_CREDIT_CAP` = $25. Solo cuenta una ronda terminada con dinero real y apuesta ≥ $1; el multiplicador solo en una ronda ganada. Rondas, victorias y ganancias se detienen en el tope diario de rondas de casino (30); el mejor multiplicador no. | `backend/economy.py:174`, `backend/activity.py:66-81` | `test_game_goals.py::Counting.*` |
| `REWARD_SCALE` multiplica el dinero al asignar. | `backend/rules.py:91-92`, `backend/economy.py:169` | `test_challenges.py::Assignment.test_rewards_follow_the_reward_scale_at_assignment` |
| Cobrar: botón explícito; abono **externo** a la cuenta del reto, razón `challenge.weekly` o `challenge.accumulated`, `txid` `chal:<id>:<persona>`, más su XP. Solo durante su semana. | `backend/challenges.py:181-214` | `test_challenges.py::Claiming.*` |
| Al cierre, lo terminado y no cobrado se abona solo (paso 3); lo no terminado expira. | `backend/challenges.py:217-250` | `test_challenges.py::ClosingTheWeek.*` |

### 9.2 Hitos

| Regla | Dónde | Prueba |
|---|---|---|
| 11 hitos generales y 27 de juego (dos por cada uno de los 13 juegos, más póker), con sus metas, dinero y XP. | `backend/rules.py:145-165`, `backend/rules.py:203-255` | `test_milestones.py::TheCatalogue.*`, `test_game_goals.py::TheCatalogue.*` |
| Cada escalón paga **una vez** a la **acumulada** al cobrarlo, externo, razón `milestone`, `txid` `mile:<escalón>:<persona>`, más su XP. Nunca expira. | `backend/milestones.py:72-92` | `test_milestones.py::Claiming.test_the_money_goes_to_the_accumulated_account_with_xp_and_a_ledger_row`, `test_each_tier_pays_exactly_once` |
| Los hitos de rango ("Climber") pagan dinero y 0 XP, para que el rango no se alimente solo. | `backend/rules.py:246-247` | `test_milestones.py::TheCatalogue.test_rank_milestones_pay_money_only_so_ranks_cannot_feed_themselves` |
| Los contadores tienen tope diario propio (`COUNT_CAPS`): mercados 10, rondas 30, bolsa 6, póker 10, propuestas 3, círculos 3. | `backend/rules.py:79`, `backend/activity.py:47` | `test_milestones.py::Progress.test_the_daily_caps_stop_the_counters_too` |

## 10. La tienda (cuenta acumulada)

| Regla | Dónde | Prueba |
|---|---|---|
| 44 productos en 7 tipos; 14 gratis y 30 a la venta de $100 a $750; dos con requisito (3 recompensas semanales; cuenta de 14 días). `STORE_OVERRIDES` cambia precios o disponibilidad. | `backend/catalog.py:18-136` | `test_store.py` (catálogo y compras) |
| Se compra desde la **acumulada**: razón `store.buy`, `txid` `buy:<producto>`; precio y requisito se revisan al momento; no se vende dos veces. | `backend/cosmetics.py:316-354` | `test_store.py` (compras), `test_profile.py::Appearance.test_locked_items_need_to_be_owned_and_the_server_checks_it` |
| Lo cosmético nunca cambia probabilidades, precios ni pagos. | `backend/cosmetics.py` (no lo leen los juegos ni los mercados) | Sin prueba directa |

## 11. La bolsa (cuenta acumulada)

| Regla | Dónde | Prueba |
|---|---|---|
| 10 empresas ficticias; un mercado compartido por el servidor. | `backend/stockengine.py:58-81` | `test_exchange.py::TheCompanies.*` |
| Precio entre $1 y $5,000; paso máximo de 1 % por segundo; banda de 0.45× a 2.2× del valor justo; un movimiento de 8 % en 5 minutos pausa las órdenes 60 s. | `backend/stockengine.py:40-43`, `backend/stockengine.py:270-278` | `test_exchange.py::ThePriceEngine.*` |
| Solo acciones enteras, sin apalancamiento ni ventas en corto; máximo `STOCK_MAX_ORDER_SHARES` = 100,000 por orden. | `backend/exchange.py:66-82`, `backend/exchange.py:170-179` | `test_exchange.py::Trading.test_bad_orders_are_refused_with_a_reason`, `test_you_can_not_spend_more_than_you_have_or_sell_more_than_you_own` |
| Diferencial `STOCK_SPREAD_BPS` = 30 pb en total: compra al *ask* (redondeado hacia arriba), venta al *bid* (hacia abajo), al menos un centavo de diferencia. | `backend/economy.py:114`, `backend/exchange.py:40-48` | `test_exchange.py::Trading.test_buying_and_straight_away_selling_always_loses`, `test_no_sequence_of_trades_at_one_price_ever_makes_money` |
| Cotización de un uso, de una persona, válida `STOCK_QUOTE_TTL_S` = 15 s. Si el precio se movió más de `STOCK_MAX_SLIPPAGE_BPS` = 50 pb no se llena y se da otra; si se movió menos, se llena al precio **actual**. | `backend/economy.py:115-116`, `backend/exchange.py:95-129`, `backend/exchange.py:142-170` | `test_exchange.py::Trading.test_a_quote_expires_and_you_get_a_fresh_one`, `test_if_the_price_moves_too_far_before_you_confirm_nothing_is_filled`, `test_a_small_move_fills_at_the_current_price_in_both_directions_so_waiting_gains_nothing` |
| Cargo o abono a la **acumulada**: razones `stocks.buy` y `stocks.sell`, `txid` `stk:<operación>`. | `backend/exchange.py:184`, `backend/exchange.py:189` | `test_exchange.py::Trading.test_a_buy_is_paid_from_the_accumulated_account_at_the_ask`, `test_a_sell_pays_the_bid_and_records_the_gain_or_loss` |
| No cuenta para la semana ni la toca el reinicio. | `backend/weekly.py:49-54` | `test_exchange.py::Trading.test_the_stock_account_does_not_touch_the_weekly_leaderboard_or_the_weekly_reset` |

## 12. El casino: ventaja de la casa y pago de cada juego

Reglas comunes:

| Regla | Dónde | Prueba |
|---|---|---|
| El servidor reparte y tira con una fuente segura (`secrets`). El navegador nunca decide (D8). | `backend/util.py:63-76` | `test_casino_three.py::HiLoRounds.test_the_random_source_is_the_secure_one`, `test_roulette_odds.py::TheRealRandomSourceIsFair.*` |
| Apuesta mínima `MIN_BET` = $0.10, redondeada a centavos; no más de lo que tiene la cuenta elegida. | `backend/config.py:55`, `backend/games.py:62-68` | `test_new_games.py::War.test_funds_and_minimums` |
| La apuesta se cobra **antes** de jugar (`users.debit`) y el pago se abona al terminar (`users.credit`). Una ronda de varios pasos guarda su apuesta como "en juego" (`escrow`), que cuenta como dinero de quien juega. | `backend/games.py:222-230` | `test_casino_three.py::HiLoRounds.test_the_stake_in_play_counts_as_the_players_money` |
| Una ronda de cada juego a la vez por cuenta. | p. ej. `backend/games.py:415-417` | `test_casino_three.py::HiLoRounds.test_one_round_at_a_time_and_the_stake_is_taken_once` |

### 12.1 Con la cuenta acumulada

| Regla | Dónde | Prueba |
|---|---|---|
| `acct: "accumulated"` juega con la acumulada (una vista sobre la cuenta real: todo pasa por el libro). Sus rondas, historial y estadísticas van aparte (`accGame`): no cuentan para la semana ni para el mínimo, sí para XP, retos e hitos. | `backend/games.py:34-52`, `backend/users.py:205-209`, `backend/users.py:220-224` | `test_casino_accounts.py::*` |

### 12.2 Cada juego

"Retorno" es lo que regresa en promedio de cada peso apostado; la ventaja de la casa es 1 − retorno.

| Juego | Cómo paga | Retorno | Dónde | Prueba |
|---|---|---|---|---|
| **Limbo** | Resultado `max(1.00, ⌊0.99/u⌋)` hasta 1,000,000×. Gana si el resultado ≥ objetivo (1.01× a 1,000,000×); paga apuesta × objetivo. | 99 % | `backend/games.py:9`, `backend/games.py:11`, `backend/games.py:102-124` | `test_backend.py::Games.test_limbo_accounting` |
| **Ruleta** | Europea, 37 casillas. Pleno 36×; rojo, negro, par, impar, bajo y alto 2×; docena y columna 3×; el 0 pierde todo lo de fuera. Hasta 120 fichas por tirada. | 36/37 = 97.30 % | `backend/games.py:13`, `backend/games.py:129-192` | `test_roulette_odds.py::TheMathIsExact.test_every_bet_returns_exactly_36_over_37` |
| **Blackjack** | 6 barajas; el crupier se planta en 17 (también 17 suave); blackjack paga 3:2 (2.5× en total); doblar con las dos primeras cartas (también después de dividir); dividir una vez; ases divididos reciben una carta; el crupier revisa blackjack si muestra 10 o As; sin seguro ni rendición. | No lo calcula el código ni lo mide una prueba | `backend/games.py:197-376` | `test_backend.py::Games.test_blackjack_balance_is_conserved`, `test_blackjack_hand_values` |
| **Chicken** | Fácil 92 %/24 carriles, medio 85 %/20, difícil 75 %/18, extremo 60 %/15; tras *k* carriles paga ⌊0.97/p^k⌋ (a centésimas de multiplicador). | 97 % | `backend/games.py:10`, `backend/games.py:381-395` | `test_backend.py::Games.test_chicken_multipliers_fair` |
| **Coinflip** | Atinarle a 1 a 10 volados seguidos paga ⌊0.99 × 2^n⌋ (1.98×, 3.96×…). | 99 % | `backend/games.py:468-504` | `test_new_games.py::Coinflip.test_return_to_player_is_99_percent_for_every_streak_length` |
| **Dice** | Tirada de 0.00 a 99.99; arriba o abajo de un objetivo, probabilidad de 0.01 % a 98 %; paga ⌊0.99/probabilidad⌋ a diezmilésimas. | 99 % | `backend/games.py:509-539` | `test_new_games.py::Dice.test_return_to_player_is_99_percent_at_every_chance` |
| **War** | Una carta cada quien de 6 barajas, gana la más alta 1:1. Empate: guerra con una apuesta igual; gana si su carta es ≥ y cobra la apuesta original (la del aumento se devuelve); si no le alcanza para el aumento, se rinde y recupera la mitad. Apuesta lateral de empate 12:1 y de empate del mismo color 26:1. | Principal ≈ 97.12 %; empate ≈ 96.14 %; empate de color ≈ 95.50 % (cálculo exacto de E3, no lo mide una prueba) | `backend/games.py:544-603` | `test_new_games.py::War.*`, `Fairness.test_war_main_bet` |
| **Mines** | Tablero de 25, 36, 49 o 64 con 1 a tamaño−1 minas; tras *k* casillas seguras paga ⌊0.99 / P(k seguras)⌋; se cobra solo al pasar de 1,000,000×. | 99 % | `backend/games.py:608-705` | `test_new_games.py::Mines.test_return_to_player_is_99_percent_everywhere` |
| **Moles** | 7 hoyos, 1 a 6 topos; tras *k* aciertos paga ⌊0.96 × (7/topos)^k⌋, máximo 20 aciertos o 1,000,000×. | 96 % | `backend/games.py:710-809` | `test_new_games.py::Moles.test_return_to_player_is_96_percent` |
| **Tower** | 8 filas; riesgo fácil 4 casillas/1 trampa, medio 3/1, difícil 2/1, experto 3/2, maestro 4/3; tras *k* filas paga ⌊0.96 / (seguras/casillas)^k⌋. | 96 % | `backend/games.py:814-908` | `test_new_games.py::Tower.test_return_to_player_is_96_percent` |
| **Hi-Lo** | Adivinar si la siguiente carta (13 valores, independiente) es mayor o igual, o menor o igual; paga ⌊0.96 × 13/ganadoras⌋ y la racha se multiplica; no se ofrece la apuesta que no puede perder; hasta 52 saltos gratis; se cobra sola al llegar a 1,000,000×. Pago en centavos hacia abajo. | ≤ 96 % | `backend/games.py:934-1065` | `test_casino_three.py::HiLoMaths.test_every_guess_that_is_offered_returns_at_most_96_percent_and_the_clean_ones_exactly_96` |
| **Wheel** | 50 segmentos iguales; tablas bajo, medio, alto y arriesgado (24× máximo). Pago en centavos hacia abajo. | 96 % exacto | `backend/games.py:1073-1113` | `test_casino_three.py::WheelMaths.test_every_risk_level_returns_exactly_96_percent` |
| **Piedra, papel o tijera** | El empate se repite gratis; la escalera paga 0.98 × 2^n (1.96×, 3.92×…) hasta 10 victorias. Pago en centavos hacia abajo. | 98 % | `backend/games.py:1122-1203` | `test_casino_three.py::RpsMaths.test_every_rung_returns_98_percent_when_each_round_is_a_fair_coin` |

**Redondeo del pago.** Hi-Lo, Wheel y Piedra, papel o tijera pagan en centavos hacia abajo. Los demás juegos
redondean el pago con `round2` (a la mitad hacia arriba). Ver la diferencia **D1**.

## 13. Mercados (LMSR)

| Regla | Dónde | Prueba |
|---|---|---|
| Cada mercado tiene de 2 a 12 resultados (Sí/No por omisión) y un creador de mercado LMSR con profundidad fija `b` = 250 (`MARKET_LIQUIDITY`), que nadie elige. | `backend/config.py:57-60`, `backend/markets.py:96-104`, `backend/markets.py:121` | `test_amm.py::SizeVersusLiquidity.test_the_one_standard_depth_behaves_as_advertised` |
| Precio de cada resultado = `exp(q_i/b) / Σ exp(q_j/b)`; los precios suman 100 %; los porcentajes mostrados, enteros que suman exactamente 100. | `backend/lmsr.py:33-36`, `backend/lmsr.py:98-107` | `test_amm.py::Direction.test_probabilities_always_total_exactly_100_percent_for_any_number_of_outcomes` |
| Comprar: el costo es `C(q') − C(q)`, con `C(q) = b · ln Σ exp(q_j/b)`. Nunca se entregan más acciones de las que paga la apuesta. Mínimo `MIN_BET` = $0.10. | `backend/lmsr.py:57-71`, `backend/lmsr.py:89-90`, `backend/markets.py:316-330` | `test_amm.py::Accounting.test_a_buy_costs_exactly_what_the_cost_function_says` |
| Vender: paga la diferencia de `C`, **redondeada hacia abajo** al centavo; no se vende algo que valga menos de un centavo. | `backend/lmsr.py:93-95`, `backend/markets.py:331-350` | `test_amm.py::Accounting.test_selling_pays_the_cost_function_difference_rounded_down_to_the_cent`, `Refusals.test_a_sliver_worth_less_than_a_cent_cannot_be_sold` |
| Comprar y vender de inmediato nunca deja ganancia. | `backend/lmsr.py:6-8` | `test_amm.py::NoFreeMoney.*` |
| Un `requestId` repetido no opera dos veces; `minShares`/`minAmount` rechazan con 409 si el precio empeoró. | `backend/markets.py:383-412`, `backend/markets.py:420-473` | `test_amm.py::Safeguards.*` |
| Se opera hasta la fecha de cierre; después, solo se espera el resultado. | `backend/markets.py:50-55`, `backend/markets.py:286-292` | `test_amm.py::Lifecycle.*` |
| Liquida el creador (o el dueño del círculo, si es de un círculo): cada acción ganadora paga $1, las perdedoras nada. El pago se redondea con `round2`. | `backend/markets.py:478-517`, `backend/markets.py:500` | `test_amm.py::Settlement.test_winning_shares_pay_one_dollar_each_and_losers_nothing` |
| Cancelar devuelve lo invertido que sigue en la posición. | `backend/markets.py:520-529` | `test_amm.py::Settlement.test_calling_it_off_refunds_what_is_still_invested` |
| Una persona puede tener a lo más 20 mercados públicos abiertos. | `backend/markets.py:14`, `backend/markets.py:83-88` | `test_market_features.py::SiteWideBets.test_cap_on_open_public_bets` |
| El pago o la devolución va a la **semanal** de la semana en que se liquida. | `backend/markets.py:505`, `backend/markets.py:527` | `test_weekly_rewards.py::PendingAtTheEndOfAWeek.test_a_bet_that_settles_next_week_pays_into_that_weeks_weekly_account_and_counts_there` |

### 13.6 Editar un mercado publicado

| Regla | Dónde | Prueba |
|---|---|---|
| Edita quien lo propuso o el dueño del círculo, mientras no esté liquidado ni cancelado; solo la fecha de cierre y las reglas. | `backend/markets.py:634-700` | `test_poll_edit.py::WhoMayEdit.*`, `WhenItIsAllowed.*` |
| Sin apuestas de otros: cualquier cambio. Con apuestas: razón de al menos 10 caracteres; cambiar la fecha siempre es **material**, y también todo cambio de reglas que no se declare aclaración. | `backend/markets.py:630`, `backend/markets.py:715-724` | `test_poll_edit.py::WhenPeopleHaveBet.*` |
| Un cambio material abre una ventana de salida de `EDIT_EXIT_WINDOW_H` = 48 h: quien apostó antes puede retirarse con **exactamente lo que pagó** (razón `market.withdraw`), salvo quien hizo el cambio. Solo un cambio material por mercado. | `backend/economy.py:139`, `backend/markets.py:725-738`, `backend/markets.py:778-786`, `backend/markets.py:811-857` | `test_poll_edit.py::WhenPeopleHaveBet.test_a_holder_can_walk_away_at_exactly_what_they_paid`, `test_only_one_material_change_once_people_have_bet` |
| Adelantar el cierre: no a menos de 24 h ni antes de que termine la ventana; cualquier fecha nueva, al menos 5 minutos adelante. | `backend/markets.py:631`, `backend/markets.py:690-691`, `backend/markets.py:729-735`, `backend/economy.py:138` | `test_poll_edit.py::WhenPeopleHaveBet.test_people_need_a_day_to_react_if_the_date_is_brought_forward` |

## 14. Póker (no está en `ECONOMY.md`)

| Regla | Dónde | Prueba |
|---|---|---|
| Mesas de 2 a 9 lugares; una mesa por persona; máximo 2 mesas por anfitrión y 60 en total. | `backend/poker.py:22-24` | `test_poker_tables.py::OpeningAndJoining.test_one_table_at_a_time_and_a_cap_on_hosting` |
| Fichas de juego: ciega grande de 2 a 1,000,000 fichas; pila de 10 a 1,000 ciegas grandes; no tocan ninguna cuenta. | `backend/poker.py:33`, `backend/poker.py:284-292` | `test_poker_tables.py::SettingsAndVotes.test_fake_money_limits` |
| **Dinero real** (de la semanal): ciega grande de $0.10 a $100, chica desde $0.05; entrada de 20 a 200 ciegas grandes y máximo $10,000; por omisión $0.50/$1 y $100 de entrada, sin recompras (el anfitrión puede activarlas: cada una cuesta otra entrada); reloj de turno de 2 minutos como máximo. | `backend/poker.py:34`, `backend/poker.py:234-239`, `backend/poker.py:293-301`, `backend/poker.py:587-603` | `test_poker_tables.py::SettingsAndVotes.test_real_money_limits`, `RealMoney.test_a_rebuy_costs_another_buy_in` |
| La entrada se cobra de la semanal al sentarse o empezar; la pila vuelve a la semanal al levantarse, al terminar el juego o al cerrarse la mesa. Nadie paga si alguien no alcanza. | `backend/poker.py:393-424`, `backend/poker.py:520-551` | `test_poker_tables.py::RealMoney.test_starting_takes_the_buy_in_from_cash_and_puts_it_in_front_of_you`, `test_nobody_is_charged_if_somebody_cannot_afford_it`, `test_ending_the_game_pays_everybody_back_and_writes_history` |
| **Sin comisión de la casa:** todo el bote va a los ganadores. Botes laterales por nivel de aportación; lo de quien se retiró se queda en el bote; la ficha impar va al primer lugar a la izquierda del botón. | `backend/poker.py:861-931` | `test_poker.py::SidePots.*`, `Betting.test_odd_chip_goes_to_the_first_seat_left_of_the_button`, `Conservation.test_real_money_dollars_are_conserved_too` |
| Las ciegas pueden duplicarse cada 5, 10, 15 o 20 manos; 3 turnos vencidos seguidos te levantan; quien se queda sin fichas tiene 2 minutos para recomprar. | `backend/poker.py:28-37`, `backend/poker.py:647-649`, `backend/poker.py:933-951` | `test_poker.py::Clocks.*`, `Rebuys.*` |
| Lo que hay en una mesa con dinero real cuenta como tuyo para la semana. Una sesión cuenta como una ronda de casino para el mínimo; cada mano dada da XP de póker. | `backend/poker.py:216-231`, `backend/poker.py:414-416`, `backend/poker.py:673` | `test_poker_tables.py::RealMoney.test_the_weekly_standings_see_money_at_the_table` |

## 15. Los números que se pueden cambiar

Todos los de `backend/economy.py` (variables de entorno con el mismo nombre; la tabla está en `ECONOMY.md` §15) y estos
que viven en otros archivos:

| Número | Valor | Dónde | ¿Se cambia por entorno? |
|---|---|---|---|
| `START_BALANCE` | $1,000 | `backend/config.py:26-37` | Sí |
| `VOUCHER_AMOUNT`, `VOUCHER_BELOW` | $250, $0.50 | `backend/config.py:52-53` | No |
| `MIN_BET` | $0.10 | `backend/config.py:55` | No |
| `MARKET_LIQUIDITY` (`b`) | 250 | `backend/config.py:60` | No |
| `MAX_DEPOSIT`, `MAX_BALANCE` | 1e15, 1e18 | `backend/config.py:61-62` | No |
| `DEMO_START` | $1,000 | `backend/games.py:21` | No |
| Retorno y tablas de cada juego | §12 | `backend/games.py` | No |
| Límites de póker | §14 | `backend/poker.py:22-37` | No |
| XP, retos e hitos | §8, §9 | `backend/rules.py` | Solo `XP_SCALE`, `RANK_XP_SCALE`, `REWARD_SCALE` |
| Mercados públicos abiertos por persona | 20 | `backend/markets.py:14` | No |

## 16. El ranking global (no está en `ECONOMY.md`)

| Regla | Dónde | Prueba |
|---|---|---|
| Todos los registrados (sin suspendidos ni borrados), por el efectivo de su **acumulada**; mismo monto, mismo lugar ("1, 2, 2, 4"); empate, la cuenta más antigua primero. | `backend/ranking.py:10-24` | `test_ranking.py::Board.*` |


## Dónde se mueve el dinero

Cada lugar del código que cambia un saldo. Es lo que E2 convierte en funciones SQL en la ronda 2. Hoy el libro guarda
solo la pierna de la persona; la **contrapartida** es la cuenta del sistema que haría de otra pierna en un libro de doble
partida. Se proponen estas, para que E2 decida sus nombres:

| Contrapartida | Qué es |
|---|---|
| `emision` | Dinero que nace fuera del juego: bienvenida, asignación semanal, bonos, cupón, fondos del anfitrión, recompensas de semana, retos e hitos, devoluciones de una migración |
| `caducidad` | Lo que el reinicio semanal quita de la semanal (`weekly.expired`) |
| `casa` | El casino: recibe las apuestas y paga los premios de los 13 juegos |
| `mercado:<id>` | El creador de mercado LMSR de cada mercado: recibe compras y paga ventas, liquidaciones y devoluciones |
| `mesa:<id>` | Una mesa de póker con dinero real: tiene las pilas mientras la gente está sentada |
| `prestamos` | El que presta: entrega el préstamo y recibe los pagos |
| `tienda` | Recibe lo que se gasta en la tienda |
| `bolsa` | La bolsa simulada: recibe compras de acciones y paga ventas |
| la otra persona | En una transferencia, la misma cuenta de la otra persona |

### Llamadas directas a `ledger.*`

La columna **Función** es `módulo.función`; la prueba `tests/test_dinero_solo_en_libro.py` revisa que cada función del
código que llama a `ledger.post` o `ledger.opening` esté en esta tabla.

| Función | Línea | Razón | Cuenta de la persona | Contrapartida | `txid` | Externo |
|---|---|---|---|---|---|---|
| `users.register` | `backend/users.py:59` | `welcome` | + semanal | `emision` | — | sí |
| `users.credit` | `backend/users.py:207`, `:210` | la de quien llama (abajo) | + semanal, o + acumulada si la cartera es la acumulada (`isAcc`) | la de quien llama | la de quien llama | la de quien llama |
| `users.debit` | `backend/users.py:222`, `:225` | la de quien llama (abajo) | − semanal, o − acumulada (`isAcc`) | la de quien llama | la de quien llama | no |
| `users.apply_deposit` | `backend/users.py:253` | `deposit` | + semanal o + acumulada (la elegida) | `emision` | `fundvote-<voto>` si viene de una votación | sí |
| `weekly.pay_rewards` | `backend/weekly.py:257` | `weekly.reward` | + acumulada | `emision` | `reward:<semana>:<círculo>:<persona>` | no (es la acumulada) |
| `weekly.refill_weekly` | `backend/weekly.py:614` | `weekly.allocation` | + semanal (lo que falta para la asignación, o la asignación entera en modo `topup`) | `emision` | — (lo protege la marca `user.wk.week`) | sí |
| `weekly.refill_weekly` | `backend/weekly.py:616` | `weekly.expired` | − semanal (lo que sobra de la asignación) | `caducidad` | — (igual) | sí |
| `weekly.pay_midweek` | `backend/weekly.py:649` | `weekly.midweek` | + semanal | `emision` | `midweek-<semana>` | sí |
| `challenges._pay` | `backend/challenges.py:189` | `challenge.weekly` o `challenge.accumulated` | + la cuenta del reto | `emision` | `chal:<reto>:<persona>` | sí |
| `milestones.claim` | `backend/milestones.py:88` | `milestone` | + acumulada | `emision` | `mile:<escalón>:<persona>` | sí |
| `loans.borrow` | `backend/loans.py:153` | `loan.borrow` | + semanal | `prestamos` | `loan:<préstamo>:out` | no |
| `loans._apply_payment` | `backend/loans.py:165` | `loan.repay` (pago de la persona) o `loan.collect` (al cierre y de la asignación) | − semanal | `prestamos` | `loan:<p>:pay:<requestId>`, `loan:<p>:close:<semana>`, `loan:<p>:alloc:<semana>` | no |
| `transfers.send` | `backend/transfers.py:339` | `transfer.out` | − la cuenta elegida | la misma cuenta de la otra persona | `xfer:<transferencia>:out` | sí |
| `transfers.send` | `backend/transfers.py:340` | `transfer.in` | + la misma cuenta, de quien recibe | la misma cuenta de quien envía | `xfer:<transferencia>:in` | sí |
| `cosmetics.buy` | `backend/cosmetics.py:343` | `store.buy` | − acumulada | `tienda` | `buy:<producto>` | no |
| `exchange.trade` | `backend/exchange.py:184` | `stocks.buy` | − acumulada | `bolsa` | `stk:<operación>` | no |
| `exchange.trade` | `backend/exchange.py:189` | `stocks.sell` | + acumulada | `bolsa` | `stk:<operación>` | no |
| `migrations.split_accounts` (E2) | `backend/migrations.py:38-39` | `opening` | ninguna: deja constancia del saldo que ya había | — | — | sí |
| `migrations.retire_horses` (E2) | `backend/migrations.py:70` | `casino.horses` | + semanal (devuelve la apuesta) | `casa` | `horse:retired:<carrera>:<clave>` | no |

### A través de `users.credit` y `users.debit`

| Función | Línea | Razón | Cuenta de la persona | Contrapartida |
|---|---|---|---|---|
| `users.redeem_voucher` | `backend/users.py:298` | `voucher` (externo) | + semanal | `emision` |
| `markets.trade` (compra) | `backend/markets.py:436` | `market.buy` | − semanal | `mercado:<id>` |
| `markets.trade` (venta) | `backend/markets.py:448` | `market.sell` | + semanal | `mercado:<id>` |
| `markets.resolve` | `backend/markets.py:505` | `market.payout` | + semanal | `mercado:<id>` |
| `markets.cancel` | `backend/markets.py:527` | `market.refund` | + semanal | `mercado:<id>` |
| `markets.withdraw` | `backend/markets.py:836` | `market.withdraw` | + semanal | `mercado:<id>` |
| `poker._buy_in` | `backend/poker.py:397` | la de la ruta: `poker` (ver D4) | − semanal | `mesa:<id>` |
| `poker._cash_out` | `backend/poker.py:411` | la de la ruta: `poker`, u `other` desde el reloj (D4) | + semanal | `mesa:<id>` |
| Casino: apuesta | `backend/games.py:114` (`limbo`), `:176` (`roulette`), `:310` (`blackjack_deal`), `:349` y `:360` (`blackjack_action`: doblar y dividir), `:422` (`chicken_start`), `:490` (`coinflip`), `:530` (`dice`), `:572` y `:587` (`war`: apuesta y aumento), `:658` (`mines_start`), `:765` (`moles_start`), `:861` (`tower_start`), `:996` (`hilo_start`), `:1102` (`wheel`), `:1156` (`rps_start`) | `casino.<juego>`, de la ruta | − semanal, o − acumulada con `acct: "accumulated"` | `casa` |
| Casino: premio | `backend/games.py:120` (`limbo`), `:186` (`roulette`), `:287` (`_bj_finish`), `:430` (`_chicken_cash`), `:500` (`coinflip`), `:535` (`dice`), `:597` (`war`), `:669` (`_mines_cash`), `:774` (`_moles_cash`), `:873` (`_tower_cash`), `:1008` (`_hilo_cash`), `:1108` (`wheel`), `:1165` (`_rps_cash`) | `casino.<juego>`, de la ruta | + la misma cuenta de la apuesta | `casa` |

Con la cartera de práctica, las mismas funciones del casino cambian `user["demo"]["balance"]` y no tocan el libro: no es
dinero (`backend/users.py:202-204`, `:215-219`).

### Escrituras directas a un saldo que no pasan por el libro

| Dónde | Qué es | ¿Mueve dinero? |
|---|---|---|
| `backend/users.py:203`, `:218` | La cartera de práctica (demo) | No: no es una cuenta |
| `backend/users.py:208`, `:223` | Copia el saldo de la acumulada en la vista de la cartera del casino, después de `ledger.post` | No: es un espejo |
| `backend/games.py:27`, `:58` (`demo_account`, `demo_reset`) | Pone la cartera de práctica en $1,000 | No |
| `backend/migrations.py:35-36` (E2) | Reparte el saldo único entre las dos cuentas, con su renglón `opening` | Sí, una sola vez y documentado |
| `backend/migrations.py:68` (E2) | Devuelve a la cartera de práctica una apuesta de Horses | No |
| `backend/seed.py:24` | Reinicio de temporada | **Sí, fuera del libro (D3)** |

---

## Diferencias

Lo que `ECONOMY.md` (o el propio código, en sus comentarios) dice y el código no hace, o al revés. **Ninguna está corregida
todavía.** "Código" quiere decir que el error es del código y se corrige con una prueba vista en rojo (entregable 5);
"Documento", que el código está bien y se corrige el texto; "Pregunta", que necesita la firma del dueño.

| # | Dónde | Qué dice | Qué hace el código | Tipo |
|---|---|---|---|---|
| D1 | `backend/games.py:118`, `:498`, `:533`, `:429`, `:668` (y `:271`, `:277`, `:581`, `:585`, `:592-594`, `:773`, `:872`) | Cada juego declara su retorno (Dice 99 %, Limbo 99 %, Chicken 97 %, Mines 99 %…) y `lmsr.py:7-8` dice que todo redondeo va contra el jugador | Limbo, Dice, Chicken y Mines redondean el pago a la mitad hacia arriba (`round2`). Con apuestas chicas, varias combinaciones devuelven **más del 100 %**: Dice con 94.28 % de probabilidad y apuesta de $0.10 devuelve 103.7 %; Limbo a 1.05× con $0.10, 103.7 %; Mines 49 casillas/1 mina/3 aciertos con $0.10, 103.3 %; Chicken fácil un carril con $0.10, 101.2 %. Es una ganancia segura para quien la repite. Blackjack (2.5×), War (mitad al rendirse) y los demás también redondean hacia arriba, aunque sin pasar del 100 % | Código |
| D2 | `backend/markets.py:500` | `markets.py:304-305` y `lmsr.py:7-8`: "every dollar amount paid OUT is rounded down to a whole cent" | Al liquidar, cada posición ganadora cobra `round2(acciones)`, a la mitad hacia arriba: 10.005 acciones cobran $10.01 | Código |
| D3 | `backend/seed.py:24-26` | D2 de `DECISIONES.md`: el dinero solo se mueve por el libro | El reinicio de temporada (`new_season`, que corre con `SEASON_RESET` o `scripts/seed.py`) asigna `user["balance"]` directamente: no deja renglón y la auditoría del libro deja de cuadrar | Código |
| D4 | `backend/poker.py:397`, `:411` | La razón de un renglón de póker es `poker` (`server.py:124`) | La entrada y el cobro no dan razón: la toman de la ruta. Cuando un asiento se libera desde el reloj (turnos vencidos, mesa inactiva, sin recompra), el renglón queda con la razón `other` | Código |
| D5 | `backend/seed.py:20-28` | — | El reinicio de temporada no toca la cuenta acumulada, los préstamos, los retos, el XP ni las posiciones en la bolsa, y reinicia la semanal a `START_BALANCE`, no a la asignación. ¿Es lo que se quiere de una temporada nueva? | Pregunta |
| D6 | `ECONOMY.md` líneas 4-6 | "Every number lives in `economy.py` (plus `catalog.py`)… Nothing else in the code has these figures" | Hay números en `config.py` (`START_BALANCE`, cupón, `MIN_BET`, `b`, topes), `games.py` (retornos y tablas), `poker.py`, `rules.py`, `markets.py` (§15 de este contrato) | Documento |
| D7 | `ECONOMY.md` §1, tabla y línea 22 | La acumulada solo recibe recompensas, transferencias y abonos del anfitrión; la semanal recibe ganancias, asignación, abonos, préstamos y retos | Falta: la semanal recibe la bienvenida, el cupón, el bono del miércoles y transferencias semanales; la acumulada recibe ventas en la bolsa y ganancias del casino jugado con ella (§13c) | Documento |
| D8 | `ECONOMY.md` (todo) | — | No documenta: bienvenida (§2.1), cupón (§2.2), cartera de práctica, retorno y pago de cada juego (§12), mercados y LMSR (§13), póker (§14), premios y castigo (§4.3), ranking global (§16) | Documento |
| D9 | `ECONOMY.md` §8, tabla de XP | Cobrar un reto da "10 to 25" XP y un hito "10 to 120" | Retos: 15 a 25 (`rules.py:99-123`, `:174-182`). Hitos: 0 a 120 (los de rango dan 0, los de juego empiezan en 5: `rules.py:162-166`, `:247`) | Documento |
| D10 | `ECONOMY.md` §10, metas de un juego | *Game* Regular: 25/100/500 solo para Blackjack y Ruleta | También War (sus rondas se llaman "hands") y Wheel ("spins") usan 25/100/500 (`rules.py:146-149`, `:162`) | Documento |
| D11 | `ECONOMY.md` §10 | "The same daily caps as XP apply to the counters (30 casino rounds, 10 poll bets, 6 trades a day...)" | Los números son los de `COUNT_CAPS` (`rules.py:79`), que no son los topes de XP (10, 4, 2) | Documento |
| D12 | `backend/challenges.py:1`, `:6`, `:154`; `backend/rules.py:96` | "three for the weekly account and three for the accumulated account", "the same six" | Son cuatro y cuatro, ocho (`rules.py:134`, `:183`), como dice bien `ECONOMY.md` §9 | Documento (comentarios del código) |
| D13 | `backend/config.py:40-51`, `:73-76` | `WEEKLY_BONUS` y `RANK_BY` se leen como ajustes | Nadie los usa: la asignación la lee `economy.py:41` y el orden de la semana no depende de `RANK_BY`. Son ajustes muertos (`config.py` es de E1) | Documento (código muerto) |
| D14 | `ECONOMY.md` §15 | La tabla de ajustes | Faltan `START_BALANCE` y `SEASON_RESET` | Documento |
