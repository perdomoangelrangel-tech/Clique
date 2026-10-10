# Definición de terminado

*Vale para cualquier entregable de cualquier encargo. Si falta una casilla, no está terminado.*

## Las siete casillas

1. **La prueba nueva existe, se vio en rojo y ahora está en verde.** Si es lógica, la prueba se escribió antes que el código y se comprobó con un mutante.
2. **La suite completa pasa:** `python -m unittest discover -s tests -t .` (salvo lo anotado en `ROJOS_CONOCIDOS.json`, con dueño y porqué).
3. **La app arranca y la pantalla tocada se ve** a 390×844 y a 1366×768, si el entregable toca la interfaz. La captura va en la bitácora o en `docs/`.
4. **Los textos nuevos o tocados pasan por el sistema de idioma** y los colores por los tokens, si toca la interfaz.
5. **El contrato que toca está al día**, si cambia una firma, una ruta o una forma de datos.
6. **Línea en `BITACORA.md`** de tu rama: `[E<n>] fecha · HECHO · PENDIENTE · BLOQUEADO POR · COMANDO`.
7. **Commit en tu rama, empujado**, con el porqué en el mensaje.

## Lo que hace que un entregable se rechace

- Datos de ejemplo inventados en pantalla (lo vacío se dice vacío).
- Un botón que no lleva a ningún lado.
- Una cifra en la interfaz que no se puede rastrear hasta el servidor.
- Un saldo que se mueve fuera del libro (D2) o un resultado que decide el navegador (D8).
- Cambiar un contrato sin anotarlo.
- Tocar un archivo de otro encargo.
- Dependencias nuevas sin permiso escrito en la orden.
- Una prueba quitada o debilitada para que pase.
