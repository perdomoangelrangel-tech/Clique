// Prueba de la animación de la ruleta: node docs/arte/ruleta-animacion.test.mjs
// La corre tests/test_arte.py. Cada regla se vio en rojo con un mutante en ruleta-animacion.mjs.
import assert from 'node:assert/strict';
import { WHEEL_ORDER, POCKETS, pocketAngle, planSpin, POCKET, TRACK } from './ruleta-animacion.mjs';

const TAU = 2 * Math.PI;
const wrap = (a) => ((a % TAU) + TAU + Math.PI) % TAU - Math.PI;    // a ∈ (-π, π]
const near = (a, b, eps, msg) => assert.ok(Math.abs(wrap(a - b)) < eps, `${msg}: ${a} vs ${b}`);
let n = 0;
const caso = (nombre, fn) => { fn(); n++; };

caso('la rueda europea: 37 casillas, cada número una vez', () => {
  assert.equal(POCKETS, 37);
  assert.deepEqual([...WHEEL_ORDER].sort((a, b) => a - b), Array.from({ length: 37 }, (_, i) => i));
});

caso('cada casilla en su ángulo del contrato (§9)', () => {
  WHEEL_ORDER.forEach((num, k) => near(pocketAngle(num), -TAU * (k + 0.5) / 37, 1e-12, `casilla ${num}`));
  assert.throws(() => pocketAngle(37));
});

// Para cada número, varios puntos de partida y marcadores: la bola acaba bajo el marcador, en la casilla del número.
for (const marker of [-Math.PI / 2, 0, 1.234]) {
  for (const rotorStart of [0, 2.5, -40.1]) {
    caso(`los 37 números aterrizan (marcador ${marker.toFixed(3)}, rotor ${rotorStart})`, () => {
      for (const number of WHEEL_ORDER) {
        const spin = planSpin({ number, marker, rotorStart });
        const end = spin.at(spin.duration);
        assert.ok(end.done);
        near(end.ball.angle, marker, 1e-9, `bola del ${number}`);
        near(end.ball.angle - end.rotor, pocketAngle(number), 1e-9, `casilla bajo la bola del ${number}`);
        assert.ok(Math.abs(end.ball.r - POCKET.r) < 1e-9 && Math.abs(end.ball.z - POCKET.z) < 1e-9, `bola en el fondo (${number})`);
        assert.ok(spin.rotorEnd - rotorStart >= TAU - 1e-9, `el rotor da al menos una vuelta (${number})`);
        // después del final, nada se mueve
        assert.deepEqual(spin.at(spin.duration + 3), end);
      }
    });
  }
}

caso('la bola empieza en la pista y nunca se teletransporta', () => {
  for (const number of WHEEL_ORDER) {
    const spin = planSpin({ number });
    const start = spin.at(0);
    assert.ok(Math.abs(start.ball.r - TRACK.r) < 1e-9, 'empieza en la pista');
    const dt = 1 / 240;
    let prev = start, worst = 0;
    for (let t = dt; t <= spin.duration + 1e-9; t += dt) {
      const cur = spin.at(t);
      const p = (s) => [s.ball.r * Math.cos(s.ball.angle), s.ball.r * Math.sin(s.ball.angle), s.ball.z];
      const [a, b] = [p(prev), p(cur)];
      worst = Math.max(worst, Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
      // el rotor nunca da marcha atrás
      assert.ok(cur.rotor >= prev.rotor - 1e-12, 'el rotor no retrocede');
      prev = cur;
    }
    // la bola corre a ~2 vueltas por segundo en una pista de 0.379 m: ~5 m/s, ~2 cm por paso de 1/240 s
    assert.ok(worst < 0.03, `salto de ${worst.toFixed(4)} m entre dos cuadros con el ${number}`);
  }
});

caso('la bola va contra el rotor al principio y con él al final', () => {
  const spin = planSpin({ number: 17 });
  const a = spin.at(0.10), b = spin.at(0.11);
  assert.ok(b.ball.angle < a.ball.angle, 'al principio gira en sentido contrario');
  assert.ok(b.rotor > a.rotor, 'el rotor gira en sentido antihorario');
  const c = spin.at(spin.tIn + 0.2), d = spin.at(spin.tIn + 0.21);
  near(d.ball.angle - d.rotor, c.ball.angle - c.rotor, 1e-12, 'en la casilla viaja con el rotor');
});

console.log(`ruleta: ${n} casos · 0 fallos`);
