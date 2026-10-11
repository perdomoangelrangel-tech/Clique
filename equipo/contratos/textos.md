# Contrato de textos

*Dueño: E5. Estado: Propuesto (10-oct). Lo leen todos los que escriben algo que se ve en pantalla (E4, E5 y quien venga).*

Clique habla **español de México** (D5). El inglés es el segundo idioma. Todo texto visible pasa por el sistema de idioma de `static/js/i18n.js`; el auditor `tests/test_i18n.py` cuenta lo que se escape.

## 1. Cómo se usa

```js
import { t, th, tp } from './i18n.js';        // desde views/ o games/: '../i18n.js'

el.textContent = t('Mercados');                              // texto plano
el.innerHTML = `<h2>${th('Hola, {nombre}', { nombre: u.username })}</h2>`;   // HTML: th() escapa los valores
t('Apostaste {cantidad}', { cantidad: money(x) });           // valores con {llave}
tp(n, '{n} ficha', '{n} fichas');                            // plurales: {n} sale con el formato es-MX
```

- **La clave es la frase en español**, completa y tal como se ve. No hay claves tipo `auth.login.title`. Si una frase no tiene traducción, se ve en español, que es lo que queremos.
- **`t()` devuelve texto plano.** Si va a `innerHTML`, usa `th()` (escapa los valores) o `esc()` sobre el resultado. Nunca metas un dato que escribió una persona (nombre, mensaje, título de mercado, castigo) en una frase con `t()` y luego a `innerHTML` sin escapar.
- **Una frase, una llamada.** No partas una oración en pedazos (`t('Tienes') + n + t('fichas')`): en otro idioma el orden cambia. Usa `{llave}`.
- Las llaves van en minúsculas y en español: `{nombre}`, `{cantidad}`, `{juego}`, `{n}`. Las mismas llaves deben estar en la traducción (la prueba lo revisa).
- Un HTML mínimo dentro de la frase (`<b>`) se permite con `th()` cuando la negrita es parte de la oración. Nada de atributos ni clases dentro de una frase.
- Lo que no se traduce (nombres propios de juegos como *Blackjack*, *Hi-Lo*; marcas; códigos) se deja sin `t()` y se anota en la lista de exentos del auditor.

## 2. El inglés

- `static/i18n/en.json`: `{ "frase en español": "English sentence" }`. Una línea por frase, en el orden en que se agregaron.
- Al migrar una pantalla, el inglés sale del texto original de la app (que estaba en inglés): así el inglés no se pierde.
- Cambiar de idioma **no recarga la página**: `setLang('en')` avisa con `onLang()` y la app vuelve a pintar la pantalla en su lugar. El idioma se guarda en el navegador (`clique-lang`) y se pone en `<html lang>`.
- El selector está en tu perfil (*Idioma de la app*).

## 3. Tono

- **Tuteo** siempre: *Entra*, *Tu saldo*, *Te faltan fichas*. Nunca *usted*.
- **Frases cortas.** Una idea por frase. Botones de una a tres palabras, con verbo: *Apostar*, *Entrar*, *Plantarte*.
- **El humor de la app se queda** (es parte de Clique: "Tus amigos creen que saben cosas"), pero sin groserías ni albures, y entendible en todo México.
- **Nunca prometas dinero real.** Son fichas. No digas *dinero*, *pesos*, *retirar*, *cobrar en efectivo*, *ganar dinero*. Si el original en inglés dice *money* o *cash*, en español va *fichas*.
- Palabras fijas del producto (las del `GLOSARIO.md`): *círculo*, *mercado*, *fichas*, *cuenta semanal*, *cuenta acumulada*, *ranking*, *castigo*, *bolsa*, *póker*, *casino*. Sí/No para las opciones de un mercado.
- Fechas en minúsculas a la mexicana: *10 oct 2026*, *12:05 p.m.*

## 4. Números, fichas y fechas

Siempre con los formateadores de `i18n.js` (o los de `util.js`, que los llaman), nunca con `toLocaleString('en-US')` a mano:

| Qué | Función | es-MX | en |
|---|---|---|---|
| Fichas | `chips(x)` / `money(x)` | `$1,234.50` | `$1,234.50` |
| Fichas grandes | `chips(2.5e6)` | `$2.5 M`, `$3.2 mil M`, `$1 B` (billón = 10¹²) | `$2.5M`, `$3.2B`, `$1T` |
| Con signo | `chips(x, { plus: true })` | `+$25.00` | igual |
| Entero sin centavos | `chips(x, { noCents: true })` | `$1,000` | igual |
| Número | `number(x, decimales)` | `1,234,567.89` | igual |
| Fecha | `date(t)` / `dateShort(t)` | `10 oct 2026` / `10 oct` | `Oct 10, 2026` |
| Hora | `time(t)` | `12:05 p.m.` | `12:05 PM` |
| Hace cuánto | `ago(t)` | `hace 5 min` | `5m ago` |
| Cuánto falta | `until(t)` | `2 d 3 h` | `2d 3h` |

**El signo de las fichas** (`CHIP_SIGN` en `i18n.js`) hoy es `$`, como en la app original. Está pendiente de decisión del dueño porque `$` puede leerse como dinero real (ver §5). Vive en un solo lugar para cambiarlo en una línea.

## 5. Preguntas abiertas para el dueño

| Fecha | Pregunta | Propuesta de E5 |
|---|---|---|
| 10-oct | Las fichas se escriben con `$` delante (`$1,000`). En México `$` es pesos. | Cambiar el signo por la palabra o un ícono de ficha: `1,000 fichas` en textos largos y un ícono de ficha (o `ƒ`) en tablas y saldos. Mientras tanto se queda `$`. |
| 10-oct | El botón *Cash out* de los juegos del casino. *Cobrar* suena a dinero. | *Retirarte* o *Plantarte* ("Plántate con {cantidad}"). Uso *Plantarte* hasta que decidas. |
| 10-oct | *Add funds* (agregar fondos con la contraseña de fondos). *Fondos* suena a dinero real. | *Agregar fichas*. |
| 10-oct | *Loans* (préstamos entre amigos) y *Transfers* (transferencias). | *Préstamos de fichas* y *Enviar fichas*. |

## 6. Errores del servidor

Los errores se muestran por su **código** con `tError(error)`: si el código tiene frase, sale la frase en el idioma del usuario; si no, sale el texto del servidor tal cual (un código nuevo nunca se esconde). La lista de códigos es de E3 (`equipo/contratos/errores.md`); E5 mantiene las frases en `i18n.js` (`ERRORS`).

## 7. El auditor

`python -m unittest tests.test_i18n` cuenta en cada archivo de `static/js/**` las frases visibles escritas sin `t()`, y las claves usadas que faltan en `en.json`. Imprime la cobertura por archivo. **Falla si en un archivo suben las frases sin `t()`** respecto a lo anotado en la prueba; un archivo nuevo empieza en cero. Cuando migras un archivo, baja su número en la prueba (el auditor te dice el nuevo).
