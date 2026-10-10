/**
 * LAS REGLAS DE LOS GANCHOS DE CLIQUE — funciones puras, sin git ni disco
 * ======================================================================
 *
 * Adaptadas de los ganchos de Ches-Hex. Los ganchos de Claude Code (`.claude/settings.json`)
 * llaman a `sesion.mjs` y a `permisos.mjs`; toda la decisión vive aquí para poder probarla con
 * `node herramientas/ganchos.test.mjs` sin abrir una sesión.
 *
 * QUÉ CONVIERTEN EN REGLA
 *   · quién puede editar qué            → equipo/PROPIEDAD_DE_ARCHIVOS.md
 *   · qué comandos de git no se corren  → equipo/COORDINACION.md y equipo/EQUIPO.md
 *   · la raíz de la carpeta es `main`   → nadie edita ni comitea ahí (se trabaja en `_ramas/`)
 *
 * DIFERENCIA CON CHES-HEX: aquí todas las conversaciones abren en la raíz (una sola ventana de
 * VS Code). Por eso el encargo no sale del directorio de la sesión sino del archivo que se edita
 * (`_ramas/e2-datos/...` → E2) o del `cd` del comando (`cd _ramas/e2-datos && git push`).
 *
 * LO QUE NO HACEN: no son seguridad contra quien quiera saltárselas. Son una baranda para un
 * agente de buena fe que está a punto de equivocarse. Cada bloqueo dice qué hacer en su lugar.
 */

// ─── ¿Quién soy? El encargo sale de la rama ─────────────────────────────────────────────────

/** `e2-datos` → `E2`; `integracion` → `E7`; cualquier otra (`main` incluida) → `null`. */
export function encargoDeRama(rama) {
    if (!rama) return null;
    if (rama === 'integracion') return 'E7';
    const m = /^e(\d+)-/.exec(rama);
    return m ? `E${Number(m[1])}` : null;
}

// ─── La tabla de propiedad ──────────────────────────────────────────────────────────────────

/**
 * Lee `PROPIEDAD_DE_ARCHIVOS.md`: cada fila `| \`ruta\` | dueño | nota |` y cada viñeta de la
 * «Zona prohibida». En las viñetas cuentan todas las rutas entre comillas invertidas; en las
 * filas, solo la primera.
 */
