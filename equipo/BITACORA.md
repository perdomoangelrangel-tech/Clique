# Bitácora del equipo

*Cada rama solo agrega al final. Al fusionar, git junta las líneas de todas (`merge=union`).*
*Formato de cada línea:* `[E<n>] <dd-mmm> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
*Avisos del dueño o del cerebro:* `[E0] …` o `[DUEÑO] …`

---

## Peticiones

*Cuando un encargo necesita un archivo ajeno, lo pide aquí con una fila. El dueño del archivo responde con una línea en el registro (`[E<n>] … · HECHO: petición de E<m> del <fecha> atendida en <commit>`). **La fila no se edita**: con `merge=union`, una fila cambiada en dos ramas queda dos veces.*

| Fecha | De | Para | Qué necesita (archivo, línea y por qué) |
|---|---|---|---|
| 10-oct | E5 | E4 | `static/css/` (shell.css o layout.css): estilo de la barra inferior de celular. Marcado ya en la app: `nav#tabbar.tabbar` con 5 `a.tab` (ícono + `<span>`), la activa con `.on` y `aria-current`. Solo en `@media (max-width: 720px)` (la orden dice <768 px; 720 es el corte compartido más cercano), fija abajo con `env(safe-area-inset-bottom)`. **Define el token `--tabbar-h` en `:root`: la app enciende la barra cuando lo ve.** Con la barra visible, `.page` termina arriba de ella (`padding-bottom` con `var(--nav-h)`, que mide `layout.js`) y `.vdock` va encima (`bottom: var(--nav-h)`). |
| 10-oct | E5 | E4 | `static/css/games*.css`: el botón de apostar sin desplazarse (F2, R3). Medido con `node tests/layout/bet.mjs --vp 1366x768,390x844`: a 390×844 el `.btn-bet` queda de 23 a 505 px abajo en los 13 juegos porque el panel va debajo del escenario (propuesta: en ≤720 px, `.btn-bet` pegado abajo con `position: sticky; bottom: calc(var(--nav-h) + 8px)`, o el panel antes del escenario); a 1366×768 faltan chicken 93 px, coinflip 10 px y blackjack 4 px (`--stage-h`). Cuando salga limpio, E5 quita el `expectedFailure` de `tests/test_layout.py`. |
| 10-oct | E5 | E4 | `static/js/art.js` y `static/js/looks.js`: sus textos visibles con `t()` (el auditor cuenta 6 en art.js: HEADS/TAILS, No., Bronze III; y 1 en looks.js). Y marcar `html: seguro (razón)` las 3 líneas de art.js (`label` de rankBadge, ya saneado) y la de looks.js (`body` es SVG propio) que señala `node tests/js/htmlcheck.mjs`. |

---

## Registro

### 10 de octubre de 2026

- `[E0] 10-oct · HECHO: ronda 0 cerrada (repositorio, Supabase Pro, verificación de la computadora del dueño en OT-001, dirección de arte 3D en OT-006). El dueño decidió mejorar la app original en su lugar (D1) y trabajar como en Ches-Hex (D7). La app pasó a la raíz, nacieron equipo/ y los ganchos, y se etiquetó cimiento-1. · PENDIENTE: ronda 1 · BLOQUEADO POR: nada · COMANDO: python -m unittest discover -s tests -t .`
- `[E5] 10-oct · HECHO: entregable 1, sistema de idioma: static/js/i18n.js (t, th, tp, setLang, onLang, formatos es-MX de fichas, números y fechas; util.js los usa), static/i18n/en.json, selector "Idioma de la app" en tu perfil, <html lang> al día; cambiar a inglés y volver no recarga (visto en Chrome). Contrato en equipo/contratos/textos.md · PENDIENTE: E3, la lista de códigos de error (equipo/contratos/errores.md) para traducirlos por código · BLOQUEADO POR: nada · COMANDO: node --test tests/js/i18n.test.mjs`
- `[E5] 10-oct · HECHO: entregable 2, auditor de textos tests/test_i18n.py (frases sin t() por archivo y claves sin inglés); hoy 2,189 frases sin t() en 62 archivos, anotadas como línea base. Visto en rojo con dos mutantes (frase nueva en ui.js, clave sin inglés) · PENDIENTE: que la cobertura suba con la migración · BLOQUEADO POR: nada · COMANDO: python -m unittest tests.test_i18n`
- `[E5] 10-oct · HECHO: entregable 5, HTML seguro: escape, setText y la etiqueta html en static/js/ui.js; arnés tests/js/html_seguro.test.mjs (lee cada ${...} de las plantillas con HTML y, en Chrome, abre un mundo con <img onerror> en cada campo que escribe una persona). 183 innerHTML: ninguno pinta texto de persona sin escapar en archivos de E5; se escaparon 15 valores que no lo estaban (constantes y ex.message) y se marcaron los revisados. Visto en rojo con el título del mercado sin esc(). La CSP del servidor ya bloqueaba los onerror: segunda cerradura · PENDIENTE: E4 marca 4 líneas en art.js y looks.js (petición) · BLOQUEADO POR: nada · COMANDO: node --test tests/js/html_seguro.test.mjs`
- `[E5] 10-oct · HECHO: entregable 7, la ruta /diseno (sin #, sin enlace en ningún menú), probada con una vista provisional · PENDIENTE: verla con static/js/views/diseno.js cuando E4 la entregue · BLOQUEADO POR: E4 entregable 4 · COMANDO: python -m unittest tests.test_layout.LayoutRules`
- `[E5] 10-oct · HECHO: entregable 4 en parte: en el casino ya no salen el buscador ni la cinta (R3, con eso 10 de 13 juegos caben a 1366×768); barra inferior de 5 destinos armada y medida (--nav-h), se enciende con el estilo de E4; arnés tests/layout/bet.mjs para los 14 juegos a 1366×768 y 390×844 · PENDIENTE: el CSS de la barra y del botón de apostar en celular (peticiones a E4) · BLOQUEADO POR: E4 · COMANDO: node tests/layout/bet.mjs --vp 1366x768,390x844`
- `[E5] 10-oct · PREGUNTA AL DUEÑO: textos que suenan a dinero real, con propuesta en equipo/contratos/textos.md §5: el signo $ de las fichas (propongo "fichas" o un ícono de ficha), "Cash out" (propongo "Plantarte"), "Add funds" (propongo "Agregar fichas"), Loans/Transfers ("Préstamos de fichas", "Enviar fichas"). Mientras decides, uso las propuestas en los textos y dejo el $ · COMANDO: —`
- `[E5] 10-oct · AVISO: en Windows tests/test_layout.py no encuentra Chrome (su lista no trae la ruta de Windows), así que LayoutInBrowser se salta en las computadoras con Windows. Lo arreglo cuando el CSS de E4 llegue, para no meter rojos nuevos en la suite · COMANDO: —`
