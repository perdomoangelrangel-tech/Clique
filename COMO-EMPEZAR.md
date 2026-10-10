# Cómo empezar (para el dueño)

Esta guía es para ti, no para los agentes. Son los pasos para tener Clique en tu computadora y lanzar a los agentes.

## Una sola vez

1. **Instala Git for Windows:** https://git-scm.com/download/win (deja las opciones por defecto). Trae "Git Bash", que los agentes usan para algunas verificaciones.
2. **Instala Node 22 LTS** desde https://nodejs.org. Luego, en una terminal: `npm install -g pnpm`.
3. **Instala Python 3** desde https://www.python.org/downloads/ si no lo tienes (marca "Add python.exe to PATH"). Sirve para correr la app actual.
4. **Opcional pero recomendado: GitHub CLI** desde https://cli.github.com y luego `gh auth login`. Con eso los agentes abren los PR solos.
5. **El repositorio ya está clonado** en `C:\Users\legma\Downloads\Clique\Clique-1`. Esa es la **carpeta principal**: ábrela en VS Code. Las carpetas de cada orden se crean solas en `C:\Users\legma\Downloads\Clique\Clique-trabajo\`.

En `Downloads\Clique` también están `clique\` (la app original), `_viejo\` (copias anteriores de la coordinación) y `_ot006\` (el taller de Blender del cerebro). No trabajes ahí.

## Lanzar a los agentes

Los mensajes de cada agente están listos en `coordinacion/AGENTES.md` (sección "Mensajes listos"). Para cada uno:

1. En la ventana de la **carpeta principal**, abre Claude y pega el mensaje del agente.
2. El agente prepara su carpeta de trabajo y abre una **ventana nueva** de VS Code. Ahí abre Claude y pega **el mismo mensaje**. Desde ahí trabaja.
3. Repite con el siguiente agente en la ventana principal. Puedes tener todas las ventanas trabajando a la vez.

Si el agente no logra abrir la ventana nueva, en VS Code usa "Archivo → Abrir carpeta" y elige `Downloads\Clique\Clique-trabajo\OT-NNN`.

## Cuando un agente termina

1. En su ventana escribe `/entregar`. Te mostrará la entrega y el enlace del PR.
2. Avísale al cerebro (el chat del proyecto Clique en Claude): "OT-NNN lista para revisión".
3. Cuando el cerebro la apruebe, fusiona el PR en GitHub (botón "Merge pull request") y en la ventana principal escribe `/cerrar OT-NNN`.

E2, E3 y E4 no pueden entregar hasta que OT-002 (E1) esté fusionada: avanzan en lo demás y te avisan cuando estén esperando. Cuando fusiones OT-002, ve a sus ventanas y escribe "OT-002 ya está en main, sigue".

## Si algo sale mal

- Un agente se detiene con una pregunta: contéstale si sabes, o pásale la pregunta al cerebro.
- No sabes en qué va todo: escribe `/estado` en cualquier ventana.
- Si el cerebro deja correcciones en una orden, ve a la ventana de esa orden y escribe `/orden OT-NNN`: el agente las lee y las resuelve.
- Un agente quiere hacer algo que te da miedo (borrar, pagar, publicar, subir a `main`): dile que no y pregúntale al cerebro.
