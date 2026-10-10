# Orden 1 · E6 · Arte 3D · los 14 juegos, la mesa y el ícono con la estética aprobada · 10-oct

*E6 lo lleva E0 desde la app de Claude, porque Blender está conectado solo a la app de escritorio.
Trabaja en el árbol `_ramas/e6-arte3d` de la computadora del dueño. Esta orden sigue la plantilla
igual que las demás, para que E7 la verifique igual que las demás.*

## Objetivo (una frase)
Que cada imagen de la app que hoy es un dibujo plano (los 14 juegos del casino, el fondo, el ícono)
sea un render con la luz, los materiales y el color de los cuadros que el dueño aprobó el 10-oct.

## Parte de
Rama `e6-arte3d`, árbol `_ramas/e6-arte3d`, sobre `cimiento-1`. Cada sesión empieza con
`cd _ramas/e6-arte3d && git fetch origin && git rebase origin/integracion`, y se empuja con
`git push --force-with-lease origin e6-arte3d`. Los `.blend` van en Git LFS: se empujan desde la
computadora del dueño, nunca desde el contenedor (en la ronda 0 el contenedor no pudo subir a LFS).

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` (D4 y D8) y `equipo/decisiones/ADR-005-arte-casino-premium-blender.md`
2. `equipo/contratos/arte3d.md` completo: escala, nombres, materiales, luz, presupuestos
3. Los cuadros `docs/arte/*.webp` y sus escenas `assets3d/estilo/*.blend`: son la regla de la casa
4. `static/js/art.js`, líneas 108 a 140: qué imagen usa cada juego y sobre qué color se pone

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Hoja de prueba con 3 juegos** (ruleta, blackjack, dados) renderizados con la receta de los cuadros: objeto de la mesa sobre fondo transparente, sombra suave de contacto incluida, luz cálida de lámpara. Se ven sobre su color de póster (`bg` en `art.js`) | `docs/arte/juegos-prueba.webp` y la página `docs/arte/juegos-prueba.html` que los pone sobre su color | **el dueño dice que sí** en el chat. Sin ese sí no se hacen los otros 11 |
| 2 | **Los 14 juegos**: `chicken`, `blackjack`, `roulette`, `limbo`, `coinflip`, `war`, `dice`, `mines`, `moles`, `tower`, `poker`, `hilo`, `wheel`, `rps`. **Mismo nombre y formato** que hoy (`static/casino-icons/<juego>.png` a 480 px y `static/casino-icons/small/<juego>.png` a 128 px, fondo transparente), para que la app los tome sin tocar código. Cada uno con su escena en `assets3d/juegos/<juego>.blend` | `python -m unittest tests.test_arte` | en verde, y la hoja `docs/arte/juegos.webp` con los 14 en la bitácora |
| 3 | **`tests/test_arte.py`** (solo biblioteca estándar): cada juego de `GAME_ICON` en `art.js` tiene sus dos archivos; medidas exactas leídas del encabezado PNG; canal alfa; presupuesto **≤ 100 KB a 480 px y ≤ 15 KB a 128 px**; `static/3d/ficha.glb` ≤ 300 KB; los renders de `static/renders/` dentro de su presupuesto. La lista de juegos se lee de `art.js`, no se escribe a mano | `python -m unittest tests.test_arte` | en verde, y en rojo con un mutante en cada regla |
| 4 | **Fondo de mesa** para el armazón de E4: fieltro oscuro con viñeta y la luz de lámpara de los cuadros, sin objetos. `static/renders/fondo-mesa-1080x2340.webp` y `static/renders/fondo-mesa-1920x1080.webp`, **≤ 150 KB cada uno**. Avisa a E4 en tu bitácora cuando esté | `python -m unittest tests.test_arte` | E4 lo puede usar con `url(/renders/…)` sin pedir nada más |
| 5 | **Ícono de la app y arranque**: la ficha vista de frente con la marca. `static/renders/icono-192.png`, `icono-512.png`, `icono-maskable-512.png` (la ficha dentro del círculo seguro del 80 %) y `apple-touch-icon-180.png`. Avisa a E5, que los pone en `manifest.webmanifest` | las cuatro medidas en `tests/test_arte.py` | E5 los referencia; se ven bien en el lanzador de Android y en iOS (captura del dueño) |
| 6 | **El contrato al día**: `equipo/contratos/arte3d.md` con una sección para las imágenes 2D (nombres, medidas, presupuestos, fondo transparente), los cuadros por segundo que mida el dueño en su teléfono, y de **Propuesto** a **Vigente** cuando E4 y E5 lo lean | lectura de E0, E4 y E5 | dice lo mismo que `tests/test_arte.py` |

## Tus archivos
`assets3d/**`, `docs/arte/**`, `static/3d/**`, `static/renders/**`, `static/casino-icons/**`,
`equipo/contratos/arte3d.md`, `tests/test_arte.py`.

## No hagas
- No toques `static/js/art.js` ni el CSS: si un juego necesita otro formato, otra medida o otro color de fondo, pídelo a E4 en tu bitácora.
- No cambies la receta de los cuadros (AgX Punchy, exposición -0.5, latón, papel, fieltro) sin el sí del dueño: es la estética de toda la app.
- No metas texto en los renders (nombres de juegos, números, "CASINO"): los textos van por i18n.
- No uses marcas, personajes ni diseños de terceros (ni cartas con el diseño de una baraja comercial).
- No subas un `.blend` con rutas absolutas: todo relativo con `//` (contrato §7).

## Para y pregunta si
- Un juego no se entiende como objeto 3D sobre la mesa (por ejemplo `rps` o `moles`): propón dos ideas con un render rápido y que elija el dueño.
- Un render no cabe en su presupuesto sin verse peor que el dibujo de hoy.
- La medición de cuadros por segundo del dueño sale por debajo de 60 en su Android.

## Cómo reportas
Al final de `equipo/BITACORA.md` de tu rama, por cada entregable:
`[E6] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
