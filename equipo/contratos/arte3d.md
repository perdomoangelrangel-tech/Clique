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
| Rueda de ruleta | Ø 0.83 m (tazón), rotor Ø 0.61 m | Europea, 37 casillas. |
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
- **Materiales:** `M_` y nombre en español (`M_laton`, `M_fieltro`).
  - Los de efectos emisivos llevan `FX_` y el color (`FX_bokeh_FBB635`).
  - Los de la ficha (`chip_body`, `chip_insert`, `chip_inlay`, `chip_ink`) son interfaz con la web: la app cambia su color por nombre. No se renombran.
- **Archivos:**
  - Cuadros de estilo y escenas: `assets3d/<tema>/<nn-nombre>.blend` (Git LFS), con texturas empacadas y rutas relativas (`//tex/`, salida `//render/`).
  - Modelos: `assets3d/<modelo>/<modelo>.blend` y su exportación cruda `<modelo>-exportada.glb`.
  - Renders: `docs/arte/<nn-nombre>-<ancho>x<alto>.webp` para la dirección de arte y `static/renders/` para lo que use la app.
  - Web: `static/3d/<modelo>.glb` y un respaldo 2D por variante: `static/3d/<modelo>-<variante>-2d.webp`.
  - Imágenes de juego y de la app: una sola escena de Blender por imagen, todas en `assets3d/juegos/juegos.blend` (`J_<juego>`, `F_fondo`, `I_icono`), con sus herramientas en el bloque de texto `e6_util.py` del mismo archivo, copiado en `assets3d/herramientas/e6_util.py` (si cambias uno, cambia el otro). Sección 11.

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

**Lima y bermellón** son las luces de ganar y perder y nunca decoración (ADR-005). En las fichas son el color de la ficha, que identifica su valor. No se usan para iluminar una escena ni para adornarla.

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
| Un modelo suelto | ≤ 300 KB y ≤ 8 mil triángulos | 6,508 triángulos, 4 primitivas (cuerpo, incrustaciones, centro, tinta) |
| Texturas | ≤ 1024 px, KTX2 | Ninguna: el logotipo y las marcas son geometría. |
| Triángulos en escena | ≤ 50 mil | 26,032 con cuatro fichas en la página de prueba |
| Cuadros por segundo | 60 en Android de gama media | PC del dueño (Chrome, pantalla de 144 Hz), 10-oct, con captura en la conversación con E0: de 138 a 145, que es el ritmo de su pantalla. La página dibuja un cuadro cada 6.9 ms; lo que tarda en dibujarlo no se midió, pero cabe en ese intervalo. **Falta medir en Android de gama media.** La página de prueba lleva la ficha sin comprimir (154,888 bytes), con los mismos triángulos |

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
  - **Comprobado** en Blender para las 37 posiciones, leyendo la UV del anillo bajo cada ángulo: 0 errores. La bola del cuadro 1 está en `k = 3` (el 19).

## 10. Versión 2D y menos movimiento (ADR-005)

- Cada modelo en vivo tiene un `-2d.webp` por variante con la misma vista de tres cuartos.
- La pantalla **arranca en 2D** y pasa a 3D solo cuando el modelo cargó.
- Se queda en 2D si no hay WebGL, si no cargó three.js o el modelo, o si la persona pidió menos movimiento (`prefers-reduced-motion: reduce`). En ese último caso puede abrir el 3D a mano, y se ve quieto.
- Mientras se ve el 2D, el ciclo de dibujo 3D está detenido.

## 11. Imágenes 2D de la app

Lo que la app muestra como imagen fija sale de Blender con la receta de los cuadros (sección 5), y la prueba
`tests/test_arte.py` comprueba nombres, medidas, transparencia y peso.

| Imagen | Archivo | Medida | Presupuesto | Fondo |
| --- | --- | --- | --- | --- |
| Juego, póster | `static/casino-icons/<juego>.png` | 480 × 480 | ≤ 100 KB | Transparente: va sobre el color de su póster (`GAME_ICON` en `static/js/art.js`) |
| Juego, mosaico | `static/casino-icons/small/<juego>.png` | 128 × 128 | ≤ 15 KB | Transparente |
| Fondo de mesa | `static/renders/fondo-mesa-1920x1080.webp`, `fondo-mesa-1080x2340.webp` | las del nombre | ≤ 150 KB | Fieltro con la luz de la lámpara; la orilla cae casi a negro |
| Ícono de la app | `static/renders/icono-192.png`, `icono-512.png` | las del nombre | ≤ 100 KB | Sala oscura, sin transparencia (Android e iOS ponen blanco o negro debajo) |
| Ícono enmascarable | `static/renders/icono-maskable-512.png` | 512 × 512 | ≤ 100 KB | La ficha dentro del 70 % del lado: cabe en el círculo seguro del 80 % |
| Ícono de iOS | `static/renders/apple-touch-icon-180.png` | 180 × 180 | ≤ 100 KB | Como el 512; iOS redondea las esquinas |

**Receta de las imágenes de juego:**
- Cycles con fondo transparente y un plano `is_shadow_catcher` debajo: la sombra suave queda en la imagen y oscurece el color del póster. En EEVEE no hay atrapasombras.
- La misma gestión de color que los cuadros: AgX "Punchy", exposición -0.5.
- Luces escaladas al tamaño del objeto (`luces()` en `e6_util.py`): llave cálida arriba a la izquierda, cenital suave para el brillo de la laca, contraluz y relleno sin sombra.
- Cámara de 70 mm, de 34° a 58° de elevación según el objeto. El objeto ocupa del 82 % al 86 % del cuadro.
- Se renderiza a 960 px y se reduce con `assets3d/herramientas/iconos_juego.py`: Lanczos y cuantización a 256 colores con libimagequant, que respeta la transparencia de la sombra.
- Sin texto en las imágenes: la leyenda impresa de las cartas de los cuadros se quita en las de juego (`carta_as_*_sin_leyenda` en el .blend). Los números de la rueda y el índice "A" de las cartas son parte del objeto y se quedan **si el dueño lo aprueba** con la hoja de prueba; si no, se quitan igual.
- **Lima y bermellón no se usan como color de un objeto de juego** (sección 3). Los dados son papel y oro.