export function leerPropiedad(texto) {
    const reglas = [];
    let enZona = false;
    for (const linea of texto.split(/\r?\n/)) {
        if (/^##\s/.test(linea)) enZona = /zona prohibida/i.test(linea);
        if (enZona) {
            if (!/^\s*-\s+`/.test(linea)) continue;
            for (const r of linea.matchAll(/`([^`]+)`/g)) {
                if (/\s/.test(r[1])) continue;
                const carpeta = r[1].endsWith('/');
                const anclada = r[1].startsWith('/');
                const base = r[1].replace(/\/$/, '').replace(/^\//, '');
                // Como en .gitignore: «/» al principio o por dentro = desde la raíz;
                // sin «/» = a cualquier profundidad (`.env` también es `backend/.env`).
                const patron = anclada || base.includes('/') ? base : `**/${base}`;
                reglas.push({ patron: carpeta ? `${patron}/**` : patron, dueno: 'PROHIBIDA' });
                if (carpeta) reglas.push({ patron, dueno: 'PROHIBIDA' });
            }
            continue;
        }
        const f = /^\|\s*`([^`]+)`\s*\|\s*([^|]+)\|/.exec(linea);
        if (!f) continue;
        const d = f[2].replace(/\*/g, '').trim();
        const dueno = /^E\d+$/.test(d) ? d
            : /^compartido/i.test(d) ? 'COMPARTIDO'
                : /^due[ñn]o/i.test(d) ? 'DUENO' : null;
        if (dueno) reglas.push({ patron: f[1], dueno });
    }
    return reglas;
}

function aRegex(patron) {
    let re = '';
    for (let i = 0; i < patron.length; i++) {
        const c = patron[i];
        if (c === '*' && patron[i + 1] === '*') {
            // `**/` son cero o más carpetas enteras: `**/data` casa `data` y `x/data`, no `metadata`.
            if (patron[i + 2] === '/') { re += '(?:.*/)?'; i += 2; }
            else { re += '.*'; i++; }
        } else if (c === '*') re += '[^/]*';
        else re += c.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
    }
    return new RegExp(`^${re}$`);
}

/** Cuánto dice un patrón: la parte fija antes del primer comodín. Gana la fila más específica. */
function especificidad(patron) {
    const i = patron.search(/\*/);
    return i === -1 ? patron.length + 1000 : i;
}

/** La regla que manda sobre una ruta relativa a la raíz (con `/`), o `null`. */
export function duenoDe(ruta, reglas) {
    let mejor = null;
    for (const r of reglas) {
        if (!aRegex(r.patron).test(ruta)) continue;
        if (r.dueno === 'PROHIBIDA') return r;
        if (!mejor || especificidad(r.patron) > especificidad(mejor.patron)) mejor = r;
    }
    return mejor;
}

/**
 * ¿Se puede editar este archivo?
 *   · `rama` es la del árbol donde está el archivo (no la de la sesión).
 *   · En la raíz (`main`) no edita nadie: se trabaja en `_ramas/`.
 *   · Zona prohibida: nadie. Lo de E0 y del dueño: los agentes lo proponen en su bitácora.
 *   · Compartido: se edita. E7 en `integracion` puede tocar archivos ajenos (arreglos de fusión).
 *   · Una rama que no es de ningún encargo (la del dueño, una suelta) solo respeta la zona prohibida.
 *   · Una ruta que no está en la tabla pasa: la regla es «pregunta antes», y un gancho no sabe preguntar.
 */
export function decidirEdicion({ rama, ruta, reglas }) {
    if (ruta == null || ruta.startsWith('../') || /^[a-z]:\//i.test(ruta)) return { permitido: true };
    const r = duenoDe(ruta, reglas);
    if (r?.dueno === 'PROHIBIDA') {
        return { permitido: false, motivo: `\`${ruta}\` está en la zona prohibida (equipo/PROPIEDAD_DE_ARCHIVOS.md). No se toca; si hace falta, pídeselo al dueño.` };
    }
    if (rama === 'main') {
        return { permitido: false, motivo: `Ese archivo está en la raíz de la carpeta, que es \`main\` y no se edita. Trabaja en tu árbol: \`_ramas/<tu rama>/${ruta}\` (equipo/COORDINACION.md, «La carpeta y los árboles»).` };
    }
    const encargo = encargoDeRama(rama);
    if (!encargo || !r || r.dueno === 'COMPARTIDO' || r.dueno === encargo) return { permitido: true };
    if (r.dueno === 'E0' || r.dueno === 'DUENO') {
        const quien = r.dueno === 'E0' ? 'E0 (el cerebro)' : 'el dueño';
        return { permitido: false, motivo: `\`${ruta}\` es de ${quien}: los agentes proponen, no editan. Escribe la propuesta en tu bitácora, bajo «Peticiones».` };
    }
    if (encargo === 'E7' && rama === 'integracion') return { permitido: true };
    return {
        permitido: false,
        motivo: `\`${ruta}\` es de ${r.dueno} (fila \`${r.patron}\` de equipo/PROPIEDAD_DE_ARCHIVOS.md) y tú eres ${encargo}. Pídelo en tu bitácora (qué cambio, en qué línea y por qué) y sigue con otro entregable.`,
    };
}

// ─── Los comandos ───────────────────────────────────────────────────────────────────────────

/**
 * Parte un comando en tramos (`a && b; c | d`) y cada tramo en palabras, respetando comillas.
 * No es un intérprete de bash: basta con que el primer token de cada tramo diga qué programa es.
 */
