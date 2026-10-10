/**
 * Gancho PreToolUse: ¿se deja hacer esto?
 *
 *   Edit | Write | MultiEdit | NotebookEdit → ¿el archivo es de este encargo? (el encargo sale
 *                                            del árbol donde está el archivo)
 *   Bash | PowerShell                      → ¿el comando es de los prohibidos?
 *
 * Bloquea saliendo con código 2 y el motivo en stderr, que Claude Code le enseña al agente.
 * Si algo falla por dentro (no hay git, la tabla no se lee), DEJA PASAR: un gancho roto que
 * bloquea todo congela a todas las sesiones a la vez.
 */
import { relative, isAbsolute, resolve } from 'node:path';
import { leerEntrada, arbolDe, deIntegracion } from './comun.mjs';
import { leerPropiedad, decidirEdicion, decidirComando } from './reglas.mjs';

function bloquear(motivo) {
    process.stderr.write(`[gancho de Clique] ${motivo}\n`);
    process.exit(2);
}

try {
    const entrada = leerEntrada();
    const { tool_name: herramienta, tool_input: datos = {} } = entrada;
    const cwd = entrada.cwd || process.cwd();

    if (['Edit', 'Write', 'MultiEdit', 'NotebookEdit'].includes(herramienta)) {
        const archivo = datos.file_path ?? datos.notebook_path;
        if (archivo) {
            const abs = isAbsolute(archivo) ? archivo : resolve(cwd, archivo);
            const { raiz, rama } = arbolDe(abs);
            const tabla = raiz && deIntegracion(raiz, 'equipo/PROPIEDAD_DE_ARCHIVOS.md');
            if (raiz && tabla) {
                const ruta = relative(raiz, abs).split('\\').join('/');
                const d = decidirEdicion({ rama, ruta, reglas: leerPropiedad(tabla) });
                if (!d.permitido) bloquear(d.motivo);
            }
        }
    } else if (herramienta === 'Bash' || herramienta === 'PowerShell') {
        const d = decidirComando({
            comando: String(datos.command ?? ''),
            cwd,
            ramaDe: (dir) => arbolDe(dir).rama,
            unir: (a, b) => resolve(a, b),
        });
        if (!d.permitido) bloquear(d.motivo);
    }
} catch (e) {
    process.stderr.write(`[gancho de Clique] falló por dentro y dejó pasar: ${e.message}\n`);
}
process.exit(0);
