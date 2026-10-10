# OT-001 — Clonar el repositorio y verificar la computadora del dueño

- **Fase:** 0
- **Agente:** E1 · Plataforma
- **Rama:** `ot/001-verificacion`
- **Depende de:** —
- **Contratos que usa:** —
- **Contratos que crea:** —

## Objetivo

Que la computadora del dueño tenga el repositorio clonado y todas las herramientas listas, que la app actual corra y pase sus pruebas desde `legacy/clique`, y que el primer PR del proyecto (esta bitácora) quede abierto en GitHub.

## Contexto

El cerebro ya creó el repositorio en GitHub (https://github.com/perdomoangelrangel-tech/Clique) con la app actual en `legacy/clique`, la huella `legacy/clique.sha256` y todo el sistema de agentes. El dueño ya lo clonó en `C:\Users\legma\Downloads\Clique\Clique-1` (carpeta principal); cada orden trabaja en su subcarpeta `trabajo\OT-NNN` dentro de esa misma carpeta (todos los agentes en una sola ventana de VS Code, un chat por agente). Lo demás de `Downloads\Clique` (`clique/`, `_viejo/`, `_ot006/`) no se toca.

## Alcance

**Incluye**

- Comprobar y anotar las versiones de: `git`, `node` (debe ser 22), `pnpm`, `python` (3.10 o más), `gh` (opcional). Si falta algo, explícale al dueño cómo instalarlo y espera.
- Configurar git para este repo: `git config core.autocrlf false` (el repo trae `.gitattributes` con los finales de línea correctos) y `user.name` / `user.email` si no están.
- Comprobar que el legacy está intacto: en Git Bash, `cd legacy/clique && sha256sum -c --quiet ../clique.sha256`.
- Correr la app actual (`cd legacy/clique && python server.py`) y confirmar que abre en http://localhost:3000. Detenerla después.
- Correr las pruebas de la app actual y anotar cuántas corrieron, cuántas se omitieron y el tiempo.
- Si `gh` está disponible, iniciar sesión (`gh auth login`, lo hace el dueño) para que los agentes abran PR solos.
- Crear la bitácora `coordinacion/bitacoras/OT-001.md` con todo lo anterior y abrir el PR `OT-001: verificación del entorno`.

**No incluye**

- Cambiar cualquier archivo fuera de la bitácora.
- Instalar Supabase CLI o Docker (OT-004).

## Archivos y carpetas permitidos

`coordinacion/bitacoras/OT-001.md`.

## Criterios de aceptación

- [ ] La bitácora lista las versiones de cada herramienta.
- [ ] `sha256sum -c` no reporta ningún archivo distinto.
- [ ] Las pruebas del legacy pasan (anota "Ran N tests" y "OK"). Si alguna falla solo por Windows, anótala como aviso para `@motor` y `@plataforma`, sin arreglarla.
- [ ] El PR está abierto en GitHub (o, si no hay `gh`, la rama está subida y el dueño abrió el PR desde la página).

## Cómo verificar

```bash
git --version && node --version && pnpm --version && python --version
cd legacy/clique && sha256sum -c --quiet ../clique.sha256 && echo "legacy intacto"
python -m unittest discover -s tests -t .
```

## Notas del cerebro

- Es la primera orden: sirve para probar el ciclo completo (`/orden`, `/bitacora`, `/entregar`, PR, `/cerrar`). Si algo del ciclo no funciona en Windows, anótalo con detalle: es lo más valioso de esta orden.
- Las pruebas del navegador del legacy se omiten si no hay Chrome; está bien.

## Correcciones

**2026-10-10 · E0 — Ya hay clon y los demás agentes trabajan a la vez**

- No vuelvas a clonar: el repositorio ya está en `Downloads\Clique\Clique-1`. Anota en la bitácora la ruta y `git log --oneline -1` de `main`.
- Los demás agentes (E1 con OT-002, E2, E3, E4 y E5) arrancan al mismo tiempo que tú, cada uno en su subcarpeta `trabajo/OT-NNN`. No toques sus carpetas ni sus ramas. Si ves que algo de la computadora les va a fallar (por ejemplo falta Node, pnpm o Python), anótalo como aviso `@todos` y avísale al dueño de inmediato.
- Tu orden empezó con el protocolo anterior, en `Downloads\Clique\Clique-trabajo\OT-001` y en su propia ventana: termínala ahí. Al cerrarla, `/cerrar OT-001` borra esa carpeta y desde entonces todo vive en `Clique-1\trabajo\`.
- Comprueba que `git worktree list` muestra las carpetas de los demás y que `git status` en la raíz de `Clique-1` no muestra `trabajo/` (debe estar ignorada).