export function tramos(comando) {
    const salida = [];
    let actual = [], palabra = '', comilla = null, hay = false;
    const cerrarPalabra = () => { if (hay) actual.push(palabra); palabra = ''; hay = false; };
    const cerrarTramo = () => { cerrarPalabra(); if (actual.length) salida.push(actual); actual = []; };
    for (let i = 0; i < comando.length; i++) {
        const c = comando[i];
        if (comilla) {
            if (c === comilla) comilla = null;
            else if (c === '\\' && comilla === '"' && i + 1 < comando.length) palabra += comando[++i];
            else palabra += c;
            continue;
        }
        if (c === '"' || c === "'") { comilla = c; hay = true; continue; }
        if (c === '\\' && i + 1 < comando.length && !/[A-Za-z]/.test(comando[i + 1])) { palabra += comando[++i]; hay = true; continue; }
        if (c === '\n' || c === ';' || c === '|' || c === '&' || c === '(' || c === ')') { cerrarTramo(); continue; }
        if (/\s/.test(c)) { cerrarPalabra(); continue; }
        palabra += c;
        hay = true;
    }
    cerrarTramo();
    // Asignaciones delante (`CI=1 python …`) y prefijos que no cambian el programa.
    return salida.map((t) => {
        let i = 0;
        while (i < t.length && (/^[A-Za-z_][A-Za-z0-9_]*=/.test(t[i]) || ['sudo', 'env', 'command', 'exec', 'time', 'nohup'].includes(t[i]))) i++;
        return t.slice(i);
    }).filter((t) => t.length);
}

/** `git -C x -c k=v --no-pager push …` → `{ args: ['push', …], dir: 'x' }`. */
function argsDeGit(t) {
    if (!/(^|[\\/])git(\.exe)?$/i.test(t[0])) return null;
    let i = 1, dir = null;
    while (i < t.length && t[i].startsWith('-')) {
        if (t[i] === '-C') { dir = t[i + 1]; i += 2; }
        else if (['-c', '--git-dir', '--work-tree', '--namespace'].includes(t[i])) i += 2;
        else i += 1;
    }
    return { args: t.slice(i), dir };
}

function bloqueo(motivo) { return { permitido: false, motivo }; }

