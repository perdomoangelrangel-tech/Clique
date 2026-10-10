# Glosario

*Qué quiere decir cada palabra del proyecto. Si una orden usa una palabra de otra forma, manda este archivo.*

## El producto

| Palabra | Qué es | En el código |
|---|---|---|
| **Círculo** | El grupo de amigos que compite entre sí durante la semana | `circles`, `backend/circles.py` |
| **Mercado** | Una pregunta sobre la vida del grupo ("¿Ana llega tarde el viernes?") en la que se compran Sí o No | `markets`, `backend/markets.py` (en la interfaz original, "poll") |
| **LMSR** | El creador de mercado que fija el precio de Sí y No según lo comprado | `backend/lmsr.py` |
| **Fichas** | La moneda ficticia de Clique. Nunca es dinero real | saldo en centavos enteros |
| **Cuenta semanal** | Las fichas de la semana; con ellas se compite y se reinicia cada lunes | `weekly` |
| **Cuenta acumulada** | Lo ganado que se conserva entre semanas (tienda, bolsa, premios) | `accumulated` |
| **Cuenta de fichas compradas** | Las de los paquetes de hasta US$5 (D3). Aparte, fuera del ranking. Apagada | `chips` (futura) |
| **Libro** | El registro de doble partida de cada movimiento de fichas | `backend/ledger.py`; en Postgres, las funciones de E2 |
| **Cierre semanal** | El lunes a las 00:00 (hora de México): se paga, se ordena, se castiga y se reinicia | `backend/weekly.py`, `ECONOMY.md` §12 |
| **Ranking** | El orden del círculo en la semana | `backend/ranking.py` |
| **Castigo** | Lo que el grupo vota para quien quedó último | `punishment` |
| **Originals** | Los 13 juegos de casino propios (ruleta, blackjack, chicken…) | `backend/games.py`, `static/js/games/` |
| **Póker** | Mesas en vivo entre miembros del círculo | `backend/poker.py` |
| **Bolsa** | Empresas ficticias cuyas acciones se compran con la cuenta acumulada | `backend/exchange.py`, `stockengine.py` |
| **Boleto** | La tarjeta de papel con la que la interfaz muestra una apuesta o un resultado | estética (D4) |
| **Sala, mesa, papel, fieltro, latón** | Los materiales de la estética del club privado de cartas | tokens de E4, contrato de arte de E6 |

## El equipo

| Palabra | Qué es |
|---|---|
| **Encargo** | El trabajo fijo de un agente (E1 a E7). Uno por conversación |
| **Orden** | Lo que un encargo tiene que entregar en la ronda: `equipo/ORDENES_E<n>.md` |
| **Ronda** | Un conjunto de órdenes que corre en paralelo. Ronda 0: la preparación; ronda 1: la primera de la app |
| **Entregable** | Una fila de la tabla de una orden. Un entregable, un commit, una línea en la bitácora |
| **Rama** | La rama fija de cada encargo (`e2-datos`). Nadie trabaja en `main` |
| **Árbol** | La carpeta `_ramas/<rama>` donde está esa rama (`git worktree`) |
| **Integración** | La rama `integracion`, donde E7 junta lo de todos y viven las órdenes |
| **Cimiento** | Una etiqueta `cimiento-N` sobre `integracion`: un punto en verde del que todos salen |
| **Etapa A, B, C** | Los tres pasos para llevar la base a Postgres (ADR-006) |
| **Ventana de migración** | El rato en que E0 escribe en Supabase y nadie más lee como si fuera verdad |
| **Arnés** | Una prueba automática que decide si algo está bien. Se ve en rojo antes de confiar en ella |
| **Mutante** | Un error metido a propósito para comprobar que el arnés lo caza |
| **Rojo conocido** | Una prueba que falla por una razón anotada y tiene dueño (`ROJOS_CONOCIDOS.json`) |
