# ADR-003 — El dinero solo se mueve dentro de Postgres

- **Estado:** Aceptado
- **Fecha:** 2026-10-09

## Contexto

La economía es el corazón de Clique: dos cuentas por persona, apuestas, pagos, préstamos, transferencias y premios. En `legacy/clique` la integridad depende de un candado global de Python, de `txn.py` (todo o nada) y de `idem.py` (reintentos). En la versión nueva habrá varias copias del servidor y clientes en celulares con conexiones inestables.

Además, vender fichas que se pueden apostar convertiría a Clique en un juego con apuesta bajo la Ley Federal de Juegos y Sorteos y rompería las reglas de Apple (la moneda comprada no puede caducar, y Clique reinicia la cuenta semanal cada lunes).

## Decisión

1. Todo movimiento de dinero es una llamada a una función SQL (`post_transaction` y las que se construyan encima) que corre en una sola transacción, escribe renglones de doble partida que suman cero y respeta una clave de idempotencia única.
2. Los montos se guardan en centavos enteros (`bigint`).
3. Ninguna tabla de saldos ni del libro es escribible desde el cliente; RLS lo impide.
4. Los resultados de juegos y mercados se calculan en el servidor (Edge Functions o servidor de juego) con el motor compartido, y luego se paga con la función SQL.
5. Nunca se dan premios con valor real ni se cambian fichas por dinero. Se cobra por cosméticos, pase de temporada y suscripción, y por paquetes de fichas en las condiciones de ADR-004.

## Consecuencias

- Una apuesta repetida por mala conexión no cobra dos veces.
- Un error a la mitad no deja dinero creado ni perdido.
- Cualquier PR que mueva saldos fuera de estas funciones se rechaza en revisión.
- La venta de fichas se rige por ADR-004.
