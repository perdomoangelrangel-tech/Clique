// La animación de la ruleta como cuentas puras: sin three.js, sin DOM. La usa docs/arte/prueba-ruleta.html
// y la prueba docs/arte/ruleta-animacion.test.mjs; E5 la lleva a la app tal cual.
//
// El resultado lo decide el servidor (D8). Esto solo calcula cómo se mueven el rotor y la bola para que,
// al detenerse, la bola quede en la casilla de ese número, bajo un marcador fijo (equipo/contratos/arte3d.md §9):
//   · la casilla en la posición k del orden de la rueda está centrada en -2π(k + 0.5)/37 en el marco del rotor;
//   · el rotor termina en θ = φ + 2π(k + 0.5)/37 + vueltas completas, así la casilla k queda en el ángulo φ.
//
// Ángulos en radianes, en el plano de la rueda, positivos en sentido antihorario visto desde arriba
// (Blender +Z; en three.js es rotation.y con el mismo signo). Medidas en metros, con el centro de la rueda en 0.

export const WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
  22, 18, 29, 7, 28, 12, 35, 3, 26];
export const POCKETS = WHEEL_ORDER.length;
const TAU = 2 * Math.PI;

/** Where the pocket of `number` sits in the rotor's own frame. */
export function pocketAngle(number) {
  const k = WHEEL_ORDER.indexOf(number);
  if (k < 0) throw new RangeError(`la ruleta no tiene el ${number}`);
  return -TAU * (k + 0.5) / POCKETS;
}

// Medidas de la rueda, altura del centro de la bola. La rueda del dibujo (assets3d/herramientas/ruleta_toon.py, escena
// T_ruleta_vivo de juegos.blend) pone cada superficie a un radio de bola debajo de este perfil.
export const BALL_RADIUS = 0.016;
export const TRACK = { r: 0.379, z: 0.1035 };          // la pista de arriba del tazón
export const POCKET = { r: 0.244, z: 0.0565 };         // el fondo de una casilla
const PROFILE = [                                       // [radio, altura del centro de la bola] de la casilla a la pista
  [0.244, 0.0565], [0.262, 0.0640], [0.306, 0.0635], [0.310, 0.0670], [0.331, 0.0790], [0.353, 0.0890],
  [0.362, 0.0905], [0.372, 0.1005], [0.379, 0.1035],
];
const DIAMONDS = { from: 0.331, to: 0.353 };            // los rombos de latón: la bola rebota al cruzarlos

function heightAt(r) {
  if (r <= PROFILE[0][0]) return PROFILE[0][1];
  for (let i = 1; i < PROFILE.length; i++) {
    const [r1, z1] = PROFILE[i];
    if (r <= r1) {
      const [r0, z0] = PROFILE[i - 1];
      return z0 + (z1 - z0) * (r - r0) / (r1 - r0);
    }
  }
  return PROFILE[PROFILE.length - 1][1];
}

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const smooth = (x) => { const t = clamp01(x); return t * t * (3 - 2 * t); };
/** A hop: 0 outside [t0, t0 + d], a parabola of height h inside. */
const hop = (t, t0, d, h) => (t > t0 && t < t0 + d ? 4 * h * ((t - t0) / d) * (1 - (t - t0) / d) : 0);

/**
 * The whole spin for one result. Returns `at(t)` → { rotor, ball: { angle, r, z }, done } for any t in seconds.
 *
 *   number     the result the server sent (0–36)
 *   marker     φ, the world angle where the winning pocket stops (default: toward the player, -π/2)
 *   rotorStart the rotor's angle when the spin starts (keep the last one so the wheel does not jump)
 *   turns      whole turns the rotor adds on top (≥ 1)
 *   duration   seconds until everything is still
 *   ballSpeed  the ball's starting speed in turns per second, against the rotor
 */
export function planSpin({ number, marker = -Math.PI / 2, rotorStart = 0, turns = 1, duration = 4.2, ballSpeed = 2.1 }) {
  const alpha = pocketAngle(number);
  const T = duration;
  const tDrop = 0.55 * T;        // the ball leaves the track
  const tIn = 0.80 * T;          // the ball is in its pocket, carried by the rotor

  // Rotor: eases out from rotorStart to its end angle, which lands the pocket on the marker.
  const landing = marker - alpha;                                   // θ = φ + 2π(k + 0.5)/37
  const rotorEnd = landing + TAU * Math.ceil((rotorStart + TAU * turns - landing) / TAU);
  const rotorTravel = rotorEnd - rotorStart;
  const rotorAt = (t) => rotorStart + rotorTravel * (1 - (1 - clamp01(t / T)) ** 3);
  const rotorSpeedAt = (t) => (t >= T ? 0 : 3 * rotorTravel * (1 - t / T) ** 2 / T);

  // Ball, while free: starts fast against the rotor and eases into the rotor's speed by the time it is in the pocket.
  const w0 = -TAU * ballSpeed;
  const wIn = rotorSpeedAt(tIn);
  const ballSpeedAt = (t) => w0 + (wIn - w0) * smooth(t / tIn);
  // Its angle is the integral of that speed; Simpson on a fine grid, cached once per spin.
  const STEPS = 600;
  const travel = new Float64Array(STEPS + 1);
  for (let i = 1; i <= STEPS; i++) {
    const a = ((i - 1) / STEPS) * tIn, b = (i / STEPS) * tIn, m = (a + b) / 2;
    travel[i] = travel[i - 1] + (b - a) / 6 * (ballSpeedAt(a) + 4 * ballSpeedAt(m) + ballSpeedAt(b));
  }
  const travelAt = (t) => {
    const x = clamp01(t / tIn) * STEPS, i = Math.min(STEPS - 1, Math.floor(x)), f = x - i;
    return travel[i] + (travel[i + 1] - travel[i]) * f;
  };
  // Start angle chosen so that at tIn the free ball is exactly over its pocket: no jump when the rotor takes it.
  const ballStart = rotorAt(tIn) + alpha - travel[STEPS];

  function at(t) {
    const time = Math.max(0, t);
    const rotor = rotorAt(time);
    let angle, r, z;
    if (time < tIn) {
      angle = ballStart + travelAt(time);
      const fall = smooth((time - tDrop) / (tIn - tDrop));
      r = TRACK.r + (POCKET.r - TRACK.r) * fall;
      z = heightAt(r);
      // a hop when it crosses the diamonds and a smaller one at the pocket wall
      const crossing = r < DIAMONDS.to && r > DIAMONDS.from;
      const tDiamond = tDrop + 0.35 * (tIn - tDrop);
      z += hop(time, tDiamond, 0.18, 0.009) + hop(time, tDrop + 0.78 * (tIn - tDrop), 0.12, 0.005) + (crossing ? 0.001 : 0);
    } else {
      angle = rotor + alpha;
      r = POCKET.r;
      z = POCKET.z + hop(time, tIn, 0.16, 0.003);    // it settles in the pocket
    }
    return { rotor, ball: { angle, r, z }, done: time >= T };
  }

  return { at, number, marker, rotorEnd, duration: T, tDrop, tIn };
}

/** Blender (Z up) to three.js (Y up): (x, y, z) → (x, z, -y). */
export function ballPositionThree({ angle, r, z }) {
  return { x: r * Math.cos(angle), y: z, z: -r * Math.sin(angle) };
}
