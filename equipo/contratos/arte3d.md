**Estado:** Propuesto · **Dueño:** E6 · Arte 3D · **Creado en:** ronda 0, OT-006 (2026-10-10)

# Contrato de arte 3D

Cómo se hace, se nombra, se exporta y se usa todo el 3D de Clique. Lo siguen E6 (Blender) y E5 (la app). Cambiarlo requiere un ADR. Dirección de arte: ADR-005.

## 1. Escala y orientación

- **Escala real en metros: 1 unidad = 1 m**, igual que glTF. En Blender nada se escala a mano al exportar.
- En Blender, Z hacia arriba; el exportador glTF lo convierte a Y hacia arriba. No se rota a mano.
- Antes de exportar: transformaciones aplicadas (rotación y escala), geometría centrada en su origen.
- **Cuantización:** el optimizador (sección 7) guarda las posiciones normalizadas entre -1 y 1 y pone la escala y la posición reales en el nodo raíz del GLB. Por eso, en la web, la medida real es la de la geometría **por** la matriz del nodo, nunca la geometría sola (sección 8).
- Medidas de referencia:

| Objeto | Medida | Notas |
| --- | --- | --- |
| Ficha | Ø 0.039 m × 0.0033 m de canto; 0.00362 m con el relieve del centro | El nodo `ficha` del GLB la deja apoyada: base en y = 0. Paso de pila: 0.00332 m (el relieve del centro queda oculto dentro de la ficha de arriba). |
| Carta | 0.063 × 0.088 m, 0.0003 m de grueso, esquinas de 0.003 m | Tamaño póker. |
| Rueda de ruleta | Ø 0.94 m (aro), pista a 0.379 m del centro, rotor Ø 0.62 m, bola Ø 0.032 m | Europea, 37 casillas. Rueda del dibujo (§13); la de madera de la primera prueba medía Ø 0.83 m. |
| Mesa de ruleta | 2.70 × 1.30 m, esquinas de 0.26 m | Riel de 0.10 m. |
| Boleto de papel | 0.080 × 0.130 m | En el cuadro 1 se ve a 1.15× para que se lea. |
| Póster del lobby | 0.50 × 0.70 m, paspartú de 0.045 m | Marco de latón de 0.035 m. |

## 2. Nombres

- **Objetos:** prefijo por tipo y nombre en español en minúsculas con guion bajo:
  - `GEO-` geometría;
  - `I-` instancias de una geometría (fichas en una pila; el sufijo numérico lo pone Blender);
  - `LGT-` luces: `llave`, `relleno`, `contraluz`, y las prácticas por su nombre (`LGT-colgante_pano`);
  - `CAM-` cámaras, con `_v` para la vertical de celular;
  - `RIG-` controles de animación;
  - `FX-` efectos (bokeh, focos).
- **Materiales:** `M_` y nombre en español (`M_laton`, `M_fieltro`). Los del salón de las salas (§14) llevan `S_` (`S_laton`, `S_nogal`, `S_terciopelo_<sala>`, `S_alfombra_<sala>`).
  - Los de efectos emisivos llevan `FX_` y el color (`FX_bokeh_FBB635`).
  - Los de la ficha (`chip_body`, `chip_insert`, `chip_inlay`, `chip_ink`) son interfaz con la web: la app cambia su color por nombre. No se renombran.
