# OT-002 — Monorepo TypeScript e integración continua

- **Fase:** 0
- **Agente:** E1 · Plataforma
- **Rama:** `ot/002-monorepo-ci`
- **Depende de:** OT-001
- **Contratos que usa:** ADR-001 (stack)
- **Contratos que crea:** `coordinacion/contratos/comandos.md` (los comandos estándar del repo)

## Objetivo

Que el repositorio tenga el esqueleto del monorepo nuevo y que cada PR corra automáticamente lint, tipos y pruebas, incluidas las 1,142 de la app actual.

## Contexto

Es el cimiento para que los agentes trabajen en paralelo sin romperse unos a otros. Ver ADR-001.

## Alcance

**Incluye**

- pnpm workspaces en la raíz (`package.json`, `pnpm-workspace.yaml`), Node 22 LTS fijado (`.nvmrc` y `engines`).
- `apps/web`: Vite + React + TypeScript estricto, con una pantalla que diga "Clique" y un texto en español servido por i18n (`i18next` con `es-MX` por defecto y `en` de respaldo). React Router con una ruta.
- `packages/engine`: paquete TypeScript puro, sin dependencias en tiempo de ejecución, con dos funciones de ejemplo y sus pruebas en Vitest: `round2` (al centavo, mitad hacia arriba, como `legacy/clique/backend/util.py`) y `floorCents` (al centavo hacia abajo, como `legacy/clique/backend/lmsr.py`, que se usa en pagos).
- `packages/tokens`: paquete vacío con su `package.json` (lo llena OT-003).
- Convención de pruebas: cada paquete pone sus pruebas en `test/**/*.test.ts` y Vitest las encuentra ahí (OT-005 y OT-003 dependen de esto). Los paquetes que generan archivos (`build`) se construyen antes de `typecheck` y `test` (por ejemplo con `dependsOn` o un script `pretest`), para que un clon limpio pase.
- TypeScript base compartido (`tsconfig.base.json`), ESLint y Prettier compartidos.
- Scripts en la raíz: `pnpm dev`, `pnpm build`, `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm test:legacy`.
- GitHub Actions `.github/workflows/ci.yml` con dos trabajos: `nuevo` (install, lint, typecheck, test, build) y `legacy` (Python 3.12, `cd legacy/clique && python -m unittest discover -s tests -t .`).
- `coordinacion/contratos/comandos.md`: tabla de comandos y qué hace cada uno.

**No incluye**

- Diseño, tokens o pantallas reales (OT-003 en adelante).
- Supabase (OT-004).

## Archivos y carpetas permitidos

Raíz (archivos de configuración), `apps/web/`, `packages/engine/`, `packages/tokens/`, `.github/`, `coordinacion/contratos/comandos.md`, `coordinacion/bitacoras/OT-002.md`, `README.md` (solo la sección de comandos).

## Criterios de aceptación

- [ ] `pnpm install` y `pnpm build` funcionan desde cero en Windows (anota la versión de Node).
- [ ] `pnpm dev` abre la app y muestra "Clique" con un texto en español que viene de i18n.
- [ ] `pnpm lint`, `pnpm typecheck` y `pnpm test` pasan.
- [ ] Hay pruebas de `packages/engine` que comparan `round2` y `floorCents` con casos calculados por las funciones de `legacy/clique`, incluidos casos de punto flotante como 0.1 + 0.2 y 1.005.
- [ ] El flujo de CI corre en el PR y ambos trabajos salen en verde (pega el enlace en la bitácora).
- [ ] Desde un clon limpio (`git clone` a otra carpeta), `pnpm install && pnpm test` pasa sin pasos manuales.
- [ ] `coordinacion/contratos/comandos.md` existe.

## Cómo verificar

```bash
pnpm install
pnpm lint && pnpm typecheck && pnpm test && pnpm build
pnpm test:legacy
```

## Notas del cerebro

- Usa versiones estables actuales de cada herramienta; anota en la bitácora cuáles quedaron.
- Nada de plantillas con contenido de ejemplo de terceros (logos de Vite/React): la pantalla mínima es de Clique.
- La app actual tarda de 5 a 9 minutos en sus pruebas; está bien que el trabajo `legacy` corra en paralelo.
- El trabajo `legacy` también corre `sha256sum -c --quiet ../clique.sha256` dentro de `legacy/clique`: si alguien cambia el legacy, el CI falla.
- Configura `.github/workflows/ci.yml` para que corra en cada PR y en cada push a `main`.

## Correcciones

(Vacío.)
