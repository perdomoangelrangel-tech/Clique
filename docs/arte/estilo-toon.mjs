// El estilo de los dibujos de Clique en three.js (decisión del dueño, 11-oct): colores planos de la paleta en dos tonos,
// luz y sombra, y un contorno de tinta del mismo grueso en pantalla. Es lo mismo que hace assets3d/herramientas/e6_toon.py
// en Blender, así el modelo en vivo y su imagen se ven igual (equipo/contratos/arte3d.md §13).
//
// Uso:
//   import { applyToon, addOutlines } from './estilo-toon.mjs';
//   applyToon(gltf.scene, { palette });          // materiales <algo>_<color> → dos tonos de la paleta
//   const outline = addOutlines(gltf.scene);     // casco invertido de tinta, salvo piezas con extras.no_outline
//   outline.resize(renderer, px);                // al cambiar el tamaño: grueso del trazo en px CSS (antes no se ve)
//   outline.dispose();                           // al salir de la pantalla
//
// Colores: PALETTE es la tabla de equipo/contratos/arte3d.md §13, la misma de assets3d/herramientas/e6_toon.py (lo
// comprueba tests/test_arte.py). En la app, E5 pasa `palette` armada con los tokens de static/css/tokens.css en cuanto
// E4 agregue los tonos de sombra (petición en equipo/BITACORA.md); los de luz ya son tokens.
//
// Sin luces ni sombras de three.js: el tono lo da el ángulo contra una luz fija, como el sol de Blender. Por eso cuesta
// poco: dos pasadas de vértices por pieza y nada de mapas de sombra. E5 lo lleva a la app tal cual.
import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

// Paleta: el tono de luz y el de sombra de cada color (static/css/tokens.css y assets3d/herramientas/e6_toon.py)
export const PALETTE = {
  cream: ['#EFE6D2', '#CFC3A8'],
  ink: ['#1A1612', '#0E0C0A'],
  lime: ['#C6F432', '#9CC320'],
  verm: ['#FF4B2B', '#D2361B'],
  verm_soft: ['#F2664A', '#D24E36'],
  felt: ['#2F6B47', '#1E3B2C'],
  gold: ['#FBB635', '#D9952A'],
};
export const INK = '#1A1612';
// Hacia el sol de las escenas T_<juego> de Blender, (-0.40, -0.62, 0.68), pasado a three.js: (x, z, -y)
export const LIGHT = new THREE.Vector3(-0.40, 0.68, 0.62).normalize();
// En Blender la rampa corta en 0.38 con sol de 3 y ambiente de 0.25: es luz cuando el coseno pasa de ~0.08
const THRESHOLD = 0.08;
const SHADE_OF_A_PICTURE = 0.72;      // una textura en sombra: el papel en sombra entre el papel en luz, en lineal

const toonVertex = /* glsl */`
varying vec3 vNormalW;
varying vec2 vUv;
void main() {
  vUv = uv;
  vNormalW = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const toonFragment = /* glsl */`
