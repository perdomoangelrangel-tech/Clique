# ADR-004 — Paquetes de fichas de hasta US$5, separados del juego semanal

- **Estado:** Aceptado por el dueño el 2026-10-10. La compra real queda **apagada** hasta tener dictamen legal y revisión de las tiendas.
- **Fecha:** 2026-10-10

## Contexto

El dueño quiere, además de cosméticos, pase de temporada y suscripción, vender paquetes de fichas: máximo US$5 cada uno y con muchísimas fichas.

El precio bajo no elimina el riesgo legal. Lo que convierte una ficha en "apuesta" es que se pueda comprar con dinero, no cuánto cuesta. El Reglamento de la Ley Federal de Juegos y Sorteos define la apuesta como un monto "susceptible de apreciarse en moneda nacional", y en EE. UU. el caso Big Fish Casino terminó en acuerdos por US$155 millones por vender fichas de casino social. Además, Apple exige que la moneda comprada dentro de la app no caduque, y la cuenta semanal de Clique se reinicia cada lunes.

También hay un problema de juego: si las fichas compradas sirvieran en la competencia semanal, el castigo del último lugar se podría evitar pagando.

## Decisión

1. **Una cuenta aparte.** Las fichas compradas van a una tercera cuenta por persona, `chips`, separada de `weekly` y `accumulated`, en el mismo libro contable (ADR-003).
2. **Fuera de la competencia.** Las fichas de `chips` nunca cuentan para el ranking semanal, el mínimo semanal, los premios semanales ni el castigo. Se usan en el casino (con un selector de cuenta, como hoy existe para la cuenta acumulada) y en la tienda de cosméticos.
3. **Sin salida.** No se transfieren a otras personas, no se cambian por dinero ni por nada con valor real, y no hay premios físicos.
4. **No caducan.** El reinicio semanal no toca la cuenta `chips`.
5. **Paquetes:** precio máximo US$5 (o su equivalente en pesos) por paquete. El catálogo, las cantidades y los precios viven en una tabla configurable, no en el código.
6. **Límites de cuidado:** solo mayores de 18 verificados, un tope de gasto mensual configurable (propuesta inicial: US$20 al mes por persona) y un historial de compras visible para la persona.
7. **Interruptor:** `PURCHASES_ENABLED=false` por defecto. Se construye y se prueba con pagos de prueba; se enciende solo con dictamen de un abogado mexicano de juegos y sorteos y con las reglas de cada tienda revisadas.
8. **Cobro:** Stripe en la web (tarjeta y OXXO). En las apps de iOS y Android, la compra de bienes digitales se hace con el sistema de pago de cada tienda.
9. **Cada compra es una transacción del libro** con su clave de idempotencia, ligada al evento de pago confirmado (webhook). Nunca se acreditan fichas por un pago que no está confirmado.

## Consecuencias

- La economía semanal sigue siendo justa: nadie compra su salida del castigo.
- Si el dictamen dice que no, se apaga el interruptor y el resto del negocio (cosméticos, pase, suscripción) no cambia.
- Cambia el contrato de esquema: `accounts.kind` admite `chips` (OT-004 lo prevé).
- La pantalla de compra debe decir claramente que las fichas no tienen valor real y no se pueden cambiar por dinero.

## Alternativas descartadas

- Fichas compradas en la cuenta semanal: rompe la competencia y el castigo, y choca con Apple por caducar cada lunes.
- Fichas compradas en la cuenta acumulada: se podrían transferir a amigos (hoy la acumulada se transfiere), lo que crea un mercado entre personas y las acerca a "algo con valor".
