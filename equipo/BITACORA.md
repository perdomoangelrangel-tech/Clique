# Bitácora del equipo

*Cada rama solo agrega al final. Al fusionar, git junta las líneas de todas (`merge=union`).*
*Formato de cada línea:* `[E<n>] <dd-mmm> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
*Avisos del dueño o del cerebro:* `[E0] …` o `[DUEÑO] …`

---

## Peticiones

*Cuando un encargo necesita un archivo ajeno, lo pide aquí con una fila. El dueño del archivo responde con una línea en el registro (`[E<n>] … · HECHO: petición de E<m> del <fecha> atendida en <commit>`). **La fila no se edita**: con `merge=union`, una fila cambiada en dos ramas queda dos veces.*

| Fecha | De | Para | Qué necesita (archivo, línea y por qué) |
|---|---|---|---|

---

## Registro

### 10 de octubre de 2026

- `[E0] 10-oct · HECHO: ronda 0 cerrada (repositorio, Supabase Pro, verificación de la computadora del dueño en OT-001, dirección de arte 3D en OT-006). El dueño decidió mejorar la app original en su lugar (D1) y trabajar como en Ches-Hex (D7). La app pasó a la raíz, nacieron equipo/ y los ganchos, y se etiquetó cimiento-1. · PENDIENTE: ronda 1 · BLOQUEADO POR: nada · COMANDO: python -m unittest discover -s tests -t .`
- `[E3] 10-oct · HECHO: entregable 1, equipo/contratos/reglas-economia.md (Propuesto): cada regla y número de la economía y los juegos con archivo:línea y su prueba, y 14 diferencias con ECONOMY.md listadas sin corregir (4 son errores del código: pagos del casino redondeados hacia arriba con retorno de más del 100 % en apuestas chicas, pago de mercados redondeado hacia arriba, reinicio de temporada fuera del libro, razón "other" en el póker del reloj) · PENDIENTE: entregables 2 a 5 · BLOQUEADO POR: nada · COMANDO: grep -c "backend/" equipo/contratos/reglas-economia.md`
- `[E3] 10-oct · HECHO: entregable 2, sección "Dónde se mueve el dinero" en equipo/contratos/reglas-economia.md: cada llamada a ledger.post y ledger.opening, y cada users.credit/debit, con su razón, la cuenta de la persona, la contrapartida propuesta para el libro de doble partida (emision, caducidad, casa, mercado, mesa, prestamos, tienda, bolsa) y su txid; más las escrituras directas que no pasan por el libro. Para E2 (funciones SQL de la ronda 2) · PENDIENTE: entregables 3 a 5 · BLOQUEADO POR: nada · COMANDO: lectura de E2 y E0`
