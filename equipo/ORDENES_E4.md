# Orden 1 · E4 · Diseño · tokens v2 y el club privado de cartas en el armazón de la app · 10-oct

> **Adenda · 11-oct (E0).** El dueño decidió D11: los juegos del casino se ven como los dibujos 2D pero en 3D (colores
> planos de la paleta en dos tonos, contorno de tinta). Tu armazón sigue con la estética del club (D4). **Aún no hay
> commits en `e4-diseno`: empieza por tu entregable 1**, que E5 espera (barra inferior y botón de apostar en celular,
> peticiones en la bitácora). Súmale a ese entregable los tonos de sombra del estilo del dibujo como tokens (petición
> de E6 del 11-oct en la bitácora): papel `#CFC3A8`, lima `#9CC320`, bermellón `#D2361B`, bermellón suave `#F2664A` y
> `#D24E36`, oro `#FBB635` y `#D9952A` (`equipo/contratos/arte3d.md` §13).

## Objetivo (una frase)
Que la app tenga una sola fuente de color con la paleta v2 y contraste probado, y que su armazón (fondo, encabezado, navegación, tarjetas, botones, campos) se vea como los cuadros aprobados: boleto de papel sobre mesa de fieltro, con latón y luz cálida.

## Parte de
Rama `e4-diseno`, árbol `_ramas/e4-diseno`, sobre `cimiento-1`. Cada sesión empieza con `cd _ramas/e4-diseno && git fetch origin && git rebase origin/integracion` (desde la raíz el gancho no deja rebasar: la raíz es `main`), y empujas con `git push --force-with-lease origin e4-diseno`.

## Lee antes (en este orden, y nada más)
1. `equipo/DECISIONES.md` (D4) y `equipo/decisiones/ADR-005-arte-casino-premium-blender.md`
2. Los cuadros `docs/arte/*.webp` (la referencia visual) y `equipo/contratos/arte3d.md` §3 (los valores de material)
3. `equipo/historia/ronda-0/ordenes/OT-003-tokens-v2.md`, sección "Valores": la paleta v2 completa
4. `static/css/tokens.css` y `static/css/shell.css`

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Paleta v2 en `static/css/tokens.css`**: escalas lima, bermellón y oro (50 a 950), roles (`pos`, `neg`, `reward`, `focus`, `danger`, estados de botón), los materiales del club (sala, mesa, papel, fieltro, latón) y `paper-mute` a `#5A4E3C`. **Los nombres de tokens que ya existen siguen funcionando** (alias), para que nada se rompa | `python -m unittest tests.test_tokens` y la suite completa | en verde; ninguna pantalla cambia de color sin querer (capturas antes y después) |
| 2 | **`tests/test_tokens.py`**: (a) contraste AA (4.5:1) de las parejas de texto que usa la app, con fallo si `paper-mute` vuelve al valor viejo; (b) **contador de colores sueltos** (hexadecimales en los `.css`, `.js` y `.html` de `static/`, fuera de `tokens.css` y de `static/vendor/`; el `manifest.webmanifest` no cuenta porque JSON no lee variables). Hoy son 759: la prueba falla si el número sube, y anotas en la bitácora cuánto bajó cada sesión | `python -m unittest tests.test_tokens` | en verde, visto en rojo con un mutante en cada parte |
| 3 | **El armazón con la estética del club**: fondo de mesa (fieltro oscuro con viñeta; E6 entrega `static/renders/fondo-mesa-*.webp`, su entregable 4), encabezado y barra de navegación de latón y sala, tarjetas de papel con sombra dura, botones y campos. Solo CSS y tokens: si una vista necesita otra clase en su HTML, pídesela a E5 | capturas a 390×844 y 1366×768 de inicio, mercados, casino y perfil, antes y después, en `docs/diseno/` | se parece a los cuadros; ninguna prueba se rompe; el contador de colores sueltos no sube |
| 4 | **Página de muestras** `static/js/views/diseno.js`: paleta, tipografías, botones en sus estados, tarjeta de papel, campo, aviso de ganar y de perder. Sus textos van con `t()` de `static/js/i18n.js` (es el primer entregable de E5: si aún no está en `integracion`, deja este entregable para el final). E5 la registra en la ruta `/diseno` (su entregable 7) | captura a 390×844 en `docs/diseno/` | se ve completa y usa solo tokens |
| 5 | **`equipo/contratos/tokens.md`** (Propuesto): nombres, roles y reglas de uso. Por ejemplo: oro nunca para ganar o perder; Sí/No siempre con palabra o ícono, no solo color | lectura de E0 y E5 | existe y coincide con `tokens.css` |

## Tus archivos
`static/css/**`, `static/fonts/**`, `static/js/theme.js`, `static/js/looks.js`, `static/js/art.js`, `static/js/views/diseno.js`, `equipo/contratos/tokens.md`, `tests/test_tokens.py`, `docs/diseno/**`.

## No hagas
- Tus archivos con texto visible (`art.js`, `looks.js`, `views/diseno.js`) cuentan en el auditor de textos de E5: un texto nuevo va con `t()`.
- No edites vistas de `static/js/` que son de E5: pide las clases o el HTML que necesites.
- No cambies el significado de un token existente sin anotarlo (otras pantallas lo usan).
- Premium no es recargado: nada de degradados chillones, brillos animados ni más de dos sombras por elemento.

## Para y pregunta si
- Un color de la paleta v2 no da contraste AA en un uso que la app necesita.
- Una pantalla no se puede acercar a los cuadros solo con CSS.

## Cómo reportas
`[E4] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