- **Archivos:**
  - Cuadros de estilo y escenas: `assets3d/<tema>/<nn-nombre>.blend` (Git LFS), con texturas empacadas y rutas relativas (`//tex/`, salida `//render/`).
  - Modelos: `assets3d/<modelo>/<modelo>.blend` y su exportación cruda `<modelo>-exportada.glb`.
  - Renders: `docs/arte/<nn-nombre>-<ancho>x<alto>.webp` para la dirección de arte y `static/renders/` para lo que use la app.
  - Web: `static/3d/<modelo>.glb` y un respaldo 2D por variante: `static/3d/<modelo>-<variante>-2d.webp`.
  - Imágenes de juego y de la app: una sola escena de Blender por imagen, todas en `assets3d/juegos/juegos.blend` (`T_<juego>` en el estilo del dibujo, `F_fondo`, `I_icono`; las `J_<juego>` son la primera prueba, con luz de mesa), con sus herramientas en bloques de texto del mismo archivo copiados en `assets3d/herramientas/` (si cambias uno, cambia el otro): `e6_util.py`, `e6_toon.py`, `juegos_toon.py` y `ruleta_toon.py`. Secciones 11 y 13.
  - Materiales del estilo del dibujo: `T_<color>` en las imágenes y `roulette_<color>` en la ruleta en vivo. El color va en el nombre, con las claves de la paleta de §13 (`cream`, `ink`, `lime`, `verm`, `verm_soft`, `felt`, `gold`): la web los cambia por el sombreado de dos tonos por nombre. `roulette_numbers` es la tira de números (una imagen). No se renombran.

## 3. Paleta v2 → materiales

Cada material sale de un valor de la paleta v2 (la de `static/css/tokens.css`, que mantiene E4). Los materiales naturales que no existen en la paleta (madera, latón) usan un neutro cálido derivado de sala, mesa u oro. Ese valor y su origen se anotan aquí.

| Material | Valor | De dónde sale |
| --- | --- | --- |
| Cuerpo de ficha lima / bermellón / oro / papel | `#C6F432` / `#FF4B2B` / `#FBB635` / `#EFE6D2` | lima-400, bermellón-500, oro-400, papel |
| Incrustaciones del canto | `#EFE6D2` | papel |
| Incrustaciones de la ficha papel | `#1A1612` en la web; `#24201C` en los renders | tinta-papel. En render se aclara un paso para que, con luz baja, el canto no se confunda con el logotipo. |
| Centro de la ficha (`chip_inlay`) | `#EFE6D2` | papel |
| Logotipo y filete (`chip_ink`) | `#1A1612` | tinta-papel |
| Fieltro de mesa | `#0F2A1E` en render | fieltro `#1E3B2C` oscurecido: la lámpara lo levanta |
| Terciopelo | `#480701` | bermellón-950 |
| Alfombra | `#141110` | sala-2 |
| Papel del boleto y del paspartú | `#EFE6D2` | papel |
| Cara de las cartas | `#FBF6E9` | `--slip` del legacy. No está en la paleta v2. @E4 decide si entra como papel claro. |
| Latón | `#D9B061`, metálico | oro-300 `#FFCF84` con menos saturación, para que se lea como latón y no como oro |
| Madera lacada | rampa `#1E120B` → `#5A321C`; rotor `#0E0805` → `#3A2012` | neutro cálido de sala y mesa |
| Luces de bokeh, focos y luces de la web | `#FBB635`, `#FFCF84`, `#FFE0B1`, `#FEECD1`, `#DF9C03` | escala oro |
| Salón (§14): terciopelo y alfombra por sala | ruleta `#3A0A0E` y `#3A0D10` con motivo `#6B4A1A`; cartas `#0F2A1E` y `#14100D`; dados `#3B1C08` y `#1E120B`; originales `#1A1612` y `#121011` | terciopelo: bermellón-950 y fieltro oscurecidos para que con la luz del salón no se vean rosas; alfombra: sala-2 con el tono del terciopelo; motivo: latón apagado. Vidrios de la barra: ámbar, verde y humo de la escala oro y fieltro |

**Lima y bermellón** son las luces de ganar y perder y nunca decoración (ADR-005). En las fichas son el color de la ficha, que identifica su valor. No se usan para iluminar una escena ni para adornarla. **Excepción del 11-oct:** en el estilo del dibujo (§13) son colores de los objetos de juego, como en los dibujos que eligió el dueño; ahí no hay luces, así que no se confunden con las de ganar y perder.

## 4. Recetas PBR (Principled BSDF de Blender 5.2)

