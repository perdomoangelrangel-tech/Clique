# Cómo empezar (para el dueño)

Esta guía es para ti, no para los agentes. Clique se trabaja como Ches-Hex: un agente por encargo (E1 a E7), cada uno en su rama fija, todos en la misma ventana de VS Code.

## Una sola vez

1. **Python 3.11 o más** (ya lo tienes: 3.11.9) y **Node** (ya lo tienes: lo usan los ganchos).
2. **Recomendado: GitHub CLI.** En PowerShell `winget install GitHub.cli`, cierra y abre VS Code, y corre `gh auth login`. Con eso E7 abre los PR solo.
3. **Abre la carpeta correcta en VS Code:** Archivo → Abrir carpeta → `Downloads\Clique\Clique-1`. Es la única que se abre. Su raíz se queda en `main`; cada agente trabaja en su subcarpeta `_ramas\<su rama>`.
4. **Fusiona el PR de arranque** en GitHub (el cerebro te pasa el enlace): es el que pone la app en la raíz, la carpeta `equipo/` y los ganchos en `main`. **Hasta que lo fusiones, no lances a nadie**: las conversaciones abren en `main` y ahí sigue la ronda 0.
5. **Trae lo nuevo:** abre un chat de Claude en `Clique-1` y pídele `git pull --ff-only`. Después **cierra ese chat y abre uno nuevo**: los ganchos se cargan al abrir la conversación.

## Lanzar a los agentes

Los mensajes están en el chat del cerebro (y en `equipo/EQUIPO.md` están los encargos). Para cada agente:

1. En la ventana de `Clique-1`, abre un **chat nuevo** de Claude.
2. Pega su mensaje. **Una sola vez.**
3. El agente lee su orden, crea su subcarpeta y te dice en cinco líneas qué va a hacer. **Contéstale "adelante"** si suena bien.

Puedes tenerlos a todos trabajando a la vez.

## Tu rutina

- **Cuando un agente se detiene con una pregunta:** contéstale si sabes; si no, pásala al cerebro.
- **Cuando un agente termina un entregable:** no tienes que hacer nada. E7 lo junta en `integracion` y lo verifica.
- **Para saber en qué va todo:** escribe `/estado` en cualquier chat.
- **Cuando el cerebro te diga que una ronda está lista:** fusiona en GitHub el PR de `integracion` a `main` (botón "Merge pull request"). Es lo único que tú fusionas.
- **Si el cerebro deja una orden nueva** para un agente, ve a su chat y escribe `/orden E<n>`.
- **Cambios en Supabase:** el cerebro te pide tu "sí" antes de cada uno. Los agentes no escriben en la base de producción.

## Si algo sale mal

- **Un gancho bloquea a un agente:** es a propósito, porque iba a tocar algo que no es suyo o algo peligroso. El mensaje le dice qué hacer en su lugar.
- **Un agente quiere hacer algo que te da miedo** (borrar, pagar, publicar, subir a `main`): dile que no y pregúntale al cerebro.
- **Git dice que hay un candado (`.lock`):** otro agente está trabajando al mismo tiempo; que espere unos segundos y reintente.
