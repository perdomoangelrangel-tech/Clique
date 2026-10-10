# ADR-006 — Mejorar la app original en su lugar, sólida para crecer

- **Estado:** Aceptado por el dueño el 2026-10-10 ("la opción 1, pero déjala sólida para crecer")
- **Fecha:** 2026-10-10
- **Sustituye a:** ADR-001 (reconstruir en TypeScript)

## Contexto

El plan de la Fase 0 era reconstruir Clique desde cero en TypeScript (React + Supabase) y dejar la app original congelada como especificación. El dueño pidió trabajar como en Ches-Hex: sobre la app que ya existe, mejorándola en su lugar, y que quede sólida para crecer.

La app original funciona y tiene 1,142 pruebas: servidor en Python con la biblioteca estándar, base en un archivo JSON en memoria, interfaz en JavaScript sin framework, 13 juegos de casino, póker, mercados con LMSR, libro contable y cierre semanal. Sus límites ya están medidos en el diagnóstico:

- la base es un solo archivo con un candado global (unos 48 MB y 0.45 s por apuesta a mil jugadores);
- la interfaz está solo en inglés y arma HTML con `innerHTML`;
- no hay despliegue, CI ni respaldo.

## Decisión

**Se mejora la app original en su lugar.** El código vive en la raíz del repositorio y se cambia con pruebas, una pieza a la vez, sin reescribirla en otro lenguaje.

**"Sólida para crecer" se cumple así:**

| Pieza | Hoy | Hacia dónde | Cuándo |
|---|---|---|---|
| Base de datos | Archivo JSON en memoria (`backend/store.py`) | Postgres en Supabase con esquema relacional | Etapas A, B y C (abajo) |
| Dinero | `backend/ledger.py` sobre el archivo | Funciones SQL de un libro de doble partida (ADR-003) | Etapa B |
| Pruebas | 1,142 que pasan | Siguen pasando en cada cambio, más las nuevas; CI en cada rama | Desde la ronda 1 |
| Servidor | `server.py`, biblioteca estándar, una sola copia | Igual mientras haya archivo. Con Postgres, varias copias y tiempo real compartido. Se decide con medición de carga | Etapa C |
| Cuentas | Registro y sesión propios | Supabase Auth (correo verificado, Google, Apple) | Se decide en la ronda 2 |
| Interfaz | JavaScript sin framework, inglés | La misma base, en español de México con sistema de traducciones, tokens v2, la estética de los renders, instalable (PWA) y sin `innerHTML` con datos de personas | Desde la ronda 1 |
| 3D | Íconos planos | Renders de Blender y modelos ligeros solo donde se interactúa (ADR-005) | Desde la ronda 1 |
| Despliegue | Dockerfile sin usar | Imagen en un servicio de contenedores + Supabase, primero un ambiente de prueba | Ronda 1 |

**Las tres etapas de la base:**

- **A · Esquema y libro en paralelo (ronda 1).**
  - E2 escribe el esquema de Postgres a partir del modelo real del archivo, las funciones del libro y sus pruebas.
  - También escribe un importador del archivo a Postgres con modo `--simular`.
  - La app sigue en el archivo.
- **B · Una capa de datos con dos motores (ronda 2).**
  - Los módulos dejan de tocar el diccionario del archivo y llaman a una capa de datos.
  - La capa tiene dos implementaciones, archivo y Postgres; se elige con `DB_BACKEND`.
  - Las pruebas corren contra las dos. El dinero pasa por las funciones SQL.
- **C · Producción en Postgres (ronda 3).** Se migra con el importador en una ventana de migración y se retira el archivo.

## Lo que se conserva de las decisiones anteriores

- **ADR-003:** el dinero solo se mueve dentro de Postgres. Es el destino de la etapa B; hasta entonces, nada mueve saldos fuera de `backend/ledger.py`.
- **ADR-004:** las fichas compradas viven aparte y la compra está apagada.
- **ADR-005:** la estética del club privado de cartas, con los cuadros aprobados.

## Consecuencias

- Hay avances visibles desde la primera semana: idioma, estética y despliegue sobre una app que ya funciona.
- Las pruebas existentes son la red de seguridad. Un cambio que rompe una prueba no entra, salvo que la prueba esté mal y se diga por qué.
- La migración a Postgres es la parte cara y va por etapas. Mientras tanto, el límite de una sola copia del servidor sigue ahí: no se abre al público hasta la etapa C.
- Se pierde la paridad automática contra una versión nueva. Ya no hace falta: el original es la versión que crece.
