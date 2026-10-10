# Orden 1 · E7 · Integración · fusionar cada día lo que está en verde y decir qué está terminado de verdad · 10-oct

## Objetivo (una frase)
Que `integracion` tenga todos los días lo último que está en verde de cada encargo, con su etiqueta
`cimiento-N`, y que "terminado" signifique que tú corriste el comando sobre el árbol fusionado.

## Parte de
Rama `integracion`, árbol `_ramas/integracion`, desde `cimiento-1`. Eres el único que fusiona y empuja
a `integracion` (E0 también empuja ahí, solo para publicar órdenes, desde una rama `cerebro/*`).

## Lee antes (en este orden, y nada más)
1. `equipo/EQUIPO.md` y `equipo/COORDINACION.md`
2. `equipo/DEFINICION_DE_TERMINADO.md` y `equipo/PROPIEDAD_DE_ARCHIVOS.md`
3. `equipo/ROJOS_CONOCIDOS.json` y `equipo/VERIFICADO.md`
4. Las órdenes de los demás, por encima: `equipo/ORDENES_E1.md` a `ORDENES_E6.md` (para saber qué comando decide cada entregable)

## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
|---|---|---|---|
| 1 | **Tu árbol y los ganchos probados en la computadora del dueño** (Windows): crea `_ramas/integracion` y corre las dos pruebas de los ganchos. Comprueba también el gancho de verdad, en tu conversación: que el mensaje de inicio explique cómo leer la orden, y que al intentar agregar una línea en blanco a `_ramas/integracion/equipo/ORDENES_E7.md` te bloquee diciendo que es de E0 | `git worktree add _ramas/integracion integracion` y luego `cd _ramas/integracion && node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs` | las dos dicen "0 fallos" en Windows; una fila en `VERIFICADO.md` |
| 1b | **La etiqueta `cimiento-1` en GitHub.** La nube de E0 no puede empujar etiquetas, así que la pones tú, en el commit donde nacieron las ramas | `git tag -a cimiento-1 -m "cimiento-1: la app en la raíz y el equipo de la ronda 1" 6cc0acbba9181936f932d737d76fcbf5790293d6` y `git push origin cimiento-1` | `git ls-remote --tags origin cimiento-1` la muestra |
| 2 | **`herramientas/revisar_propiedad.mjs <rama>`**: lista los archivos que la rama cambió (`origin/integracion...origin/<rama>`) y que, según `PROPIEDAD_DE_ARCHIVOS.md` de `integracion`, son de otro encargo (ni suyos ni compartidos). Sale 1 si hay alguno. Los que **no tienen fila** solo se avisan (sale 0): se resuelven pidiéndole a E0 la fila. Usa `leerPropiedad` y `duenoDe` de `herramientas/ganchos/reglas.mjs`, sin copiar la lógica | `node herramientas/revisar_propiedad.mjs e2-datos` | sale 0 con una rama limpia y 1 con una rama de prueba que toca un archivo ajeno (bórrala después) |
| 3 | **El ciclo diario** (abajo), la primera vez que haya al menos una rama con trabajo empujado | el ciclo completo, con la salida de la suite y de los ganchos en tu bitácora | `integracion` empujada con `cimiento-2` y una fila por rama en `VERIFICADO.md` |
| 4 | **`VERIFICADO.md` al día**: por cada línea `HECHO` de las bitácoras, corres su `COMANDO` sobre tu árbol fusionado y anotas fecha, encargo y entregable, comando, resultado y etiqueta. Si no pasa, no se anota: le escribes al dueño del entregable en tu bitácora | las filas nuevas | cada `HECHO` fusionado tiene su fila o su línea de rechazo |
| 5 | **`ROJOS_CONOCIDOS.json` al día**: quitas una fila cuando su dueño la arregla y tú la ves en verde 3 veces seguidas en Windows. Una fila nueva solo con dueño, porqué y el visto bueno de E0. Cuando E1 entregue `scripts/correr_pruebas.py`, lo usas en lugar de comparar a ojo | `python scripts/correr_pruebas.py` (o la suite y la lista, a ojo) | ninguna prueba en rojo fuera de la lista |
| 6 | **El PR de `integracion` a `main`**, cuando E0 lo pida: con las etiquetas que entran, lo de `VERIFICADO.md` y los rojos que quedan. Si no hay `gh` en la computadora, le das al dueño el enlace `https://github.com/perdomoangelrangel-tech/Clique/compare/main...integracion` | `gh pr create --base main --head integracion --title "…" --body-file …` | el PR abierto y el enlace en tu bitácora. Lo fusiona el dueño, nunca tú |

## El ciclo diario
Una rama a la vez. Si algo se pone en rojo, esa rama no entra hoy y las demás sí.

```
cd _ramas/integracion
git fetch origin
git pull --ff-only origin integracion          # las órdenes que haya publicado E0
git log --oneline HEAD..origin/e2-datos        # ¿trae algo nuevo? si no, sigue con la otra rama
node herramientas/revisar_propiedad.mjs e2-datos
git merge --no-ff --no-commit origin/e2-datos
python -m unittest discover -s tests -t .      # o scripts/correr_pruebas.py cuando exista
node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs
#  verde → git commit -m "chore(integracion): fusiona e2-datos [E7]"
#  rojo  → git merge --abort, y en tu bitácora: qué prueba falla y para quién es
```
Orden de las ramas: `e1-plataforma`, `e2-datos`, `e3-motor`, `e4-diseno`, `e5-frontend`, `e6-arte3d`.
Al final:
```
bash equipo/combinar_bitacoras.sh
git add equipo/BITACORA_COMBINADA.md equipo/VERIFICADO.md equipo/ROJOS_CONOCIDOS.json
git commit -m "docs(equipo): bitácora combinada y verificado del <fecha> [E7]"
git tag cimiento-N
git push origin integracion cimiento-N
```
Si el push se rechaza porque E0 publicó algo mientras tanto: `git fetch origin && git merge origin/integracion`,
la suite otra vez, y vuelves a empujar.

## Tus archivos
`equipo/BITACORA_COMBINADA.md`, `equipo/VERIFICADO.md`, `equipo/ROJOS_CONOCIDOS.json`,
`herramientas/ganchos.test.mjs`, `herramientas/ganchos.en-vivo.test.mjs`, `herramientas/revisar_propiedad.mjs`.
En `integracion` puedes resolver un conflicto de fusión en cualquier archivo que no sea de E0 ni de la zona prohibida.

## No hagas
- No empujes ni fusiones a `main`.
- No etiquetes `cimiento-N` con algo en rojo que no esté en `ROJOS_CONOCIDOS.json`.
- No arregles el código de otro encargo más allá de una línea para resolver un conflicto, y anótalo en tu bitácora con el archivo y la línea.
- No cambies las órdenes ni las decisiones (son de E0): si ves una contradicción, escríbela en tu bitácora.
- No apliques migraciones a Supabase: una rama que trae una migración se fusiona, pero aplicarla es de E0 con el sí del dueño (D9).

## Para y pregunta si
- `revisar_propiedad.mjs` encuentra archivos ajenos en una rama: no la fusionas hasta que su dueño o E0 digan.
- Un conflicto necesita más que una línea, o es en un archivo de E0.
- La suite se pone roja después de fusionar dos ramas que por separado estaban en verde.

## Cómo reportas
Al final de `equipo/BITACORA.md` de tu rama, una línea por ciclo:
`[E7] <fecha> · HECHO: fusioné e1, e3 (cimiento-N) · PENDIENTE: e2 en rojo por <prueba> · BLOQUEADO POR: … · COMANDO: …`
