# ADR-005 — Dirección de arte: casino privado premium, hecho en Blender

- **Estado:** Aceptado por el dueño el 2026-10-10
- **Fecha:** 2026-10-10

## Contexto

El dueño quiere que Clique se sienta como un casino de verdad, premium en todo, algo que pocas apps sociales tienen. La identidad actual ("sala de cartas clandestina con boleto impreso", negro cálido, papel crema, lima y bermellón) se queda. Se usará Blender para la estética y los juegos.

El reto es doble: que se vea de lujo y que corra fluido en celulares de gama media, que son la mayoría en México.

## Decisión

**El concepto: un club privado de cartas.** Dos materiales conviven:

- **La mesa (los juegos):** escenas 3D hechas en Blender con materiales reales. Fieltro, terciopelo, madera lacada, latón, fichas de cerámica con canto de colores, cartas con acabado de lino y luz cálida de lámpara baja.
- **El boleto (la interfaz):** papel crema impreso, tipografía precisa y números en monoespaciada. Encima de la mesa, como un boleto real sobre un fieltro real. Ese contraste es lo que nadie más tiene.

**Color:** la paleta v2 se respeta. Negro cálido para la sala, papel para boletos y cartas, fieltro para las mesas y oro para el latón y lo premium. Lima y bermellón son las luces de ganar y perder, nunca decoración.

**Cómo llega el 3D a la app** (de lo más ligero a lo más pesado):

1. **Imágenes renderizadas** (WebP o AVIF) para el lobby, íconos de juego, cosméticos, rangos e insignias. Es la mayoría del arte.
2. **Secuencias cortas o video** (WebM o MP4, en bucle) para celebraciones, gran premio y transiciones.
3. **Modelos en vivo** (GLB comprimido con Draco o meshopt, texturas KTX2, en three.js o React Three Fiber) solo donde la interacción lo pide: rueda de ruleta, dados, Plinko, Crash, fichas que se apilan, cartas que se reparten.

**Presupuestos por pantalla de juego en celular:** GLB hasta 1.5 MB, texturas hasta 1024 px, hasta 50 mil triángulos en escena, 60 cuadros por segundo en un Android de gama media. Si no hay WebGL o la persona pidió menos movimiento, se muestra una versión 2D con las imágenes renderizadas.

**El resultado manda:** el servidor decide primero y la animación aterriza en ese resultado. Ninguna física 3D decide nada.

**Dónde viven los archivos:** los `.blend` en `assets3d/` con Git LFS. Las exportaciones listas para la web en `static/3d/` y `static/renders/`. La especificación (nombres, escalas, materiales, presupuestos, cómo exportar) es el contrato `equipo/contratos/arte3d.md`. El 10 de octubre el dueño aprobó los cuadros de `docs/arte/` como la estética de toda la app.

**Quién:** el rol `arte3d`. Lo puede ejecutar el cerebro con el conector de Blender de la computadora del dueño, o un agente en VS Code que tenga Blender configurado.

## Consecuencias

- Hace falta Git LFS para los `.blend`; el plan gratuito de GitHub incluye almacenamiento limitado, así que solo se suben los archivos fuente finales.
- Cada juego tiene dos versiones visuales (3D y 2D de respaldo); el motor y el servidor son los mismos.
- El QA visual incluye rendimiento: cuadros por segundo y peso de descarga en celular.