| Receta | Rugosidad | Otros valores | Relieve |
| --- | --- | --- | --- |
| Cerámica (fichas) | 0.32 | Capa 0.35 (rugosidad 0.18), subsuperficie 0.05 | Ruido escala 900, fuerza 0.03 |
| Tinta (logotipo de la ficha) | 0.75 | Especular 0.25 | — |
| Latón | 0.18 a 0.34 (ruido escala 90) | Metálico 1.0, anisotropía 0.35 | — |
| Fieltro | 0.97 | Brillo de tela (sheen) 0.6, rugosidad 0.35; especular 0.2 | Ruido escala 2500, fuerza 0.25 |
| Terciopelo | 0.90 | Sheen 1.0, rugosidad 0.3, tinte cálido; especular 0.1 | Ruido escala 60, fuerza 0.15 |
| Madera lacada | 0.45 | Capa 1.0 (rugosidad 0.04; rotor 0.12) | Anillos de onda, escala 18 |
| Papel | 0.55 a 0.85 | — | Ruido escala 1200 a 1500, fuerza 0.04 a 0.05 |
| Lino (cartas) | 0.42 a 0.60 | Capa 0.25 en el reverso | Tejido: dos ondas cruzadas, escala 260, fuerza 0.12 |
| Alfombra | 0.95 | Sheen 0.5 | Ruido escala 900, fuerza 0.2 |

En la web (three.js), la ficha llega como `MeshPhysicalMaterial` con capa (`KHR_materials_clearcoat`). El relieve procedimental no se exporta; a la distancia de la app no se nota.

## 5. Luz, cámara y render

- **Motor:** EEVEE. **Color:** AgX, aspecto "Punchy", exposición -0.5.
- **Luz:** cálida y baja. Llave en `(1.0, 0.80, 0.58)`, contraluz pequeño (área de 0.03 m en la ficha) para no lavar el fondo. Pocas luces, bien puestas. Una luz rasante o de relleno no da reflejos (`specular_factor` 0) si deja manchas en la madera.
- **Fondo:** sala casi negra y bokeh de lámparas lejanas en la escala oro, en la franja del cuadro por encima del riel o de la mesa.
- **Profundidad de campo:** f/2.2 a f/2.8, foco en el objeto principal.
- **Calidad final:** 256 muestras, profundidad de campo con jitter y overblur 40 (sin esto el bokeh sale punteado), tamaño máximo de bokeh 320.
- **Medidas:** 1920×1080 y 1080×2340. En la vertical, la parte de arriba queda libre para el logotipo y el 20% de abajo para los botones de la app.
- **Entrega:** WebP calidad 86. Respaldo 2D de modelos: 512×512 con fondo transparente, WebP calidad 88.

## 6. Presupuestos (ADR-005) y lo medido

| Concepto | Presupuesto | `ficha.glb` |
| --- | --- | --- |
| GLB por pantalla | ≤ 1.5 MB | 50,704 bytes (22,169 con gzip, 20,727 con brotli) |
| Un modelo suelto | ≤ 300 KB y ≤ 8 mil triángulos | 6,508 triángulos, 4 primitivas (cuerpo, incrustaciones, centro, tinta). La ruleta: 7,206. `tests/test_arte.py` comprueba el tope en cada GLB de `static/3d` |
| Panorama de sala (§14) | ≤ 4096 × 2048 y ≤ 600 KB, WebP | Ruleta: 3072 × 1536, 56 KB. Excepción al tope de 1024 px (D16): el salón entero en una imagen; 4096 × 2048 son 32 MB en la tarjeta del celular |
| Texturas | ≤ 1024 px, KTX2 | Ficha: ninguna, el logotipo y las marcas son geometría. Ruleta: la tira de números, 1024 × 92 en dos filas, en WebP y no en KTX2: para una sola tira no vale cargar el transcodificador de Basis. Se revisa cuando haya más texturas. `tests/test_arte.py` comprueba el tope |
| Triángulos en escena | ≤ 50 mil | 26,032 con cuatro fichas en la página de prueba. La ruleta: 7,206 del modelo más 3,968 de la esfera del salón (§12, §14) |
| Cuadros por segundo | 60 en iPhone y en Android de gama media; la app es para escritorio y para celular | **iPhone (el del dueño):** Safari dibuja a 60 como máximo, aunque la pantalla dé 120; la meta es no bajar de 60. **Falta medir la ruleta en el iPhone del dueño.**  PC del dueño (Chrome, pantalla de 144 Hz), 10-oct, con captura en la conversación con E0: de 138 a 145, que es el ritmo de su pantalla. La página dibuja un cuadro cada 6.9 ms; lo que tarda en dibujarlo no se midió, pero cabe en ese intervalo. **Falta medir en Android de gama media.** La página de prueba lleva la ficha sin comprimir (154,888 bytes), con los mismos triángulos |

