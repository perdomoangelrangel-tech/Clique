/**
 * Lo que comparten los ganchos: leer la entrada de Claude Code y preguntarle a git dónde
 * estamos. Las DECISIONES están en `reglas.mjs` (funciones puras, con prueba).
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

/** El JSON que Claude Code manda por stdin, o `{}` si no llega nada legible. */
export function leerEntrada() {
    try {
        return JSON.parse(readFileSync(0, 'utf8') || '{}');
    } catch {
        return {};
    }
}

/** `git …` en `cwd`, o `null` si falla. Nunca lanza: un gancho roto no debe parar la sesión. */
export function git(cwd, args, timeout = 8000) {
    try {
        return execFileSync('git', args, { cwd, encoding: 'utf8', timeout, stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    } catch {
        return null;
    }
}

/** El directorio existente más cercano (un archivo nuevo aún no existe, ni quizá su carpeta). */
export function directorioExistente(ruta) {
    let d = ruta;
    while (d && !existsSync(d)) {
        const arriba = dirname(d);
        if (arriba === d) return null;
        d = arriba;
    }
    if (!d) return null;
    try { return statSync(d).isDirectory() ? d : dirname(d); } catch { return null; }
}

/** La raíz del árbol de git que contiene `ruta`, y su rama. */
export function arbolDe(ruta) {
    const d = directorioExistente(resolve(ruta));
    if (!d) return { raiz: null, rama: null };
    const raiz = git(d, ['rev-parse', '--show-toplevel']);
    const rama = raiz ? git(raiz, ['rev-parse', '--abbrev-ref', 'HEAD']) : null;
    return { raiz, rama };
}

/**
 * Un archivo tal como está en `origin/integracion` (lo vigente para todos); si no se puede,
 * el de la rama local `integracion`, y si tampoco, el del propio árbol.
 */
export function deIntegracion(raiz, ruta) {
    return git(raiz, ['show', `origin/integracion:${ruta}`])
        ?? git(raiz, ['show', `integracion:${ruta}`])
        ?? (() => { try { return readFileSync(`${raiz}/${ruta}`, 'utf8'); } catch { return null; } })();
}
