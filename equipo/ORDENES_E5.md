# Orden 1 · E5 · Frontend · la app en español de México, navegación de celular, instalable y sin HTML inseguro · 10-oct

> **Adenda · 11-oct (E0).** El dueño decidió D11 y D14: los juegos se ven como los dibujos pero en 3D, y la app es
> para escritorio y celular (iPhone, 60 cuadros). Sigue con tus entregables 1 a 7 y suma este:
>
> | # | Qué | Cómo se comprueba | Hecho cuando |
> |---|---|---|---|
> | 8 | **La ruleta en vivo en la pantalla de la ruleta.** Lleva `static/3d/ruleta.glb` con `docs/arte/ruleta-animacion.mjs` (`planSpin`) y `docs/arte/estilo-toon.mjs` (`applyToon`, `addOutlines`) tal cual (cópialos a `static/js/` o pide a E6 que los ponga ahí). Arranca en 2D con `static/3d/ruleta-dibujo-2d.webp` y pasa a 3D cuando cargó; se queda en 2D sin WebGL o con menos movimiento. **El número lo manda el servidor (D8)** y la animación cae en él. El número que cayó se ve **grande fuera de la rueda** (en 390 px los del anillo miden unos 6 px). Solo dibuja durante la tirada. three.js y el decodificador de meshopt desde `static/vendor/`, no de un CDN. Las rutas de `static/casino-icons/` llevan `?v=` (los 14 dibujos cambiaron con el mismo nombre) | `python -m unittest tests.test_layout` con un caso de la ruleta en vivo, y en Chrome a 1366×768 y 390×844: "el servidor dijo N · cayó en N" con tres números | en verde, y el dueño la ve en su iPhone a 60 cuadros |
>
> Referencia completa: `docs/arte/prueba-ruleta.html` y `equipo/contratos/arte3d.md` §12 y §13. Las preguntas de textos
> que suenan a dinero real ya están en DECISIONES como preguntas abiertas para el dueño.

## Objetivo (una frase)
Que toda la interfaz hable español de México con un sistema de traducciones medido, que en el celular se navegue con una barra inferior y el botón de apostar siempre se vea, que la app se pueda instalar, y que ningún dato de una persona se pinte con `innerHTML`.

## Parte de
Rama `e5-frontend`, árbol `_ramas/e5-frontend`, sobre `cimiento-1`. Cada sesión empieza con `cd _ramas/e5-frontend && git fetch origin && git rebase origin/integracion` (desde la raíz el gancho no deja rebasar: la raíz es `main`), y empujas con `git push --force-with-lease origin e5-frontend`.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` (D4, D5, D8) y `equipo/GLOSARIO.md`
2. `static/js/app.js`, `static/js/ui.js`, `static/js/layout.js` (cómo se arma la app)
3. `docs/plan-maestro.md`: funciones F1 y F2, y el arreglo R3

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Sistema de idioma** `static/js/i18n.js`: `t('Texto en español')` (la clave es el propio español, como en Ches-Hex; una frase sin traducir se ve en español), `static/i18n/en.json` para inglés, formatos con `Intl` en `es-MX` (fichas, fechas, horas), selector en el perfil y `<html lang>` al día. Más `equipo/contratos/textos.md`: tono, cómo se escribe una clave, plurales y formato de fichas. **Es tu primer entregable porque E4 lo necesita** para su página de muestras | `node --test tests/js/i18n.test.mjs` | en verde; cambiar a inglés y volver no recarga la página |
| 2 | **Auditor de textos** `tests/test_i18n.py`: cuenta las frases visibles escritas sin `t()` en `static/js/**` y las claves usadas sin traducción en `en.json`. Imprime cobertura por archivo. **Falla si en algún archivo suben las frases sin `t()`** respecto a lo anotado para ese archivo en la prueba; un archivo nuevo empieza en cero. Los archivos de E4 (`theme.js`, `looks.js`, `art.js`, `views/diseno.js`) cuentan igual: sus textos los migra E4 y tú se lo pides en tu bitácora | `python -m unittest tests.test_i18n` | en verde; visto en rojo con un mutante |
| 3 | **Migrar pantallas al español**, en este orden: armazón y navegación, registro y entrada, inicio, círculos, mercados y apostar, semana y ranking, casino (vestíbulo y cada juego), póker, perfil, tienda, bolsa, préstamos, transferencias, retos. **Completo quiere decir todas las pantallas**: cuando termines una, sigue con la siguiente. Los mensajes de error del servidor se traducen por su código (la lista es de E3: `equipo/contratos/errores.md`) | `python -m unittest tests.test_i18n` (la cobertura sube en cada entrega) y capturas de cada pantalla en `docs/producto/capturas/` | 100 % de cobertura; tono: tuteo, frases cortas, sin prometer dinero real |
| 4 | **Navegación de celular:** barra inferior de máximo 5 destinos a menos de 768 px (F2) y fuera del casino el buscador de mercados y la cinta de precios (R3). A 1366×768 y a 390×844, el botón de apostar de cada juego se ve sin desplazarse | `python -m unittest tests.test_layout` (agrega los casos) | en verde en las dos medidas, para los 14 juegos |
| 5 | **HTML seguro:** cero `innerHTML` con datos que escribe una persona (nombres, mensajes, títulos de mercados, castigos). Ayudante `escape`/`textContent` en `static/js/ui.js` y un arnés que falla si aparece uno nuevo. Hoy hay 177 `innerHTML` en total: no todos son peligrosos, el arnés distingue | `node --test tests/js/html_seguro.test.mjs` | en verde, visto en rojo con un mutante (un título de mercado con `<img onerror>` no se ejecuta) |
| 6 | **Instalable (PWA):** `manifest.webmanifest` con nombre, colores del club e íconos (E6 los entrega en `static/renders/icono-*.png`; mientras no lleguen, usa los que hay), y `sw.js` que guarda el armazón para abrir sin red y avisa "sin conexión" | instalar desde Chrome en Android o escritorio; `node --test tests/js/sw.test.mjs` | se instala y abre sin red mostrando el aviso |
| 7 | **La ruta `/diseno`** con la vista de E4 (`static/js/views/diseno.js`, suya): solo el registro en la navegación, sin enlace en el menú | abrir `/diseno` con la app corriendo | se ve la página de muestras de E4 |

## Tus archivos
`static/index.html`, `static/js/**` salvo lo de E4, `static/i18n/**`, `static/manifest.webmanifest`, `static/sw.js`, `static/vendor/**`, `docs/producto/**`, `tests/js/**`, `tests/layout/**`, `tests/layout_world.py`, `tests/test_layout.py`, `tests/test_i18n.py`.

## No hagas
- No cambies estilos ni colores (son de E4): usa sus clases y tokens, y pide lo que falte.
- No calcules en el navegador un saldo, un pago o un resultado para mostrarlo como definitivo (D8).
- No agregues un framework ni un paso de compilación: la interfaz sigue siendo JavaScript servido tal cual.

## Para y pregunta si
- Un texto puede sonar a dinero real o a apuesta con dinero ("cobrar", "retirar", "$"): anótalo como pregunta para el dueño con tu propuesta.
- Una pantalla necesita una ruta nueva del servidor (pídela a E1 con su firma).

## Cómo reportas
`[E5] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
