# Protocolo de trabajo

Cómo trabajan juntos el dueño, el cerebro y los agentes. Si algo aquí choca con una orden, gana la orden; si choca con un ADR, gana el ADR.

## Quién es quién

| Quién | Dónde trabaja | Hace | No hace |
| --- | --- | --- | --- |
| **Dueño** (tú) | VS Code y el chat con el cerebro | Aprueba fases y decisiones. Lanza cada agente con `/orden OT-NNN`. Fusiona los PR aprobados y corre `/cerrar`. | Escribir código |
| **Cerebro** | Proyecto "Clique" en Claude, con acceso al repositorio de GitHub y a Supabase | Escribe las órdenes y sus correcciones, mantiene `TABLERO.md`, `AGENTES.md`, `decisiones/` y `bitacoras/cerebro.md`. Sube esos cambios por PR desde ramas `cerebro/*`, que el dueño fusiona con un clic. Revisa los PR, corre las pruebas de aceptación y los asesores de Supabase. | Programar dentro de las ramas de los agentes |
| **Agentes** | Claude en VS Code: un chat por orden, todos en la misma ventana y la misma carpeta | Ejecutan una orden en su rama, con su bitácora, y abren un PR. | Tocar `main`, otras ramas o contratos |

Cada agente tiene un código fijo de E1 a E7, según `coordinacion/AGENTES.md`. Sus roles están en `.claude/agents/`: `plataforma` (E1), `datos` (E2), `motor` (E3), `diseno` (E4), `frontend` (E5) y `arte3d` (E6) ejecutan órdenes; `qa` (E7) solo revisa. El cerebro es E0.

## El ciclo de una orden

1. **El cerebro escribe la orden** en `coordinacion/ordenes/OT-NNN-nombre.md`, la marca "Lista" en el tablero y lo sube a `main`.
2. **El dueño la lanza.** En VS Code, con la carpeta principal abierta, abre un chat nuevo de Claude y pega el mensaje del agente (`AGENTES.md`), o escribe `/orden OT-NNN`.
3. **El agente prepara su lugar de trabajo.** Crea la rama `ot/NNN-nombre` desde `origin/main` en la subcarpeta `trabajo/OT-NNN` de la misma carpeta principal (git worktree: no es un clon y no se abre otra ventana). Desde ahí trabaja en el mismo chat.
4. **El agente trabaja.** Lee la orden y sus "Correcciones" desde `origin/main` (siempre la versión más nueva), los contratos y las bitácoras relacionadas. Hace commits pequeños. Anota en su bitácora con `/bitacora` y sube la rama seguido (`git push`), así el cerebro ve el avance en GitHub.
5. **El agente entrega** con `/entregar`: corre las verificaciones, pide revisión al subagente `qa`, completa la sección "Entrega" de la bitácora, sube la rama y abre el PR. Le muestra al dueño la sección "Entrega" completa y el enlace del PR.
6. **El cerebro revisa** el PR en GitHub. Si falta algo, escribe "Correcciones" al final de la orden (PR `cerebro/*`, que el dueño fusiona) y el dueño vuelve a escribir `/orden OT-NNN` en el chat de esa orden. Si está bien, lo aprueba.
7. **El dueño fusiona** el PR en GitHub y corre `/cerrar OT-NNN` en un chat de Claude. El cerebro marca la orden como "Hecha" en el tablero.

Varias órdenes pueden correr a la vez, cada una en su chat y en su subcarpeta `trabajo/OT-NNN`. La raíz de la carpeta principal siempre está en `main` y nadie la edita: una carpeta de git solo puede tener una rama a la vez, por eso cada orden tiene la suya dentro de `trabajo/`. Solo se lanzan las que tienen sus dependencias "Hechas" (o lo que la orden diga explícitamente).

## Estados del tablero

`Lista` → `En curso` → `En revisión` → `Correcciones` → `Hecha`. También `Bloqueada` (con el motivo).

El tablero solo lo edita el cerebro (por PR desde `cerebro/*`). Los agentes reportan su estado en la primera línea de su bitácora; si el tablero y la bitácora no coinciden, gana la bitácora y el cerebro corrige el tablero.

## Cómo se comunican los agentes

Siempre por escrito, nunca de memoria:

- **Bitácora propia** (`coordinacion/bitacoras/OT-NNN.md`, en su rama). Cada entrada tiene "Preguntas para el cerebro" y "Avisos para otros agentes". Un aviso empieza con el código del agente (por ejemplo `@E5`), `@OT-NNN` o `@todos`.
- **Al iniciar cada sesión** el agente corre `/estado` y busca avisos dirigidos a su código, a su orden o a `@todos`.
- **Contratos** (`coordinacion/contratos/`). Son los acuerdos que permiten trabajar en paralelo: esquema de datos, API, tokens, reglas de economía, especificación de arte 3D. Quien crea un contrato es su dueño; los demás lo usan tal cual. Un cambio requiere un ADR aprobado por el cerebro.
- **Las bitácoras de otras ramas** se leen así: si su carpeta de trabajo existe, en `trabajo/OT-NNN/coordinacion/bitacoras/OT-NNN.md`; si no, con `git fetch origin` y `git show origin/ot/NNN-nombre:coordinacion/bitacoras/OT-NNN.md`.

## Cuándo parar y preguntar

Detente, anota la pregunta en la bitácora y avísale al dueño cuando:

- La orden es ambigua o contradice un contrato, un ADR o el comportamiento de `legacy/clique`.
- Necesitas tocar archivos fuera del alcance.
- La decisión es difícil de revertir: borrar datos, cambiar el esquema de dinero, activar cobros, agregar un servicio de pago, exponer datos personales.
- Llevas dos intentos fallidos con el mismo enfoque.

Mientras esperas, avanza en lo que no depende de la respuesta.

## Ramas, commits y fusiones

- Rama: `ot/NNN-nombre-corto` desde `origin/main` actualizado.
- Commits pequeños: `feat(web): barra inferior para celular [OT-007]`.
- Antes de entregar: `git fetch origin && git rebase origin/main` y vuelve a correr las pruebas. Si la rama ya estaba subida, súbela con `git push --force-with-lease` (solo tu propia rama `ot/...`).
- Nunca `git push --force` sin `-with-lease`. Nunca a `main`.
- Conflicto con otra rama: no lo resuelvas reescribiendo el trabajo ajeno. Anótalo como aviso para esa orden y pregunta al cerebro.
- GitHub gratuito no permite proteger ramas en repositorios privados; la protección de `main` es por estas reglas y por los permisos de `.claude/settings.json`. Si el dueño pasa a GitHub Pro, se activa la protección real (PR obligatorio y CI en verde).

## Revisión del cerebro (lo que revisa en cada PR)

1. Cada criterio de aceptación con evidencia.
2. Pruebas: existen, cubren lo nuevo y pasan en CI.
3. Paridad con `legacy/clique` en las reglas tocadas.
4. Dinero solo en Postgres; nada de lógica de resultados en el navegador; fichas compradas separadas (ADR-004).
5. Textos en i18n, estilos con tokens, accesibilidad básica (foco visible, etiquetas, contraste).
6. Calidad premium: nada se ve de plantilla; animaciones fluidas; presupuesto de peso y rendimiento del 3D (ADR-005).
7. Alcance respetado y bitácora completa.
