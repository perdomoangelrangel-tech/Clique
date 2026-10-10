/**
 * Gancho SessionStart: al abrir o reanudar una conversación, le pone delante al agente lo que
 * tiene que saber. Si abrió dentro de un árbol de encargo, su orden; si abrió en la raíz (lo
 * normal en Clique, una sola ventana), cómo leerla. Siempre, el aviso del cerebro si lo hay y lo
 * último de la bitácora combinada.
 *
 * Nunca falla hacia fuera: si no puede leer algo, lo dice en el texto.
 */
import { leerEntrada, arbolDe, deIntegracion, git } from './comun.mjs';
import { encargoDeRama, mensajeDeSesion } from './reglas.mjs';

try {
    const entrada = leerEntrada();
    const { raiz, rama } = arbolDe(entrada.cwd || process.cwd());
    if (raiz) git(raiz, ['fetch', 'origin', 'integracion', '--quiet'], 10000);
    const encargo = encargoDeRama(rama);
    let etiqueta = null, tieneEtiqueta;
    if (raiz && encargo) {
        etiqueta = (git(raiz, ['tag', '-l', 'cimiento-*', '--sort=-v:refname']) ?? '').split('\n')[0] || null;
        if (etiqueta) tieneEtiqueta = git(raiz, ['merge-base', '--is-ancestor', etiqueta, 'HEAD']) !== null;
    }
    process.stdout.write(`${mensajeDeSesion({
        rama,
        encargo,
        ordenes: raiz && encargo ? deIntegracion(raiz, `equipo/ORDENES_${encargo}.md`) : null,
        bitacora: raiz ? (deIntegracion(raiz, 'equipo/BITACORA_COMBINADA.md') ?? deIntegracion(raiz, 'equipo/BITACORA.md') ?? '') : '',
        aviso: raiz ? deIntegracion(raiz, 'equipo/AVISO.md') : null,
        etiqueta,
        tieneEtiqueta,
    })}\n`);
} catch (e) {
    process.stdout.write(`[Clique] El gancho de inicio falló (${e.message}). Lee tu orden a mano: git fetch origin && git show origin/integracion:equipo/ORDENES_E<n>.md\n`);
}
process.exit(0);
