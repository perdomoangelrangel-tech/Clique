# Cómo trabaja el equipo de agentes

*Escrito el 10 de octubre de 2026, con la forma de trabajo de Ches-Hex. Varias conversaciones en
paralelo, un solo repositorio y un dueño que decide. Las reglas están aquí; los encargos, en
`ORDENES_E<n>.md`.*

---

## Los encargos

| Encargo | Nombre | Rama | Árbol | De qué se encarga |
|---|---|---|---|---|
| **E0** | Cerebro | `cerebro/*` (publica en `integracion`) | — | Dirige: escribe las órdenes, revisa, aplica las migraciones con el sí del dueño. Corre en la app de Claude, no en VS Code |
| **E1** | Plataforma | `e1-plataforma` | `_ramas/e1-plataforma` | Servidor HTTP, configuración, CI, despliegue, monitoreo |
| **E2** | Datos | `e2-datos` | `_ramas/e2-datos` | La base: el archivo de hoy y Postgres en Supabase, el libro en SQL, migraciones |
| **E3** | Motor | `e3-motor` | `_ramas/e3-motor` | La lógica del servidor: economía, mercados, juegos, póker, semana, usuarios |
| **E4** | Diseño | `e4-diseno` | `_ramas/e4-diseno` | Tokens, CSS, tipografía, la estética del club en cada pantalla |
| **E5** | Frontend | `e5-frontend` | `_ramas/e5-frontend` | Pantallas, navegación, idioma, PWA y conexión con el servidor |
| **E6** | Arte 3D | `e6-arte3d` | `_ramas/e6-arte3d` | Blender: renders y modelos. La ejecuta E0 desde la app de Claude, sobre ese árbol en la computadora del dueño, porque Blender solo está conectado a la app de escritorio |
| **E7** | Integración | `integracion` | `_ramas/integracion` | Fusiona las ramas, corre todo, etiqueta `cimiento-N` y verifica lo entregado |

Cada encargo es **una conversación**. Nadie abre dos para el mismo encargo.

---

## La regla que hace posible el paralelo

**Un archivo tiene un solo dueño.** Está en `PROPIEDAD_DE_ARCHIVOS.md`, y un gancho lo hace cumplir.
Si un encargo necesita cambiar un archivo ajeno:

1. No lo toca.
2. Escribe la petición en su `BITACORA.md`, bajo `## Peticiones`: archivo, línea, qué cambio y por qué.
3. Sigue con otro entregable mientras el dueño del archivo responde.

---

## Cómo se coordinan sin hablarse

Los agentes no se ven entre sí. Se coordinan por cosas escritas:

1. **`DECISIONES.md`**: lo que firmó el dueño. Manda sobre todo.
2. **`CONTRATOS.md`**: las firmas de funciones, rutas y formas de datos que cruzan encargos. No se cambian sin avisar en la bitácora.
3. **`BITACORA.md`**: una línea por avance, bloqueo o petición. Es lo primero que cada agente lee al empezar y lo último que escribe al terminar.
4. **Ramas de git:** una por encargo. Nadie trabaja en `main`. A `integracion` solo empuja E7, y E0 cuando escribe órdenes.

---

## El ciclo de cada turno

```
1. ponerse al día   cd _ramas/<su rama> && git fetch origin && git rebase origin/integracion
2. leer             su orden (/orden E<n>) + lo nuevo de la bitácora combinada
3. trabajar         un entregable: primero la prueba que falla, después el código
4. verificar        las pruebas que toca, en verde (y la suite completa antes de entregar)
5. escribir         su línea en equipo/BITACORA.md
6. entregar         commit en su rama, con el porqué en el mensaje, y
                    git push --force-with-lease origin <su rama>   (después de rebasar, el push normal se rechaza)
```

Si el paso 4 falla, no se escribe avance: se arregla.

La línea de la bitácora, siempre así:

```
[E<n>] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …
```

---

## Ritmo con el dueño

- E7 fusiona en `integracion` todos los días lo que esté en verde, y etiqueta `cimiento-N`.
- E0 lee la bitácora combinada, verifica y escribe las órdenes de la siguiente ronda.
- **A `main` solo entra por un PR de `integracion` que el dueño fusiona** cuando E0 y E7 lo dan por bueno.

---

## Lo que ningún agente hace, nunca

1. Trabajar en `main`, empujar a `main` o fusionar ramas (salvo E7 hacia `integracion`).
2. Tocar archivos de otro encargo.
3. Agregar dependencias sin que su orden lo permita por escrito.
4. Inventar datos de ejemplo en pantalla: lo vacío se dice vacío.
5. Escribir en el Supabase de producción (D9).
6. Escribir credenciales, claves o contraseñas en el repositorio. Por ahora es **público**.
7. Encender cobros, la venta de fichas o cualquier cosa que mueva dinero real (D3).
8. Mover saldos fuera del libro (D2) o decidir un resultado en el navegador (D8).
