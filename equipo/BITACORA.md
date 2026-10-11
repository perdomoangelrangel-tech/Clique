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
- `[E0] 11-oct · HECHO: el dueño pidió que los juegos se vean como un casino de verdad y que al abrir uno entres a su sala (D16), y aprobó los textos de casino de E5 mientras no prometan dinero real (D15). Orden 2 de E6 al día (sala de ruleta como muestra, después las demás salas y los pósters con acabado real) y adenda de E5 (la sala de ruleta en su pantalla; los textos aprobados) · PENDIENTE: el visto bueno del dueño a la sala de ruleta · BLOQUEADO POR: nada · COMANDO: node herramientas/ganchos.test.mjs`
- `[E6] 10-oct · HECHO: entregable 1, hoja de prueba con ruleta, blackjack y dados en 3D (docs/arte/juegos-prueba.webp, juegos-prueba.html y el vestíbulo real con las tres en docs/arte/juegos-prueba-vestibulo-*.webp). Enviada al dueño · PENDIENTE: su sí para los otros 11 juegos (entregable 2) · BLOQUEADO POR: el visto bueno del dueño · COMANDO: python -m http.server 8000 y abrir /docs/arte/juegos-prueba.html`
- `[E6] 10-oct · HECHO: entregable 3, tests/test_arte.py (solo biblioteca estándar; la lista de juegos sale de GAME_ICON en art.js). Revisada por qa: tapé los cuatro huecos que encontró (esquinas transparentes en un ícono RGBA, juego con fondo opaco, archivos de más en static/renders, respaldo 2D sin transparencia) y la extensión sale de `ext` en GAME_ICON. Vista en rojo con 13 mutantes, uno por regla · PENDIENTE: nada · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_arte`
- `[E6] 10-oct · HECHO: entregable 4, fondo de mesa: static/renders/fondo-mesa-1920x1080.webp (10 KB) y fondo-mesa-1080x2340.webp (12 KB). Fieltro del tono --felt bajo la lámpara, la orilla cae casi a negro. @E4 ya lo puedes usar con url(/renders/fondo-mesa-…webp) · PENDIENTE: nada · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_arte.AppRenders`
- `[E6] 10-oct · HECHO: entregable 5, íconos de la app: static/renders/icono-192.png, icono-512.png, icono-maskable-512.png (ficha en el 70 %, cabe en el círculo seguro) y apple-touch-icon-180.png. Ficha lima con la marca, sobre la sala oscura y sin transparencia. @E5 son los del manifest y del apple-touch-icon · PENDIENTE: captura del dueño en su teléfono · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_arte.AppRenders`
- `[E6] 10-oct · HECHO: entregable 6 en parte. equipo/contratos/arte3d.md tiene la sección 11 (imágenes 2D: nombres, medidas, presupuestos, receta) y los cuadros por segundo que el dueño midió en su PC y mandó con captura en la conversación con E0 (138 a 145: el ritmo de su pantalla de 144 Hz; lo que tarda en dibujar cada cuadro no se midió). Herramientas nuevas: assets3d/herramientas/iconos_juego.py (render → PNG de 480 y 128) y e6_util.py (la copia del bloque de texto del .blend). Las cartas de las imágenes de juego ya no llevan la leyenda impresa · PENDIENTE: la medición en Android de gama media; el sí del dueño a los números de la rueda y al índice A de las cartas; pasar el contrato a Vigente cuando lo lean E4 y E5; subir assets3d/juegos/juegos.blend (Git LFS) desde la computadora del dueño, y E0 corrige la orden: un solo juegos.blend con una escena por juego en vez de un .blend por juego · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_arte`
