// Optimiza un GLB exportado de Blender para la web (contratos/arte3d.md, sección 7).
//
// Uso (Node 22, en una carpeta con las dependencias instaladas):
//   npm i @gltf-transform/core@4.5.1 @gltf-transform/extensions@4.5.1 @gltf-transform/functions@4.5.1 meshoptimizer@1.3.0
//   node optimizar-glb.mjs entrada.glb salida.glb [--simplificar <error>] [--textura <px>]
//   Ficha:  node optimizar-glb.mjs assets3d/ficha/ficha-exportada.glb static/3d/ficha.glb
//   Ruleta: node optimizar-glb.mjs assets3d/juegos/ruleta-exportada.glb static/3d/ruleta.glb --simplificar 0.0004 --textura 1024
//   (con esas versiones el resultado es idéntico byte por byte)
//
// --simplificar <error>: quita triángulos con el simplificador de meshoptimizer sin pasar de ese error
//   (fracción del tamaño de cada malla). Sirve para modelos de mesa grandes; la ficha no lo usa.
// --textura <px>: reduce las texturas al lado máximo del contrato (sección 6), con sharp (npm i sharp@0.35.5).
//
// Pasos: quita escenas vacías, nombra la escena y el nodo raíz como el archivo,
// materiales de una sola cara (los modelos son cerrados), dedup + weld + prune,
// y compresión meshopt (EXT_meshopt_compression + KHR_mesh_quantization).
// No toca los nombres de material: la web cambia colores por nombre (chip_body, chip_insert).
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune, dedup, weld, meshopt, simplify, textureCompress } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';
import path from 'node:path';

const [, , entrada, salida, ...opciones] = process.argv;
const opcion = (nombre) => { const i = opciones.indexOf(nombre); return i === -1 ? null : Number(opciones[i + 1]); };
const errorSimplificar = opcion('--simplificar');
const ladoTextura = opcion('--textura');
if (!entrada || !salida) {
  console.error('Uso: node optimizar-glb.mjs entrada.glb salida.glb [--simplificar <error>] [--textura <px>]');
  process.exit(1);
}
await MeshoptEncoder.ready;
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(entrada);
const root = doc.getRoot();
const nombre = path.basename(salida, '.glb');

for (const escena of root.listScenes()) if (escena.listChildren().length === 0) escena.dispose();
const escena = root.listScenes()[0];
escena.setName(nombre);
root.setDefaultScene(escena);
for (const nodo of escena.listChildren()) if (nodo.getName().startsWith('GEO-')) nodo.setName(nombre);
for (const material of root.listMaterials()) material.setDoubleSided(false);

const pasos = [dedup(), weld()];
if (errorSimplificar) {
  await MeshoptSimplifier.ready;
  pasos.push(simplify({ simplifier: MeshoptSimplifier, ratio: 0, error: errorSimplificar, lockBorder: true }));
}
if (ladoTextura) {
  const { default: sharp } = await import('sharp');
  pasos.push(textureCompress({ encoder: sharp, resize: [ladoTextura, ladoTextura] }));
}
pasos.push(prune(), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await doc.transform(...pasos);
await io.write(salida, doc);

const triangulos = root
  .listMeshes()
  .flatMap((m) => m.listPrimitives())
  .reduce((n, p) => n + (p.getIndices() ? p.getIndices().getCount() : p.getAttribute('POSITION').getCount()) / 3, 0);
console.log(JSON.stringify({ salida, triangulos, materiales: root.listMaterials().map((m) => m.getName()) }));
