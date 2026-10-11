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

### 11 de octubre de 2026

- `[E0] 11-oct · HECHO: el dueño decidió D11 (los juegos como los dibujos 2D pero en 3D), D12 (la monetización no está decidida: se conservan la compra de fichas apagada y el pase de temporada), D13 (el repositorio pasa a privado; lo cambia él en GitHub) y D14 (escritorio y celular, iPhone a 60 cuadros, modelos en vivo ≤ 8 mil triángulos). Orden 2 de E6; adendas a E5 (la ruleta en vivo en su pantalla), E4 (empezar por los tokens, con los tonos de sombra) y E1 (minutos de Actions con el repositorio privado). Dos preguntas abiertas nuevas para el dueño en DECISIONES · PENDIENTE: que el dueño cambie la visibilidad del repositorio; que E7 fusione las ramas de la ronda 1 · BLOQUEADO POR: nada · COMANDO: node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs`
