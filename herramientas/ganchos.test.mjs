// Prueba de los ganchos de Clique: node herramientas/ganchos.test.mjs
// Cada regla de reglas.mjs tiene al menos un caso que la cumple y otro que la rompe.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { encargoDeRama, leerPropiedad, duenoDe, decidirEdicion, decidirComando, tramos, mensajeDeSesion, ultimosReportes } from './ganchos/reglas.mjs';

const aqui = dirname(fileURLToPath(import.meta.url));
const tabla = readFileSync(resolve(aqui, '../equipo/PROPIEDAD_DE_ARCHIVOS.md'), 'utf8');
const reglas = leerPropiedad(tabla);
let n = 0;
const caso = (nombre, fn) => { fn(); n++; };

// ─── encargo por rama
caso('ramas', () => {
    assert.equal(encargoDeRama('e2-datos'), 'E2');
    assert.equal(encargoDeRama('e10-algo'), 'E10');
    assert.equal(encargoDeRama('integracion'), 'E7');
    assert.equal(encargoDeRama('main'), null);
    assert.equal(encargoDeRama('cerebro/x'), null);
    assert.equal(encargoDeRama(null), null);
});

// ─── la tabla real
const dueno = (ruta) => duenoDe(ruta, reglas)?.dueno ?? null;
caso('tabla: dueños', () => {
    assert.ok(reglas.length > 60, `pocas reglas: ${reglas.length}`);
    assert.equal(dueno('server.py'), 'E1');
    assert.equal(dueno('backend/assets.py'), 'E1');
    assert.equal(dueno('backend/store.py'), 'E2');
    assert.equal(dueno('backend/datos/pg.py'), 'E2');
    assert.equal(dueno('supabase/migrations/001.sql'), 'E2');
    assert.equal(dueno('backend/ledger.py'), 'E3');
    assert.equal(dueno('backend/poker.py'), 'E3');
    assert.equal(dueno('tests/test_poker.py'), 'E3');
    assert.equal(dueno('tests/test_deploy.py'), 'E1');
    assert.equal(dueno('tests/test_store.py'), 'E2');
    assert.equal(dueno('tests/test_layout.py'), 'E5');
    assert.equal(dueno('static/css/tokens.css'), 'E4');
    assert.equal(dueno('static/js/theme.js'), 'E4');
    assert.equal(dueno('static/js/views/diseno.js'), 'E4');
    assert.equal(dueno('static/js/views/markets.js'), 'E5');
    assert.equal(dueno('static/js/app.js'), 'E5');
    assert.equal(dueno('static/3d/ficha.glb'), 'E6');
    assert.equal(dueno('assets3d/ficha/ficha.blend'), 'E6');
    assert.equal(dueno('equipo/ORDENES_E1.md'), 'E0');
    assert.equal(dueno('equipo/COORDINACION.md'), 'E0');
    assert.equal(dueno('.claude/settings.json'), 'E0');
    assert.equal(dueno('equipo/BITACORA.md'), 'COMPARTIDO');
    assert.equal(dueno('equipo/VERIFICADO.md'), 'E7');
});
caso('tabla: zona prohibida', () => {
    for (const r of ['.env', 'backend/.env', '.env.local', 'data/db.json', 'data', '.claude/settings.local.json', '.git/config']) {
        assert.equal(dueno(r), 'PROHIBIDA', r);
    }
    assert.notEqual(dueno('docs/datos/modelo.md'), 'PROHIBIDA');
    assert.notEqual(dueno('.env.example'), 'PROHIBIDA');
    // `/data/` es solo la de la raíz; `**/` son carpetas enteras, no un pedazo de nombre.
    for (const r of ['tests/data/caso.json', 'supabase/seed_data/x.sql', 'backend/metadata.py', 'static/js/data.js']) {
        assert.notEqual(dueno(r), 'PROHIBIDA', r);
    }
    assert.equal(dueno('tests/test_metadata.py'), 'E3');
    assert.equal(dueno('backend/.env'), 'PROHIBIDA', '.env a cualquier profundidad');
});

// ─── editar
const edita = (rama, ruta) => decidirEdicion({ rama, ruta, reglas }).permitido;
caso('editar', () => {
    assert.equal(edita('main', 'backend/store.py'), false, 'en la raíz no edita nadie');
    assert.equal(edita('e2-datos', 'backend/store.py'), true);
    assert.equal(edita('e3-motor', 'backend/store.py'), false);
    assert.equal(edita('e3-motor', 'backend/ledger.py'), true);
    assert.equal(edita('e5-frontend', 'static/js/theme.js'), false);
    assert.equal(edita('e4-diseno', 'static/js/theme.js'), true);
    assert.equal(edita('e1-plataforma', 'equipo/ORDENES_E1.md'), false, 'lo de E0 se propone');
    assert.equal(edita('e1-plataforma', 'equipo/BITACORA.md'), true, 'compartido');
    assert.equal(edita('integracion', 'backend/store.py'), true, 'E7 arregla fusiones');
    assert.equal(edita('integracion', '.env'), false, 'la zona prohibida es para todos');
    assert.equal(edita('e2-datos', 'algo/nuevo/sin-dueno.txt'), true, 'sin fila: pasa');
    assert.equal(edita('una-rama-suelta', 'backend/store.py'), true, 'sin encargo: solo zona prohibida');
    assert.equal(edita('e2-datos', '../fuera.txt'), true);
});

