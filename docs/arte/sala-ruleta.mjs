// La sala de ruleta en three.js: el panorama del salón (renderizado en Blender desde la cámara del juego), la rueda en
// vivo con su acabado de casino, y la entrada: al abrir el juego la cámara mira el salón y baja a la mesa. Sin DOM; lo
// usan docs/arte/prueba-ruleta.html y, después, la pantalla de la ruleta de la app (E5). equipo/contratos/arte3d.md §14.
//
// La cámara se queda en el punto desde el que se renderizó el panorama (VIEW): solo gira y abre o cierra el ángulo, así
// la rueda nunca se despega de su mesa, en cualquier pantalla.
import * as THREE from 'three';

// assets3d/herramientas/sala_ruleta.py: VIEW_OFFSET (Blender) = (0, -1.15, 0.80) → three.js (x, z, -y)
export const VIEW = new THREE.Vector3(0, 0.80, 1.15);
const WHEEL_RADIUS = 0.47;
const TARGET = new THREE.Vector3(0, 0.04, 0);       // el centro de la rueda, un poco arriba del fieltro

/** The room all around: an inside-out sphere with the panorama, not tone mapped again (Blender already did). */
export function roomSphere(texture) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.mapping = THREE.UVMapping;
  const geo = new THREE.SphereGeometry(50, 64, 32);
  geo.scale(-1, 1, 1);                               // seen from inside
  const mat = new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, depthWrite: false });
  const sphere = new THREE.Mesh(geo, mat);
  // three's sphere (r170) puts u = 0 at -X and u = 0.25 at +Z; Blender's equirect has +X at u = 0.5 and three's -Z
  // (Blender +Y) at u = 0.25. Mirrored by the scale and given a half turn, the sphere lines up (tests/test_arte.py
  // checks that the web camera stands where Blender rendered the room).
  sphere.rotation.y = Math.PI;
  sphere.position.copy(VIEW);                        // centred on the camera: no parallax, the room stays put
  sphere.renderOrder = -10;
  sphere.name = 'sala';
  return sphere;
}

/** The light of the room on the wheel: reflections from the panorama, plus the pendant lamp above the table. */
export function roomLight(renderer, scene, texture) {
  const env = texture.clone();
  env.mapping = THREE.EquirectangularReflectionMapping;
  env.colorSpace = THREE.SRGBColorSpace;
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(env).texture;
  scene.environmentIntensity = 0.85;
  pmrem.dispose();
  // LGT-colgante_ruleta of the frame: 0.51 m to the right of the wheel, 1.3 m above the felt
  const lamp = new THREE.SpotLight(0xffe4c8, 10, 4, 0.9, 0.7, 1.6);
  lamp.position.set(0.51, 1.3, 0);
  lamp.target.position.set(0, 0, 0);
  scene.add(lamp, lamp.target);
  // the warm room tints everything amber; a soft neutral fill keeps the ivory ivory
  scene.add(new THREE.HemisphereLight(0xfff6ea, 0x24160e, 0.5));
  return lamp;
}

/** The finish of the live wheel under the room's light: softer clear coat, so the reflections do not wash the red. */
export function roomFinish(root) {
  // the coat a little rougher than in Blender: the panorama is sharper as a reflection than the room it stands for
  root.traverse((o) => {
    if (o.isMesh && o.material && o.material.isMeshPhysicalMaterial) {
      o.material.clearcoatRoughness = Math.max(0.12, o.material.clearcoatRoughness);
      o.material.envMapIntensity = 0.9;
    }
  });
}

// The ray to the near edge of the rim, below the horizon: the wheel's lowest point on screen (with a little air).
const NEAR_EDGE = Math.atan2(VIEW.y - 0.13, VIEW.z - WHEEL_RADIUS) + THREE.MathUtils.degToRad(3);

/**
 * Where the camera looks and how wide, for a screen of `aspect` (width / height): the whole wheel fits across with a
 * margin and rests at the bottom of the free area, so the room shows above it. `inset` is the fraction of the screen
 * height that the controls cover at the bottom (on a phone).
 */
export function playView(aspect, inset = 0) {
  const dist = VIEW.distanceTo(TARGET);
  const across = 2 * Math.atan((WHEEL_RADIUS * 1.2) / dist);           // the angle the wheel needs, side to side
  const vfov = Math.max(THREE.MathUtils.degToRad(52), 2 * Math.atan(Math.tan(across / 2) / aspect));
  const below = Math.atan((1 - 2 * inset) * Math.tan(vfov / 2));       // where the free area ends, under the middle
  return { pitch: -(NEAR_EDGE - below), yaw: 0, vfov };
}

/** Where the entrance starts, for a play view `to`: looking up at the room, to the side, wider. */
export function entranceView(to) {
  return { pitch: THREE.MathUtils.degToRad(8), yaw: THREE.MathUtils.degToRad(-24), vfov: Math.min(Math.PI * 0.5, to.vfov * 1.45) };
}

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
export function blendView(a, b, t) {
  const k = ease(Math.min(1, Math.max(0, t)));
  return { pitch: a.pitch + (b.pitch - a.pitch) * k, yaw: a.yaw + (b.yaw - a.yaw) * k, vfov: a.vfov + (b.vfov - a.vfov) * k };
}

/** Puts a camera at VIEW with the given view: yaw around the vertical, then pitch, field of view in radians. */
export function applyView(camera, view) {
  camera.position.copy(VIEW);
  camera.rotation.order = 'YXZ';
  camera.rotation.set(view.pitch, view.yaw, 0);
  camera.fov = THREE.MathUtils.radToDeg(view.vfov);
  camera.updateProjectionMatrix();
}
