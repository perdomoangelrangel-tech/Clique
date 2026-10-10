# Bitácora del cerebro

Decisiones, revisiones y cambios de plan. Lo más nuevo arriba.

---

## 2026-10-10 (tarde) — Todos los agentes a la vez

**Contexto:** el dueño fusionó el PR #1 (agentes E0 a E7) y clonó el repositorio en `Downloads\Clique\Clique-1` (el nombre `Clique` chocaba en Windows con la carpeta `clique` de la app original). Pidió que todos los agentes puedan trabajar ya.

**Hecho:**
- Dependencias separadas en "para empezar" y "para entregar": OT-002, OT-003 (parte A), OT-004, OT-005 y la nueva OT-007 empiezan ya, en paralelo con OT-001. Solo las entregas de OT-003, OT-004 y OT-005 esperan a que OT-002 esté fusionada.
- `packages/tokens` pasa de OT-002 a OT-003 para que E4 pueda empezar sin chocar.
- Nueva OT-007 para E5: inventario de pantallas y rutas de la API del legacy, navegación de la app nueva y todos los textos en es-MX (la "base de traducciones" de la Fase 0).
- `/orden` y `/entregar` leen las dos columnas de dependencias.
- En la computadora del dueño: el `CLAUDE.md` de `Downloads\Clique` ya no manda a clonar en Documentos; las copias viejas de `coordinacion/`, `docs/` y `COMO-EMPEZAR.md` se movieron a `_viejo/`.

**Riesgo aceptado:** se lanzan seis ventanas antes de que OT-001 pruebe el ciclo en Windows. Si `/orden` falla igual en todas, se corrige una vez en `orden.md`.

---

## 2026-10-10 — Aprobaciones del dueño, repositorio y Supabase

**Decisiones del dueño:**
- Aprueba todo el plan (ADR-001 aceptado).
- Estética de casino premium hecha en Blender: "todo se debe sentir premium" → ADR-005, rol `arte3d`, OT-006.
- Agrega paquetes de fichas de máximo US$5 con muchísimas fichas → ADR-004. Se le explicó que el precio bajo no quita el riesgo legal; se diseñó con cuenta `chips` aparte, fuera de la competencia semanal, sin transferencias ni canje, sin caducidad, y con la compra apagada hasta dictamen legal.

**Hecho:**
- Repositorio `perdomoangelrangel-tech/Clique` con la app actual en `legacy/clique` (301 archivos, sin cambios), su huella `legacy/clique.sha256`, el sistema de agentes y las órdenes OT-001 a OT-006.
- Proyecto de Supabase `Clique` (ref `rrmifvptjajfvxxdqqek`, us-east-1) creado por el dueño en el plan Pro.
- Revisión independiente del sistema de agentes: se corrigieron 12 problemas (sincronizar `main` antes de crear ramas, leer órdenes desde `origin/main`, quién escribe en `main`, OT-001 sin excepción de rama, finales de línea en Windows, permisos de `git push`, superposición de OT-002 y OT-005, criterios circulares, concurrencia y RLS en OT-004, notas del azar en OT-005).

**Siguiente paso:** el dueño clona el repositorio en VS Code y lanza OT-001.

---

## 2026-10-09 — Diagnóstico y arranque de la Fase 0

**Hecho:**
- Diagnóstico completo de `legacy/clique`: 11,692 líneas de Python, 8,441 de JavaScript, 119 rutas de API, 13 juegos + póker. Las 1,142 pruebas pasan (7 omitidas por falta de Chrome en el entorno), 411 s.
- Revisión visual en 390×844 y 1366×768.
- Documento "Clique — Diagnóstico y plan maestro".
- Protocolo de agentes, ADR-001 a ADR-003, órdenes OT-001 a OT-005.

**Hallazgos clave:**
- Base de datos en un archivo JSON con candado global: no escala (ADR-001).
- Interfaz solo en inglés; encabezado del celular ocupa ~29% de la pantalla; en Mines a 1366×768 el botón de apostar queda fuera de pantalla porque el buscador de mercados y la cinta aparecen en el casino.
- Sin git, sin moderación, sin PWA, sin aviso de privacidad ni verificación de edad.
- `round2` en el legacy redondea a la mitad hacia arriba; los pagos usan `floor_cents` (hacia abajo). No confundirlos al portar.