// ─── comandos
const ramas = { '/r': 'main', '/r/cerebro': 'cerebro/ronda-1', '/r/_ramas/e2-datos': 'e2-datos', '/r/_ramas/e3-motor': 'e3-motor', '/r/_ramas/integracion': 'integracion' };
const unir = (a, b) => (b.startsWith('/') ? b : `${a}/${b}`.replace(/\/\.\//g, '/'));
const corre = (comando, cwd = '/r') => decidirComando({ comando, cwd, ramaDe: (d) => ramas[d] ?? null, unir }).permitido;
caso('comandos: push', () => {
    assert.equal(corre('cd _ramas/e2-datos && git push origin e2-datos'), true);
    assert.equal(corre('cd _ramas/e2-datos && git push'), true);
    assert.equal(corre('cd _ramas/e2-datos && git push origin main'), false);
    assert.equal(corre('cd _ramas/e2-datos && git push origin HEAD:main'), false);
    assert.equal(corre('git -C _ramas/e2-datos push origin main'), false);
    assert.equal(corre('cd _ramas/e2-datos && git push origin integracion'), false);
    assert.equal(corre('cd _ramas/integracion && git push origin integracion'), true);
    assert.equal(corre('cd _ramas/e2-datos && git push --force origin e2-datos'), false);
    assert.equal(corre('cd _ramas/e2-datos && git push origin +e2-datos'), false);
    assert.equal(corre('cd _ramas/e2-datos && git push --force-with-lease origin e2-datos'), true);
    assert.equal(corre('cd _ramas/e2-datos && git push --force-with-lease origin e3-motor'), false);
    assert.equal(corre('git push origin main'), false, 'desde la raíz tampoco');
    assert.equal(corre('git push origin cerebro/ronda-1:integracion', '/r/cerebro'), true, 'E0 publica órdenes desde cerebro/*');
    assert.equal(corre('git push origin cerebro/ronda-1:main', '/r/cerebro'), false, 'ni E0 empuja a main');
});
caso('comandos: la raíz es main', () => {
    assert.equal(corre('git commit -m x'), false);
    assert.equal(corre('cd _ramas/e2-datos && git commit -m x'), true);
    assert.equal(corre('git switch e2-datos'), false);
    assert.equal(corre('git checkout e2-datos'), false);
    assert.equal(corre('git checkout -- static/index.html'), true);
    assert.equal(corre('git fetch origin && git worktree add _ramas/e2-datos e2-datos'), true);
    assert.equal(corre('git status'), true);
    assert.equal(corre('git rebase origin/integracion'), false);
    assert.equal(corre('cd _ramas/e3-motor && git rebase origin/integracion'), true);
});
caso('comandos: fusiones y pull', () => {
    assert.equal(corre('cd _ramas/e2-datos && git merge origin/integracion'), true);
    assert.equal(corre('cd _ramas/e2-datos && git merge e3-motor'), false);
    assert.equal(corre('cd _ramas/integracion && git merge --no-ff origin/e2-datos'), true);
    assert.equal(corre('cd _ramas/e2-datos && git merge --abort'), true);
    assert.equal(corre('cd _ramas/e2-datos && git pull'), false);
    assert.equal(corre('cd _ramas/e2-datos && git pull --rebase'), true);
    assert.equal(corre('git pull --ff-only'), true);
});
caso('comandos: borrar y cerraduras', () => {
    assert.equal(corre('rm -rf _ramas/e3-motor'), false);
    assert.equal(corre('rm -fr static'), false);
    assert.equal(corre('rm -f _ramas/e2-datos/basura.txt'), true);
    assert.equal(corre('Remove-Item -Recurse -Force static'), false);
    assert.equal(corre('rmdir /s static'), false);
    assert.equal(corre('git worktree prune'), false);
    assert.equal(corre('git worktree unlock _ramas/e3-motor'), false);
    assert.equal(corre('rm .git/worktrees/e3-motor/locked'), false);
    assert.equal(corre('echo "no toques .git/worktrees/x/locked" >> nota.md'), false, 'echo cuenta como tocar');
    assert.equal(corre('cd _ramas/e2-datos && git add .claude/settings.local.json'), false);
});
caso('tramos', () => {
    assert.deepEqual(tramos('CI=1 python -m unittest && git status'), [['python', '-m', 'unittest'], ['git', 'status']]);
    assert.deepEqual(tramos('git commit -m "a && b"'), [['git', 'commit', '-m', 'a && b']]);
    assert.deepEqual(tramos('cd _ramas\\e2-datos'), [['cd', '_ramas\\e2-datos']]);
});

// ─── el mensaje de inicio
caso('sesión', () => {
    const raiz = mensajeDeSesion({ rama: 'main', encargo: null, ordenes: null, bitacora: '' });
    assert.match(raiz, /ORDENES_E<n>\.md/);
    assert.match(raiz, /_ramas/);
    const e2 = mensajeDeSesion({ rama: 'e2-datos', encargo: 'E2', ordenes: '# Orden de E2', bitacora: '- `[E1] 10-oct · HECHO: algo`', aviso: 'ALTO: nadie migra hoy' });
    assert.match(e2, /Eres E2/);
    assert.match(e2, /# Orden de E2/);
    assert.match(e2, /ALTO: nadie migra hoy/);
    assert.match(e2, /\[E1\] 10-oct/);
    assert.match(mensajeDeSesion({ rama: 'e2-datos', encargo: 'E2', ordenes: null, bitacora: '' }), /No hay equipo\/ORDENES_E2/);
    assert.match(mensajeDeSesion({ rama: 'e2-datos', encargo: 'E2', ordenes: 'x', bitacora: '', etiqueta: 'cimiento-2', tieneEtiqueta: false }), /cimiento-2/);
    assert.deepEqual(ultimosReportes('nada\n[E3] a\n- `[E4] b`\n', 5), ['[E3] a', '[E4] b']);
});

console.log(`ganchos: ${n} casos · 0 fallos`);