## 7. Exportar para la web

1. En Blender: Archivo → Exportar → glTF 2.0 (`.glb`). Solo lo seleccionado, +Y arriba, aplicar modificadores, materiales exportados, **sin Draco**, sin cámaras ni luces. Guarda esa exportación cruda junto al `.blend`.
2. Optimiza con `assets3d/herramientas/optimizar-glb.mjs` (versiones fijas en su encabezado). El script quita escenas vacías, deja los materiales de una cara, aplica dedup, weld y prune, y comprime con **meshopt** (`EXT_meshopt_compression` y `KHR_mesh_quantization`). Con las mismas versiones, el resultado sale idéntico byte por byte.
3. Se usa meshopt y no Draco: el decodificador de meshopt es un módulo pequeño que se sirve con la app desde `static/vendor/`. Draco necesita descargar aparte un decodificador de cientos de KB.
4. Anota en la bitácora el peso en bytes, el peso con gzip y los triángulos.

## 8. Usar la ficha en la app

```ts
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
// Fichas sueltas: clona gltf.scene (trae la escala del nodo), clona los materiales y pinta por nombre.
// chip_body = color de la ficha; chip_insert = incrustaciones del canto.
```

- **Colores:** salen de los tokens de `static/css/tokens.css` (E4), nunca escritos a mano.
  - Cuerpo: lima-400, bermellón-500, oro-400 o papel.
  - Incrustaciones: papel, o tinta en la ficha papel.
- **Pilas grandes** (más de 20 fichas):
  - Usa `InstancedMesh`, **uno por primitiva**: son 4 (cuerpo, incrustaciones, centro y tinta).
  - Cada matriz de instancia debe multiplicar la matriz del nodo `ficha`, que trae la escala 0.0195 y la altura. Con la geometría sola, la ficha sale 51 veces más grande.
- **Ejemplo completo:** `docs/arte/prueba-ficha.html`.

## 9. El resultado lo decide el servidor

- Ninguna animación 3D decide nada: el servidor manda el resultado y la animación se calcula para aterrizar en él.
- **Ruleta:**
  - El rotor gira con `RIG-ruleta_rotor` alrededor del eje vertical.
  - **Referencia:** con el rotor en 0, se mide el ángulo en el plano del rotor desde su eje +X local. En Blender es positivo en sentido antihorario visto desde arriba (+Z).
  - **Posición de cada casilla:** la casilla en la posición `k` del orden de la rueda está centrada en `-2π(k + 0.5)/37`. Los números corren en sentido horario visto desde arriba.
  - **Orden de la rueda:** 0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26.
  - **Cómo aterrizar:** para dejar el número de la posición `k` bajo un marcador fijo en el ángulo `φ` (en el mundo y alrededor del centro de la rueda), el giro final del rotor es `θ = φ + 2π(k + 0.5)/37`, más vueltas completas.
  - **En three.js** (Y arriba), el mismo `θ` va en `rotation.y` con el mismo signo: el paso de Z arriba a Y arriba es un giro de -90° en X, que lleva un giro en Z a un giro en Y igual.
  - **Comprobado** en Blender para las 37 posiciones de la rueda de madera, leyendo la UV del anillo bajo cada ángulo: 0 errores. La bola del cuadro 1 está en `k = 3` (el 19). La rueda del dibujo lo comprueba `tests/test_arte.py` (`RouletteModel`): el color de cada casilla, el número sobre cada una y la bola de la animación.

