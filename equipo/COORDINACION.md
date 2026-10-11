# Coordinación del equipo

*Escrito el 10 de octubre de 2026. Es la memoria del sistema: si mañana se abre una conversación
nueva sin contexto, se retoma leyendo esto.*

---

## Quién hace qué

**El dueño (Ángel)** decide: dinero, precios, qué se promete y cuándo, y todo lo que define qué es
Clique. Lanza a los agentes, les contesta cuando se detienen y fusiona `integracion` a `main`.

**E0, el cerebro** (Claude, en el proyecto Clique de la app de Claude) dirige la construcción:
- escribe las órdenes en `integracion` y mantiene esta carpeta;
- verifica contra el repositorio y la base lo que reportan los agentes;
- aplica las migraciones de Supabase con el sí del dueño;
- hace el arte 3D (E6) con el conector de Blender.

Solo avisa al dueño cuando hay algo que decidir.

**E1 a E5 y E7** son sesiones de Claude Code en VS Code, todas en la misma ventana: la carpeta
`Downloads\Clique\Clique-1`. Cada una trabaja en su rama y su árbol. No se ven entre ellas.

---

## La carpeta y los árboles

- **`Clique-1`** es la carpeta principal y se queda en `main`. **Nadie trabaja en su raíz.**
- **`Clique-1\_ramas\<rama>`** es el árbol de cada encargo (`git worktree`), con su rama fija. Git
  lo ignora. No es un clon: todos comparten el mismo `.git`.
- **Crear el árbol** (lo hace el agente la primera vez, desde la raíz):

  ```
  git fetch origin
  git worktree add _ramas/e1-plataforma e1-plataforma
  ```

  Las ramas ya existen en GitHub, salen de la etiqueta `cimiento-1`.
- **Cada comando del agente corre dentro de su árbol:** `cd _ramas/e1-plataforma && …`.

---

## Cómo se leen las órdenes

Las órdenes viven en `integracion`, la rama que todos comparten. Cualquier árbol las lee sin
fusionar nada:

```
git fetch origin
git show origin/integracion:equipo/ORDENES_E1.md
git show origin/integracion:equipo/BITACORA_COMBINADA.md
```

**En la conversación, con `/orden E<n>`**, que hace eso mismo y crea el árbol si falta.

**El gancho `SessionStart`** (`.claude/settings.json`) corre cada vez que el dueño abre o reanuda una
conversación. Como todas abren en la raíz, el gancho no sabe qué encargo es cada una: le pone delante
el aviso del cerebro (`equipo/AVISO.md` de `integracion`, si existe), las últimas líneas de la
bitácora combinada y cómo leer la orden. Un aviso urgente llega aunque nadie lo pegue. (Si alguna vez
se abre una conversación dentro de un árbol, el gancho sí reconoce la rama e imprime la orden.)

Si la orden y algo más chocan, manda la orden. Si la orden choca con `DECISIONES.md`, se para y se
anota en la bitácora.

---

## La bitácora

- Cada encargo escribe en `equipo/BITACORA.md` **de su rama**, solo al final.
- Al fusionar, git junta las líneas de todas las ramas, porque `.gitattributes` le pone
  `merge=union`.
- `equipo/BITACORA_COMBINADA.md` **se genera, no se escribe**: `bash equipo/combinar_bitacoras.sh`
  (lo corre E7 cada día). Lee la bitácora de cada rama `e*` y de `integracion`.

---

## La ventana de migración (Supabase)

Cuando alguien va a **escribir** en Supabase, lo que los demás **lean** mientras tanto no es de fiar.
Por eso:

1. **Se abre:** aviso en la bitácora. Nadie escribe ni mide contra Supabase; leer es libre.
2. E0 aplica la migración, con el sí del dueño.
3. Se verifica con una consulta, no con el mensaje del script.
4. **Se cierra:** aviso en la bitácora.

**El conector de Supabase** sirve para leer la base y es la fuente de verdad de lo que hay. Escribir
en producción, nunca desde una sesión de agente (D9). Para probar migraciones se usa un Postgres
local o una rama de base de datos de Supabase que pide E2 y crea E0.

---

## Reglas que ya costaron caro (aquí o en Ches-Hex)

- **Cerraduras de git.** `.git/index.lock` y `.git/HEAD.lock` huérfanos se pueden borrar.
  `.git/worktrees/<nombre>/locked` **no se toca nunca**: es la cerradura del árbol de otro encargo.
  Borrarla, más un `git worktree prune` desde otra sesión, deja a alguien sin repositorio.
- **Si git dice que otro proceso tiene un candado**, es otro agente trabajando a la vez: espera unos
  segundos y reintenta.
- **Para quitar un archivo: `rm -f <el archivo exacto>`**, nunca `rm -rf <carpeta>`.
- **Windows.** Cuatro pruebas de la app original fallan en Windows y pasan en Linux. Están en la
  bitácora de OT-001 (`equipo/historia/ronda-0/bitacoras/OT-001.md`) y E1 las arregla en la ronda 1.
  El CI corre en Linux y en Windows.
- **El repositorio pasa a privado (D13)**, pero sigue público mientras el dueño no lo cambie en GitHub: nada de credenciales, datos reales
  ni capturas con datos de personas.
- **Los `.blend` van en Git LFS** y solo los sube E6. La nube de E0 no alcanza el almacenamiento de
  LFS, así que E6 trabaja sobre `_ramas/e6-arte3d` en la computadora del dueño (a través de la app de
  Claude) y empuja desde ahí. Si eso fallara, queda el camino de la ronda 0: un paquete de git que el
  dueño sube.
- **Arnés antes que código, y visto en rojo.** Antes de dar por buena una prueba nueva, se rompe a
  propósito el código que prueba (un mutante) y se comprueba que la prueba lo caza.
- **Nunca se borra y se repunta en el mismo cambio.** Primero deja de leerse, se comprueba que nada
  se rompe, y en otra tanda se quita.

---

## Dónde está lo anterior

La ronda 0 (las órdenes OT-001 a OT-006, el tablero y el protocolo de "una orden, una rama") quedó en
`equipo/historia/ronda-0/`. Sigue valiendo como contexto:
- la bitácora de OT-001: la computadora del dueño y las pruebas en Windows;
- la de OT-006: el arte 3D y la página de prueba.
