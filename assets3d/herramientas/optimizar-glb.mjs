// Optimiza un GLB exportado de Blender para la web (contratos/arte3d.md, sección 7).
//
// Uso (Node 22, en una carpeta con las dependencias instaladas):
//   npm i @gltf-transform/core@4.5.1 @gltf-transform/extensions@4.5.1 @gltf-transform/functions@4.5.1 meshoptimizer@1.3.0
//   node optimizar-glb.mjs entrada.glb salida.glb
//   Ficha: node optimizar-glb.mjs assets3d/ficha/ficha-exportada.glb apps/web/public/3d/ficha.glb
//   (con esas versiones el resultado es idéntico byte por byte)
//
// Pasos: quita escenas vacías, nombra la escena y el nodo raíz como el archivo,
// materiales de una sola cara (los modelos son cerrados), dedup + weld + prune,
// y compresión meshopt (EXT_meshopt_compression + KHR_mesh_quantization).
// No toca los nombres de material: la web cambia colores por nombre (chip_body, chip_insert).
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune, dedup, weld, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import path from 'node:path';

const [, , entrada, salida] = process.argv;
if (!entrada || !salida) {
  console.error('Uso: node optimizar-glb.mjs entrada.glb salida.glb');
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

await doc.transform(dedup(), weld(), prune(), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await io.write(salida, doc);

const triangulos = root
  .listMeshes()
  .flatMap((m) => m.listPrimitives())
  .reduce((n, p) => n + (p.getIndices() ? p.getIndices().getCount() : p.getAttribute('POSITION').getCount()) / 3, 0);
console.log(JSON.stringify({ salida, triangulos, materiales: root.listMaterials().map((m) => m.getName()) }));