function destinosDePush(args, rama) {
    const pos = args.filter((a) => !a.startsWith('-'));
    const refspecs = pos.slice(1);
    if (!refspecs.length) return [rama];
    return refspecs.map((r) => {
        const dst = r.includes(':') ? r.split(':').pop() : r;
        return dst.replace(/^\+/, '').replace(/^refs\/heads\//, '').replace(/^HEAD$/, rama ?? 'HEAD');
    });
}

const TOCAN_ARCHIVOS = new Set(['rm', 'mv', 'cp', 'touch', 'del', 'erase', 'rd', 'rmdir', 'ln', 'chmod',
    'tee', 'truncate', 'echo', 'printf', 'cat', 'find', 'git', 'remove-item', 'move-item', 'copy-item',
    'set-content', 'add-content', 'out-file', 'clear-content', 'new-item', 'rename-item', 'python', 'node']);
const LOCKED = /\.git[\\/]+worktrees[\\/].*locked/;

/**
 * ¿Se puede correr este comando? `ramaDe(dir)` dice la rama del árbol de un directorio (o `null`);
 * con ella se sigue el `cd` de cada tramo y el `git -C`, porque las sesiones abren en la raíz.
 *
 * Bloquea:
 *   · tocar `.git/worktrees/*\/locked`, `git worktree prune|unlock`;
 *   · `rm -rf` y borrar carpetas enteras;
 *   · en la raíz (`main`): `git commit`, `git switch`/`checkout` de rama, `git rebase`, `git reset`;
 *   · `git merge`, salvo traer `integracion` a la rama propia, y salvo E7 en `integracion`;
 *   · `git pull` sin `--ff-only` o `--rebase`;
 *   · `git push` a `main` (nadie), a `integracion` (solo E7), forzado, `--all` o `--mirror`;
 *   · comitear `.claude/settings.local.json`.
 */
export function decidirComando({ comando, cwd = '.', ramaDe = () => null, unir = (a, b) => `${a}/${b}` }) {
    let dir = cwd;
    for (const t of tramos(comando)) {
        const prog = t[0].toLowerCase().replace(/^.*[\\/]/, '').replace(/\.exe$/, '');
        if (prog === 'cd' || prog === 'pushd' || prog === 'set-location') {
            if (t[1]) dir = unir(dir, t[1]);
            continue;
        }
        if (TOCAN_ARCHIVOS.has(prog) && t.slice(1).some((a) => LOCKED.test(a))) {
            return bloqueo('Ese comando toca `.git/worktrees/*/locked`, la cerradura del árbol de otro encargo. No se toca nunca (equipo/COORDINACION.md).');
        }
        if (prog === 'rm') {
            const banderas = t.slice(1).filter((a) => a.startsWith('-'));
            const r = banderas.some((b) => (/^-[a-z]*r/i.test(b) && !b.startsWith('--')) || b === '--recursive');
            const f = banderas.some((b) => (/^-[a-z]*f/i.test(b) && !b.startsWith('--')) || b === '--force');
            if (r && f) return bloqueo('`rm -rf` no: para quitar un archivo, `rm -f <el archivo exacto>`. Si de verdad hace falta borrar una carpeta, pídeselo al dueño.');
        }
        const bajo = t.map((a) => a.toLowerCase());
        if ((prog === 'remove-item' && bajo.some((a) => a.startsWith('-r')) && bajo.some((a) => a.startsWith('-fo')))
            || ((prog === 'rd' || prog === 'rmdir') && bajo.includes('/s'))) {
            return bloqueo('Borrar una carpeta entera no: para quitar un archivo, `rm -f <el archivo exacto>`.');
        }
        const g = argsDeGit(t);
        if (!g || !g.args.length) continue;
        const aqui = g.dir ? unir(dir, g.dir) : dir;
        const rama = ramaDe(aqui);
        const encargo = encargoDeRama(rama);
        const [sub, ...args] = g.args;
        if (sub === 'worktree' && ['prune', 'unlock'].includes(args[0])) {
            return bloqueo(`\`git worktree ${args[0]}\` no: toca las cerraduras de los árboles de los demás. Si un árbol sobra, lo quita el dueño.`);
        }
        if (rama === 'main') {
            if (sub === 'commit' || sub === 'rebase' || sub === 'reset' || sub === 'cherry-pick' || sub === 'revert') {
                return bloqueo(`\`git ${sub}\` en la raíz no: la raíz es \`main\`. Haz \`cd _ramas/<tu rama> && git ${sub} …\`.`);
            }
            if ((sub === 'switch' || sub === 'checkout') && !args.includes('--')) {
                return bloqueo('Cambiar de rama en la raíz no: la raíz se queda en `main` para todos. Tu rama ya está en su árbol: `cd _ramas/<tu rama>`.');
            }
        }
        if (sub === 'merge') {
            if (args.some((a) => ['--abort', '--continue', '--quit'].includes(a))) continue;
            const ramas = args.filter((a) => !a.startsWith('-'));
            if (ramas.length === 1 && /^(origin\/)?integracion$/.test(ramas[0]) && rama !== 'integracion') continue;
            if (encargo === 'E7' && rama === 'integracion') continue;
            return bloqueo('`git merge` no. A tu rama solo se trae `integracion` (mejor: `git rebase origin/integracion`). Hacia `integracion` fusiona E7.');
        }
        if (sub === 'pull' && !args.some((a) => a === '--ff-only' || a === '--rebase' || a === '-r')) {
            return bloqueo('`git pull` es una fusión: usa `git pull --ff-only` o `git pull --rebase`.');
        }
        if (sub === 'push') {
            if (args.some((a) => a === '--force' || a === '-f' || a === '--mirror' || a === '--all')) {
                return bloqueo('`git push --force`, `--all` o `--mirror` no: reescribe o arrastra ramas ajenas. Si rebasaste tu rama, usa `--force-with-lease` solo hacia tu rama.');
            }
            if (args.filter((a) => !a.startsWith('-')).slice(1).some((r) => r.startsWith('+'))) {
                return bloqueo('Un `+` delante de la rama es un push forzado. No.');
            }
            const destinos = destinosDePush(args, rama);
            if (destinos.includes('main')) return bloqueo('A `main` no empuja nadie: entra por el PR de `integracion` que fusiona el dueño.');
            // A integracion empujan E7 (desde su árbol) y E0 (desde una rama `cerebro/*`, con las órdenes).
            if (destinos.includes('integracion') && !(encargo === 'E7' && rama === 'integracion') && !/^cerebro\//.test(rama ?? '')) {
                return bloqueo('A `integracion` solo empuja E7. Deja tu rama empujada y lista, y dilo en tu bitácora.');
            }
            if (args.some((a) => a.startsWith('--force-with-lease')) && destinos.some((d) => encargoDeRama(d) !== encargo)) {
                return bloqueo('`--force-with-lease` solo hacia tu propia rama.');
            }
        }
        if ((sub === 'add' || sub === 'commit') && g.args.some((a) => /settings\.local\.json$/.test(a))) {
            return bloqueo('`.claude/settings.local.json` no se comitea: son los permisos de esta computadora.');
        }
    }
    return { permitido: true };
}

// ─── Lo que se imprime al abrir la sesión ───────────────────────────────────────────────────

/** Las últimas `n` líneas `[E…] …` de una bitácora, recortadas. */
export function ultimosReportes(bitacora, n = 8, largo = 600) {
    const lineas = bitacora.split(/\r?\n/).map((l) => l.replace(/^\s*-\s*/, '').replace(/^`|`$/g, ''))
        .filter((l) => /^\[E\d+\]\s/.test(l));
    return lineas.slice(-n).map((l) => (l.length > largo ? `${l.slice(0, largo)} …` : l));
}

/**
 * El texto que el gancho `SessionStart` le pone delante al agente. Si la sesión abrió dentro de un
 * árbol de encargo, imprime su orden. Si abrió en la raíz (lo normal aquí), recuerda cómo leerla.
 */
export function mensajeDeSesion({ rama, encargo, ordenes, bitacora, aviso, etiqueta, tieneEtiqueta }) {
    const partes = [];
    if (aviso && aviso.trim()) partes.push(`━━ AVISO DEL CEREBRO (integracion:equipo/AVISO.md) ━━\n${aviso.trim()}\n`);
    if (!encargo) {
        partes.push(`[Clique] Esta conversación abrió en \`${rama ?? '(sin rama)'}\`, la raíz de la carpeta. Nadie edita ni comitea aquí.`);
        partes.push('Si eres un encargo (E1 a E7): tu árbol es `_ramas/<tu rama>` (créalo con `git worktree add _ramas/<tu rama> <tu rama>` la primera vez) y tu orden se lee con:');
        partes.push('  git fetch origin && git show origin/integracion:equipo/ORDENES_E<n>.md');
        partes.push('Haz todo dentro de tu árbol: `cd _ramas/<tu rama> && …`. Los ganchos saben de quién es cada archivo por el árbol donde está.');
    } else {
        partes.push(`[Clique] Eres ${encargo}, en la rama \`${rama}\`. Esto lo imprime el gancho SessionStart de .claude/settings.json.`);
        if (etiqueta && tieneEtiqueta === false) {
            partes.push(`\n⚠ Tu rama no contiene \`${etiqueta}\`, la última etiqueta de integracion. Antes de nada: \`git fetch origin && git rebase origin/integracion\`.`);
        }
        partes.push(ordenes
            ? `\n━━ Tu orden vigente (origin/integracion:equipo/ORDENES_${encargo}.md) ━━\n${ordenes.trim()}`
            : `\n⚠ No hay equipo/ORDENES_${encargo}.md en integracion. Pregúntale al dueño cuál es tu orden antes de construir.`);
    }
    const ult = ultimosReportes(bitacora ?? '');
    if (ult.length) partes.push(`\n━━ Lo último de la bitácora combinada ━━\n${ult.join('\n')}`);
    partes.push('\nLos ganchos PreToolUse impiden: editar en la raíz (`main`) o archivos de otro encargo (equipo/PROPIEDAD_DE_ARCHIVOS.md), `git merge` salvo traer integracion, push a main o integracion, push forzado, `rm -rf` y las cerraduras de los árboles. Si te bloquean, el mensaje dice qué hacer.');
    return partes.join('\n');
}
