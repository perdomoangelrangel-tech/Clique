# OT-006 — Dirección de arte del casino premium en Blender

- **Fase:** 0
- **Agente:** E6 · Arte 3D (la ejecuta E0, el cerebro, con el conector de Blender)
- **Rama:** `ot/006-direccion-de-arte`
- **Depende de:** —. Usa los valores de color de OT-003 (están en esa orden aunque no esté fusionada).
- **Contratos que usa:** ADR-005, valores de color de OT-003
- **Contratos que crea:** `coordinacion/contratos/arte3d.md`

## Objetivo

Fijar cómo se ve el "club privado de cartas" de Clique antes de construir pantallas: tres cuadros de estilo renderizados en Blender, una ficha de casino lista para la web dentro de presupuesto, y la especificación que seguirán todos los modelos.

## Contexto

Lee ADR-005 completo. La interfaz es papel impreso sobre una mesa 3D real. Referencia de la app actual: `legacy/clique/static/casino-icons/` (íconos planos de cada juego) y las capturas en `legacy/clique/docs/screenshots/`. No copies el arte de ningún casino, marca o juego existente: todo es original.

## Alcance

**Incluye**

- `assets3d/estilo/`: archivos `.blend` (con Git LFS: `git lfs track "*.blend"`) de tres cuadros de estilo:
  1. **Mesa de ruleta** vista a 3/4 con luz cálida baja, fieltro, madera lacada, latón y un boleto de papel de Clique encima.
  2. **Héroe de ficha y carta:** una ficha de cerámica de Clique (canto con marcas, centro con el logotipo) y dos cartas con acabado de lino.
  3. **Lobby:** un fragmento del lobby con tres "pósters" de juego como objetos físicos.
- Renders de cada cuadro en `docs/arte/` a 1920×1080 y en recorte de celular 1080×2340, en WebP.
- **Ficha lista para la web:** `apps/web/public/3d/ficha.glb` con Draco o meshopt y texturas KTX2 de hasta 1024 px. Peso máximo 300 KB, hasta 8 mil triángulos. Incluye 4 variantes de color de la paleta (lima, bermellón, oro, papel) como materiales o con color por instancia.
- Una página de prueba mínima (`docs/arte/prueba-ficha.html` o una ruta temporal si OT-002 ya está en `main`) que muestre la ficha girando con three.js y el contador de cuadros por segundo.
- `coordinacion/contratos/arte3d.md`: escala (1 unidad = 1 cm), orientación, nombres de objetos y materiales, recetas PBR (fieltro, terciopelo, latón, cerámica, papel, lino, madera lacada) con sus valores, presupuestos de ADR-005, cómo exportar (ajustes de glTF), y cómo nombrar renders.

**No incluye**

- Modelar todos los juegos (cada juego tendrá su orden en la Fase 2).
- Integrar el 3D en pantallas de producto.

## Archivos y carpetas permitidos

`assets3d/`, `docs/arte/`, `apps/web/public/3d/`, `.gitattributes` (solo las líneas de Git LFS), `coordinacion/contratos/arte3d.md`, `coordinacion/bitacoras/OT-006.md`.

## Criterios de aceptación

- [ ] Los tres cuadros están renderizados en las dos medidas y se ven en la bitácora.
- [ ] Los colores usados salen de la paleta v2 (anota qué valor usa cada material).
- [ ] `ficha.glb` pesa 300 KB o menos y tiene 8 mil triángulos o menos (anota los números exactos).
- [ ] La página de prueba muestra la ficha a 60 cuadros por segundo en Chrome de escritorio y anota cuántos da en el modo de celular de las herramientas de Chrome con CPU 4× más lenta.
- [ ] Los `.blend` están en Git LFS (`git lfs ls-files` los lista).
- [ ] `contratos/arte3d.md` existe con estado "Propuesto".

## Notas del cerebro

- El conector de Blender vive en la computadora del dueño. Si este agente no lo tiene configurado, el cerebro puede ejecutar la parte de Blender y dejar los archivos en la rama; anótalo en la bitácora.
- Premium no es recargado: pocos materiales muy bien hechos, luz cálida y sombras suaves en la mesa; el papel de la interfaz conserva sus sombras duras.

## Correcciones

(Vacío.)
