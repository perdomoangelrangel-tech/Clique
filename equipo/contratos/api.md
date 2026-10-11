# Contrato de la API

*Propuesto · dueño E1 · 10-oct-2026*

Las rutas del servidor (`server.py`) que usan la interfaz, el servicio de despliegue y el monitoreo. Cada fila dice
método, ruta, si pide sesión, qué recibe y qué devuelve. E3 y E5 piden sus filas en la bitácora; las agrega E1.

## Reglas comunes

- Todo va y viene en JSON (`Content-Type: application/json`). Un cuerpo de más de 1 MB se rechaza con 413; un cuerpo que no es
  JSON, con 415. La única ruta que recibe un archivo crudo es `POST /api/profile/avatar` (PNG, JPEG o WebP).
- La sesión es la cookie `sid` (`HttpOnly`, `SameSite=Lax`, y `Secure` detrás de https). Una ruta que pide sesión sin ella responde 401.
- Una petición con `Origin` de otro sitio se rechaza con 403.
- Las respuestas llevan `Cache-Control: no-store`; las largas van en gzip si el navegador lo acepta.

## La respuesta de error

Cualquier error responde con su código HTTP (400, 401, 403, 404, 409, 413, 415, 429, 503…) y este cuerpo:

```json
{ "error": "Texto para la persona, en inglés por ahora", "code": "insufficient_funds" }
```

| Campo | Siempre | Qué es |
|---|---|---|
| `error` | sí | El texto del servidor. La interfaz no lo muestra tal cual cuando hay `code`: lo traduce (D5). |
| `code` | cuando el error lo tiene | Un código estable en inglés, de la lista de E3 en `equipo/contratos/errores.md`. Es lo que la interfaz usa para decidir qué decir. Un error sin código aún llega con `code: null`. |
| otros | a veces | Algunos errores llevan datos para seguir (por ejemplo, un precio nuevo). Los dice la fila de su ruta. |

Un error inesperado responde 500 con `{"error": "Something went wrong on the server", "code": "server_error"}` y el detalle va al registro del servidor, nunca a la respuesta.

## Rutas

| Método | Ruta | Sesión | Recibe | Devuelve | Dueño |
|---|---|---|---|---|---|
| GET | `/api/salud` | no | nada | 200 `{"ok": true, "version": "<commit>", "uptimeSeconds": 1234, "database": {"read": true, "write": true}}`. Si la carpeta de la base no se puede leer o escribir: 503 con el mismo cuerpo, `ok: false` y `error`. No dice nada de las personas. `version` sale de `CLIQUE_COMMIT` o `RENDER_GIT_COMMIT`, o de git en la computadora; si no hay ninguno, `"unknown"`. | E1 |

*Las demás rutas de `server.py` se irán describiendo aquí conforme E3 y E5 las pidan o las cambien.*