uniform vec3 litColor;
uniform vec3 shadeColor;
uniform vec3 lightDir;
uniform float threshold;
#ifdef TOON_MAP
uniform sampler2D map;
#endif
varying vec3 vNormalW;
varying vec2 vUv;
void main() {
  vec3 c = dot(normalize(vNormalW), lightDir) > threshold ? litColor : shadeColor;
#ifdef TOON_MAP
  c *= texture2D(map, vUv).rgb;
#endif
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`;

/** Two flat tones: `lit` where the light reaches, `shade` where it does not. With `map`, the picture in both tones. */
export function toonMaterial(lit, shade, { map = null, name = '' } = {}) {
  const m = new THREE.ShaderMaterial({
    name,
    uniforms: {
      litColor: { value: new THREE.Color(map ? '#ffffff' : lit) },
      shadeColor: { value: map ? new THREE.Color().setScalar(SHADE_OF_A_PICTURE) : new THREE.Color(shade) },
      lightDir: { value: LIGHT },
      threshold: { value: THRESHOLD },
      map: { value: map },
    },
    vertexShader: toonVertex,
    fragmentShader: toonFragment,
    defines: map ? { TOON_MAP: '' } : {},
  });
  return m;
}

/** Every material named `<thing>_<colour>` gets its two tones; one with a picture keeps it. Returns the colours used. */
export function applyToon(root, { palette = PALETTE } = {}) {
  const made = new Map();
  root.traverse((o) => {
    if (!o.isMesh || o.userData.isOutline) return;
    const old = o.material;
    if (!made.has(old)) {
      const key = Object.keys(palette).find((k) => old.name.endsWith('_' + k));
      const map = old.map || old.emissiveMap || (old.uniforms && old.uniforms.map && old.uniforms.map.value) || null;
      let tones = key ? palette[key] : null;
      if (!tones && !map) {
        // un color que no es de la paleta: su propio color en luz y un paso más oscuro en sombra, nunca negro
        const c = old.color ? old.color.clone() : new THREE.Color(1, 1, 1);
        tones = [c, c.clone().multiplyScalar(SHADE_OF_A_PICTURE)];
      }
      made.set(old, toonMaterial(tones && tones[0], tones && tones[1], { map, name: old.name }));
      if (old !== made.get(old)) old.dispose();
    }
    o.material = made.get(old);
  });
  return [...new Set([...made.values()].map((m) => m.name))];
}

const outlineVertex = /* glsl */`
uniform float width;
uniform vec2 resolution;
void main() {
  vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  vec3 n = normalize(normalMatrix * normal);
  clip.xy += n.xy * width * 2.0 / resolution * clip.w;     // el mismo grueso en pantalla, cerca o lejos
  gl_Position = clip;
}`;
const outlineFragment = /* glsl */`
uniform vec3 ink;
void main() {
  gl_FragColor = vec4(ink, 1.0);
  #include <colorspace_fragment>
}`;

/** The hull keeps only the shape: vertices welded and normals averaged, so hard edges (a fret, a cap) do not split it. */
function hullGeometry(geometry) {
  const source = geometry.getAttribute('position');            // puede venir cuantizada o intercalada
  const positions = new Float32Array(source.count * 3);
  for (let i = 0; i < source.count; i++) {
    positions[3 * i] = source.getX(i); positions[3 * i + 1] = source.getY(i); positions[3 * i + 2] = source.getZ(i);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  if (geometry.index) g.setIndex(geometry.index.clone());
  const welded = mergeVertices(g, 1e-4);
  welded.computeVertexNormals();
  return welded;
}

const skip = (o) => {
  if (o.userData.isOutline || o.children.some((c) => c.userData.isOutline)) return true;   // ya tiene el suyo
  for (let p = o; p; p = p.parent) if (p.userData && p.userData.no_outline) return true;
  return false;
};

/**
 * An ink outline around every piece: a copy of its shape, pushed out along its normals by `width` screen pixels and
 * drawn from the inside (BackSide), so only the rim that sticks out shows. Pieces with extras.no_outline are left
 * alone: the ink ones (it would not show) and thin flat ones (it would show through the rim behind them).
 */
export function addOutlines(root, { color = INK } = {}) {
  const material = new THREE.ShaderMaterial({
    name: 'contorno',
    // ancho 0 hasta el primer resize(): sin la medida del lienzo, el trazo saldría gigante
    uniforms: { width: { value: 0 }, resolution: { value: new THREE.Vector2(1, 1) }, ink: { value: new THREE.Color(color) } },
    vertexShader: outlineVertex,
    fragmentShader: outlineFragment,
    side: THREE.BackSide,
  });
  const meshes = [];
  root.traverse((o) => { if (o.isMesh && !skip(o)) meshes.push(o); });
  const cache = new Map();
  const hulls = [];
  let triangles = 0;
  for (const mesh of meshes) {
    if (!cache.has(mesh.geometry)) cache.set(mesh.geometry, hullGeometry(mesh.geometry));
    const hull = new THREE.Mesh(cache.get(mesh.geometry), material);
    hull.name = mesh.name + '_contorno';
    hull.userData.isOutline = true;
    hull.renderOrder = -1;
    mesh.add(hull);
    hulls.push(hull);
    triangles += (hull.geometry.index ? hull.geometry.index.count : hull.geometry.getAttribute('position').count) / 3;
  }
  return {
    material,
    triangles,
    /** `width` in CSS pixels; the drawing buffer size of `renderer` turns it into device pixels. */
    resize(renderer, width) {
      const size = renderer.getDrawingBufferSize(new THREE.Vector2());
      material.uniforms.resolution.value.copy(size);
      material.uniforms.width.value = width * renderer.getPixelRatio();
    },
    /** Takes the outlines off and frees their memory (leaving the screen). */
    dispose() {
      for (const hull of hulls) hull.removeFromParent();
      for (const g of cache.values()) g.dispose();
      material.dispose();
      hulls.length = 0;
      cache.clear();
    },
  };
}

/** Triangles of the model itself, without the outline: the number the budget of the contract counts (§6). */
export function modelTriangles(root) {
  let n = 0;
  root.traverse((o) => {
    if (o.isMesh && !o.userData.isOutline) n += (o.geometry.index ? o.geometry.index.count : o.geometry.getAttribute('position').count) / 3;
  });
  return n;
}
