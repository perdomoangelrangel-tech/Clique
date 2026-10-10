# OT-003 — Tokens de diseño v2

- **Fase:** 0
- **Agente:** E4 · Diseño
- **Rama:** `ot/003-tokens-v2`
- **Depende de:** OT-002
- **Contratos que usa:** `contratos/comandos.md`
- **Contratos que crea:** `coordinacion/contratos/tokens.md`

## Objetivo

Que exista una sola fuente de verdad de diseño (`packages/tokens/tokens.json`) con la paleta v2, que genere las variables CSS de los dos temas (sala y papel) y constantes TypeScript, y una página `/diseno` en la app que las muestre.

## Contexto

La identidad se queda: "sala de cartas clandestina con boleto de apuesta impreso". Fuente actual: `legacy/clique/static/css/tokens.css`. La paleta v2 está completa en la sección "Valores" de esta orden (y en el documento del plan): mismos colores base, escalas completas, oro nuevo, colores para gráficas y un ajuste de contraste. El oro es también el latón del casino premium (ADR-005).

## Valores

**Base (no cambian):** sala `#0E0C0A`, sala-2 `#141110`, mesa `#1C1815`, mesa-2 `#26211C`, línea `#5A4E41`, línea-suave `#3A322A`, línea-campo `#8C8171`, texto `#F2EADB`, texto-2 `#BDB19C`, texto-3 `#A09482`, papel `#EFE6D2`, papel-2 `#E2D6BB`, tinta-papel `#1A1612`, fieltro `#1E3B2C`, fieltro-2 `#2F6B47`.

**Escalas (50 → 950):**

| Paso | lima | bermellón | oro (nuevo) |
| --- | --- | --- | --- |
| 50 | `#F0FDD7` | `#FFF0EC` | `#FEF5E8` |
| 100 | `#E9F7D0` | `#FEE0DA` | `#FEECD1` |
| 200 | `#D3FD62` | `#FEC4B8` | `#FFE0B1` |
| 300 | `#CDF859` | `#FEA28F` | `#FFCF84` |
| 400 | `#C6F432` (actual) | `#FE7A62` | `#FBB635` |
| 500 | `#A7D00B` | `#FF4B2B` (actual) | `#DF9C03` |
| 600 | `#88AB08` | `#DC3215` | `#BB8307` |
| 700 | `#6B8703` | `#B8200A` (actual) | `#996A05` |
| 800 | `#4C6300` (actual) | `#941701` | `#795300` |
| 900 | `#354401` | `#6F0F01` | `#593C02` |
| 950 | `#1E2901` | `#480701` | `#382501` |

**Series para gráficas:** lima-400, bermellón-500, oro-400, menta `#51DAA7`, cielo `#59C5F5`, lila `#B995F6`, rosa `#F47DB9`, papel `#EFE6D2`.

**Ajuste de contraste:** `paper-mute` pasa de `#6A5E49` a `#5A4E3C` (de 4.4:1 a 5.6:1 sobre papel-2).

**Roles semánticos:** `pos` (ganar/Sí), `neg` (perder/No), `reward` (oro: premios, rangos, premium; nunca ganar o perder), `focus`, `danger`, más estados `hover`, `pressed`, `disabled` y `subtle` para botones primario, secundario y peligro, derivados de las escalas.

**También:** tipografías (Bricolage Grotesque, Instrument Sans, JetBrains Mono, con sus fallbacks medidos de `tokens.css`), radios, sombras duras sin desenfoque, grosor de borde, espacios y los puntos de corte de `legacy/clique/static/css/layout.css`.

## Alcance

**Incluye**

- `packages/tokens/tokens.json` y un script de construcción que genere `dist/tokens.css` (variables para `:root`, `[data-theme="sala"]` y `[data-theme="papel"]`, y la clase `.paper`) y `dist/tokens.ts`.
- Prueba automática que verifique contrastes mínimos WCAG AA de las parejas de texto que usa la app (texto sobre fondo, texto-3 sobre mesa-2, tinta sobre papel, paper-mute sobre papel-2, lima-800 sobre papel, bermellón-700 sobre papel) y que falle si alguna baja de 4.5:1.
- Copiar las fuentes `.woff2` de `legacy/clique/static/fonts/` con su licencia.
- Página `/diseno` en `apps/web` con muestras de todas las escalas, tipografías y botones primario, secundario y peligro en sus estados, en ambos temas.
- `coordinacion/contratos/tokens.md`: nombres de tokens y reglas de uso (por ejemplo: oro nunca para ganar o perder; Sí/No siempre con palabra o ícono).

**No incluye**

- Rediseñar pantallas de producto (eso llega en la Fase 1).

## Archivos y carpetas permitidos

`packages/tokens/`, `apps/web/src/` (solo la ruta `/diseno` y la importación de tokens), `apps/web/public/fonts/`, `coordinacion/contratos/tokens.md`, `coordinacion/bitacoras/OT-003.md`.

## Criterios de aceptación

- [ ] `pnpm --filter @clique/tokens build` genera `tokens.css` y `tokens.ts`.
- [ ] La prueba de contraste pasa y falla a propósito si se cambia `paper-mute` al valor viejo (anota la prueba en la bitácora).
- [ ] `/diseno` muestra todo en tema sala y papel; capturas a 390×844 y 1366×768 en la bitácora.
- [ ] Ningún archivo de `apps/web` usa un color hexadecimal fuera de `packages/tokens`.
- [ ] `contratos/tokens.md` existe con estado "Propuesto" en su primera línea.
- [ ] `pnpm typecheck` y `pnpm test` pasan desde un clon limpio, sin construir tokens a mano (el build de tokens corre solo antes).

## Cómo verificar

```bash
pnpm --filter @clique/tokens build
pnpm test
pnpm dev   # abrir /diseno
```

## Correcciones

(Vacío.)