## 10. Versión 2D y menos movimiento (ADR-005)

- Cada modelo en vivo tiene un `-2d.webp` por variante con la misma vista de tres cuartos.
- La pantalla **arranca en 2D** y pasa a 3D solo cuando el modelo cargó.
- Se queda en 2D si no hay WebGL, si no cargó three.js o el modelo, o si la persona pidió menos movimiento (`prefers-reduced-motion: reduce`). En ese último caso puede abrir el 3D a mano, y se ve quieto.
- Mientras se ve el 2D, el ciclo de dibujo 3D está detenido.

## 11. Imágenes 2D de la app

Lo que la app muestra como imagen fija sale de Blender: los juegos con la receta del dibujo (§13) y los fondos y los
íconos de la app con la de los cuadros (§5). La prueba `tests/test_arte.py` comprueba nombres, medidas, transparencia y peso.

| Imagen | Archivo | Medida | Presupuesto | Fondo |
| --- | --- | --- | --- | --- |
| Juego, póster | `static/casino-icons/<juego>.png` | 480 × 480 | ≤ 100 KB | Transparente: va sobre el color de su póster (`GAME_ICON` en `static/js/art.js`) |
| Juego, mosaico | `static/casino-icons/small/<juego>.png` | 128 × 128 | ≤ 15 KB | Transparente |
| Fondo de mesa | `static/renders/fondo-mesa-1920x1080.webp`, `fondo-mesa-1080x2340.webp` | las del nombre | ≤ 150 KB | Fieltro con la luz de la lámpara; la orilla cae casi a negro |
| Ícono de la app | `static/renders/icono-192.png`, `icono-512.png` | las del nombre | ≤ 100 KB | Sala oscura, sin transparencia (Android e iOS ponen blanco o negro debajo) |
| Ícono enmascarable | `static/renders/icono-maskable-512.png` | 512 × 512 | ≤ 100 KB | La ficha dentro del 70 % del lado: cabe en el círculo seguro del 80 % |
| Ícono de iOS | `static/renders/apple-touch-icon-180.png` | 180 × 180 | ≤ 100 KB | Como el 512; iOS redondea las esquinas |

**Receta de las imágenes de juego (desde el 11-oct):** la del estilo del dibujo, en la sección 13. La receta de abajo es
la de la primera prueba (luz de mesa, `J_<juego>`) y sigue siendo la de los fondos y los íconos de la app.

**Receta de la luz de mesa:**
- Cycles con fondo transparente y un plano `is_shadow_catcher` debajo: la sombra suave queda en la imagen y oscurece el color del póster. En EEVEE no hay atrapasombras.
- La misma gestión de color que los cuadros: AgX "Punchy", exposición -0.5.
- Luces escaladas al tamaño del objeto (`luces()` en `e6_util.py`): llave cálida arriba a la izquierda, cenital suave para el brillo de la laca, contraluz y relleno sin sombra.
- Cámara de 70 mm, de 34° a 58° de elevación según el objeto. El objeto ocupa del 82 % al 86 % del cuadro.
- Se renderiza a 960 px y se reduce con `assets3d/herramientas/iconos_juego.py`: Lanczos y cuantización a 256 colores con libimagequant, que respeta la transparencia de la sombra.
- Sin texto en las imágenes: la leyenda impresa de las cartas de los cuadros se quita en las de juego (`carta_as_*_sin_leyenda` en el .blend). Los números de la rueda y el índice "A" de las cartas son parte del objeto y se quedan **si el dueño lo aprueba** con la hoja de prueba; si no, se quitan igual.
- Con la luz de mesa, lima y bermellón no se usan como color de un objeto (sección 3). En el estilo del dibujo sí: es la paleta de los dibujos que eligió el dueño (§13).

## 12. Animación de los juegos

