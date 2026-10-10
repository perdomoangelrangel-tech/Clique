# OT-001 — Clonar el repositorio y verificar la computadora del dueño

- **Fase:** 0
- **Agente:** plataforma
- **Rama:** `ot/001-verificacion`
- **Depende de:** —
- **Contratos que usa:** —
- **Contratos que crea:** —

## Objetivo

Que la computadora del dueño tenga el repositorio clonado y todas las herramientas listas, que la app actual corra y pase sus pruebas desde `legacy/clique`, y que el primer PR del proyecto (esta bitácora) quede abierto en GitHub.

## Contexto

El cerebro ya creó el repositorio en GitHub (https://github.com/perdomoangelrangel-tech/Clique) con la app actual en `legacy/clique`, la huella `legacy/clique.sha256` y todo el sistema de agentes. La carpeta vieja `Downloads/Clique` queda como respaldo; desde ahora se trabaja en el clon.

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

(Vacío.)
