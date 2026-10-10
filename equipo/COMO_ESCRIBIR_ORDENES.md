# Cómo escribir una orden para que se cumpla

*Para E0. Sale de lo que aprendió Ches-Hex: la calidad de los agentes es alta; lo que falla es el canal y la forma de las órdenes.*

| Lo que pasó en Ches-Hex | La regla |
|---|---|
| Un ALTO vivía en un archivo y nadie lo leyó | **La orden se pega en la conversación.** El archivo es el respaldo y el gancho de inicio la recuerda |
| "Reporten contradicciones" no decía contra qué ni dónde | **Cada orden dice dónde y en qué formato se contesta** |
| Órdenes enormes con felicitaciones, doctrina y tarea mezcladas | **Lo accionable va primero y cabe en una pantalla.** La doctrina vive en `EQUIPO.md` y `COORDINACION.md` |
| "100 %" que no era cierto | **Terminado lo confirma E7 sobre el árbol fusionado** (`VERIFICADO.md`), nunca la bitácora propia |
| Ramas sin fusionar durante días | **Cada sesión empieza rebasando sobre `integracion`**; E7 fusiona todos los días |
| Un agente eligió un lado en una contradicción | **Ante una contradicción, se para y se anota** |
| Pruebas con números escritos a mano | **Ningún número fijo en una prueba** si se puede derivar de los datos |
| La propiedad de archivos dependía de la buena fe | **Un gancho bloquea** editar archivos de otro dueño |

## La plantilla

```markdown
# Orden · E<n> · <título en una línea> · <fecha>

## Objetivo (una frase)
## Parte de
Rama `e<n>-<nombre>`, árbol `_ramas/e<n>-<nombre>`, rebasada sobre `origin/integracion` (etiqueta `cimiento-N`).
## Lee antes (en este orden, y nada más)
## Entregables
| # | Qué | Cómo se comprueba (comando exacto) | Hecho cuando |
## Tus archivos
## No hagas
## Para y pregunta si
## Cómo reportas
`[E<n>] <fecha> · HECHO: … · PENDIENTE: … · BLOQUEADO POR: … · COMANDO: …`
```

## La prueba antes de mandarla

El mensaje de arranque pide: **"Antes de tocar nada, explícame en cinco líneas qué vas a hacer, en qué orden y cómo vas a saber que terminaste."** Si lo que explica no coincide con lo que se quería, la orden está mal escrita: se corrige la orden, no al agente.

## `/goal` (trabajar solo sin desbocarse)

Cuando el dueño quiera que un agente avance sin esperar entre entregables:
1. Un `/goal` para toda la orden, con una parada por entregable: cada entregable deja su commit y su línea HECHO.
2. La condición es el comando de comprobación del entregable, no una impresión.
3. Siempre con salida: "detente si algo contradice las decisiones firmadas, si necesitas el visto bueno del dueño, o después de 100 turnos".

Nunca un `/goal` que incluya fusionar, empujar a `main` o a `integracion`, o escribir en Supabase.