El servidor decide el resultado y la animación se calcula para caer en él (§9, D8). Cada juego tiene su objeto sobre la
mesa del club y una animación coreografiada, no simulada. La tabla de estilos por juego está en el documento
"Clique: un casino que no es casino", del dueño.

**Reglas de la casa:**
- Una cámara por juego, quieta o con un acercamiento lento.
- De 1.2 a 3 segundos por jugada; la ruleta y la rueda, hasta 4.5.
- Ganar: un destello lima (en el estilo del dibujo, sin luces: la casilla o el trazo se encienden en lima). Perder: el bermellón que se apaga.
- Con `prefers-reduced-motion: reduce`, el resultado aparece sin animación.
- Las cuentas de cada animación viven en un módulo puro, sin three.js ni DOM, con su prueba: E5 lo lleva a la app tal cual.

**Ruleta, el primer juego animado:**

| Pieza | Archivo | Lo medido |
| --- | --- | --- |
| Modelo | `static/3d/ruleta.glb` (nodos `RIG-ruleta`, `RIG-ruleta_rotor` y `GEO-ruleta_bola`) | 86,364 bytes (44,093 con gzip -9), 7,206 triángulos, 14 piezas (16 primitivas) con acabado de casino (§14, `KHR_materials_clearcoat`); tira de números en WebP de 1024 × 92 |
| Respaldo 2D | `static/3d/ruleta-sala-2d.webp` | 512 × 512, fondo transparente; sale del mismo prototipo con `?respaldo=1` |
| Escena y exportación | Escena `T_ruleta_vivo` de `juegos.blend`, armada y exportada con `assets3d/herramientas/ruleta_toon.py`, en Blender o sin abrirlo (`pip install bpy==5.2.2`; el comando está en su encabezado); cruda en `assets3d/juegos/ruleta-exportada.glb` | Las superficies salen del perfil de la animación menos un radio de bola |
| Anillo de números | `assets3d/texturas/ruleta-numeros.png`, de `assets3d/herramientas/ruleta_numeros.py` | Rojo → bermellón, negro → tinta, 0 → lima. Dos filas de 19 celdas: el tramo j (la casilla k = 36 − j) va en la celda j % 19 de la fila j // 19 |
| Sala en la web | `docs/arte/sala-ruleta.mjs` (`roomSphere`, `roomLight`, `playView`, la entrada) y `static/3d/salas/ruleta.webp` | El salón alrededor de la rueda y su luz sobre ella (§14). `docs/arte/estilo-toon.mjs` queda para ver la rueda en el estilo plano del dibujo |
| Cuentas | `docs/arte/ruleta-animacion.mjs` (`planSpin`) | `docs/arte/ruleta-animacion.test.mjs`: los 37 números, con tres marcadores y tres giros de partida, sin saltos de la bola |
| Prototipo | `docs/arte/prueba-ruleta.html` | Entras a la sala y la cámara baja a la mesa; elige un número de prueba y lo comprueba en pantalla: "Número de prueba 23 · cayó en 23 ✓". Solo dibuja mientras algo se mueve |

- **La tirada:** el marcador φ es -π/2, hacia el jugador. El rotor frena con una curva cúbica hasta θ = φ + 2π(k + 0.5)/37 más al menos una vuelta.
- **La bola:** corre en la pista contra el rotor y baja entre el 55 % y el 80 % del tiempo, con un rebote en los rombos y otro en la pared de la casilla. Desde el 80 % viaja con el rotor dentro de su casilla. Su ángulo de partida se calcula para que llegue sin saltos.
- **La rueda, simplificada para que funcione en celular** (el dueño, 11-oct: "hazla funcional y si es necesario simplifícala"): sin sombras en tiempo real (la suya viene en el panorama) y sin texturas de material; solo el anillo de números es imagen. La luz es la de la sala (§14). 7,206 triángulos, dentro del tope de 8 mil (§6). Lleva sus números porque es funcional: la regla de §11 de no poner texto es para las imágenes fijas.
- **La bola roza los trastes:** al entrar a su casilla se mete en ellos a lo más 1 mm durante menos de un cuadro (simulado con los 37 números). Los trastes son bajos (0.0505 m) para que casi no se note.
- **Fondo:** la sala de ruleta (§14): el salón del casino en un panorama, con la rueda en vivo sobre su mesa.
- **La rueda de madera de la primera prueba** queda en la escena `J_roulette` de `juegos.blend`, con sus nombres terminados en `_madera`. Ya no se exporta.

