# Plan maestro de Clique (resumen para agentes)

El documento completo, con diagramas, referentes y fuentes, es "Clique — Diagnóstico y plan maestro" en el proyecto Clique de Claude. Enlace: https://claude.ai/code/artifact/dd5b39ed-ab95-417a-9322-a90b4196d8bb

Este archivo es el resumen que los agentes necesitan para trabajar.

> **Cambio del 10-oct (D1, ADR-006):** la app original se mejora en su lugar, en la raíz del repositorio, en vez de reescribirse en TypeScript. Donde el documento completo hable de monorepo, React o reescribir, manda `equipo/decisiones/ADR-006-mejorar-el-original.md`. Las fases y las funciones siguen igual.

## Diagnóstico en una línea

Núcleo sólido (1,142 pruebas, economía auditada, identidad fuerte) sobre una base que no escala ni está lista para negocio: archivo JSON con candado global, solo inglés, celular secundario, sin git, sin moderación, sin legal.

## Calificación por área (1 a 5)

| Área | Nota |
| --- | --- |
| Lógica de juegos y economía | 5 |
| Pruebas automáticas | 5 |
| Identidad visual | 4 |
| Cuentas y seguridad | 3 |
| Experiencia en celular | 2 |
| Idioma | 1 |
| Base de datos e infraestructura | 1 |
| Comunidad y moderación | 1 |
| Legal y negocio | 1 |
| Proceso de desarrollo | 1 |

## Fases

| Fase | Semanas (estimado) | Qué entrega | Compuerta para pasar |
| --- | --- | --- | --- |
| 0 · Cimientos | 1–2 | Git y GitHub, equipo de agentes con ganchos, CI en Linux y Windows, esquema y libro en Postgres (etapa A), tokens v2, base de traducciones | CI en verde y `cimiento-2` fusionado a `main` |
| 1 · Núcleo en Supabase | 3–8 | La capa de datos con Postgres detrás (etapas B y C de ADR-006): cuentas, círculos, libro contable, mercados, cierre semanal; interfaz para celular, en español, instalable | Paridad en economía y mercados; 20 amigos en beta |
| 2 · Casino y comunidad | 9–14 | Los 14 juegos verificables; chat y amigos; moderación, panel de admin, push, rachas, misiones, compartir | Retención a 7 días de 20% o más en beta cerrada |
| 3 · En vivo | 15–20 | Servidor de juego para póker y Crash; voz con LiveKit; Plinko; liga global | 500 usuarios simultáneos en prueba de carga |
| 4 · Lanzamiento | 21–26 | Cobros (cosméticos, pase, Clique+); apps en tiendas; términos y aviso de privacidad; analítica | Dictamen legal, aviso de privacidad y clasificación 18+ |

## Funciones nuevas (por fase)

| # | Función | Fase |
| --- | --- | --- |
| F1 | Español de México con sistema de traducciones | 1 |
| F2 | Barra inferior en celular y app instalable (PWA) | 1 |
| F3 | Bienvenida: crear o unirse a un círculo en 60 s e invitar por WhatsApp | 1 |
| F4 | Moderación (bloquear, reportar, filtro de castigos) y panel de administración con roles | 2 |
| F5 | Notificaciones push accionables | 2 |
| F6 | Racha diaria con protector y misiones diarias | 2 |
| F7 | Tarjetas para compartir resultados y castigos | 2 |
| F8 | Resolución de mercados por propuesta, con voto o disputa del círculo | 2 |
| F9 | Juegos verificables con semillas publicadas | 2 |
| F10 | Crash multijugador en vivo | 3 |
| F11 | Plinko con niveles de riesgo | 3 |
| F12 | Liga global con ascenso y descenso | 3 |
| F13 | Guerra de círculos y torneos semanales | 4 |
| F14 | Pase de temporada, suscripción Clique+ y paquetes de fichas de hasta US$5 (ADR-004) | 4 |
| F15 | Mercados de eventos reales con combinadas | 4 |

## Arreglos a lo que ya existe

- R1 Base de datos en Supabase (ADR-003, ADR-006).
- R2 Git, ramas e integración continua (ronda 0 y orden 1 de E1).
- R3 Quitar el buscador de mercados y la cinta de precios de las páginas del casino: a 1366×768 tapan el botón de apostar.
- R4 Agrupar los avisos: hoy se apilan y tapan la pantalla al entrar.
- Reemplazar "Add funds" (contraseña compartida que crea dinero) por el panel de administración con roles.
- Encabezado del celular: hoy ocupa ~245 px de 844; la navegación pasa a una barra inferior.

## Dirección de arte (ADR-005)

Casino privado premium: papel impreso (la interfaz) sobre una mesa real hecha en Blender (los juegos). Fieltro, terciopelo, madera lacada, latón, fichas de cerámica, cartas de lino, luz cálida. Imágenes renderizadas para casi todo, video para celebraciones y 3D en vivo solo donde se interactúa. Presupuesto en celular: 1.5 MB de GLB, texturas de 1024 px, 50 mil triángulos y 60 cuadros por segundo. Todo debe sentirse premium.

## Infraestructura

- Repositorio: https://github.com/perdomoangelrangel-tech/Clique
- Supabase: proyecto `Clique`, ref `rrmifvptjajfvxxdqqek`, us-east-1, plan Pro.

## Reglas de negocio que no cambian

- Nunca dar premios con valor real ni cambiar fichas por dinero (ADR-003). Se cobra por cosméticos, pase de temporada, suscripción Clique+ y paquetes de fichas de hasta US$5 (ADR-004).
- Las fichas compradas viven en su propia cuenta, no cuentan para la competencia semanal, no se transfieren y no caducan. La compra queda apagada hasta el dictamen legal.
- Clique es 18+, con verificación de edad al registrarse.
- Aviso de privacidad (LFPDPPP 2025) antes de abrir al público.
