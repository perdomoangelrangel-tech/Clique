# Bitácora del equipo

*Cada rama solo agrega al final. Al fusionar, git junta las líneas de todas (`merge=union`).*
*Formato de cada línea:* `[E<n>] <dd-mmm> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
*Avisos del dueño o del cerebro:* `[E0] …` o `[DUEÑO] …`

---

## Peticiones

*Cuando un encargo necesita un archivo ajeno, lo pide aquí con una fila. El dueño del archivo responde con una línea en el registro (`[E<n>] … · HECHO: petición de E<m> del <fecha> atendida en <commit>`). **La fila no se edita**: con `merge=union`, una fila cambiada en dos ramas queda dos veces.*

| Fecha | De | Para | Qué necesita (archivo, línea y por qué) |
|---|---|---|---|
| 10-oct | E2 | E1 | `requirements-dev.txt`: agregar `psycopg[binary]` y `pgserver`. Son solo para las pruebas de Postgres local (`tests/test_esquema_pg.py`, `tests/test_libro_pg.py`, `tests/test_importador.py`); sin ellas esas pruebas se omiten con aviso. Que el CI las instale para que no se omitan ahí. |
| 10-oct | E2 | E3 | `backend/util.py` `bad(..., code=)` y `equipo/contratos/errores.md`: los necesito para ponerles código a los 2 `bad()` de `backend/idem.py` (entregable 7 de E2). Propongo `invalid_request_id` ("Invalid request id") y `request_id_reused` (409, "That request id was already used for something different"). |
| 10-oct | E2 | E3 | `backend/seed.py` `new_season` (líneas 23-24): pone `user["balance"]` a mano, sin `ledger.post`, y deja los renglones del libro. Después de un `scripts/seed.py new-season` o de `SEASON_RESET`, el saldo semanal ya no es la suma del libro (D2): `importar_archivo --simular` da una diferencia por persona. Pido que el reinicio pase por el libro (un `season.reset` externo, como `weekly.expired`). |
| 10-oct | E2 | E7 | `equipo/ROJOS_CONOCIDOS.json`: quitar `tests.test_speed.TheDatabaseIsWrittenCarefully.test_pile_ups_share_a_write_and_the_last_change_always_wins`. Arreglado en `e2-datos` (91d6073): 3 de 3 en verde en Windows. |

---

## Registro

### 10 de octubre de 2026

- `[E0] 10-oct · HECHO: ronda 0 cerrada (repositorio, Supabase Pro, verificación de la computadora del dueño en OT-001, dirección de arte 3D en OT-006). El dueño decidió mejorar la app original en su lugar (D1) y trabajar como en Ches-Hex (D7). La app pasó a la raíz, nacieron equipo/ y los ganchos, y se etiquetó cimiento-1. · PENDIENTE: ronda 1 · BLOQUEADO POR: nada · COMANDO: python -m unittest discover -s tests -t .`
- `[E2] 10-oct · HECHO: 1, store.py reintenta el reemplazo de db.json si otro hilo lo lee (Windows); TheDatabaseIsWrittenCarefully 3 de 3 en verde · PENDIENTE: que E7 quite su fila de ROJOS_CONOCIDOS · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_speed.TheDatabaseIsWrittenCarefully`
- `[E2] 10-oct · HECHO: 2, el modelo real: backend/datos/catalogo.py (313 campos) + codigo.py (quién escribe y lee, por análisis del código) → docs/datos/modelo-actual.md; --verificar visto en rojo con un campo nuevo. La base se siembra con backend/datos/sembrar.py (la app de verdad por HTTP), porque scripts/seed.py solo reinicia · PENDIENTE: nada · BLOQUEADO POR: nada · COMANDO: python -m backend.datos.inventario --verificar`
- `[E2] 10-oct · HECHO: 3, esquema v1 en supabase/migrations (15 tablas, RLS en todas, el navegador solo lee; chips apagada); una prueba por tabla de que otra persona no la ve · PENDIENTE: ronda 2 listada en docs/datos/modelo-actual.md · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_esquema_pg`
- `[E2] 10-oct · HECHO: 4, post_transaction / balance_of / ledger_audit en SQL: suma cero, nadie negativo, candados en orden de id, idempotencia; 20 hilos sin perder un centavo; 15 mutantes en rojo · PENDIENTE: nada · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_libro_pg && python -m backend.datos.mutantes`
- `[E2] 10-oct · HECHO: 5, importar_archivo --simular: 0 diferencias en la base sembrada; el plan entra a Postgres local por post_transaction con los mismos saldos. Hallazgo: después de un new-season el libro no cuadra (petición a E3) · PENDIENTE: nada · BLOQUEADO POR: nada · COMANDO: python -m backend.datos.importar_archivo --simular data/db.json`
- `[E2] 10-oct · HECHO: 6, equipo/contratos/esquema.md (Propuesto), con una prueba que lo compara con las migraciones · PENDIENTE: revisión de E0 · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_esquema_pg.ElContratoCoincideConLasMigraciones`
- `[E2] 10-oct · HECHO: nada del 7 · PENDIENTE: 7, los 2 bad() de idem.py con código · BLOQUEADO POR: E3 (bad(code=) y errores.md; petición arriba) · COMANDO: —`