## 13. El estilo del dibujo (decisión del dueño, 11-oct)

El dueño eligió la estética de los dibujos 2D de `static/casino-icons` "pero en 3D, que se ve muy superior". Los 14
juegos y la ruleta en vivo siguen esta receta. La referencia son los dibujos originales, guardados en
`docs/arte/referencia-2d/`; la hoja `docs/arte/juegos-3d.webp` (y la página `juegos-3d.html`) los pone junto a los nuevos.

**Forma:** gorda y redondeada, de primitivas con bevel y subdivisión (`e6_toon.py`: `obj`, `cylinder`, `sphere`,
`box`, `wedge`). Los símbolos planos (palos de cartas, flechas, corona, estrella) son contornos extruidos.

**Color:** de la paleta, exacto, en dos tonos. Cada material es luz y sombra; la sombra es el tono que usa el dibujo
para dar volumen.

| Color | Luz | Sombra |
| --- | --- | --- |
| Papel (`cream`) | `#EFE6D2` | `#CFC3A8` |
| Tinta (`ink`) | `#1A1612` | `#0E0C0A` |
| Lima (`lime`) | `#C6F432` | `#9CC320` |
| Bermellón (`verm`) | `#FF4B2B` | `#D2361B` |
| Bermellón suave (`verm_soft`), los gajos claros sobre el póster bermellón | `#F2664A` | `#D24E36` |
| Fieltro (`felt`) | `#2F6B47` | `#1E3B2C` |
| Oro (`gold`) | `#FBB635` | `#D9952A` |

**En Blender** (`e6_toon.py`):
- EEVEE con fondo transparente y gestión de color **Standard**, sin AgX, para que el color salga tal cual.
- Material: Diffuse → Shader to RGB → rampa constante (corte en 0.38) → Emission.
- Un sol por escena, sin sombras, desde `(-0.40, -0.62, 0.68)`: casi todo queda en luz, como el dibujo.
- **Contorno:** casco invertido por pieza (Solidify hacia afuera, normales invertidas, material de tinta con caras
  traseras ocultas). Grueso: 2.1 % del cuadro, que a 480 px da el trazo de 10 px del dibujo.
- Las piezas de tinta y las planas y delgadas llevan `no_outline`: el casco de un disco delgado asoma por detrás como
  rayas.
- Imagen: 960 px con `juegos_toon.py` (`render_game`), y de ahí `iconos_juego.py`, igual que antes.

**En la web** (`docs/arte/estilo-toon.mjs`): el mismo sombreado con un `ShaderMaterial` (el sol de Blender pasado a
three.js y el mismo corte) y el mismo casco invertido, empujado en pantalla para que el trazo mida lo mismo cerca y
lejos. Las piezas con `no_outline` en los extras del glTF no lo llevan. Sin luces, sin sombras y sin tone mapping, y
la página solo dibuja mientras algo se mueve. La meta es 60 cuadros en un celular, que falta medir en el iPhone del
dueño (§6). Los colores de sombra aún no son tokens: `applyToon` recibe la paleta, y E5 la arma con los tokens en
cuanto E4 los agregue (petición en la bitácora).
- Las piezas escaladas en Blender llevan la escala en la malla, no en el objeto (`ball()` en `juegos_toon.py`): el
  casco se mide en el espacio del objeto y una pieza aplastada aplastaría su trazo.
- Gajos (ruleta, rueda): sin casco y separados con `wedge(..., inset=)`, para que la tinta de la base asome entre ellos
  con el mismo grueso de trazo.

**Animación:** la misma de §12. El estilo no cambia las cuentas.

