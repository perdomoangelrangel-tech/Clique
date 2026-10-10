# Cómo empezar (para el dueño)

Esta guía es para ti, no para los agentes. Son los pasos para tener Clique en tu computadora y lanzar la primera orden.

## Una sola vez

1. **Instala Git for Windows:** https://git-scm.com/download/win (deja las opciones por defecto). Trae "Git Bash", que los agentes usan para algunas verificaciones.
2. **Instala Node 22 LTS** desde https://nodejs.org. Luego, en una terminal: `npm install -g pnpm`.
3. **Instala Python 3** desde https://www.python.org/downloads/ si no lo tienes (marca "Add python.exe to PATH"). Sirve para correr la app actual.
4. **Opcional pero recomendado: GitHub CLI** desde https://cli.github.com y luego `gh auth login`. Con eso los agentes abren los PR solos.
5. **Clona el repositorio en VS Code:** abre VS Code → "Clone Git Repository" → pega `https://github.com/perdomoangelrangel-tech/Clique.git` → elige la carpeta `Documentos`. Se crea `Documentos/Clique`. Ábrela.

Tu carpeta vieja `Downloads/Clique` queda como respaldo; no trabajes ahí.

## Lanzar la primera orden

1. En VS Code abre el panel de Claude y escribe: `/orden OT-001`
2. El agente lee las reglas y abre una ventana nueva de VS Code para esa orden. En la ventana nueva abre Claude y vuelve a escribir `/orden OT-001`.
3. El agente revisa tus herramientas, corre la app actual y sus pruebas, y te va contando. Si te pide instalar algo, hazlo y dile "listo".
4. Cuando termine, escribe `/entregar`. Te mostrará la entrega y el enlace del PR.
5. Avísale al cerebro (el chat del proyecto Clique en Claude): "OT-001 lista para revisión".
6. Cuando el cerebro la apruebe, fusiona el PR en GitHub (botón "Merge pull request") y en la ventana principal escribe `/cerrar OT-001`.

## Lanzar las siguientes

- `/estado` te dice qué órdenes están listas para lanzarse.
- Para cada una, en la ventana principal: `/orden OT-00X`. Se abre su ventana; ahí abre Claude y vuelve a escribir `/orden OT-00X`.
- Puedes tener varias ventanas trabajando a la vez (por ejemplo OT-002, OT-004 y OT-006).
- Si el cerebro deja correcciones, vuelve a la ventana de esa orden y escribe `/orden OT-00X`: el agente las lee y las resuelve.

## Si algo sale mal

- Un agente se detiene con una pregunta: contéstale si sabes, o pásale la pregunta al cerebro.
- No sabes en qué va todo: escribe `/estado` en cualquier ventana.
- Un agente quiere hacer algo que te da miedo (borrar, pagar, publicar, subir a `main`): dile que no y pregúntale al cerebro.
