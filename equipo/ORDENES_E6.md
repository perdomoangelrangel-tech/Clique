# Orden 2 · E6 · Arte 3D · un casino de verdad: cada juego en su sala · 11-oct

*E6 lo lleva E0 desde la app de Claude: Blender está conectado a la computadora del dueño y, para la ruleta, también
corre sin ventana en el contenedor (`pip install bpy==5.2.2`). Sigue la plantilla igual que las demás, para que E7 la
verifique igual.*

*La orden 1 (10-oct) quedó así: la hoja de prueba de luz de mesa (entregable 1) la sustituyó la decisión D11; los 14
juegos (2) están en el estilo del dibujo; la prueba (3), el fondo (4), los íconos (5) y el contrato (6) están entregados.*

## Objetivo (una frase)
Que cada juego se vea como un casino de verdad, con la idea de los dibujos del dueño y acabado real, dentro de su sala a
la que entras al abrirlo; que cada juego en vivo caiga en el resultado del servidor y vaya a 60 cuadros en el iPhone.

## Parte de
Rama `e6-arte3d`, árbol `_ramas/e6-arte3d`, rebasada sobre `origin/integracion`. Cada sesión empieza con
`cd _ramas/e6-arte3d && git fetch origin && git rebase origin/integracion` y se empuja con
`git push --force-with-lease origin e6-arte3d`. Los `.blend` van en Git LFS y se suben desde la computadora del dueño.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md`: D8, D11, D14, D16
2. `equipo/contratos/arte3d.md` §6, §9, §12, §13 y §14
3. `docs/arte/referencia-2d/` (los dibujos originales) y `docs/arte/juegos-3d.webp`
4. `docs/arte/ruleta-animacion.mjs`, `docs/arte/estilo-toon.mjs` y `assets3d/herramientas/ruleta_toon.py`: el patrón de un juego en vivo

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Los 14 dibujos en el estilo plano** (11-oct) se quedan en la app hasta que lleguen los del entregable 6; lo que el dueño pida cambiar mientras tanto, se cambia en su escena `T_<juego>` | `python -m unittest tests.test_arte` | en verde |
| 2 | **`juegos.blend` en el repositorio**: `assets3d/juegos/juegos.blend` con las escenas `T_<juego>`, `T_ruleta_vivo`, la textura empacada y sin rutas absolutas, subido con Git LFS desde la computadora del dueño | `git lfs ls-files` muestra el archivo; abrirlo en Blender 5.2 y correr `render_game("roulette", ...)` | E7 lo ve en `integracion` |
| 3 | **Cuadros por segundo en el iPhone del dueño** con la página "Ruleta 3D en vivo": el número del HUD después de una tirada, con captura | captura del dueño en el chat | anotado en el contrato §6; si sale debajo de 55, para y pregunta |
| 4 | **La sala de ruleta (D16), la muestra:** la rueda del dibujo con acabado de casino, el salón alrededor (`assets3d/herramientas/sala_casino.py` y `sala_ruleta.py`), su panorama desde la cámara del juego (`static/3d/salas/ruleta.webp`) y la entrada en el prototipo | `python -m unittest tests.test_arte` y el prototipo `docs/arte/prueba-ruleta.html` | el dueño la aprueba en el chat |
| 5 | **Las demás salas**, con el mismo salón y su mesa: cartas (blackjack, póker, guerra, mayor o menor), dados (dados, volado, piedra-papel-tijera), rueda, y los originales (gallina, limbo, minas, topos, torre). Cada juego con su objeto en vivo ≤ 8 mil triángulos y sus cuentas en un módulo puro con prueba | `python -m unittest tests.test_arte` | las 14 en la app, aprobadas por el dueño |
| 6 | **Los 14 dibujos de los pósters con el mismo acabado** (`assets3d/herramientas/juegos_premium.py`), en los mismos archivos de `static/casino-icons/` | `python -m unittest tests.test_arte` | aprobados por el dueño |


## Tus archivos
`assets3d/**`, `docs/arte/**`, `static/3d/**`, `static/renders/**`, `static/casino-icons/**`,
`equipo/contratos/arte3d.md`, `tests/test_arte.py`.

## No hagas
- No toques `static/js/**` ni el CSS: E5 lleva los juegos en vivo a la app y E4 pone los tokens; pídelo en tu bitácora.
- No decidas un resultado en el navegador (D8): el prototipo usa un número de prueba y lo dice.
- No escribas colores a mano fuera de la paleta del contrato §13; los de sombra entran a los tokens con E4.
- No subas un `.blend` con rutas absolutas ni imágenes sin empacar.
- No uses marcas, personajes ni diseños de terceros.

## Para y pregunta si
- Un juego no se entiende en el estilo del dibujo como objeto en vivo: propón dos ideas con un render rápido.
- Un modelo no cabe en 8 mil triángulos sin perder lo que lo hace legible.
- Los cuadros por segundo del iPhone salen debajo de 55.

## Cómo reportas
Al final de `equipo/BITACORA.md` de tu rama, por cada entregable:
`[E6] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