## 14. Las salas: cada juego en su casino (decisión del dueño, 11-oct, D16)

"Haz los ambientes de los juegos como un casino real y que seas transportado a esas salas." Cada juego se juega dentro
de su sala, y al abrirlo entras a ella. La sala de ruleta es la muestra; las demás siguen con el mismo salón.

**El acabado:** la forma y los colores del dibujo (§13), con materiales de casino de verdad. Cada color del dibujo
tiene su acabado (`FINISH` en `ruleta_toon.py` y `juegos_premium.py`):

| Color | Acabado |
| --- | --- |
| Papel (`cream`) | marfil satinado: rugosidad 0.38, capa 0.6 |
| Tinta (`ink`) | laca negra: rugosidad 0.35, capa 1.0 |
| Bermellón (`verm`) | laca roja: rugosidad 0.32, capa 1.0 |
| Lima (`lime`) | esmalte lima, el de la marca: rugosidad 0.28, capa 1.0 |
| Oro (`gold`) | latón: metálico, rugosidad 0.28 |
| Fieltro (`felt`) | fieltro con brillo de tela |
| Anillo de números (`numbers`) | la tira de números laqueada: rugosidad 0.30, capa 1.0 |

En la ruleta: aro de marfil con filete de latón y costado de laca negra, pista negra con rombos de latón, casillas de
laca roja y negra con el 0 en esmalte lima, trastes y bordes de latón, y la torreta de latón con bolitas lima.

**El salón** (`assets3d/herramientas/sala_casino.py`, procedural, sin texturas ni modelos de terceros): alfombra con
motivo dorado, muros de nogal lacado con paneles de terciopelo y filetes de latón, techo de casetones, candiles de
cristal, apliques, columnas, una barra con botellas de luz cálida y otras mesas, cada una bajo su lámpara. El color del
terciopelo y de la alfombra cambia por sala (`THEMES`: ruleta, cartas, dados, originales). La mesa del juego queda en el
origen con su cubierta a z = 0; el piso está 78 cm abajo.

**En la web, sin rehacer el salón en tiempo real:**
- El salón es un **panorama** (equirectangular) renderizado en Cycles desde el punto donde está la cámara del juego,
  con profundidad de campo enfocada en la rueda: `static/3d/salas/<sala>.webp`. El objeto del juego no sale en el
  panorama, pero su sombra y su reflejo en el fieltro sí.
- La cámara de la web se queda en ese punto (`VIEW` en `docs/arte/sala-ruleta.mjs`): solo gira y abre o cierra el
  ángulo para cada pantalla. Así el objeto en vivo nunca se despega de su mesa.
- El objeto en vivo toma la luz del mismo panorama (mapa de entorno), de la lámpara de su mesa y de una luz suave de
  relleno (para que el marfil no se vuelva ámbar); sin sombras en tiempo real. La web le sube un poco la rugosidad a la
  capa transparente (`roomFinish`): el panorama refleja más nítido que el salón que representa. El tone mapping es el
  neutral de Khronos, que respeta el rojo, el negro y el lima. El panorama no pasa otra vez por el tone mapping: ya viene
  de Blender, con un 18 % más de luz al pasarlo a WebP (el comando está en `sala_ruleta.py`).
- **La entrada:** al abrir el juego, un telón se levanta y la cámara baja del salón (mirando arriba, ángulo abierto) a
  la mesa en 2.4 s. Con menos movimiento no hay entrada. Una tirada durante la entrada la termina.
- Medidas: la ruleta en vivo pesa 86 KB y el panorama de 3072 × 1536 en WebP, 56 KB (el salón va desenfocado y se
  comprime bien); juntos caben de sobra en el presupuesto de pantalla (§6). Un panorama no pasa de 600 KB y mide el
  doble de ancho que de alto: lo comprueba `tests/test_arte.py` (`Rooms`), igual que la cámara de la web parada donde
  Blender renderizó la sala. Con la tarjeta de video del dueño, el panorama final se renderiza a 4096 × 2048, el tope.
