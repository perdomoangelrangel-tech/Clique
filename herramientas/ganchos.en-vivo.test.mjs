// Prueba de los ganchos de punta a punta: node herramientas/ganchos.en-vivo.test.mjs
//
// ganchos.test.mjs prueba las reglas sueltas. Esta arma una carpeta de Clique de juguete en un
// directorio temporal (raíz en `main`, árboles en `_ramas/`), le pasa a permisos.mjs y sesion.mjs
// el mismo JSON que les manda Claude Code, y mira el código de salida y el texto. Así se prueba lo
// que las reglas no ven: que el árbol se deduce bien de la ruta, que la tabla se lee de
// `integracion` y que un gancho que recibe basura deja pasar.
//
// No toca la carpeta real: todo vive en el directorio temporal y se borra al final.
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const aqui = dirname(fileURLToPath(import.meta.url));
const repo = resolve(aqui, '..');
const PERMISOS = join(aqui, 'ganchos', 'permisos.mjs');
const SESION = join(aqui, 'ganchos', 'sesion.mjs');

// realpath: en Windows el temporal puede venir con nombre corto (LEGMA~1) y git lo da largo.
const raiz = realpathSync.native(mkdtempSync(join(tmpdir(), 'clique-ganchos-')));
const git = (...args) => execFileSync('git', args, { cwd: raiz, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' });

let n = 0;
try {
    // ─── la carpeta de juguete
    git('init', '-q', '-b', 'main');
    git('config', 'user.email', 'prueba@clique.local');
    git('config', 'user.name', 'Prueba de ganchos');
    git('config', 'core.autocrlf', 'false');
    mkdirSync(join(raiz, 'equipo'), { recursive: true });
    mkdirSync(join(raiz, 'backend'), { recursive: true });
    copyFileSync(join(repo, 'equipo', 'PROPIEDAD_DE_ARCHIVOS.md'), join(raiz, 'equipo', 'PROPIEDAD_DE_ARCHIVOS.md'));
    writeFileSync(join(raiz, 'equipo', 'ORDENES_E2.md'), '# Orden de prueba para E2\n');
    writeFileSync(join(raiz, 'equipo', 'BITACORA.md'), '# Bitácora\n\n- `[E1] 10-oct · HECHO: una línea de prueba`\n');
    writeFileSync(join(raiz, 'backend', 'store.py'), '# E2\n');
    writeFileSync(join(raiz, 'backend', 'ledger.py'), '# E3\n');
    writeFileSync(join(raiz, '.gitignore'), '/_ramas/\n');
    git('add', '-A');
    git('commit', '-q', '-m', 'carpeta de juguete');
    for (const r of ['integracion', 'e2-datos', 'e3-motor']) git('branch', r);
    git('worktree', 'add', '-q', join('_ramas', 'e2-datos'), 'e2-datos');
    git('worktree', 'add', '-q', join('_ramas', 'integracion'), 'integracion');

    const gancho = (script, entrada, cwd = raiz) => {
        const r = spawnSync(process.execPath, [script], {
            cwd,
            input: typeof entrada === 'string' ? entrada : JSON.stringify({ cwd, ...entrada }),
            encoding: 'utf8',
            timeout: 30000,
        });
        return { codigo: r.status, salida: r.stdout, error: r.stderr };
    };
    const edita = (ruta, cwd) => gancho(PERMISOS, { tool_name: 'Edit', tool_input: { file_path: ruta } }, cwd);
    const corre = (comando, cwd) => gancho(PERMISOS, { tool_name: 'Bash', tool_input: { command: comando } }, cwd);
    const caso = (nombre, r, codigo, texto) => {
        assert.equal(r.codigo, codigo, `${nombre}: salió ${r.codigo}, se esperaba ${codigo}. stderr: ${r.error}`);
        if (texto) assert.match(r.error + r.salida, texto, nombre);
        n++;
    };

    // ─── editar: el encargo sale del árbol donde está el archivo
    caso('E2 edita lo suyo', edita('_ramas/e2-datos/backend/store.py'), 0);
    caso('E2 no edita lo de E3', edita('_ramas/e2-datos/backend/ledger.py'), 2, /es de E3/);
    caso('ruta absoluta, mismo trato', edita(join(raiz, '_ramas', 'e2-datos', 'backend', 'ledger.py')), 2, /es de E3/);
    caso('desde dentro del árbol, ruta relativa', edita('backend/ledger.py', join(raiz, '_ramas', 'e2-datos')), 2, /es de E3/);
    caso('la raíz es main: nadie edita', edita('backend/store.py'), 2, /raíz/);
    caso('las órdenes son de E0', edita('_ramas/e2-datos/equipo/ORDENES_E2.md'), 2, /E0/);
    caso('la bitácora es compartida', edita('_ramas/e2-datos/equipo/BITACORA.md'), 0);
    caso('archivo nuevo en carpeta que no existe', edita('_ramas/e2-datos/backend/datos/pg/nuevo.py'), 0);
    caso('E7 en integracion arregla una fusión', edita('_ramas/integracion/backend/ledger.py'), 0);
    caso('zona prohibida, para todos', edita('_ramas/integracion/.env'), 2, /zona prohibida/);
    caso('fuera de la carpeta: no es asunto del gancho', edita(join(tmpdir(), 'otra-cosa.txt')), 0);

    // ─── comandos: se sigue el cd y el -C
    caso('push a main', corre('cd _ramas/e2-datos && git push origin main'), 2, /main/);
    caso('push a su rama', corre('cd _ramas/e2-datos && git push origin e2-datos'), 0);
    caso('push a integracion desde un encargo', corre('cd _ramas/e2-datos && git push origin integracion'), 2, /E7/);
    caso('E7 empuja integracion', corre('cd _ramas/integracion && git push origin integracion cimiento-2'), 0);
    caso('fusionar otra rama', corre('git -C _ramas/e2-datos merge e3-motor'), 2, /merge/);
    caso('E7 fusiona sin comitear', corre('cd _ramas/integracion && git merge --no-ff --no-commit origin/e2-datos'), 0);
    caso('commit en la raíz', corre('git commit -m x'), 2, /raíz/);
    caso('rm -rf', corre('rm -rf _ramas/e2-datos'), 2, /rm -rf/);

    // ─── un gancho que recibe basura deja pasar (si no, congela todas las sesiones)
    caso('entrada ilegible', gancho(PERMISOS, 'esto no es json'), 0);

    // ─── el mensaje de inicio
    const enArbol = gancho(SESION, { hook_event_name: 'SessionStart' }, join(raiz, '_ramas', 'e2-datos'));
    caso('inicio en el árbol de E2', enArbol, 0);
    assert.match(enArbol.salida, /Eres E2/);
    assert.match(enArbol.salida, /# Orden de prueba para E2/, 'la orden se lee de integracion');
    assert.match(enArbol.salida, /\[E1\] 10-oct/, 'y lo último de la bitácora');
    const enRaiz = gancho(SESION, { hook_event_name: 'SessionStart' });
    caso('inicio en la raíz', enRaiz, 0);
    assert.match(enRaiz.salida, /ORDENES_E<n>\.md/);
} finally {
    try { execFileSync('git', ['worktree', 'remove', '--force', join('_ramas', 'e2-datos')], { cwd: raiz, stdio: 'ignore' }); } catch { /* se borra igual */ }
    try { execFileSync('git', ['worktree', 'remove', '--force', join('_ramas', 'integracion')], { cwd: raiz, stdio: 'ignore' }); } catch { /* se borra igual */ }
    rmSync(raiz, { recursive: true, force: true });
}

console.log(`ganchos en vivo: ${n} casos · 0 fallos`);
