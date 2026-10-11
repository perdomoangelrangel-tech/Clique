# Clique — instrucciones para todos los agentes

Clique es una app social de apuestas con fichas ficticias entre amigos: mercados de predicción sobre la vida del grupo, un casino premium de juegos propios, póker, ranking semanal por círculo y castigo votado para el último. La estamos llevando a uso comercial en México. **Todo debe sentirse premium**, como un club privado de cartas.

**Se mejora la app original en su lugar** (decisión D1): el código de la raíz es el producto. No se reescribe en otro lenguaje; se cambia con pruebas, una pieza a la vez, y se deja sólida para crecer (ADR-006).

## Antes de nada

1. Lee `equipo/DECISIONES.md`: lo que firmó el dueño. Manda sobre todo.
2. Lee `equipo/EQUIPO.md` y `equipo/COORDINACION.md`: cómo trabaja el equipo.
3. Lee tu orden: `git fetch origin && git show origin/integracion:equipo/ORDENES_E<n>.md` (o `/orden E<n>`).

## Dónde se trabaja

- **La raíz de esta carpeta es `main` y nadie edita ni comitea aquí.** Los ganchos lo impiden.
- **Cada encargo trabaja en su árbol** `_ramas/<su rama>` (`git worktree`), con su rama fija: `e1-plataforma`, `e2-datos`, `e3-motor`, `e4-diseno`, `e5-frontend`, `e6-arte3d` e `integracion` (E7).
- **Todo comando del encargo corre dentro de su árbol:** `cd _ramas/<rama> && …`.

## Mapa del repositorio

```
CLAUDE.md                este archivo
COMO-EMPEZAR.md          guía para el dueño
server.py                el servidor HTTP (biblioteca estándar de Python; corre en 3.11 y 3.12)
backend/                 la lógica: libro, mercados, juegos, póker, semana, usuarios, base en archivo
static/                  la interfaz: index.html, js/ (vistas y juegos), css/ (tokens y estilos), fuentes, 3d/
tests/                   las pruebas (1,142 al empezar la ronda 1)
scripts/                 utilidades (sembrar datos, previsualizar migraciones)
supabase/                el esquema de Postgres, funciones SQL y pruebas pgTAP (E2)
assets3d/                los .blend (Git LFS) y herramientas de exportación (E6)
docs/                    plan maestro, arte, capturas y documentos del producto
equipo/                  la coordinación: decisiones, órdenes, bitácora, propiedad de archivos, contratos
herramientas/ganchos/    los ganchos de Claude Code (orden al iniciar, permisos)
ECONOMY.md               cómo funciona la economía, regla por regla
DEPLOY.md, Dockerfile    cómo se despliega
```

## Reglas de oro

1. **Nunca en `main`.** Tu rama, tu árbol. A `integracion` empuja E7 (y E0, desde `cerebro/*`, para publicar órdenes); a `main` solo entra el PR que fusiona el dueño.
2. **Un archivo, un dueño** (`equipo/PROPIEDAD_DE_ARCHIVOS.md`). Lo ajeno se pide en tu bitácora y sigues con otra cosa.
3. **El dinero solo se mueve en el libro** (D2). El navegador nunca decide resultados (D8).
4. **Las fichas compradas viven aparte** y la compra está apagada (D3).
5. **Prueba primero, vista en rojo.** La suite completa pasa antes de entregar: `python -m unittest discover -s tests -t .`
6. **Todo texto visible en español de México** por el sistema de idioma (D5); colores y tamaños solo con tokens (D4).
7. **Supabase de producción: leer sí, escribir nunca** (D9).
8. **Sin secretos en git.** El repositorio pasa a privado (D13), pero sigue público hasta que el dueño lo cambie en GitHub.
9. **Ante una contradicción o una decisión difícil de revertir, para y pregunta** en tu bitácora, y avisa al dueño.
10. **Escribe tu línea en la bitácora** por cada entregable: `[E<n>] fecha · HECHO · PENDIENTE · BLOQUEADO POR · COMANDO`.

## Idioma

- Documentación, bitácoras, commits y textos de la interfaz: español de México.
- Código nuevo (variables, funciones, tablas): inglés, como el código original.
- Commits: `tipo(ámbito): qué y por qué [E<n>]`. Tipos: feat, fix, refactor, test, docs, chore.

## Comandos

- `/orden E<n>`: lee tu orden vigente y ponte al día.
- `/bitacora E<n> <nota>`: tu línea en la bitácora.
- `/entregar E<n> <entregable>`: pruebas, revisión de `qa`, bitácora, commit y push de tu rama.
- `/estado`: qué hizo cada encargo, qué está bloqueado y qué peticiones siguen abiertas.

## Cómo correr las cosas

- La app: `python server.py` → http://localhost:3000
- Las pruebas: `python -m unittest discover -s tests -t .` (unos 8 minutos; en Windows hay 4 rojos conocidos, ver `equipo/ROJOS_CONOCIDOS.json`)
- Los ganchos: `node herramientas/ganchos.test.mjs && node herramientas/ganchos.en-vivo.test.mjs`
